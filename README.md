# GAA 개인 연구 · 차세대반도체 학술동아리

개인적으로 GAA 소자 구조를 만들고 치수를 바꾸어 성능을 평가하는 연구 저장소다. Git·VS Code·Codex로 입력과 분석을 관리하고, 학내 Linux의 Silvaco DevEdit 3D/ATLAS에서 3차원 구조·전기 특성을 계산한다.

**2026-11-16: 원격 agent 등록·진단 회수와 실제3D 구조/평형 계산까지 관찰했다. DC 시험은 시간 제한·라이선스 경고로 미완료였고 수정 r03을 제출했다. Id–Vg는 아직 없다.** 비공개 상태를 유지하며 부원 권한은 아직 변경하지 않았다. live 상태는 `control.py status`, 결과 요약은 runtime의 `latest_summary.json`을 확인한다.

## 읽는 순서

1. [처음 저장한 실행 프롬프트](md/실행프롬프트.md)
2. [화면을 점유하지 않는 자동화](md/백그라운드자동화.md)
   · [토큰 절약 운영](md/토큰절약운영.md)
3. [첫 소자의 설계와 사전 목표](연구/01_GAA_IdVg/md/설계와목표.md)
4. [주요 참조 문헌과 코드 문법 출처](문헌/README.md)
5. [실행/검증 상태](연구/01_GAA_IdVg/검증/상태.json), [접근 권한 방안](md/접근권한.md)

## 폴더 지도

```text
README.md / AGENTS.md / .gitignore / .gitattributes
md/                         실행 프롬프트, 권한, 작업 방식
문헌/                       출처와 사용 위치
python/automation/          백그라운드 controller, agent, 전송 계층
연구/
  01_GAA_IdVg/
    md/                     구조·모델·정의·사전 목표
    tcad/                   DevEdit 3D + ATLAS 덱/JSON 사양
    python/                 덱 생성, 원격 실행, 수치 판독/그래프
    검증/                   로컬 검증 기록과 실제 실행 상태
    그림/                   검토한 결과 그림
  02_치수변화/               첫 기준 소자 검증 후 시작
.local/                     Git 제외: 패키지, 원시 회수 자료, 로컬 임시물
```

토큰·bootstrap·중계 runtime은 `.local/`보다도 바깥인 `%LOCALAPPDATA%/TCAD_PRIVATE/`에 저장한다. 원시 TCAD 구조/대용량 ZIP은 Git에서 제외한다. 공개 상태를 임의로 바꾸지 않는다.

## 실행

Windows의 실제 Python3.11 또는 `py -3.11`을 사용한다. 이 PC의 `python` 명령은 다른 실행 파일을 가리킬 수 있다. 분석/전송은 표준 라이브러리를 쓰며 `--plot`만 matplotlib가 필요하다.

```powershell
cd C:\dev\gaa
py -3.11 연구/01_GAA_IdVg/python/generate.py
py -3.11 연구/01_GAA_IdVg/python/generate.py --smoke
py -3.11 연구/01_GAA_IdVg/python/generate.py --fine
py -3.11 -m unittest discover -s 연구/01_GAA_IdVg/python -p "test_*.py" -v
py -3.11 -m unittest discover -s python/automation -p "test_*.py" -v
```

백그라운드 세션 시작 예시(기존 공식 바이너리 경로를 지정):

```powershell
py -3.11 python/automation/control.py start --cloudflared C:/Users/MinjaeKwak/AppData/Local/TCAD_PRIVATE/tools/cloudflared-2026.10.7.exe
py -3.11 python/automation/control.py status
```

최초 등록은 `status`가 표시하는 Git 밖 `bootstrap.txt`와 `token.txt`를 이용해 기존 MobaXterm Linux shell에서 한 번 한다. remote Python의 CA 경로가 맞지 않으면 검증된 공개 root CA를 `start --ca-pem <파일>`로 지정한다. TLS 검증을 끄지 않는다. 자동화가 이 PC의 화면/입력 장치를 대신 조작하지 않는다.

이후에는 다음 CLI만 사용한다. `status`에서 실제 agent 등록을 확인하고 preflight 결과를 검토한 후 다음 단계를 보낸다. 예시 작업 ID는 새 실행마다 바꾼다.

```powershell
py -3.11 python/automation/control.py queue --job gaa_preflight_r01 --mode preflight
py -3.11 python/automation/control.py status
py -3.11 python/automation/control.py collect --job gaa_preflight_r01
py -3.11 python/automation/control.py queue --job gaa_smoke_r01 --mode smoke
py -3.11 python/automation/control.py collect --job gaa_smoke_r01
py -3.11 python/automation/control.py queue --job gaa_full_r01 --mode full --stage-timeout 1800
py -3.11 python/automation/control.py collect --job gaa_full_r01
py -3.11 python/automation/control.py queue --job gaa_fine_r01 --mode fine --stage-timeout 3600
py -3.11 python/automation/control.py request-stop
```

회수 자료의 `.local/collected/<job>/gaa/execution/`에 export가 있으면 아래 분석을 실행한다. 출력 폴더가 이미 있으면 덮어쓰지 않고 다른 경로를 쓴다.

```powershell
py -3.11 연구/01_GAA_IdVg/python/analyze.py .local/collected/gaa_full_r01/gaa/execution --out .local/analysis/gaa_full_r01 --plot
```

실행 도구의 return code, 수렴/오류 로그, 실제 구조, 전류 그리드/단위/KCL, 메시와 물리 모델을 따로 판정한다. 로컬 합성 시험 통과는 Silvaco 문법·라이선스·소자 성능의 증명이 아니다. 저장소에 없는 Id–Vg 값을 결과처럼 사용하지 않는다.

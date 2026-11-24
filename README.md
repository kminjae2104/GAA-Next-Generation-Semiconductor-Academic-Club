# GAA 개인 연구 · 차세대반도체 학술동아리

**2026-11-21 통신 보완:** [agent 자동 복구](md/agent_자동복구_20261121.md)와 [터널 주소 자동 발견](md/터널주소_자동복구_20261121.md)을 구성했다. 실제 터널 프로세스 종료·새 주소 게시·원격 agent 재접속·결과 왕복을 수동 등록 없이 검증했다. 인증 정보는 Git에 포함하지 않는다.

**2026-11-20 후속 실행:** [명시 바이어스 복구 실험](md/연구계획/명시바이어스_복구실험_20261120.md). 새 실행 `gaa_continuation_explicit_20261120T063127Z`의 12개 덱을 제출했고, 15:34 KST 실제 ATLAS screen3개 실행·9개 대기 및 독립 scheduler를 확인했다. 최대3개 병렬, 덱/전체 기한 없음. 아래48개는 이전 계획의 분석이며 새 결과와 구분한다.

**2026-11-20 최신 확인:** [전체 결과 분석](md/연구결과_총분석_20261120.md). agent 통신을 복구하고 예정 만료 기한을 제거했다. 15:03 KST 원격 확인에서 세 계획 48개 작업은 수치 게이트 통과28/실패14/보류6이며 실행 중인 작업은 없다. 기준 메시 비교는 통과했지만 전체 연구·물리 보정은 미완료다. 아래 11/16~18 진행 문구는 과거 기록이다. [무기한 통신 운용](md/통신무기한운용_20261120.md).

## 빠른 길찾기

| 찾는 자료 | 위치 |
| --- | --- |
| 발표 자료·입문 리서치·발표 대본 | [md/발표자료](md/발표자료/) |
| 후속 야간 실험 계획 | [md/연구계획](md/연구계획/) |
| 실행·연결 운용 안내 | 아래의 인계 문서와 `md/` 운용 문서 |
| 실행 중 자동화 | `python/automation/`, `python/presentation_connection_guard.py`, `python/presentation_remote_snapshot.py` |
| 발표 생성·검증·이미지 도구 | `python/presentation/` |
| 실행 ID별 입력 덱 | `연구/01_GAA_IdVg/tcad/` |
| 회수 근거·검증 기록 | `검증/`, `연구/01_GAA_IdVg/검증/` |
| 발표용 이미지 | [그림/발표선정_20261118](그림/발표선정_20261118/) |

실행 중인 프로그램과 원시 자료의 경로는 유지했다. `.local/`은 임시 회수·중계 상태용이며 Git에서 제외한다. 11/18 후속 실행 ID는 `gaa_continuation_20261118T053927Z`이며 아래의 11/16 상태 문구는 과거 기록이다.

**새 채팅·새 세션:** [5항목 인계 문서](md/새세션_인계.md) → [화면 조작 없는 야간 운용](md/무인야간운용.md). 11/17 상태와 새 실행은 이 두 문서를 우선한다. 기존 아래 11/16 상태는 당시 기록이다.

개인적으로 GAA 소자 구조를 만들고 치수를 바꾸어 성능을 평가하는 연구 저장소다. Git·VS Code·Codex로 입력과 분석을 관리하고, 학내 Linux의 Silvaco DevEdit 3D/ATLAS에서 3차원 구조·전기 특성을 계산한다.

**2026-11-16: 실제3D 구조·평형 계산과 저 Vds의 짧은5점 Id–Vg 시험(r03)을 완료했다. 저/고 Vds 전체 sweep을 제출했으며 최종 성능·메시·양자 보정 검증은 미완료다.** 비공개 상태를 유지하며 부원 권한은 아직 변경하지 않았다. live 상태는 `control.py status`, 결과 요약은 runtime의 `latest_summary.json`을 확인한다.

[최신: 무제한 야간 계산·접속 감시](md/무제한야간실행.md): 34개 덱, 최대 3개 동시 실행, 계산 시간 제한 없음. 실제 계산 및 검증은 진행 중이다.

## 읽는 순서

1. [처음 저장한 실행 프롬프트](md/실행프롬프트.md)
2. [화면을 점유하지 않는 자동화](md/백그라운드자동화.md)
   · [토큰 절약 운영](md/토큰절약운영.md)
   · [순차·병렬 의존성 스케줄러](md/의존성스케줄러.md)
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

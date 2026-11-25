# VS Code와 AI로 TCAD 결과 공유하기

대상: GitHub가 처음인 팀원. AI에게 아래 프롬프트를 붙여 넣어 도움을 받되, 실제 결과와 업로드할 파일은 본인이 확인한다. 메뉴 이름은 설치 버전·언어에 따라 다를 수 있다.

## 1. 처음 한 번 준비

1. 본인 GitHub 계정을 만들고 아이디를 관리자에게 전달한다. 초대가 오면 수락한다.
2. Git과 VS Code를 설치한다. 설치 후 VS Code 터미널에서 `git --version`을 확인한다. 설치는 본인 PC에서 직접 진행한다.
3. VS Code의 `Ctrl+Shift+P` → `Git: Clone` → 아래 주소를 입력한다. 기존 개인 폴더나 다른 Git 저장소 **안쪽**을 복제 위치로 고르지 않는다.

   ```text
   https://github.com/kminjae2104/GAA-Next-Generation-Semiconductor-Academic-Club.git
   ```

4. 복제한 폴더를 연다. 처음 복제할 때 `Initialize Repository`나 `Publish to GitHub`로 새 저장소를 만들 필요는 없다.
5. 사용할 AI 확장/도구를 본인 환경에 설치·로그인한다. 이미 있는 도구를 사용해도 된다. AI 없이도 [같은 작업을 수행](AI없이_GitHub.md)할 수 있다.
6. 첫 커밋 전에 본인 이름·이메일을 설정한다. 이메일을 공개하고 싶지 않으면 GitHub `Settings → Emails`에서 본인에게 표시되는 noreply 주소를 사용한다. 남의 정보를 복사하지 않는다.

   ```powershell
   git config user.name "본인 이름"
   git config user.email "본인 GitHub 설정에서 확인한 이메일"
   ```

로그인은 VS Code/Git의 인증 창으로 한다. 비밀번호·PAT·서버 암호·라이선스·private runtime을 AI 채팅에 붙여 넣지 않는다. 공개 가능한 연구 파일만 AI에 제공한다.

## 2. 작업 시작 프롬프트

아래의 이름·주제·실행 ID를 바꾼다. 실행 ID는 예를 들어 `20261125_lg40_r01`처럼 **날짜_조건_시도**로 짓는다. 같은 ID를 재사용하지 않는다.

```text
이 저장소의 AGENTS.md, README.md, md/협업/실험공유규칙.md를 읽어라.
먼저 현재 브랜치, git status, origin URL을 확인하라. 다른 작업자의 변경은 보존하라.
내 이름은 권도현이고 주제는 gate_length, 실행 ID는 20261125_lg40_r01이다.
이 이름은 내 GitHub 아이디와 별개다. 인증이나 권한을 추정하지 말아라.
작업 트리가 깨끗하면 main을 git pull --ff-only로 갱신하고
exp/myid/gate-length-20261125-r01 브랜치를 만들어라.
변경이 있으면 덮어쓰지 말고 상황을 설명하고 그 변경과 독립적으로 진행하라.
py -3.11 python/collaboration/new_run.py --member 권도현 --topic gate_length --run-id 20261125_lg40_r01
명령으로 새 실험 공간을 만들고 목적, 기준 실험, 변경 변수, 단위,
메시·모델·바이어스·온도, 실행 전 합격 기준을 작성하도록 도와라.
실제 TCAD는 내가 지정한 허가된 환경에서만 실행한다.
아직 계산하지 않은 값은 비워 두고 NOT_RUN이라고 적어라.
```

Python이 없으면 [양식](../양식/실험/README.md)을 복사해 같은 구조로 수동 작성한다. `myid`는 실제 본인 아이디로 바꾸거나 중복되지 않는 짧은 이름을 사용한다.

## 3. 본인이 TCAD를 실행한 다음

입력 덱은 새 실행의 `tcad/`, 원시 로그와 export는 `검증/raw/`, 분석 코드는 `python/`, 그림은 `그림/`에 넣는다. `.str`·대용량 원본은 별도 승인된 저장소에 보관하고 `검증/원본목록.md`에 위치·크기·SHA-256을 기록한다. 서버 암호가 포함된 접속 링크는 적지 않는다.

```text
내 실험 폴더 연구/팀원실험/권도현/gate_length/20261125_lg40_r01만 검토하라.
실제 원시 로그가 있는지 확인하고 입력 덱, 종료 코드, 정상 ATLAS 종료,
바이어스 범위, 누락/미수렴, 전류 단위, KCL을 각각 구분해서 요약하라.
메시 수렴·모델 보정·물리 검증은 근거가 없으면 NOT_VALIDATED로 남겨라.
A와 A/um를 구분하고 정규화 둘레를 적어라. 로그로 확인되지 않은 수치를 만들지 말아라.
비교 조건이 다르면 차이를 표시하라. 실패 결과도 보존하라.
md/실행정보.md, md/결과요약.md, 검증/검증기록.md와 원본목록.md 작성을 도와라.
기존 원본과 다른 사람 폴더를 수정하지 말아라.
```

AI가 덱을 작성했거나 로컬 문법 검사를 통과한 것은 실제 Silvaco 실행 성공이 아니다. 그래프에는 원시 파일, 바이어스, 단위, 불완전 sweep 여부를 적는다.

## 4. 업로드 프롬프트와 직접 확인

```text
변경 목록과 diff를 먼저 보여줘라.
이번 내 실험 폴더만 stage하고, 비밀정보·대용량 파일·기존 결과 덮어쓰기가 없는지 확인하라.
python/collaboration/check_workspace.py의 구조 검사를 실행하라.
이 검사는 실제 TCAD나 물리 검증이 아님을 표시하라.
문제가 없으면 의미 있는 메시지로 commit하고 현재 exp/ 작업 브랜치에 push하라.
main에는 직접 push하지 말아라. force push, reset --hard, clean -fd는 하지 말아라.
실험 목적/조건/실행 ID/실제 실행 여부/검증 상태/한계를 담은 PR 본문을 작성하라.
PR은 내가 만들거나, 내가 생성까지 요청하면 만들어라.
완료 보고에서 로컬 저장, commit SHA, 원격 브랜치 반영, PR, main 반영 여부를 구별하라.
```

그다음 GitHub에서 본인 브랜치를 선택해 파일을 열어 본다. `Compare & pull request` → base `main`, compare 본인 `exp/...` → 제목·본문 확인 → `Create pull request`. PR 링크를 팀에 공유한다. 승인 뒤 main 반영은 검토자가 진행한다.

## 5. 막혔을 때 AI에게 전달할 정보

실행한 명령, 비밀값을 지운 오류 메시지, `git status --short --branch`를 전달한다. 403이면 GitHub 로그인 계정·초대 수락·쓰기 권한부터 확인한다. 충돌이 나면 양쪽 의도를 확인하고 본인 실행 폴더의 변경을 보존한다. AI가 임의로 강제 덮어쓰도록 맡기지 않는다.

공식 자료(2026-11-25 확인): [VS Code Git 입문](https://code.visualstudio.com/docs/sourcecontrol/quickstart), [브랜치](https://code.visualstudio.com/docs/sourcecontrol/branches-worktrees), [GitHub PR](https://code.visualstudio.com/docs/sourcecontrol/github), [충돌 해결](https://code.visualstudio.com/docs/sourcecontrol/merge-conflicts). 프롬프트와 실험 규칙은 이 팀의 운영 방식이다.

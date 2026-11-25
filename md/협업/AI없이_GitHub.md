# AI 없이 TCAD 결과 공유하기

세 가지 방법 중 편한 것을 고른다. 모두 **새 실행 폴더 → 본인 브랜치 → PR → 검토 후 main 반영**이다. 저장소 주소는 [GAA GitHub](https://github.com/kminjae2104/GAA-Next-Generation-Semiconductor-Academic-Club)다.

## A. VS Code 버튼으로 하기

### 처음 한 번

1. GitHub 가입 → 관리자에게 아이디 전달 → 초대 수락. 본인 PC에 Git·VS Code 설치.
2. `Ctrl+Shift+P` → `Git: Clone` → 위 저장소 HTTPS 주소 입력 → 저장할 상위 폴더 선택 → 복제한 폴더 열기.
3. `Terminal → New Terminal`에서 본인 커밋 이름과 이메일을 설정한다. 공개 이메일이 싫으면 GitHub `Settings → Emails`의 본인 noreply 주소를 사용한다.

   ```powershell
   git config user.name "본인 이름"
   git config user.email "본인 이메일 또는 GitHub noreply 주소"
   ```

### 매 실험마다

1. 좌측 Source Control에서 미커밋 변경을 확인한다. 변경이 있으면 먼저 본인 작업을 커밋하거나 별도로 보존한다. `Discard Changes`는 변경을 버리는 기능이다.
2. 좌측 아래 브랜치 이름 → `main` 선택 → `Ctrl+Shift+P` → `Git: Pull`. 충돌/오류가 나오면 중단하고 [아래 도움말](#문제가-생겼을-때)을 따른다.
3. `Ctrl+Shift+P` → `Git: Create Branch` → `exp/myid/gate-length-20261125-r01`처럼 본인 작업 이름 입력. **현재 브랜치가 main이 아닌지** 확인한다.
4. [실험 양식](../양식/실험/README.md)을 본인 이름/주제/새 실행 ID 폴더에 복사하거나, Python 설치 시 아래 명령을 실행한다.

   ```powershell
   py -3.11 python/collaboration/new_run.py --member 권도현 --topic gate_length --run-id 20261125_lg40_r01
   ```

5. 사전계획 작성 → TCAD 실행 → 덱·원시 로그·조건·검증·요약·그림 추가. [공유 규칙](실험공유규칙.md)을 따른다.
6. Source Control(`Ctrl+Shift+G`)에서 변경 파일을 클릭해 diff를 읽는다. 본인 실험 파일 옆 `+`로 **선택한 파일만** stage한다.
7. 메시지에 `권도현: lg40 r01 실제 실행 결과와 검증 기록 추가`처럼 내용을 적고 `Commit`을 누른다. 이때는 PC에만 기록된다.
8. 새 브랜치는 `Publish Branch`, 이후는 `… → Push`로 올린다. 로그인 요청은 본인 GitHub 계정으로 진행한다. `Sync Changes`는 pull과 push를 함께 하므로 오류 원인을 모를 때 반복해서 누르지 않는다.
9. GitHub에서 본인 브랜치 파일 확인 → `Compare & pull request` → base `main`, compare 본인 브랜치 → PR 양식 작성 → 생성.
10. 검토 의견을 반영할 때 같은 브랜치에서 수정·commit·push하면 기존 PR에 추가된다. 원래 실행을 바꾸는 수정/재실행은 **새 실행 ID**에 보존한다.

## B. 터미널로 하기

이 예시는 **초대를 수락한 쓰기 권한자**를 위한 것이다. 폴더 이름·날짜·조건을 본인 것으로 바꾼다. 현재 미커밋 작업이 있으면 브랜치 전환 전 보존한다.

처음 복제(저장할 상위 폴더에서 실행):

```powershell
git clone https://github.com/kminjae2104/GAA-Next-Generation-Semiconductor-Academic-Club.git
cd GAA-Next-Generation-Semiconductor-Academic-Club
git config user.name "본인 이름"
git config user.email "본인 이메일 또는 GitHub noreply 주소"
```

실험 시작:

```powershell
git status --short --branch
git switch main
git pull --ff-only origin main
git switch -c exp/myid/gate-length-20261125-r01
py -3.11 python/collaboration/new_run.py --member 권도현 --topic gate_length --run-id 20261125_lg40_r01
```

내용을 작성하고 결과를 복사한 뒤:

```powershell
py -3.11 python/collaboration/check_workspace.py
git status --short
git diff
git add -- "연구/팀원실험/권도현/gate_length/20261125_lg40_r01"
git diff --cached --stat
git diff --cached --check
git commit -m "Share gate length r01 conditions and verified outputs"
git push -u origin exp/myid/gate-length-20261125-r01
```

이제 GitHub에서 PR을 만든다. 위 명령은 계산을 실행하지 않는다. 구조 검사도 실제 TCAD 통과 판정은 아니다. 정상 push 뒤에도 PR 생성과 main 반영은 따로 필요하다.

다른 팀의 최신 main을 현재 작업 브랜치에 반영할 필요가 있을 때는 미커밋 작업을 먼저 보존하고 `git fetch origin` → `git merge origin/main`을 사용한다. 충돌이 있으면 내용을 검토한 뒤 병합 커밋을 만든다. 공유된 브랜치의 이력을 강제로 바꾸지 않는다.

## C. 설치 없이 GitHub 웹으로 하기

작은 문서와 결과 파일을 올릴 때 적합하다. 웹에서는 `.gitignore`가 업로드를 자동으로 걸러 준다고 가정하지 않는다.

1. GitHub에 로그인하고 저장소를 연다. 쓰기 권한이 있으면 `main` 브랜치 선택 메뉴에서 `exp/myid/...` 브랜치를 만든다.
2. 본인 `연구/팀원실험/이름/주제/실행ID/` 구조를 PC에 준비한다. [양식의 문서](../양식/실험/README.md)를 복사하고 빈칸을 채운다. `tcad/`, `python/`, `검증/raw/`, `그림/`도 구분한다.
3. GitHub에서 업로드할 **상위 경로**를 연 뒤 `Add file → Upload files`를 선택한다. 예: `연구/팀원실험/권도현`에서 `gate_length` 폴더를 올린다. 미리보기에 경로가 두 번 중첩되지 않는지 확인한다.
4. 작은 문서 하나는 `Add file → Create new file`로도 만들 수 있다. 이름에 `/`를 넣어 하위 경로를 만든다. 예: `gate_length/20261125_lg40_r01/md/사전계획.md`.
5. 브라우저 업로드는 파일당 **25 MiB**, 한 번에 **100개 파일** 제한이 있다. 이 팀은 관리 편의를 위해 Git에 올리는 파일을 **20 MiB 이하**로 정한다. 더 큰 원본과 `.str`, `.zip`은 별도 보관하고 위치·해시를 기록한다.
6. 업로드 목록을 확인한다. token·비밀번호·라이선스·원본 중복을 빼고 **본인 브랜치**에 커밋한다. main 직접 커밋은 선택하지 않는다.
7. `Pull requests → New pull request`에서 base `main`, compare 본인 브랜치를 선택하고 PR을 작성한다.

**쓰기 권한 초대 전:** 공개 저장소에서 본인 계정으로 `Fork` → fork에서 새 브랜치와 파일 작성 → 원본 저장소의 `main`을 대상으로 PR을 만든다. 초대 전에도 이 방식으로 제출할 수 있다. fork URL을 원본 origin과 혼동하지 않는다.

## 문제가 생겼을 때

| 증상 | 할 일 |
| --- | --- |
| `git`을 찾을 수 없음 | Git 설치 후 VS Code를 다시 열고 `git --version` 확인 |
| commit에서 이름/이메일 요구 | 위 `git config user.name`, `user.email` 설정 |
| push 403/permission denied | 로그인 계정, 초대 수락, 원본/fork URL 확인. 비밀번호를 채팅에 보내지 않기 |
| main push 거절 | 본인 `exp/...` 브랜치에 push하고 PR 만들기 |
| push가 non-fast-forward | 강제 push 금지. `git fetch origin` 후 같은 원격 작업 브랜치를 merge하고 내용 확인 |
| `<<<<<<<` 충돌 표시 | Source Control의 Merge Changes에서 양쪽 의도를 확인. 모두 검토·stage·commit. 원본 로그 충돌은 새 실행 ID로 분리하고 관리자와 조율 |
| 생성 도구가 기존 ID 거절 | 새 실행 ID 사용. 기존 폴더 삭제나 덮어쓰기로 해결하지 않기 |
| `.str`이 변경 목록에 안 보임 | 의도된 제외다. 별도 보관 후 원본목록에 경로·해시 기록 |
| 본인 변경이 main에서 안 보임 | 본인 브랜치 push, PR 생성, PR merge 여부를 차례로 확인 |

공식 자료(2026-11-25 확인): [VS Code Git 입문](https://code.visualstudio.com/docs/sourcecontrol/quickstart), [원격 저장소](https://code.visualstudio.com/docs/sourcecontrol/repos-remotes), [GitHub PR](https://code.visualstudio.com/docs/sourcecontrol/github), [웹 업로드](https://docs.github.com/en/repositories/working-with-files/managing-files/adding-a-file-to-a-repository), [협업자 초대](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/managing-repository-settings/inviting-collaborators-to-a-personal-repository).

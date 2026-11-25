# 협업 체계 검증

이 폴더는 문서·폴더 도구·GitHub 설정·통신 호환 확인 기록이다. 실제 Silvaco 계산이나 소자 물리 검증 결과가 아니다.

- `transport_migration.json`: 기존 토큰·runtime·큐 보존 여부, Windows 중계만 교체했는지, 인증 HTTPS·비인증 거부·새 agent 이벤트 확인.
- `github_settings.json`: 공개 전환·브랜치 보호·협업자·대기 초대의 API 재조회. 팀원 계정 아이디가 없으므로 초대 미발송.
- `public_access.json`: 인증 없이 공개 저장소·주소 문서 조회가 되는지, 주소 문서 서명, 공개 전환 후 새 agent heartbeat 확인.
- `workspace_static.json`: 필수 구조·문서 링크·파일 크기·위험 파일명 정적 검사.
- `verification.json`: 수행한 시험과 기존 자료 보존 범위 요약.
- `member_roots.json`: 후속 지시에 따른 팀원 최상위 이동과 새 하위 구조 기록. 공통 기준 연구·원격 자동화 경로는 유지했다.
- `member_roots_static.json`: 이동 후 5명 개인 공간·59개 문서 링크·파일 구조 정적 검사. 생성 도구의 경로·기존 ID 보존 시험 4개도 이동 후 재실행해 통과했다.
- `guidance_update_static.json`: 안내 보완 후 5명 개인 공간·61개 문서의 정적 검사. 폴더 누락 검사를 추가한 로컬 시험 5개도 통과했다. 과거 검증 파일의 검사 범위·개수는 당시 기록으로 유지한다.

첫 `verification_initial_git_blob_comparison.json`은 Git blob과 Windows 작업 파일의 CRLF/LF 차이까지 변경으로 집계했다. 최종 `verification.json`은 Git의 text 속성에 따라 줄바꿈 차이를 따로 분류한다. 원시 바이너리 지정 로그·export는 바이트 그대로 비교한다. 이 분류를 위해 기존 파일을 다시 쓰거나 줄바꿈을 변경하지 않았다.

기존 파일 7,921개 중 7,629개는 Git blob과 바이트가 같고, 292개는 text 속성 파일의 CRLF/LF 차이만 있었다. 예상하지 않은 내용 변경은 0개다. 이 기록은 기준 커밋과의 비교이며 작업 전 전체 디스크 바이트 스냅샷을 새로 수집했다는 뜻은 아니다.

인증정보 패턴 검사의 상세 임시 보고서는 Git 제외 `.local/collaboration_20261125/`에 있다. 자격 증명 값·private runtime·토큰 해시는 이 검증 폴더에 기록하지 않는다. 문서에 기록된 통과와 실제 API 상태는 [설정 기록](../../md/협업/설정변경_20261125.md)에서 구분한다.

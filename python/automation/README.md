# 원격 자동화 전송 계층

`relay.py`, `agent.py`, `start_session.py`, `keep_awake.py`는 기존 STOB 자동화 소스 commit `e0c6e650b339a2daa6239f48f899e60550c5e50b`에서 복사해 새 GAA 작업 경로/서비스 이름으로 분리했다. 과거 실행기·토큰·진행 작업은 재사용하지 않는다.

로컬127.0.0.1 서버와 기존 Cloudflare 공식 바이너리의 임시 HTTPS 경로로, 작업별 토큰이 검증된 코드 패키지와 결과만 교환한다. 일반 셸 API·영구 서비스·방화벽 변경은 만들지 않는다. token/bootstrap/runtime은 Git 밖에 보관하고 세션 만료는 최대6시간이다. 클라이언트는 코드 SHA-256을 확인하고 결과 archive와 각 파일의 해시를 검증한다.

연구 실행기는 [run_study.py](../../연구/01_GAA_IdVg/python/run_study.py)다. 단계별 패키지를 새 ID로 게시한다. 기존 Linux 세션에서 bootstrap을 한 번 실행한 후에는 패키지 게시→실행→회수→분석을 파일/상태 API로 진행한다. 직접 SSH가 막힌 현재 접속 경로를 위한 일시적 전송 수단이다.

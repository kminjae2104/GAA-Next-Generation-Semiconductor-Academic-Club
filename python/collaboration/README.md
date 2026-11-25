# 팀 실험 도구

저장소 루트에서 Python 3.11 표준 라이브러리만으로 실행한다. 계산·네트워크·GitHub 변경을 하지 않는다.

```powershell
py -3.11 python/collaboration/new_run.py --member 권도현 --topic gate_length --run-id 20261125_lg40_r01
py -3.11 python/collaboration/check_workspace.py
py -3.11 -m unittest discover -s python/collaboration -p "test_*.py" -v
```

생성 도구는 등록된 이름 폴더 아래 새 실행 ID만 만든다. 기존 ID가 있으면 빈 폴더여도 거절한다. `check_workspace.py`는 문서 링크·필수 경로·추적/추가 파일의 크기·일부 위험 파일명만 확인하며 내용에 포함된 비밀정보 전체나 물리 검증을 보장하지 않는다. 제출 전에 diff와 실제 원시 근거도 직접 검토한다.

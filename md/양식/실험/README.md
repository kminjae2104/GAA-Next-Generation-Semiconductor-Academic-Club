# 실험 제목 / 실행 ID

**이 폴더는 빈 양식이다. 실제 계산 결과가 아니다.** 이름·주제·실행 ID를 정해 `연구/팀원실험/이름/주제/실행ID/`에 복사한다. Python 설치 시 저장소 루트에서 생성 도구를 사용할 수 있다.

```powershell
py -3.11 python/collaboration/new_run.py --member 권도현 --topic gate_length --run-id 20261125_lg40_r01
```

| 항목 | 기록 |
| --- | --- |
| 작성자 / GitHub 아이디 | 미입력 |
| 주제 / 실행 ID | 미입력 |
| 계산 상태 | NOT_RUN |
| 실제 출력 수치 검사 | NOT_VALIDATED |
| 메시 수렴 / 물리 검증 | NOT_VALIDATED / NOT_VALIDATED |
| 기준 실험 / 커밋 | 미입력 |

- [사전계획](md/사전계획.md)
- [실행정보](md/실행정보.md)
- [결과요약](md/결과요약.md)
- [검증기록](검증/검증기록.md)
- [원본목록](검증/원본목록.md)

`tcad/`에 사용한 덱, `python/`에 분석 코드, `검증/raw/`에 원시 로그/export, `그림/`에 결과 그림을 둔다. 웹이나 VS Code로 수동 복사할 때도 이 폴더를 만든다. 폴더별 README는 실제 파일을 넣은 뒤 필요하면 설명으로 바꾼다. 수정/재실행은 새 실행 ID로 보존한다.

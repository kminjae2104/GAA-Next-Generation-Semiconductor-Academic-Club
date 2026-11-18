# 발표용 실제 로그 이미지

11/18 12:32 KST 회수본에서 선택했다. PNG는 실제 native log의 마지막 6행을 표로 옮긴 자료이며 프로그램 화면 캡처나 구조 그림이 아니다. 원본 .log와 선정근거.json의 해시를 함께 제공한다.

| 이미지 | 발표에서 설명할 내용 |
| --- | --- |
| [eq_bicgst_fine.png](eq_bicgst_fine.png) | 기준 소자의 목표 Vds=0.6 V, 최종 Vgs=0.8 V 도달 |
| [wf4p6_fine.png](wf4p6_fine.png) | Vgs가 끝까지 진행돼도 실제 Vds가 약 0.3407 V이면 high 결과로 사용할 수 없음 |
| [bqp_fine.png](bqp_fine.png) | Vds가 맞더라도 Vgs가 약 0.58484 V에서 끝나면 전체 sweep 검증 실패 |

## TonyPlot3D 구조 사진 시도

기준 eq_bicgst_fine의 실제 geometry.str와 final_high.str를 원격 TonyPlot3D로 PNG 내보내기 시도했다. 두 실행 모두 종료 코드 1, PNG 미생성이다. 설치된 3.10.69.R 실제 실행 파일에서 `cannot connect to X server` 오류를 확인했다. Xvfb/xvfb-run이 없으며 사용자가 추가 설치를 하지 말라고 지시하여 중단했다. 기존 사용자 화면이나 입력 장치는 사용하지 않았다. 따라서 이 폴더에 TonyPlot3D 구조 사진은 없다.

진단 원본: `.local/collected/gaa_tonyplot_trace_20261118T034500Z/binary_help.txt`. 원격의 원시 구조는 유지되며 새 소자 계산은 실행하지 않았다.

# DevEdit 3D / ATLAS 입력

`python/generate.py`가 이 폴더에 ASCII 덱과 JSON 설계 사양을 생성한다. 생성된 덱은 아직 실제 Silvaco 파서로 검증되지 않았다. 원격 자동화는 이를 새 실행 디렉터리의 `gaa.in`으로 묶어 보내며 입력/로그를 보존한다.

- `gaa_coarse_smoke.in`: 3D 구조→평형→저 Vds의 짧은 gate sweep.
- `gaa_coarse.in`: 저/고 Vds의 전체 전달 특성.
- `gaa_fine.in`: 같은 물리·치수에서 메시 간격을 절반으로 한 수렴 점검.

게이트의 네 금속 영역은 같은 전극 ID=1/name=gate로 묶었다. 실제 출력에서 하나의 게이트로 인식되고 산화막으로 Si와 절연되는지 확인한다. ATLAS에서 도핑을 설정하므로 `geometry.str`만으로 도핑이 완료됐다고 판단하지 않는다. 평형 출력 구조로 다시 확인한다.

원격 결과의 `execution/`에서 아래 export가 만들어진다.

```text
low_drain.dat   low_source.dat   low_gate.dat
high_drain.dat  high_source.dat  high_gate.dat
idvg_low.log   idvg_high.log    solver.out   console.txt
geometry.str   equilibrium.str final_low.str final_high.str
```

버전·모델·라이선스·메시·수렴·종료 상태와 파일 내용을 함께 검사한다. export가 생겼다는 사실만으로 실제 소자의 성능을 보증하지 않는다.

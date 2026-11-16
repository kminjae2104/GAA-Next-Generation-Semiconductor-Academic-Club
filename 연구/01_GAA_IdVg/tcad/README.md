# DevEdit 3D / ATLAS 입력

`python/generate.py`가 `v2_common_gate/`에 ASCII 덱과 JSON 설계 사양을 생성한다. 루트의 초기 덱은 당시 스냅샷으로 보존했다. 초기 덱의 DevEdit 생성과 ATLAS 평형은 실제 실행됐으나 Id–Vg 완료는 확인하지 못했다. 수정 v2는 실제 실행으로 다시 검증한다. 원격 자동화는 현재 생성기를 새 실행 디렉터리의 `gaa.in`으로 묶어 보내며 입력/로그를 보존한다.

- `gaa_coarse_smoke.in`: 3D 구조→평형→저 Vds의 짧은 gate sweep.
- `gaa_coarse.in`: 저/고 Vds의 전체 전달 특성.
- `gaa_fine.in`: 같은 물리·치수에서 메시 간격을 절반으로 한 수렴 점검.

초기 실제 출력에서 같은 gate 이름/ID만으로는 접촉표가 하나로 합쳐지지 않았다. v2는 gate/gate_right/gate_top/gate_bottom을 명시하고 `CONTACT ... COMMON=gate SHORT`로 전위와 출력 전류를 묶는다(R3 §2, PDF p.47). 실제 로그의 바이어스/접촉표로 다시 확인한다. smoke만 Si2nm·산화막0.5nm의 진단 메시를 쓰고 full/fine은 사전 기준의1nm/0.25nm 및 그 절반을 유지한다. ATLAS에서 도핑을 설정하므로 `geometry.str`만으로 도핑이 완료됐다고 판단하지 않는다. 평형 출력 구조로 다시 확인한다.

원격 결과의 `execution/`에서 아래 export가 만들어진다.

```text
low_drain.dat   low_source.dat   low_gate.dat
high_drain.dat  high_source.dat  high_gate.dat
idvg_low.log   idvg_high.log    solver.out   console.txt
geometry.str   equilibrium.str final_low.str final_high.str
```

버전·모델·라이선스·메시·수렴·종료 상태와 파일 내용을 함께 검사한다. export가 생겼다는 사실만으로 실제 소자의 성능을 보증하지 않는다.

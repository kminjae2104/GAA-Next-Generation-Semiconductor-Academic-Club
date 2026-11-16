# 주요 참조 문헌

아래 원문/제조사 자료를 2026-11-16 확인했다. 저작권 자료 전체는 Git에 재배포하지 않는다. 구문 설명은 설치 버전의 매뉴얼과 실제 파서로 다시 확인한다.

| ID | 출처 | 이번 작업에 사용한 부분 |
| --- | --- | --- |
| R1 | S. R. Kola, Y. Li, N. Thoti, *Characteristics of Gate-All-Around Silicon Nanowire and Nanosheet MOSFETs with Various Spacers*, SISPAD 2020, pp.79–82. [학회 원문](https://in4.iue.tuwien.ac.at/pdfs/sispad2020/SISPAD2020_4-5.pdf) | Table I, Fig.1, Fig.2–3, Table II: 3D 직사각 GAA 단면, ECW=2(W+H), 0.6V 평가 및 양자 보정의 필요성. 성능 수치는 해당 논문 조건의 참고값이다. |
| R2 | Silvaco, *VWF Interactive Tools User's Manual*, DevEdit chapter 9. [제조사 매뉴얼의 대학 보관본](https://perso.esiee.fr/~polleuxj/Documents/vwf_inter_tools.pdf) | §9.13: REGION/POINTS/Z1/Z2/ELECTRODE.ID, 메시 제약, Z.PLANE, STRUCTURE. PDF pp.424–425,431 등. |
| R3 | Silvaco, *ATLAS User's Manual*. [제조사 매뉴얼의 RIT 보관본](https://ridl.cfd.rit.edu/products/manuals/Silvaco/atlas_users.pdf) | §2.6.2 및 §6.2: DevEdit 3D 구조를 MESH INFILE로 로딩하면 3D를 자동 판별. 모델/CONTACT/SOLVE/LOG/EXTRACT와 batch 실행. PDF pp.29,289. 오래된 판본이므로 설치 버전 확인 필수. |
| R4 | Silvaco, *Comparison of 3-Dimensional Quantum Effects in Nano Devices Using the ATLAS 3D BQP Model*, Simulation Standard, May 2006. [공식 기술 자료](https://silvaco.com/ko/simulation-standard-ko/comparison-of-3-dimensional-quantum-effects-in-nano-devices-using-the-atlas-3d-bqp-model/) | 4면 게이트 및 wire의 양자 보정 비교. NA=1e16, ND=1e20 cm^-3와 산화막 1nm를 출발 가정의 근거로 사용. 논문의 극단적인 길이를 그대로 재현하지 않는다. |

주요 연구 참조는 R1이고, 코드 문법의 주요 참조는 R2/R3이다. R1은 채널 16nm, EOT 약 0.963nm, 고유전율 적층 및 보정된 수송 모델을 사용한다. 첫 구조/수치해석 점검 소자는 길이 40nm·단일 SiO2·고전적 DD로 단순화하므로 R1의 직접 재현이 아니다. 최신 Silvaco `Fin_GAA_ex03`은 Victory 계열 예제이므로 DevEdit/ATLAS 코드로 그대로 복사하지 않았다.

"""Build a table-only Markdown report from preserved real GAA outputs; no solver runs."""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import hashlib
import importlib.util
import json
import math
import shutil
import re

ROOT = Path(__file__).resolve().parents[2]
STUDY = ROOT / '연구/01_GAA_IdVg'
SNAP = ROOT / '.local/collected/gaa_night_snapshot_20261117T072717Z'
OUT = ROOT / '검증/GAA_발표_20261118'
DECKS = STUDY / 'tcad/gaa_overnight_20261116T080149Z'
CASES = ['eq_bicgst_full', 'eq_bicgst_fine', 'wf4p55_full', 'wf4p6_full', 'bqp_full']
OUTPUT_NAME = 'GAA_연구현황_발표자료_20261118.md'
FRESH = False


def read(p):
    return json.loads(p.read_text(encoding='utf-8'))


def table(headers, rows):
    rows = [[str(cell).replace('|Id+Is+Ig|', 'abs(Id+Is+Ig)').replace('|Id|', 'abs(Id)') for cell in row] for row in rows]
    return '\n'.join(['| ' + ' | '.join(headers) + ' |', '| ' + ' | '.join(['---'] * len(headers)) + ' |'] +
                     ['| ' + ' | '.join(map(str, row)) + ' |' for row in rows])


def main():
    OUT.mkdir(parents=True, exist_ok=False)
    spec = importlib.util.spec_from_file_location('gaa_analysis', STUDY / 'python/analyze.py')
    analysis = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(analysis)
    snapshot = read(SNAP / 'snapshot.json')
    metrics, checks, hashes = {}, {}, {}
    def preserve(src, rel):
        dst = OUT / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        hashes[rel] = {'source': src.relative_to(ROOT).as_posix(),
                       'sha256': hashlib.sha256(dst.read_bytes()).hexdigest(), 'bytes': dst.stat().st_size}
    preserve(SNAP / 'snapshot.json', 'snapshot.json')
    preserve(SNAP / 'recovery.json', 'recovery.json')
    preserve(SNAP / 'collection_verified.json', 'collection_verified.json')
    if not FRESH:
        preserve(ROOT / '.local/presentation_remote_check_20261118.json', 'remote_check.json')
    else:
        preserve(SNAP / 'presentation_snapshot.json', 'presentation_snapshot.json')
    for case in CASES:
        src = SNAP / 'cases' / case
        computed, _ = analysis.analyze(src, .04)
        recorded = read(src / 'validated_metrics.json')
        for bias in ['low', 'high']:
            for key, value in computed['metrics'][bias].items():
                old = recorded['metrics'][bias][key]
                assert (math.isclose(value, old, rel_tol=1e-10, abs_tol=1e-20)
                        if isinstance(value, (int, float)) and not isinstance(value, bool) else value == old), (case, bias, key)
        process = read(src / 'process.json')
        tail = (src / 'solver_tail.txt').read_text(errors='replace')
        assert process['returncode'] == 0 and not process['missing'] and not process['timeout']
        assert process['normal_atlas_finish'] and re.search(r'ATLAS version[^\n]*finished', tail)
        assert not process['fatal_lines']
        config = read(src / 'run_config.json')
        deck = DECKS / (case + '.in')
        deck_text = deck.read_text()
        assert 'common=gate short' in deck_text and 'go devedit simflags="-3d"' in deck_text
        assert 'models fermi conmob fldmob srh bgn' in deck_text
        assert str(config['parameters']['workfunction_eV']) in deck_text
        metrics[case] = computed
        checks[case] = {'native_and_exports_recomputed': True, 'saved_metrics_match': True,
                        'process_and_finish_checked': True, 'config': config,
                        'recorded_mesh_comparison': recorded.get('mesh_comparison')}
        for f in src.iterdir():
            if f.suffix in ['.dat', '.log'] or f.name in ['run_config.json', 'process.json', 'solver_tail.txt', 'validated_metrics.json', 'retained_structures.json']:
                preserve(f, '原始資料/' + case + '/' + f.name)
        preserve(deck, '덱/' + deck.name)
    for case, state in snapshot['states'].items():
        if state['status'] in ['FAILED', 'RUNNING']:
            for name in ['solver.out', 'solver_tail.txt', 'process.json', 'progress.json', 'scheduler_console.txt', 'idvg_high.log', 'high_drain.dat']:
                p = SNAP / 'cases' / case / name
                if p.exists(): preserve(p, '실패와미완료/' + case + '/' + name)
    counts = {}
    for state in snapshot['states'].values():
        counts[state['status']] = counts.get(state['status'], 0) + 1
    assert sum(counts.values()) == 34
    timestamp = datetime.fromtimestamp(snapshot['snapshot_epoch'], timezone(timedelta(hours=9))).strftime('%Y-%m-%d %H:%M:%S KST')
    def m(c, b='high'): return metrics[c]['metrics'][b]
    def f(x, n=3): return f'{x:.{n}f}'
    sections = []
    def slide(title, text): sections.append('## ' + title + '\n\n' + text.strip())
    slide('01. 3D GAA nMOS 연구 중간보고', f'''
단일 사각 Si 나노와이어의 구조 구현, 전기 특성, 메시 의존성과 남은 검증

작성일: 2026-11-18 · 연구 동아리 발표용 · 수치는 실제 Silvaco 로그에서 재계산

**3D 소자 실행과 기준 메시 비교를 확보했다. 일함수 변경의 full 결과는 공학 목표에 들어왔으나, fine 재현과 물리 보정 검증은 남아 있다.**

자료 기준: **{timestamp}**의 원격 스냅샷. 11/18에는 이전 중계의 두 주소가 DNS 조회에 실패했고, 같은 cau103 서버의 SSH 연결도 시간 초과였다. 이후 계산 상태는 미확인이다.
''')
    slide('02. 연구 목적과 평가 순서', '''
GAA 구조를 생성하고, 설정한 전압에서 동작하는지 확인한 뒤 메시와 물리 모델에 따른 신뢰 범위를 평가한다.

''' + table(['단계', '확인할 내용', '이번 자료의 범위'], [
        ['구조', 'Si 채널의 네 면을 산화막·공통 게이트가 감싸는 3D 소자', '실행 덱·구조 파일 생성 기록 확인'],
        ['전기 동작', '두 Vds에서 Id–Vg, Ion/Ioff, Vth, SS, DIBL', '완료된 대표 5조건의 native log·export 재계산'],
        ['수치 신뢰성', '목표 바이어스·KCL·full–fine 메시 비교', '기준 4.5 eV 분기 통과'],
        ['물리 타당성', '양자·계면 이동도·누설 모델 보정 및 비교 자료', '미완료'],
    ]) + '\n\n근거: [사전 설계와 목표](../연구/01_GAA_IdVg/md/설계와목표.md). 문헌의 다른 소자를 직접 일치 목표로 사용하지 않는다.')
    slide('03. 구조 덱과 소자 치수', '''
전류 방향은 z, Si 단면은 x–y이다. DevEdit 3D에서 13개 영역을 정의하고 ATLAS로 읽는다.

''' + table(['구성', '덱의 좌표·설정', '물리적 의미'], [
        ['Si 단면', 'x,y = 0~0.010 µm', '10 × 10 nm 정사각 단면'],
        ['소스 / 채널 / 드레인', 'z = 0~20 / 20~60 / 60~80 nm', 'Lg = 40 nm, 양쪽 연장부 각 20 nm'],
        ['절연막', 'SiO2 1 nm, Si 네 면; z = 0~80 nm', 'high-k 적층 미적용'],
        ['게이트', '금속 두께 3 nm, z = 20~60 nm', '네 금속 영역을 common=gate short로 연결'],
        ['S/D 접촉', '금속 길이 각 5 nm', '소스 z = −5~0, 드레인 z = 80~85 nm'],
        ['도핑', '채널 p: 1e16, S/D n+: 1e20 cm⁻³', '구조 로딩 후 uniform doping'],
        ['정규화 둘레', '2(W+H) = 40 nm = 0.04 µm', 'Id[A/µm] = Id[A] / 0.04'],
    ]) + '''

근거: [실행 덱](../검증/GAA_발표_20261118/덱/eq_bicgst_full.in). 실제 `.str`의 생성·크기·해시는 회수된 manifest에 남아 있다. 대용량 구조 본체는 이번에 내려받지 못했으므로 좌표·계면 메시의 독립 재판독은 하지 못했다.
''')
    slide('04. 계산 조건과 지표 정의', table(['항목', '조건 / 정의'], [
        ['실행 환경', 'DevEdit 3D → ATLAS 5.34.0.R; 대표 분기 BICGST, 4 processors'],
        ['고전 모델', 'DD, FERMI, CONMOB, FLDMOB, SRH, BGN; 300 K'],
        ['바이어스', 'Vds = 0.05 / 0.6 V; Vgs = −0.2~0.8 V, 0.02 V 간격, 각 51점'],
        ['Ion / Ioff', '|Id| at Vgs=0.6 / 0 V; 목표 평가는 Vds=0.6 V'],
        ['Vth', '둘레당 100 nA/µm = 단일 wire 4 nA의 일정전류 교차점'],
        ['SS', '1e−10~1e−8 A/µm 고정 창의 log10(|Id|) 회귀; 최소 6점·2 decade'],
        ['DIBL', '(Vth@0.05 V − Vth@0.6 V) / 0.55 × 1000 [mV/V]'],
        ['KCL', '|Id+Is+Ig| ≤ max(1e−14 A, 최대 단자전류의 0.1%); 각 점에서 검사'],
    ]) + '\n\n`equilibrium.str`는 이 분기에서 carriers=0으로 gate를 −0.2 V까지 초기화한 저장 상태이다. 파일명을 무바이어스 열평형 검증으로 해석하지 않는다. 대표 분기만 이 초기화 조건을 공유하며, 전체 34개에는 다른 solver·초기화 조건도 포함된다.')
    slide('05. 실행 현황과 완료의 의미', table(['원래 34개 계획', '개수', '의미'], [
        ['SUCCEEDED', counts['SUCCEEDED'], '스케줄러의 실행·수치 검사 게이트 통과'],
        ['FAILED', counts['FAILED'], '실행 또는 검증 실패'],
        ['BLOCKED', counts['BLOCKED'], '선행 작업 실패로 후속 보류'],
        ['RUNNING', counts.get('RUNNING', 0), '없음' if FRESH else 'bqp_fine; 스냅샷 당시 Vg≈0.58 V 계산 시도 중'],
    ]) + '''

추가 복구 계획 `gaa_autonomous_20261117T064609Z`: 당시 `wf4p55_fine_ramp002` 실행 중, `wf4p6_fine_ramp002` 대기 중. 원래 34개와 구별한다.

24개에는 **smoke 7개, screen 9개, full 7개, fine 1개**가 포함된다. smoke는 5점의 기능 점검이며 최종 성능 결과가 아니다. SUCCEEDED도 공학 목표 충족이나 물리 검증 완료를 뜻하지 않는다. [상태 원본](../검증/GAA_발표_20261118/snapshot.json)
''')
    slide('06. 기준 소자의 Id–Vg 표', '''
조건: `eq_bicgst_fine`, 일함수 4.5 eV, 고전 DD, Si 메시 설정 최대 0.5 nm. 전체 51점 중 대표점을 표시한다. 전류는 절댓값이다.

''' + table(['Vgs (V)', 'Id@0.05 V (A/wire)', 'Id@0.6 V (A/wire)', 'Id@0.6 V (µA/µm)'], [
        [f(v, 2), f'{analysis.at(analysis.read_curve(SNAP / "cases/eq_bicgst_fine/low_drain.dat"),v):.6e}',
         f'{analysis.at(analysis.read_curve(SNAP / "cases/eq_bicgst_fine/high_drain.dat"),v):.6e}',
         f(analysis.at(analysis.read_curve(SNAP / 'cases/eq_bicgst_fine/high_drain.dat'),v)/.04*1e6, 6)] for v in [-.2, 0, .2, .4, .6, .8]
    ]) + '''

Vds=0.6 V에서 **Ion = 23.9896 µA/wire = 599.739 µA/µm**, **Ioff = 6.80245e−11 A/wire = 1.70061 nA/µm**이다. 게이트 전압에 따른 드레인 전류 증가는 확인되지만 Ioff 목표 1 nA/µm를 넘는다.

근거: [low native log](../검증/GAA_발표_20261118/原始資料/eq_bicgst_fine/idvg_low.log), [high native log](../검증/GAA_발표_20261118/原始資料/eq_bicgst_fine/idvg_high.log). 세 단자 export와 native 값·바이어스를 대조했다.
''')
    slide('07. 기준 소자의 사전 목표 대비', table(['지표', '사전 기준', '4.5 eV fine 결과', '판정'], [
        ['Ion@high', '≥100 µA/µm', f(m('eq_bicgst_fine')['Ion_A_per_um']*1e6)+' µA/µm', '통과'],
        ['Ioff@high', '≤1 nA/µm', f(m('eq_bicgst_fine')['Ioff_A_per_um']*1e9, 5)+' nA/µm', '미달'],
        ['Ion/Ioff@high', '≥1e6', f"{m('eq_bicgst_fine')['Ion_Ioff']:.5e}", '미달'],
        ['Vth@low', '0.1~0.5 V', f(m('eq_bicgst_fine','low')['Vth_V'], 6)+' V', '통과'],
        ['SS@low / high', '각 60~90 mV/dec', f(m('eq_bicgst_fine','low')['SS_mV_dec'])+' / '+f(m('eq_bicgst_fine')['SS_mV_dec']), '통과'],
        ['DIBL', '0~50 mV/V', f(metrics['eq_bicgst_fine']['DIBL_mV_V'])+' mV/V', '통과'],
        ['KCL / 단조성', '점별 기준 / Vgs≥0에서 5% 초과 감소 없음', '두 Vds 모두 통과', '수치 검사 통과'],
    ]) + '\n\n**기준 소자의 공학 목표 전체 판정은 미달이다.** KCL 최대 절대 잔차는 low 1.104e−11 A, high 4.100e−12 A이며 각 점의 상대 기준과 함께 검사했다. SS≈60 mV/dec라는 결과만으로 물리 모델 보정을 입증할 수 없다.')
    base, fine = m('eq_bicgst_full'), m('eq_bicgst_fine')
    slide('08. full–fine 메시 비교', table(['지표 @Vds=0.6 V', 'full', 'fine', '변화', '허용값'], [
        ['Ion (µA/µm)', f(base['Ion_A_per_um']*1e6), f(fine['Ion_A_per_um']*1e6), f(abs(fine['Ion_A']/base['Ion_A']-1)*100)+'%', '≤5%'],
        ['Ioff (nA/µm)', f(base['Ioff_A_per_um']*1e9,5), f(fine['Ioff_A_per_um']*1e9,5), f(abs(fine['Ioff_A']/base['Ioff_A']-1)*100)+'%', '≤20%'],
        ['Vth (V)', f(base['Vth_V'],6), f(fine['Vth_V'],6), f(abs(fine['Vth_V']-base['Vth_V'])*1000,6)+' mV', '≤10 mV'],
        ['SS (mV/dec)', f(base['SS_mV_dec'],6), f(fine['SS_mV_dec'],6), f(abs(fine['SS_mV_dec']-base['SS_mV_dec']),6), '≤5 mV/dec'],
    ]) + '''

`eq_bicgst_full → eq_bicgst_fine`은 low·high의 8개 지표 모두 기준을 만족했다. Si 단면 최대 간격 설정은 1→0.5 nm, 산화막 수직 간격은 0.25→0.125 nm로 줄였다. z 최대 간격 설정은 2→1 nm이다. 이는 덱의 제약값이며 실제 모든 요소가 균일 간격이라는 뜻은 아니다.

screen(설정 배율 2)→full(배율 1)은 진단 비교이다. 이를 정식 full→fine 통과로 대신하지 않는다. 기준 분기의 메시 통과를 일함수 변경·BQP 분기에 확대하지 않는다.
''')
    slide('09. 일함수 변화의 full 결과', '''
같은 구조·full 메시·고전 DD·BICGST·초기화에서 일함수만 바꾼 별도 실험이다. Ion·Ioff·비율은 Vds=0.6 V 기준이다.

''' + table(['일함수 (eV)', 'Ion (µA/µm)', 'Ioff (nA/µm)', 'Ion/Ioff', 'Vth low (V)', '공학 목표 전체'], [
        [wf, f(m(c)['Ion_A_per_um']*1e6), f(m(c)['Ioff_A_per_um']*1e9,6), f"{m(c)['Ion_Ioff']:.4e}", f(m(c,'low')['Vth_V'],6), '통과' if metrics[c]['engineering_targets_pass'] else '미달']
        for wf,c in [('4.50','eq_bicgst_full'),('4.55','wf4p55_full'),('4.60','wf4p6_full')]
    ]) + '''

일함수 증가에 따라 Vth가 높아지고 Ioff와 Ion이 함께 줄었다. 4.55·4.60 eV full에서는 설정된 공학 목표가 모두 충족된다. **두 조건의 fine high 바이어스 검증이 실패했으므로 최종 설계 확정이나 메시 수렴 통과로 발표하지 않는다.** 실제 금속 공정·실험에 맞춘 일함수 보정도 수행하지 않았다.
''')
    slide('10. BQP 추가의 full 결과', table(['지표', '고전 DD full', 'BQP full'], [
        ['일함수 / Si 단면', '4.5 eV / 10×10 nm', '동일'],
        ['Ion@high (µA/µm)', f(m('eq_bicgst_full')['Ion_A_per_um']*1e6), f(m('bqp_full')['Ion_A_per_um']*1e6)],
        ['Ioff@high (nA/µm)', f(m('eq_bicgst_full')['Ioff_A_per_um']*1e9,6), f(m('bqp_full')['Ioff_A_per_um']*1e9,6)],
        ['Vth@low (V)', f(m('eq_bicgst_full','low')['Vth_V'],6), f(m('bqp_full','low')['Vth_V'],6)],
        ['SS@high (mV/dec)', f(m('eq_bicgst_full')['SS_mV_dec']), f(m('bqp_full')['SS_mV_dec'])],
        ['DIBL (mV/V)', f(metrics['eq_bicgst_full']['DIBL_mV_V']), f(metrics['bqp_full']['DIBL_mV_V'])],
        ['Ion/Ioff@high', f"{m('eq_bicgst_full')['Ion_Ioff']:.4e}", f"{m('bqp_full')['Ion_Ioff']:.4e}"],
    ]) + '''

BQP full에서는 Ioff 목표를 만족하지만 Ion/Ioff≥1e6은 미달이다. 이 결과는 양자 보정 모델을 추가했을 때의 **계산상 민감도**이다. BQP 파라미터의 실험/기준 해석 보정과 fine 검증이 완료되지 않아 정량적인 양자 효과의 정확도를 주장할 수 없다.
''')
    slide('11. 실패 원인과 복구 실험', table(['분기', '실제 관측', '판단 / 후속'], [
        ['bias_bicgst_full / bias_default_full', 'Cannot trap, gate sweep 수렴 실패; ATLAS 종료 표시는 존재', '정상 종료 표식만으로 성능 채택 불가'],
        ['bias_direct_fine / eq_direct_fine', 'Unable to allocate memory, 필수 출력 누락', '메모리·solver 자원 조건 검토'],
        ['eq_default_fine', '프로세스 return code 11, 필수 출력 누락', '원인 미분류; 전체 로그 추가 확인'],
        ['wf4p55_fine', 'high sweep 최종 drain≈0.4900 V; 목표 0.6 V', 'high 지표·full–fine 비교 무효'],
        ['wf4p6_fine', 'high sweep 최종 drain≈0.3407 V; 목표 0.6 V', 'high 지표·full–fine 비교 무효'],
        ['ramp002 복구 두 덱', 'drain ramp 간격 0.01→0.002 V; 구조·물리·목표 유지', '11/17 당시 첫 덱 실행·다음 덱 대기; 결과 미확인'],
    ]) + '\n\n라이선스 통신 경고와 계산 오류는 구별한다. 일부 성공 작업에도 라이선스 경고가 있으므로 종료 코드·필수 출력·native 바이어스·KCL을 함께 확인한다. [실패·미완료 원시 발췌](../검증/GAA_발표_20261118/실패와미완료/)')
    slide('12. 현재 결론과 다음 검증', '''
**단일 3D GAA의 실제 계산과 기준 DD 분기의 full–fine 메시 비교를 확보했다. 기준 소자는 누설·전류비 목표가 남아 있으며, 일함수 변경의 유망한 full 결과는 fine 재현이 필요하다.**

''' + table(['우선순위', '다음 확인', '완료 판단'], [
        ['1', '동일 cau103 계정의 agent 재연결 후 원격 상태·결과 회수', '새 snapshot의 관측 시각·종료·해시 확인'],
        ['2', 'bqp_fine 및 ramp002 두 작업의 native log 검사', '실제 Vds=0.6 V, 전체 51점·KCL·정상 종료'],
        ['3', '일함수/BQP 각 분기의 full–fine 비교', '기존 Ion·Ioff·Vth·SS 허용값 유지'],
        ['4', '실제 .str의 영역·전극·도핑·계면 메시 재판독', '덱의 의도와 생성 구조 일치'],
        ['5', '계면 이동도·양자 모델 보정과 누설 모델 범위 검토', '동일 조건의 기준 자료 및 모델 한계 명시'],
    ]) + '''

게이트 누설이 0으로 계산돼도 터널링 미적용 상태에서는 실제 누설 검증이 아니다. 16 nm 축소·high-k·치수 변화는 기준 검증 이후 별도 실험으로 진행한다. 현재 상태에서 소자 물리 검증 완료나 연구 전체 완료를 주장하지 않는다.
''')
    appendix = '''## 부록 A. 근거와 재현 방법

대표 5조건은 원본 native log와 3단자 export를 다시 읽어 바이어스·51점 격자·KCL·지표를 계산하고 저장된 검증 JSON과 대조했다. 실제 실행의 return code·필수 출력·정상 종료 표식도 확인했다. 전체 solver.out 대신 보존된 process 요약과 마지막 8 KiB를 읽었으므로 전체 경고의 독립 재검토를 대체하지 않는다.

- [재계산 결과와 검증 기록](../검증/GAA_발표_20261118/검증기록.json)
- [원시 자료·덱의 SHA-256 목록](../검증/GAA_발표_20261118/출처해시.json)
- [발표 작성 실행 프롬프트](GAA_발표자료_실행프롬프트_20261118.md)
- [사전 설계와 정량 목표](../연구/01_GAA_IdVg/md/설계와목표.md)
- [분석기](../연구/01_GAA_IdVg/python/analyze.py), [실행 검증기](../python/automation/validate_case.py)
- [원래 34개 덱](../연구/01_GAA_IdVg/tcad/gaa_overnight_20261116T080149Z/), [복구 덱](../연구/01_GAA_IdVg/tcad/gaa_autonomous_20261117T064609Z/)

원래 실행 ID: `gaa_overnight_20261116T080149Z`
회수 ID: `gaa_night_snapshot_20261117T072717Z`
원격 원본: `~/gaa_tcad_runs/<실행 ID>/durable/`
원시 회수본: `.local/collected/<회수 ID>/`
자료 재계산 스크립트: `python/build_presentation_20261118.py` (산출 폴더가 이미 있으면 덮어쓰지 않고 중단)

대표 덱·로그의 사본은 `검증/GAA_발표_20261118/`에 보존했다. 원격 보존 `.str`의 manifest 해시는 원격에서 보고된 값이며 이번 PC에서 본체 바이트를 대조한 값은 아니다. 입력 JSON의 `simulator_execution: NOT_RUN`은 생성 당시 상태로, 실제 실행 여부는 회수한 process·로그로 판단했다.
'''
    appendix += '\n## 부록 B. 34개 작업의 마지막 관측 상태\n\n' + table(['작업 ID', '상태'], [[k,v['status']] for k,v in snapshot['states'].items()])
    text = '# GAA 연구 발표 자료\n\n' + '\n\n---\n\n'.join(sections) + '\n\n---\n\n' + appendix + '\n'
    assert len(sections) == 12
    assert '![' not in text and '<svg' not in text
    broken=[]
    for target in re.findall(r'\]\(([^)]+)\)', text):
        if not (ROOT/'md'/target).resolve().exists(): broken.append(target)
    # These two evidence files are written immediately below.
    # Final relocated links are verified after path conversion below.
    text = text.replace('(../', '(../../')
    output = ROOT/'md/발표자료'/OUTPUT_NAME
    if FRESH:
        replacements = {
            '11/18에는 이전 중계의 두 주소가 DNS 조회에 실패했고, 같은 cau103 서버의 SSH 연결도 시간 초과였다. 이후 계산 상태는 미확인이다.': '11/18에 이 PC의 중계를 새로 구성하고 cau103 agent를 재등록했다. 인증된 agent에서 두 실행 계획의 새 스냅샷을 회수했으며 ZIP과 파일별 SHA-256을 검증했다. 원래 계획의 scheduler PID는 종료됐고, 복구 supervisor의 PID와 명령행은 일치했다.',
            '이번에 내려받지 못했으므로': '전송량을 제한하기 위해 이번 회수에서 제외했으므로',
            '당시 `wf4p55_fine_ramp002` 실행 중, `wf4p6_fine_ramp002` 대기 중.': '`wf4p55_fine_ramp002` 실패, `wf4p6_fine_ramp002` 실행 중이다. 원래 계획의 `bqp_fine`은 high sweep이 Vgs=0.58484375 V에서 끝나 검증 실패로 종료됐다.',
            '11/17 당시 첫 덱 실행·다음 덱 대기; 결과 미확인': '4.55 eV 실패(빈 high log); 4.60 eV 실행 중(초기 drain ramp 수렴 경고)',
            '동일 cau103 계정의 agent 재연결 후 원격 상태·결과 회수': '실행 중인 4.60 eV 복구 작업의 종료·오류·결과 회수',
            '새 snapshot의 관측 시각·종료·해시 확인': '최종 종료 코드·native log·해시 확인; 단순 heartbeat와 구별',
            'bqp_fine 및 ramp002 두 작업의 native log 검사': 'BQP fine과 4.55 eV 복구 실패의 수치 원인 분류',
            '실제 Vds=0.6 V, 전체 51점·KCL·정상 종료': '목표 Vds·전체 51점·KCL·정상 종료를 모두 만족하는 별도 시도 필요',
            '회수 ID: `gaa_night_snapshot_20261117T072717Z`': '회수 ID: `' + read(ROOT/'.local/presentation_received.json')['job'] + '`',
        }
        for old, new in replacements.items():
            if old != new:
                assert old in text, old
                text = text.replace(old, new)
        text = text.replace('GAA_발표_20261118/', OUT.name+'/')
        text = text.replace('마지막 8 KiB', '마지막 16 KiB')
        text = text.replace('| ramp002 복구 두 덱 |', '| bqp_fine | high의 Vds=0.6 V는 도달했으나 Vgs=0.58484375 V에서 스윕 종료 | 목표 Vgs=0.8 V 미달; Ion·SS·메시 비교 채택 불가 |\n| ramp002 복구 두 덱 |')
        text = text.replace('원격 보존 `.str`의 manifest 해시는', '현재 회수 자료의 추가 상태: BQP fine은 ATLAS 정상 종료·return code 0이어도 목표 Vgs=0.8 V에 미달해 제외했다. 4.55 eV 복구는 high log가 비었고 EXTRACT 오류로 정상 종료하지 못했다. 4.60 eV 복구의 마지막 기록은 drain=3.125e−5 V의 초기 ramp 시도이며 최종 0.6 V 도달이나 성능 값으로 사용할 수 없다. 스냅샷은 파일을 순서대로 읽으므로 완전히 동시적인 원자적 상태는 아니다.\n\n원격 보존 `.str`의 manifest 해시는')
    for target in re.findall(r'\]\(([^)]+)\)', text):
        if not (output.parent/target).resolve().exists() and not target.endswith(('/검증기록.json','/출처해시.json')):
            raise ValueError('Broken output link: '+target)
    with output.open('w' if FRESH else 'x', encoding='utf-8', newline='\n') as stream: stream.write(text)
    record = {'created_utc': datetime.now(timezone.utc).isoformat(), 'snapshot_kst': timestamp,
              'current_remote_verified': FRESH, 'remote_connection': 'Fresh authenticated agent snapshot received and SHA verified' if FRESH else 'Both relay routes DNS failed; direct SSH timed out',
              'states': counts, 'representative_cases': checks, 'recomputed': metrics,
              'physical_validation': 'NOT_VALIDATED', 'graphs_created': 0, 'presentation_sections': 12,
              'raw_structure_byte_validation': 'NOT_DOWNLOADED', 'whole_solver_review': False,
              'output_sha256': hashlib.sha256(output.read_bytes()).hexdigest()}
    (OUT/'검증기록.json').write_text(json.dumps(record,ensure_ascii=False,indent=2), encoding='utf-8')
    (OUT/'출처해시.json').write_text(json.dumps(hashes,ensure_ascii=False,indent=2), encoding='utf-8')
    print(json.dumps({'markdown':str(output),'evidence_files':len(hashes),'recomputed_cases':len(metrics),
                      'snapshot_kst':timestamp,'links_checked':True},ensure_ascii=False))


if __name__ == '__main__':
    main()

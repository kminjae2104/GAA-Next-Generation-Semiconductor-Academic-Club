"""Recompute trend diagnostics and build a complete, source-linked GAA case ledger."""
import argparse
import csv
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '검증/전체연구검토_20261124'
AUDIT = OUT / '최신재계산/audit.json'
FIGURES = ROOT / '그림/전체연구검토_20261124'
sys.path.insert(0, str(ROOT / 'python/automation'))
sys.path.insert(0, str(ROOT / '연구/01_GAA_IdVg/python'))
import analyze
from validate_case import mesh_comparison
from validate_explicit_bias import canonical_curve


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def dump(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def stamp(epoch):
    return datetime.fromtimestamp(epoch, timezone(timedelta(hours=9))).isoformat() if epoch else ''


def rehash(folder):
    bad = []
    manifest = read(folder / 'output_hashes.json')
    for name, digest in manifest.items():
        p = (folder / name).resolve()
        p.relative_to(folder.resolve())
        if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest() != digest:
            bad.append(name)
    if bad:
        raise ValueError('Evidence hash mismatch: ' + str(bad))
    return {'collection': folder.name, 'files_rehashed': len(manifest), 'mismatches': bad}


def main():
    OUT.mkdir(parents=True, exist_ok=False)
    audit = read(AUDIT)
    source = Path(audit['source'])
    supplemental = {'snapshot_time': audit['snapshot_time'], 'explicit_raw_checks': {},
                    'early_collections': [], 'physical_validation': 'NOT_VALIDATED'}
    rows = []
    ledger = ['# GAA 전체 실행 목록 — 2026-11-24', '',
              '동일 실행 ID/조건의 반복 snapshot은 한 번만 센다. screen과 smoke는 진단이며 최종 소자 수가 아니다.', '',
              '| 실행 ID | 조건 | 상태 | 실행 코드 | 공학 목표 | 메시 | 재계산 |',
              '| --- | --- | --- | --- | --- | --- | --- |']
    for job, data in audit['jobs'].items():
        for name, case in data['cases'].items():
            result = case.get('recomputed')
            status = case['scheduler']['status']
            rc = (case.get('process') or {}).get('returncode')
            mesh = (case.get('independent_mesh_comparison') or {}).get('status', '미검증')
            target = '진단' if name.endswith(('screen', 'smoke')) else ('충족' if result and result['engineering_targets_pass'] else '미달' if result else '판정불가')
            relative = (source / job / 'cases' / name).relative_to(ROOT).as_posix()
            ledger.append(f'| {job} | {name} | {status} | {rc} | {target} | {mesh} | {"확인" if result else "없음"} |')
            rows.append(dict(job=job, case=name, status=status, worker_returncode=case['scheduler'].get('returncode'),
                             simulator_returncode=rc, started_KST=stamp(case['scheduler'].get('started')),
                             finished_KST=stamp(case['scheduler'].get('finished')), engineering=target,
                             mesh=mesh, evidence_path=relative, metrics_recomputed=bool(result)))
            if result and 'explicit' in job:
                checks, recalculated = {}, {}
                for direction, reverse in [('forward', False), ('reverse', True)]:
                    dest = OUT / '독립원시검사' / name / direction
                    dest.mkdir(parents=True, exist_ok=False)
                    checks[direction] = {bias: canonical_curve(source / job / 'cases' / name, dest, bias, reverse)
                                         for bias in ['low', 'high']}
                    recalculated[direction], _ = analyze.analyze(dest, .04)
                entry = {'raw': checks, 'reverse_engineering_pass': recalculated['reverse']['engineering_targets_pass']}
                if name.endswith('fine'):
                    refname = name[:-5] + '_full'
                    reference = audit['jobs'][job]['cases'][refname]
                    entry['forward_mesh'] = mesh_comparison(reference['recomputed'], recalculated['forward'])
                    entry['reverse_mesh'] = mesh_comparison(reference['reverse_recomputed'], recalculated['reverse'])
                supplemental['explicit_raw_checks'][name] = entry
    early_ids = ['gaa_preflight_20261116_bg01', 'gaa_smoke_20261116_r01', 'gaa_smoke_20261116_r02',
                 'gaa_smoke_20261116_r03', 'gaa_full_20261116_r01', 'gaa_full_20261116_r02',
                 'gaa_parallel_20261116T062844Z', 'gaa_modelhints_20261116_r01', 'gaa_modelhints_20261116_r02']
    ledger += ['', '## 초기 실행과 설치 모델 조회', '',
               '| 수집 ID | 하위 경로 | 보존 상태 | 코드 | timeout | 초 | 정상 종료 문자열 | native 로그 |',
               '| --- | --- | --- | --- | --- | --- | --- | --- |']
    for job in early_ids:
        folder = ROOT / '.local/collected' / job
        hashes = rehash(folder)
        statuses = []
        for path in sorted(folder.rglob('status.json')):
            state = read(path)
            rel = path.parent.relative_to(folder)
            stages = []
            for stage in state.get('stages', []):
                if isinstance(stage.get('result'), dict):
                    continue  # nested coarse/fine status files below hold the actual stage record
                if (path.parent / stage.get('stage', '') / 'status.json').is_file():
                    continue  # aggregate parallel status repeats the child status record
                execution = path.parent / stage.get('stage', 'gaa') / 'execution'
                solver = execution / 'solver.out'
                text = solver.read_text(errors='replace') if solver.exists() else ''
                import re
                finish = bool(re.search(r'ATLAS version[^\n]*finished', text, re.I))
                native = []
                for log in execution.glob('idvg_*.log'):
                    lines = log.read_text(errors='replace').splitlines()
                    native.append({'name': log.name, 'points': sum(s.startswith('d ') for s in lines)})
                record = {k: stage.get(k) for k in ['stage', 'returncode', 'timeout', 'seconds', 'missing']}
                record.update(normal_finish=finish, native=native)
                stages.append(record)
                ledger.append(f"| {job} | {rel}/{stage.get('stage')} | {state.get('status')} | {stage.get('returncode')} | {stage.get('timeout')} | {stage.get('seconds')} | {finish} | {native} |")
            statuses.append({'path': str(rel), 'status': state.get('status'), 'stages': stages})
            if not state.get('stages'):
                ledger.append(f"| {job} | {rel} | {state.get('status')} | — | — | — | — | — |")
        supplemental['early_collections'].append({**hashes, 'statuses': statuses})
    job = 'gaa_continuation_explicit_20261120T063127Z'
    cases = audit['jobs'][job]['cases']
    result = {key: cases[key]['recomputed'] for key in ['dd45_full', 'dd455_full', 'dd46_full', 'dd45_fine', 'dd46_fine']}
    high = {key: r['metrics']['high'] for key, r in result.items()}
    a, b, c = [high[n] for n in ['dd45_full', 'dd455_full', 'dd46_full']]
    trend = {'source_conditions': [job + '/' + key for key in result],
             'DD_45_to_46': {'Ion_change_percent': (c['Ion_A']/a['Ion_A']-1)*100,
                            'Ioff_reduction_factor': a['Ioff_A']/c['Ioff_A'],
                            'low_Vth_change_V': result['dd46_full']['metrics']['low']['Vth_V']-result['dd45_full']['metrics']['low']['Vth_V'],
                            'Ioff_log10_slope_per_eV': math.log10(c['Ioff_A']/a['Ioff_A'])/.1}}
    pairs = {}
    for bias in ['low', 'high']:
        curves = {}
        for name in ['dd45_full', 'dd46_full', 'dd45_fine', 'dd46_fine']:
            curves[name] = analyze.read_curve(AUDIT.parent / 'canonical_forward' / job / name / (bias + '_drain.dat'))
        for mesh in ['full', 'fine']:
            ref = {round(v, 7): abs(i) for v, i in curves['dd45_' + mesh]}
            matched = [(v, abs(i), ref[round(v-.1, 7)]) for v, i in curves['dd46_' + mesh]
                       if round(v-.1, 7) in ref and 1e-10 <= ref[round(v-.1, 7)]/.04 <= 1e-3]
            errors = [abs(i-j)/j for _, i, j in matched]
            pairs[bias + '_' + mesh] = dict(points=len(errors), max_relative_current_error=max(errors),
                                            RMS_relative_error=math.sqrt(sum(x*x for x in errors)/len(errors)),
                                            gate_shift_V=.1, interpolated=False, normalized_current_window_A_um=[1e-10,1e-3])
    trend['rigid_shift_exact_native_pairs'] = pairs
    original = audit['jobs']['gaa_overnight_20261116T080149Z']['cases']
    q = original['bqp_full']['recomputed']
    d = original['eq_bicgst_full']['recomputed']
    trend['uncalibrated_BQP_vs_DD_full'] = dict(
        Ion_change_percent=(q['metrics']['high']['Ion_A']/d['metrics']['high']['Ion_A']-1)*100,
        Ioff_change_percent=(q['metrics']['high']['Ioff_A']/d['metrics']['high']['Ioff_A']-1)*100,
        low_Vth_change_mV=(q['metrics']['low']['Vth_V']-d['metrics']['low']['Vth_V'])*1000,
        DIBL_change_mV_V=q['DIBL_mV_V']-d['DIBL_mV_V'])
    supplemental['trends'] = trend
    dump(OUT / 'supplemental_validation.json', supplemental)
    with (OUT / 'case_ledger.csv').open('x', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (OUT / '실행전체목록.md').write_text('\n'.join(ledger) + '\n', encoding='utf-8')
    figures(source, audit)
    print(json.dumps({'DAG_cases': len(rows), 'recomputed_conditions': sum(r['metrics_recomputed'] for r in rows),
                      'early_files_rehashed': sum(x['files_rehashed'] for x in supplemental['early_collections']),
                      'trends': trend}, ensure_ascii=False))


def figures(source, audit):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    figdir = FIGURES
    figdir.mkdir(parents=True, exist_ok=False)
    job = 'gaa_continuation_explicit_20261120T063127Z'
    fig, axs = plt.subplots(1, 3, figsize=(15, 4.5))
    for name, wf, color in [('dd45_full',4.5,'#1d4ed8'),('dd455_full',4.55,'#d97706'),('dd46_full',4.6,'#047857')]:
        p = AUDIT.parent / 'canonical_forward' / job / name / 'high_drain.dat'
        curve = analyze.read_curve(p)
        axs[0].semilogy([v for v,i in curve], [abs(i)/.04 for v,i in curve], color=color, label=f'DD {wf:.2f} eV full')
        axs[1].semilogy([v-(wf-4.5) for v,i in curve], [abs(i)/.04 for v,i in curve], color=color, label=f'{wf:.2f} eV')
    curve = analyze.read_curve(source / 'gaa_overnight_20261116T080149Z/cases/bqp_full/high_drain.dat')
    axs[0].semilogy([v for v,i in curve], [abs(i)/.04 for v,i in curve], '--',color='#9d174d',label='BQP 4.50 eV full (uncalibrated)')
    axs[0].axvline(0, color='gray', linewidth=.7)
    axs[0].axvline(.6, color='gray', linewidth=.7)
    axs[0].set_title('Actual TCAD exports, Vds = 0.6 V')
    axs[0].set_xlabel('Vgs (V)')
    axs[1].set_title('Work-function shift diagnostic')
    axs[1].set_xlabel('Vgs - (WF - 4.50 eV)/q (V)')
    axs[1].set_xlim(-.2,.7)
    axs[1].text(.03,.03,'Axis shift only; no new simulated points',transform=axs[1].transAxes,fontsize=8)
    for ax in axs[:2]:
        ax.set_ylabel('|Id| (A/um of gate perimeter)')
        ax.set_ylim(1e-13,2e-3)
        ax.legend(fontsize=7,loc='upper left')
    for name, wf, color in [('dd45_full',4.5,'#1d4ed8'),('dd455_full',4.55,'#d97706'),('dd46_full',4.6,'#047857'),('dd45_fine',4.5,'#1d4ed8'),('dd46_fine',4.6,'#047857')]:
        m = audit['jobs'][job]['cases'][name]['recomputed']['metrics']['high']
        axs[2].semilogx(m['Ioff_A_per_um']*1e9,m['Ion_A_per_um']*1e6,'s' if 'fine' in name else 'o',color=color,fillstyle='none' if 'fine' in name else 'full',label=f'{wf:.2f} eV {name.split("_")[-1]}')
    axs[2].axvline(1, color='gray',linestyle=':',label='Ioff target')
    axs[2].set_xlabel('Ioff (nA/um of gate perimeter)')
    axs[2].set_ylabel('Ion (uA/um of gate perimeter)')
    axs[2].set_title('Fixed bias trade-off')
    axs[2].legend(fontsize=7)
    for ax in axs:
        ax.grid(True,which='major',alpha=.2)
    fig.suptitle('10 x 10 nm Si wire; Lg = 40 nm; SiO2 = 1 nm; 300 K; physics calibration pending',fontsize=11)
    fig.tight_layout()
    for ext in ['png','svg']:
        fig.savefig(figdir / ('observed_trends.'+ext),dpi=180)
    plt.close(fig)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audit', type=Path, default=AUDIT)
    parser.add_argument('--out', type=Path, default=OUT / '추가재검산')
    parser.add_argument('--figures', type=Path, default=FIGURES / '추가재검산')
    args = parser.parse_args()
    OUT, AUDIT, FIGURES = [p.resolve() for p in [args.out, args.audit, args.figures]]
    for p in [OUT, AUDIT, FIGURES]:
        p.relative_to(ROOT)
    main()

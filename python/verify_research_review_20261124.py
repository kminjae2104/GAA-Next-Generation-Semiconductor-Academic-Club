"""Validate review artifacts against collected TCAD evidence, without simulator calls."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '검증/전체연구검토_20261124'
sys.path.insert(0, str(ROOT / '연구/01_GAA_IdVg/python'))
import analyze


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def main():
    audit = read(OUT / '최신재계산/audit.json')
    source = Path(audit['source'])
    supplement = read(OUT / 'supplemental_validation.json')
    comparison = read(OUT / '교차검산/supplemental_validation.json')
    assert supplement == comparison
    counts = Counter(c['scheduler']['status'] for d in audit['jobs'].values() for c in d['cases'].values())
    assert counts == {'SUCCEEDED':37,'FAILED':15,'BLOCKED':6,'RUNNING':1,'PENDING':1}
    conditions = [c for d in audit['jobs'].values() for c in d['cases'].values() if 'recomputed' in c]
    assert len(conditions) == 30
    assert all(c['recorded_metrics_match'] and c['execution_checks_pass'] and not c.get('audit_error') for c in conditions)
    for name in ['dd45_fine','dd46_fine']:
        x = supplement['explicit_raw_checks'][name]
        assert x['forward_mesh']['status'] == x['reverse_mesh']['status'] == 'PASS'
        assert all(check['all_raw_points_checked'] and not check['interpolation_used']
                   for direction in x['raw'].values() for check in direction.values())
    assert supplement['explicit_raw_checks']['dd46_fine']['reverse_engineering_pass'] is True
    smoke_folders = [(j, n, source / j / 'cases' / n)
                     for j,d in audit['jobs'].items() for n in d['cases'] if n.endswith('smoke')]
    smoke_folders += [('gaa_smoke_20261116_r03','gaa',ROOT / '.local/collected/gaa_smoke_20261116_r03/gaa/execution'),
                      ('gaa_parallel_20261116T062844Z','smoke',ROOT / '.local/collected/gaa_parallel_20261116T062844Z/smoke/gaa/execution')]
    smoke_rows = []
    for job, name, folder in smoke_folders:
        curves = {t:analyze.read_curve(folder / ('low_'+t+'.dat'),min_points=1) for t in ['gate','source','drain']}
        bias = analyze.validate_native_log(folder / 'idvg_low.log', .05, curves)
        residuals, passes = [], []
        for d,s,g in zip(curves['drain'],curves['source'],curves['gate']):
            currents = [d[1],s[1],g[1]]
            r = abs(sum(currents))
            residuals.append(r)
            passes.append(r <= max(1e-14,max(map(abs,currents))*.001))
        assert all(passes)
        smoke_rows.append(dict(job=job,case=name,**bias,kcl_max_abs_A=max(residuals),kcl_pass=True,
                               gate_range_V=[curves['drain'][0][0],curves['drain'][-1][0]],
                               Id_at_Vg0_A=analyze.at(curves['drain'],0),
                               use='SHORT_LOW_VDS_DIAGNOSTIC_NOT_ION_IOFF_PERFORMANCE'))
    (OUT / 'smoke_checks.json').write_text(json.dumps(smoke_rows,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    docs = [ROOT / 'md/GAA_전체결과와_연구방향_20261124.md',
            ROOT / 'md/연구계획/후속실험_사전계획_20261124.md',
            ROOT / 'md/연구계획/연구주제와_선행연구검토_20261124.md',
            ROOT / 'md/연구계획/전체결과_후속실험_연구주제_실행프롬프트_20261124.md']
    link_errors, trailing = [], []
    for doc in docs:
        text = doc.read_text(encoding='utf-8')
        for label, target in re.findall(r'\[([^\]]*)\]\(([^)]+)\)',text):
            if not target.startswith(('http:','https:','#')) and not (doc.parent / target).resolve().exists():
                link_errors.append([str(doc.relative_to(ROOT)),target])
        trailing += [f'{doc.name}:{i}' for i,line in enumerate(text.splitlines(),1) if line.rstrip()!=line]
        assert text.count('```') % 2 == 0
    assert not link_errors, link_errors
    assert not trailing, trailing
    scripts = [ROOT / 'python' / name for name in ['research_audit_20261124.py','research_results_20261124.py','verify_research_review_20261124.py']]
    for script in scripts:
        compile(script.read_text(encoding='utf-8'),str(script),'exec')
    artifacts = docs + scripts + [OUT / 'literature_search.json',OUT / 'smoke_checks.json',
                  OUT / 'case_ledger.csv',OUT / '실행전체목록.md',OUT / 'supplemental_validation.json',
                  ROOT / '그림/전체연구검토_20261124/observed_trends.png',ROOT / '그림/전체연구검토_20261124/observed_trends.svg']
    report = dict(snapshot_time=audit['snapshot_time'],snapshot_files_rehashed=audit['files_rehashed'],
                  early_files_rehashed=sum(x['files_rehashed'] for x in supplement['early_collections']),
                  DAG_counts=dict(counts),recomputed_conditions=len(conditions),smoke_checks=len(smoke_rows),
                  stored_metrics_and_execution_checks_match=True,forward_reverse_mesh_checks=True,
                  independent_repeat_matches=True,local_link_errors=link_errors,trailing_whitespace=trailing,
                  figures='PNG_VISUALLY_INSPECTED_SVG_EXPORTED',new_simulator_executions=0,
                  physical_calibration='NOT_VALIDATED',literature_novelty='CONDITIONAL_NOT_PROVEN',
                  artifacts={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in artifacts})
    (OUT / 'final_validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='artifacts'},ensure_ascii=False))


if __name__ == '__main__':
    main()

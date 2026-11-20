"""Audit an immutable collected snapshot; never modify remote or collected data."""
import argparse,csv,hashlib,importlib.util,json,math,re,shlex,sys
from datetime import datetime,timedelta,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'연구/01_GAA_IdVg/python'))
import analyze
from validate_case import mesh_comparison
from validate_continuation import canonical
from validate_explicit_bias import canonical_curve

def read(p):return json.loads(p.read_text(encoding='utf-8'))
def stamp(epoch):return datetime.fromtimestamp(epoch,timezone(timedelta(hours=9))).strftime('%Y-%m-%d %H:%M:%S KST')
def same(a,b):
    if isinstance(a,dict):return isinstance(b,dict) and all(k in b and same(v,b[k]) for k,v in a.items())
    if isinstance(a,list):return a==b
    if isinstance(a,(int,float)) and not isinstance(a,bool):return isinstance(b,(int,float)) and math.isclose(a,b,rel_tol=1e-9,abs_tol=1e-20)
    return a==b

def native_diagnostic(path):
    names=None;values=[]
    for line in path.read_text().splitlines():
        if line.startswith('f '):names=shlex.split(line)[2:]
        if line.startswith('d '):
            row=list(map(float,line.split()[1:]))
            if names!=['gate','source','drain'] or len(row)!=9 or not all(map(math.isfinite,row)):raise ValueError('Unknown native diagnostic layout')
            values.append(row)
    if not values:return dict(points=0)
    vg=[r[0] for r in values];vd=[r[6]-r[3] for r in values]
    reverse='_rev' in path.stem;grid=[(.8-.02*i) if reverse else (-.2+.02*i) for i in range(51)]
    return dict(points=len(values),gate_first_V=vg[0],gate_last_V=vg[-1],gate_min_V=min(vg),gate_max_V=max(vg),vds_min_V=min(vd),vds_max_V=max(vd),missing_expected_gate_V=[x for x in grid if not any(abs(x-y)<1e-6 for y in vg)],extra_gate_V=[x for x in vg if not any(abs(x-y)<1e-6 for y in grid)],expected_gate_grid_pass=len(vg)==51 and all(abs(x-y)<1e-6 for x,y in zip(vg,grid)))

def main():
    p=argparse.ArgumentParser();p.add_argument('snapshot',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    source=a.snapshot.resolve();out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
    snapshot=read(source/'presentation_snapshot.json')
    verified=read(source/'collection_verified.json')
    if not verified['transport_verified']:raise ValueError('Unverified collection')
    # Recheck every archive member against the hash manifest, including source bytes.
    manifest=read(source/'output_hashes.json');bad=[]
    for name,digest in manifest.items():
        target=(source/name).resolve();target.relative_to(source)
        if not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest()!=digest:bad.append(name)
    if bad:raise ValueError('Collected data changed: '+repr(bad[:3]))
    report=dict(source=str(source),snapshot_time=stamp(snapshot['snapshot_epoch']),files_rehashed=len(manifest),jobs={},physical_validation='NOT_VALIDATED')
    rows=[]
    for job,info in snapshot['jobs'].items():
        tasks=info.get('files',{}).get('results/progress.json',{}).get('tasks',{})
        data=dict(snapshot_time=stamp(info['snapshot_epoch']),counts={},cases={},complete=info.get('files',{}).get('complete.json'),workflow_status=info.get('files',{}).get('results/workflow_status.json'),pid_exists=info.get('recorded_pid_exists'),pid_cmdline=info.get('pid_cmdline'),scoped_live_processes=info.get('scoped_live_processes'))
        for name,state in tasks.items():
            status=state['status'];data['counts'][status]=data['counts'].get(status,0)+1
            folder=source/job/'cases'/name
            item=dict(scheduler=state,process=read(folder/'process.json') if (folder/'process.json').exists() else None)
            process=item['process'] or {}
            text='\n'.join((folder/f).read_text(errors='replace') for f in ['solver_tail.txt','scheduler_console.txt'] if (folder/f).exists())
            item['normal_finish_in_tail']=bool(re.search(r'ATLAS version[^\n]*finished',text,re.I))
            item['native_diagnostics']={}
            for native in folder.glob('idvg_*.log'):
                try:item['native_diagnostics'][native.name]=native_diagnostic(native)
                except Exception as exc:item['native_diagnostics'][native.name]=dict(error=str(exc))
            item['diagnostic_excerpt']=[s[:260] for s in text.splitlines() if re.search(r'ValueError|Error:|failed|converg|missing|mismatch|insufficient|incorrect|truncat',s,re.I)][-8:]
            if (folder/'progress.json').exists():item['progress']=read(folder/'progress.json')
            if status=='FAILED':
                item['diagnostic_only_valid_forward_curves']={}
                for bias,vd in [('low',.05),('high',.6)]:
                    try:
                        curves={t:analyze.read_curve(folder/(bias+'_'+t+'.dat')) for t in ['drain','source','gate']}
                        analyze.validate_native_log(folder/('idvg_'+bias+'.log'),vd,curves)
                        item['diagnostic_only_valid_forward_curves'][bias]=analyze.metric(curves,.04)
                    except (ValueError,OSError):pass
            if status=='SUCCEEDED' and not name.endswith('smoke'):
                try:
                    recorded=read(folder/'validated_metrics.json')
                    explicit=recorded.get('acquisition_revision')=='explicit_bias_v1'
                    analysis_folder=folder
                    if explicit:
                        analysis_folder=out/'canonical_forward'/job/name
                        analysis_folder.mkdir(parents=True,exist_ok=False)
                        for bias in ['low','high']:canonical_curve(folder,analysis_folder,bias,False)
                    result,raw=analyze.analyze(analysis_folder,.04)
                    item['recomputed']=result
                    item['recorded_metrics_match']=same(result['metrics'],recorded['metrics'])
                    item['execution_checks_pass']=bool(process.get('returncode')==0 and not process.get('timeout') and not process.get('missing') and item['normal_finish_in_tail'] and not [s for s in process.get('fatal_lines',[]) if 'transport error: no error' not in s.lower()])
                    item['recorded_mesh_comparison']=recorded.get('mesh_comparison')
                    if 'continuation' in job:
                        reverse_dir=out/'canonical_reverse'/job/name
                        reverse_dir.parent.mkdir(parents=True,exist_ok=True)
                        if explicit:
                            reverse_dir.mkdir(exist_ok=False)
                            for bias in ['low','high']:canonical_curve(folder,reverse_dir,bias,True)
                        else:canonical(folder,reverse_dir)
                        reverse,rr=analyze.analyze(reverse_dir,.04)
                        direction={}
                        for bias in ['low','high']:
                            pointpass=all(abs(x-y)<=max(1e-14,max(abs(x),abs(y))*.05) for (_,x),(_,y) in zip(raw[bias]['drain'],rr[bias]['drain']))
                            differences={k:abs(result['metrics'][bias][k]-reverse['metrics'][bias][k]) if result['metrics'][bias][k] is not None and reverse['metrics'][bias][k] is not None else None for k in ['Vth_V','SS_mV_dec']}
                            direction[bias]=dict(current_pass=pointpass,differences=differences,pass_all=pointpass and differences['Vth_V'] is not None and differences['Vth_V']<=.01 and differences['SS_mV_dec'] is not None and differences['SS_mV_dec']<=5 and reverse['metrics'][bias]['kcl_pass'] and not reverse['metrics'][bias]['nonmonotonic_indices'])
                        item['reverse_recomputed']=reverse;item['direction_checks']=direction
                    m=result['metrics']['high'];low=result['metrics']['low']
                    rows.append([job,name,'diagnostic' if name.endswith('screen') else 'performance',m['Ion_A'],m['Ion_A_per_um']*1e6,m['Ioff_A'],m['Ioff_A_per_um']*1e9,m['Ion_Ioff'],low['Vth_V'],low['SS_mV_dec'],m['SS_mV_dec'],result['DIBL_mV_V'],result['engineering_targets_pass']])
                except Exception as exc:item['audit_error']=str(exc)
            data['cases'][name]=item
        report['jobs'][job]=data
    for job,data in report['jobs'].items():
        for name,item in data['cases'].items():
            if name.endswith('_fine') and 'recomputed' in item:
                ref=data['cases'].get(name[:-5]+'_full',{})
                if 'recomputed' in ref:item['independent_mesh_comparison']=mesh_comparison(ref['recomputed'],item['recomputed'])
    (out/'audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    with (out/'metrics.csv').open('x',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f);w.writerow(['job','case','use','Ion_A_wire','Ion_uA_um','Ioff_A_wire','Ioff_nA_um','Ion_Ioff','Vth_low_V','SS_low_mV_dec','SS_high_mV_dec','DIBL_mV_V','engineering_pass']);w.writerows(rows)
    lines=['# GAA 총결과 재분석 — 2026-11-20','',f"자료 시각: {report['snapshot_time']}. 표의 상태는 이 원격 snapshot 시점의 관측값이며 이후 상태와 구분한다.",'',f"수집 원본 {len(manifest)}개를 output_hashes.json과 다시 대조했다. 원시 자료는 수정하지 않았다.",'','| 실행 ID | 수집 시점 상태 |','| --- | --- |']
    for job,data in report['jobs'].items():lines.append('| '+job+' | '+', '.join(k+' '+str(v) for k,v in data['counts'].items())+' |')
    lines+=['','단일 Si 10×10 nm, Lg 40 nm, SiO2 1 nm, 300 K. 둘레 0.04 um. Ion/Ioff는 Vds=0.6 V에서 Vgs=0.6/0 V. 아래 screen은 진단용이며 최종 성능 판정에 사용하지 않는다.','','| 조건 | Ion (uA/um) | Ioff (nA/um) | Ion/Ioff | Vth low (V) | SS low/high (mV/dec) | DIBL (mV/V) | 공학 목표 |','| --- | --- | --- | --- | --- | --- | --- | --- |']
    for row in rows:
        _,name,use,ia,ion,oa,ioff,ratio,vt,ssl,ssh,dibl,passed=row
        def fmt(x):return '추출불가' if x is None else f'{x:.6g}'
        label=name+(' (후속)' if 'continuation' in row[0] else '')
        lines.append('| '+' | '.join([label,fmt(ion),fmt(ioff),fmt(ratio),fmt(vt),fmt(ssl)+' / '+fmt(ssh),fmt(dibl),'진단용' if use=='diagnostic' else '충족' if passed else '미달'])+' |')
    lines+=['','## 독립 검증 결과','']
    for job,data in report['jobs'].items():
        for name,item in data['cases'].items():
            if 'recomputed' in item:
                line=f"- {job}/{name}: 저장 지표 일치 {item['recorded_metrics_match']}, 실행/종료 검사 {item['execution_checks_pass']}"
                if item.get('independent_mesh_comparison'):line+=', full–fine 메시 '+item['independent_mesh_comparison']['status']
                if item.get('direction_checks'):line+=', 정역방향 '+str(all(d['pass_all'] for d in item['direction_checks'].values()))
                lines.append(line+'.')
    lines+=['','## 해석과 검증 범위','','기존 기준 4.5 eV full/fine은 메시 기준을 충족하지만 Ioff와 Ion/Ioff 목표를 충족하지 못한다. 구동전류가 높다는 이유로 전체 목표 통과로 판단하지 않는다.','','기존 일함수 4.55/4.60 eV full은 문턱전압 증가와 함께 Ion과 Ioff가 낮아지고 공학 목표를 충족했다. 최종 수치 판단에는 각 분기의 fine과 full–fine 비교를 함께 사용한다. 기준 분기의 메시 통과를 전용할 수 없다.','','후속 gate-first 두 캐리어 경로는 native 바이어스·정역방향 전류·Vth·SS를 독립 비교했다. 결과 일치는 수치 경로 의존성이 작다는 제한된 증거이며 실험적 히스테리시스 검증이 아니다. 조건별 결과는 위 독립 검증과 audit.json direction_checks에 기록한다.','','기존 BQP full은 고전 full보다 Ion이 낮지만 Ion/Ioff 목표는 미달이다. 보정되지 않은 파라미터의 민감도 결과이며 실제 양자 효과의 정량 정확도를 입증하지 않는다.','','최종 연구 판단에서는 회수 범위, 종료/목표 바이어스, 조건별 full–fine 비교와 구조 본체의 계면 메시를 구분한다. 계면 이동도·양자·터널링 모델의 실험 보정은 수행하지 않았다. 실제 누설·공정성·AC·전력·소자 신뢰성을 검증한 결과는 없다.','','## 실패·진행 기록','']
    for job,data in report['jobs'].items():
        for name,item in data['cases'].items():
            if item['scheduler']['status'] in ['FAILED','BLOCKED','RUNNING'] or item.get('audit_error'):
                process=item.get('process') or {}
                lines += [f"- {job}/{name}: {item['scheduler']['status']}; worker 종료 코드 {item['scheduler'].get('returncode','미확인')}, 실행 단계 종료 코드 {process.get('returncode','미확인')}, normal finish {process.get('normal_atlas_finish','미확인')}."]
                for text in item['diagnostic_excerpt']:lines.append('  - '+text.replace('\x00',''))
                if item.get('audit_error'):lines.append('  - 재분석 실패: '+item['audit_error'])
                for native,d in item['native_diagnostics'].items():
                    if d.get('points'):
                        lines.append(f"  - {native}: {d['points']}점, Vg {d['gate_first_V']:.9g}→{d['gate_last_V']:.9g} V, Vds {d['vds_min_V']:.9g}~{d['vds_max_V']:.9g} V, 51점 목표 grid {d['expected_gate_grid_pass']}.")
                        if not d['expected_gate_grid_pass']:lines.append('    - 누락 목표 Vg '+str(d['missing_expected_gate_V'])+', 추가 Vg '+str(d['extra_gate_V'])+'.')
                for bias,m in item.get('diagnostic_only_valid_forward_curves',{}).items():
                    lines.append(f"  - 분리 진단 {bias}: Ion={m['Ion_A_per_um']*1e6:.6g} uA/um, Ioff={m['Ioff_A_per_um']*1e9:.6g} nA/um. 이 단일 곡선의 유효성을 전체 조건 통과로 사용하지 않는다.")
    (out/'총분석.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    failures=[job+'/'+name+': '+v['audit_error'] for job,d in report['jobs'].items() for name,v in d['cases'].items() if v.get('audit_error')]
    print(json.dumps(dict(snapshot_time=report['snapshot_time'],files_rehashed=len(manifest),recomputed=len(rows),audit_errors=failures,out=str(out)),ensure_ascii=False))

if __name__=='__main__':main()

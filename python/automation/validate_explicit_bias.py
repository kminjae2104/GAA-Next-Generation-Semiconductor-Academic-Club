"""New acquisition protocol: retain all adaptive rows, require every target exactly once."""
import argparse,json,math,re,shlex
from pathlib import Path
import analyze
from validate_case import selected,mesh_comparison

def canonical_curve(execution,out,bias,reverse=False):
    suffix='_rev' if reverse else ''
    path=execution/('idvg_'+bias+suffix+'.log')
    headers=[];rows=[];names=None
    for line in path.read_text().splitlines():
        if line.startswith('f '):names=shlex.split(line)[2:]
        if line.startswith('d '):
            row=list(map(float,line.split()[1:]))
            if names!=['gate','source','drain'] or len(row)!=9 or not all(map(math.isfinite,row)):raise ValueError('Unknown/nonfinite native layout')
            rows.append((line,row))
        else:headers.append(line)
    if not rows:raise ValueError('No native data')
    curves={}
    for terminal in ['gate','source','drain']:
        values=[]
        for line in (execution/(bias+suffix+'_'+terminal+'.dat')).read_text().splitlines():
            try:v,i=map(float,line.split())
            except ValueError:
                if values:raise ValueError('Malformed export after data')
                continue
            if not math.isfinite(v) or not math.isfinite(i):raise ValueError('Nonfinite export')
            values.append((v,i))
        if len(values)!=len(rows):raise ValueError('Native/export count mismatch')
        curves[terminal]=values
    vd=.05 if bias=='low' else .6
    for n,(_,row) in enumerate(rows):
        if abs(row[3])>1e-8 or abs(row[6]-vd)>1e-6:raise ValueError('Native source/drain bias differs from intended Vds')
        currents=[]
        for terminal,col in [('gate',0),('source',3),('drain',6)]:
            v,i=curves[terminal][n]
            if abs(v-row[0])>1e-7 or abs(i-row[col+2])>max(1e-20,abs(row[col+2])*1e-6):raise ValueError('Native/export mismatch')
            currents.append(i)
        if abs(sum(currents))>max(1e-14,max(map(abs,currents))*.001):raise ValueError('KCL failure including adaptive points')
        if n:
            delta=row[0]-rows[n-1][1][0]
            if (delta>=-1e-8 if reverse else delta<=1e-8):raise ValueError('Native direction/duplicate violation')
            prev=abs(rows[n-1][1][8]);now=abs(row[8])
            if min(row[0],rows[n-1][1][0])>=0 and (prev<now*.95 if reverse else now<prev*.95):raise ValueError('Nonmonotonic raw current')
    targets=[-.2+.02*i for i in range(51)]
    chosen=[]
    for target in targets:
        matches=[n for n,(_,row) in enumerate(rows) if abs(row[0]-target)<1e-6]
        if len(matches)!=1:raise ValueError('Missing/duplicate target Vg %.9g'%target)
        chosen.append(matches[0])
    if abs(rows[0][1][0]-(.8 if reverse else -.2))>1e-6 or abs(rows[-1][1][0]-(-.2 if reverse else .8))>1e-6:raise ValueError('Native endpoints incorrect')
    (out/('idvg_'+bias+'.log')).write_text('\n'.join(headers+[rows[n][0] for n in chosen])+'\n')
    for terminal,values in curves.items():
        (out/(bias+'_'+terminal+'.dat')).write_text(''.join('%.16g %.16g\n'%values[n] for n in chosen))
    return dict(native_points=len(rows),target_points=51,adaptive_gate_V=[row[0] for n,(_,row) in enumerate(rows) if n not in chosen],all_raw_points_checked=True,interpolation_used=False,raw_file_unchanged=True)

def validate_folder(folder,compare=None,mode=None):
    attempt=selected(Path(folder));execution=attempt/'gaa/execution'
    process=json.loads((attempt/'gaa/process.json').read_text())
    if process['returncode']!=0 or process['timeout'] or process['missing']:raise ValueError('Execution/output failure')
    if not re.search(r'ATLAS version[^\n]*finished',(execution/'solver.out').read_text(errors='replace'),re.I):raise ValueError('No normal ATLAS finish')
    if any('transport error: no error' not in s.lower() for s in process.get('fatal_lines',[])):raise ValueError('Fatal solver error')
    checks={};results={};curves={}
    for direction,rev in [('forward',False),('reverse',True)]:
        target=attempt/('canonical_'+direction);target.mkdir(exist_ok=False)
        checks[direction]={bias:canonical_curve(execution,target,bias,rev) for bias in ['low','high']}
        results[direction],curves[direction]=analyze.analyze(target,.04)
        if not results[direction]['engineering_targets']['kcl'] or not results[direction]['engineering_targets']['monotonic']:raise ValueError('Target current integrity')
    differences={}
    for bias in ['low','high']:
        for (_,a),(_,b) in zip(curves['forward'][bias]['drain'],curves['reverse'][bias]['drain']):
            if abs(a-b)>max(1e-14,max(abs(a),abs(b))*.05):raise ValueError('Forward/reverse current mismatch')
        differences[bias]={}
        for key,limit in [('Vth_V',.01),('SS_mV_dec',5)]:
            a=results['forward']['metrics'][bias][key];b=results['reverse']['metrics'][bias][key]
            if a is None or b is None or abs(a-b)>limit:raise ValueError('Forward/reverse metric missing/mismatch')
            differences[bias][key]=abs(a-b)
    result=results['forward'];result.update(acquisition_revision='explicit_bias_v1',acquisition_checks=checks,reverse_metrics=results['reverse'],direction_checks=differences,physical_validation='NOT_VALIDATED',simulator_log_review='PROCESS_AND_NORMAL_FINISH_CHECKED')
    if compare:
        reference=json.loads((selected(Path(compare))/'validated_metrics.json').read_text())
        result['mesh_comparison']=mesh_comparison(reference,result)
        result['reverse_mesh_comparison']=mesh_comparison(reference['reverse_metrics'],result['reverse_metrics'])
        result['mesh_validation']='PASS' if all(result[k]['status']=='PASS' for k in ['mesh_comparison','reverse_mesh_comparison']) else 'FAIL'
        if mode!='fine':result['mesh_validation']='DIAGNOSTIC_COMPARISON'
    (attempt/'validated_metrics.json').write_text(json.dumps(result,indent=2))
    return result

def main():
    p=argparse.ArgumentParser();p.add_argument('folder',type=Path);p.add_argument('--compare',type=Path);p.add_argument('--mode');a=p.parse_args()
    try:validate_folder(a.folder,a.compare,a.mode)
    except Exception as exc:
        (selected(a.folder)/'validation_failure.json').write_text(json.dumps(dict(error=str(exc),physical_validation='NOT_VALIDATED'),indent=2));raise

if __name__=='__main__':main()

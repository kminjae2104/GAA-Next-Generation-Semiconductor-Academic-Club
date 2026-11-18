"""Strict validation of real forward/reverse native logs, with immutable raw files."""
from pathlib import Path
import argparse,json,math,re
import analyze
from validate_case import selected,mesh_comparison

def canonical(execution,out):
    out.mkdir(exist_ok=False)
    for bias in ['low','high']:
        p=execution/('idvg_'+bias+'_rev.log')
        lines=p.read_text().splitlines();rows=[line for line in lines if line.startswith('d ')]
        grids=[float(line.split()[1]) for line in rows]
        if len(grids)!=51 or any(abs(v-(.8-.02*i))>1e-6 for i,v in enumerate(grids)):
            raise ValueError('Reverse sweep missing/incorrect native points')
        headers=[line for line in lines if not line.startswith('d ')]
        (out/('idvg_'+bias+'.log')).write_text('\n'.join(headers+list(reversed(rows)))+'\n')
        for terminal in ['drain','source','gate']:
            values=[]
            for line in (execution/(bias+'_rev_'+terminal+'.dat')).read_text().splitlines():
                try:a,b=map(float,line.split())
                except ValueError:
                    if values:raise ValueError('Malformed reverse export')
                    continue
                if not all(math.isfinite(x) for x in [a,b]):raise ValueError('Nonfinite reverse data')
                values.append((a,b))
            if len(values)!=51 or any(abs(a-g)>1e-7 for (a,b),g in zip(values,grids)):
                raise ValueError('Reverse export grid mismatch')
            (out/(bias+'_'+terminal+'.dat')).write_text(''.join('%.16g %.16g\n'%v for v in reversed(values)))

def main():
    p=argparse.ArgumentParser();p.add_argument('folder',type=Path);p.add_argument('--mode');p.add_argument('--compare',type=Path);a=p.parse_args()
    attempt=selected(a.folder);exe=attempt/'gaa/execution';process=json.loads((attempt/'gaa/process.json').read_text())
    if process['returncode'] or process['timeout'] or process['missing']:raise ValueError('Process/output failure')
    if not re.search(r'ATLAS version[^\n]*finished',(exe/'solver.out').read_text(errors='replace')):raise ValueError('No normal finish')
    if any('transport error: no error' not in s.lower() for s in process['fatal_lines']):raise ValueError('Fatal solver error')
    canonical(exe,attempt/'canonical_reverse')
    forward,raw=analyze.analyze(exe,.04);reverse,rev=analyze.analyze(attempt/'canonical_reverse',.04)
    differences={}
    for bias in ['low','high']:
        for result in [forward,reverse]:
            if not result['metrics'][bias]['kcl_pass'] or result['metrics'][bias]['nonmonotonic_indices']:raise ValueError('Current integrity')
        for (v,x),(w,y) in zip(raw[bias]['drain'],rev[bias]['drain']):
            if abs(x-y)>max(1e-14,max(abs(x),abs(y))*.05):raise ValueError('Forward/reverse current mismatch')
        differences[bias]={}
        for key,limit in [('Vth_V',.01),('SS_mV_dec',5)]:
            x=forward['metrics'][bias][key];y=reverse['metrics'][bias][key]
            if x is None or y is None or abs(x-y)>limit:raise ValueError('Forward/reverse metric missing or mismatch')
            differences[bias][key]=abs(x-y)
    forward['reverse_metrics']=reverse;forward['direction_checks']=differences
    forward['physical_validation']='NOT_VALIDATED';forward['simulator_log_review']='PROCESS_AND_NORMAL_FINISH_CHECKED'
    if a.compare:
        forward['mesh_comparison']=mesh_comparison(json.loads((selected(a.compare)/'validated_metrics.json').read_text()),forward)
        forward['mesh_validation']=forward['mesh_comparison']['status'] if a.mode=='fine' else 'DIAGNOSTIC_COMPARISON'
    (attempt/'validated_metrics.json').write_text(json.dumps(forward,indent=2))
    return 0

if __name__=='__main__':raise SystemExit(main())

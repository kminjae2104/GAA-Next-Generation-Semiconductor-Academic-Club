"""Postcondition used before a dependent TCAD deck may start."""
import argparse
import json
from pathlib import Path
import re
import analyze


def selected(folder):
    selection=folder/'selected_attempt.json'
    if not selection.is_file():return folder
    child=(folder/json.loads(selection.read_text())['directory']).resolve();child.relative_to(folder.resolve());return child


def mesh_comparison(reference,current):
    comparisons={}
    for bias in ['low','high']:
        a=reference['metrics'][bias];b=current['metrics'][bias]
        for metric,tolerance,relative in [('Ion_A',.05,True),('Ioff_A',.20,True),('Vth_V',.01,False),('SS_mV_dec',5,False)]:
            av,bv=a[metric],b[metric];key=bias+'_'+metric
            if av is None or bv is None or metric=='Ioff_A' and min(abs(av),abs(bv))<=1e-18:
                comparisons[key]=dict(status='UNRESOLVED',passed=None);continue
            difference=abs(bv-av)/(abs(av) or 1e-300) if relative else abs(bv-av)
            comparisons[key]=dict(difference=difference,tolerance=tolerance,relative=relative,passed=difference<=tolerance)
    passed=[v['passed'] for v in comparisons.values()]
    return dict(checks=comparisons,status='PASS' if all(v is True for v in passed) else 'INCOMPLETE' if any(v is None for v in passed) else 'FAIL')


def main():
    p=argparse.ArgumentParser();p.add_argument('folder',type=Path);p.add_argument('--mode',choices=['smoke','full','fine'],required=True)
    p.add_argument('--compare',type=Path);a=p.parse_args();a.folder=selected(a.folder)
    stage=json.loads((a.folder/'gaa'/'process.json').read_text());execution=a.folder/'gaa'/'execution'
    if stage['returncode']!=0 or stage['timeout'] or stage['missing']:raise ValueError('Execution/outputs failed')
    text=(execution/'solver.out').read_text(errors='replace')
    if not re.search(r'ATLAS version[^\n]*finished',text,re.I):raise ValueError('No normal ATLAS finish marker')
    if any('transport error: no error' not in s.lower() for s in stage.get('fatal_lines',[])):raise ValueError('Fatal solver error')
    if a.mode=='smoke':
        curves={t:analyze.read_curve(execution/('low_'+t+'.dat'),min_points=5) for t in ['drain','source','gate']}
        checks=analyze.validate_native_log(execution/'idvg_low.log',.05,curves)
        for row in zip(*(curves[t] for t in ['drain','source','gate'])):
            currents=[v[1] for v in row]
            if abs(sum(currents))>max(1e-14,max(map(abs,currents))*.001):raise ValueError('KCL failed')
        drain=curves['drain'];currents=[abs(v[1]) for v in drain]
        if len(drain)!=5 or any(abs(v[0]-(-.2+.1*i))>1e-8 for i,v in enumerate(drain)):raise ValueError('Unexpected smoke bias grid')
        if any(b<a*.95 for a,b in zip(currents,currents[1:])):raise ValueError('Nonmonotonic smoke curve')
        result=dict(numerical_checks=checks,physical_validation='NOT_VALIDATED')
    else:
        result,_=analyze.analyze(execution,.04)
        if not result['engineering_targets']['kcl'] or not result['engineering_targets']['monotonic']:raise ValueError('Current integrity failed')
        if a.compare:
            previous=json.loads((selected(a.compare)/'validated_metrics.json').read_text())
            result['mesh_comparison']=mesh_comparison(previous,result)
            result['mesh_validation']=result['mesh_comparison']['status'] if a.mode=='fine' else 'DIAGNOSTIC_COMPARISON'
    (a.folder/'validated_metrics.json').write_text(json.dumps(result,indent=2))
    # Device goals/calibration remain explicit; passing this gate means numerical validity.
    return 0


if __name__=='__main__':raise SystemExit(main())

"""Postcondition used before a dependent TCAD deck may start."""
import argparse
import json
from pathlib import Path
import re
import analyze


def main():
    p=argparse.ArgumentParser();p.add_argument('folder',type=Path);p.add_argument('--mode',choices=['smoke','full','fine'],required=True);a=p.parse_args()
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
        result=dict(numerical_checks=checks,physical_validation='NOT_VALIDATED')
    else:
        result,_=analyze.analyze(execution,.04)
        if not result['engineering_targets']['kcl'] or not result['engineering_targets']['monotonic']:raise ValueError('Current integrity failed')
    (a.folder/'validated_metrics.json').write_text(json.dumps(result,indent=2))
    # Device goals/calibration remain explicit; passing this gate means numerical validity.
    return 0


if __name__=='__main__':raise SystemExit(main())

"""Read-only snapshot of this user's detached GAA workflow."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import time


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--max-seconds');a=p.parse_args()
    job=json.loads(Path(__file__).with_name('target.json').read_text())['job']
    if not re.fullmatch(r'gaa_overnight_[A-Za-z0-9_-]+',job):raise ValueError('Invalid workflow ID')
    root=Path.home()/'gaa_tcad_runs'/job/'durable'
    launch=json.loads((root/'launch.json').read_text());pid=launch['scheduler_pid']
    try:os.kill(pid,0);alive=True
    except ProcessLookupError:alive=False
    states=json.loads((root/'results/progress.json').read_text())['tasks']
    report=dict(job=job,snapshot_epoch=time.time(),scheduler_pid=pid,scheduler_alive=alive,states=states,
        calculation_time_limit_seconds=None,physical_validation='NOT_VALIDATED')
    for name,state in states.items():
        if state['status']=='PENDING':continue
        case=root/'results'/name;selection=case/'selected_attempt.json'
        if not selection.is_file():continue
        attempt=(case/json.loads(selection.read_text())['directory']).resolve();attempt.relative_to(case.resolve())
        dest=a.output/'cases'/name;dest.mkdir(parents=True)
        for filename in ['status.json','progress.json','run_config.json','retained_structures.json','validated_metrics.json']:
            source=attempt/filename
            if source.is_file():shutil.copy2(source,dest/filename)
        solver=attempt/'gaa/execution/solver.out'
        if solver.is_file():
            with solver.open('rb') as f:f.seek(max(0,solver.stat().st_size-8192));(dest/'solver_tail.txt').write_bytes(f.read())
        execution=attempt/'gaa/execution'
        if state['status']=='SUCCEEDED':
            for source in execution.iterdir():
                if source.suffix in ['.dat','.log'] and source.is_file() and source.stat().st_size<=1024*1024:
                    shutil.copy2(source,dest/source.name)
        process=attempt/'gaa/process.json'
        if process.is_file():shutil.copy2(process,dest/'process.json')
    (a.output/'snapshot.json').write_text(json.dumps(report,indent=2))
    (a.output/'status.json').write_text(json.dumps(dict(status='READ_ONLY_SNAPSHOT',stages=[],physical_validation='NOT_VALIDATED')))
    return 0


if __name__=='__main__':raise SystemExit(main())

"""Agent entry point: detach a finite TCAD workflow without a calculation deadline."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
    p.add_argument('--max-seconds',type=int);a=p.parse_args()
    code=Path(__file__).resolve().parent;root=a.output.resolve().parent/'durable'
    root.mkdir(exist_ok=False);out=root/'results';out.mkdir()
    if os.name=='posix':signal.signal(signal.SIGHUP,signal.SIG_IGN)
    plan=json.loads((code/'workflow.json').read_text())
    command=[sys.executable,str(code/'dag_scheduler.py'),'--plan',str(code/'workflow.json'),'--output',str(out)]
    with (root/'scheduler_console.txt').open('xb') as log:
        proc=subprocess.Popen(command,cwd=str(code),stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    info=dict(scheduler_pid=proc.pid,remote_directory=str(root),results_directory=str(out),
        command=command,tasks=len(plan['tasks']),max_parallel=plan['max_parallel'],
        calculation_time_limit_seconds=None,detached_session=True,launch_epoch=time.time(),
        workflow_sha256=hashlib.sha256((code/'workflow.json').read_bytes()).hexdigest(),
        disk_free_bytes=shutil.disk_usage(root).free,physical_validation='NOT_VALIDATED')
    # Observe startup only; never wait for a simulation to finish.
    for _ in range(20):
        if proc.poll() is not None:break
        progress=out/'progress.json'
        if progress.is_file():
            state=json.loads(progress.read_text())
            if any(v.get('worker_pid') for v in state['tasks'].values()):break
        time.sleep(.25)
    info['alive_at_handoff']=proc.poll() is None
    if info['alive_at_handoff'] and os.name=='posix':
        info['scheduler_session_id']=os.getsid(proc.pid)
        info['launcher_session_id']=os.getsid(0)
        info['separate_session_verified']=info['scheduler_session_id']==proc.pid and os.getsid(0)!=proc.pid
    info['initial_progress']=json.loads((out/'progress.json').read_text()) if (out/'progress.json').is_file() else None
    (root/'launch.json').write_text(json.dumps(info,indent=2))
    (a.output/'launch.json').write_text(json.dumps(info,indent=2))
    (a.output/'status.json').write_text(json.dumps(dict(status='DETACHED_WORKFLOW_STARTED' if info['alive_at_handoff'] else 'LAUNCH_FAILED',
        stages=[],remote_directory=str(root),physical_validation='NOT_VALIDATED')))
    return 0 if info['alive_at_handoff'] else 5


if __name__=='__main__':raise SystemExit(main())

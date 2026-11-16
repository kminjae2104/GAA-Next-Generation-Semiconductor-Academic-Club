"""Headless preflight supervisor; remote registration is never done through UI."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import time

import control
import relay


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--runtime',type=Path,required=True)
    p.add_argument('--job',required=True)
    a=p.parse_args()
    runtime=a.runtime.resolve()
    if not relay.JOB.fullmatch(a.job):raise ValueError('Invalid job')
    state_path=runtime/'supervisor.json'
    def report(status,**extra):
        relay.write_json(state_path,dict(status=status,time_utc=datetime.now(timezone.utc).isoformat(),
                                       ui_input_used=False,**extra))
    report('WAITING_FOR_AGENT',next_action='Authenticated agent registration once in the existing Linux session')
    while True:
        state=control.state(runtime)
        if state['session_status'] in ['STOPPED','EXPIRED'] or state['startup_error']:
            report('SESSION_CLOSED_BEFORE_AGENT',simulator_execution='NOT_RUN');return 2
        if state['live_agent']:break
        time.sleep(5)
    queued=runtime/'queue.json'
    if queued.exists():
        existing=json.loads(queued.read_text())['job']
        if existing!=a.job:raise RuntimeError('An unrelated package is already queued')
    else:
        cmd=[sys.executable,str(Path(__file__).with_name('control.py')),'--runtime',str(runtime),
             'queue','--job',a.job,'--mode','preflight']
        subprocess.run(cmd,check=True,stdout=subprocess.DEVNULL)
    report('PREFLIGHT_QUEUED',job=a.job)
    receipt=runtime/'results'/(a.job+'.receipt.json')
    while not receipt.is_file():
        state=control.state(runtime)
        if state['session_status'] in ['STOPPED','EXPIRED']:
            report('SESSION_CLOSED_WITH_REMOTE_STATE_UNVERIFIED',job=a.job);return 3
        time.sleep(5)
    record=json.loads(receipt.read_text())
    destination=control.LOCAL/'collected'/a.job
    if destination.exists():raise FileExistsError('Refuse overwriting previous collection')
    verified=control.collect_archive(runtime/'results'/(a.job+'.zip'),record,destination)
    environment=json.loads((destination/'environment.json').read_text()) if (destination/'environment.json').exists() else {}
    report('PREFLIGHT_COLLECTED_AWAITING_TOOLCHAIN_REVIEW',job=a.job,collection=str(destination),
           transport_verified=verified['transport_verified'],deckbuild_executable=environment.get('executable'),
           simulator_execution='NOT_RUN',next_action='Codex reviews installed toolchain, then queues smoke/full/fine via controller API')
    return 0


if __name__=='__main__':raise SystemExit(main())

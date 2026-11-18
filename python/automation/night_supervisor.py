"""Finite one-slot numerical recovery; independent of relay and model sessions."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from dag_scheduler import run_plan


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    a.output.mkdir(exist_ok=False)
    code=Path(__file__).resolve().parent
    old=Path.home()/'gaa_tcad_runs/gaa_overnight_20261116T080149Z/durable/results'
    # One recovery slot; wait until the original plan has at most two active tasks.
    while True:
        states=json.loads((old/'progress.json').read_text())['tasks']
        if sum(s['status']=='RUNNING' for s in states.values())<=2:break
        time.sleep(60)
    plan=json.loads((code/'workflow.json').read_text())
    for task in plan['tasks']:
        reference=old/(task['id'].split('_fine_')[0]+'_full')
        task['checks'][0] += ['--compare', str(reference)]
    (a.output/'launch.json').write_text(json.dumps(dict(pid=os.getpid(),started=time.time(),
        plan=plan,original_root=str(old),transport_required=False,model_calls=0)))
    run_plan(plan,code,a.output/'results')
    (a.output/'complete.json').write_text(json.dumps(dict(finished=time.time(),
        status='FINITE_PLAN_FINISHED_REVIEW_REQUIRED',physical_validation='NOT_VALIDATED')))


if __name__=='__main__':main()

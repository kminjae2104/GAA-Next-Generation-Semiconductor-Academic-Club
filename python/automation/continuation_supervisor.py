"""Reserve at most two new slots after checking both existing GAA plans."""
from pathlib import Path
import argparse,json,time
from dag_scheduler import run_plan
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
base=Path(__file__).resolve().parent
old=['gaa_overnight_20261116T080149Z','gaa_autonomous_20261117T064609Z']
while True:
    active=0
    for job in old:
        f=Path.home()/'gaa_tcad_runs'/job/'durable/results/progress.json'
        if f.exists():active+=sum(v['status']=='RUNNING' for v in json.loads(f.read_text())['tasks'].values())
    if active<=1:break
    time.sleep(30)
run_plan(json.loads((base/'workflow.json').read_text()),base,a.output)

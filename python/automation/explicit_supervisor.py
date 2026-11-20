"""Unlimited three-slot DAG; write final completion and preserve failures for review."""
import argparse,json,time
from pathlib import Path
from dag_scheduler import run_plan

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    code=Path(__file__).resolve().parent
    states=run_plan(json.loads((code/'workflow.json').read_text()),code,a.output)
    (a.output.parent/'complete.json').write_text(json.dumps(dict(finished=time.time(),status='PLAN_FINISHED_REVIEW_REQUIRED',all_numerically_succeeded=all(v['status']=='SUCCEEDED' for v in states.values()),physical_validation='NOT_VALIDATED'),indent=2))

if __name__=='__main__':main()

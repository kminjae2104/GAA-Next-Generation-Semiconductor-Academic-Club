"""Collect one already queued snapshot and audit it, without resubmission."""
import argparse,json,subprocess,sys,time
from pathlib import Path
import control,relay

def main():
    p=argparse.ArgumentParser();p.add_argument('--job',required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    if not relay.JOB.fullmatch(a.job):raise ValueError('Invalid job')
    runtime=control.current(None);receipt=runtime/'results'/(a.job+'.receipt.json')
    while not receipt.exists():
        if (runtime/'session_stopped.json').exists():raise RuntimeError('Transport stopped; snapshot not returned')
        time.sleep(2)
    destination=control.LOCAL/'collected'/a.job
    if not (destination/'collection_verified.json').exists():control.collect_archive(runtime/'results'/(a.job+'.zip'),json.loads(receipt.read_text()),destination)
    if not a.out.exists():subprocess.run([sys.executable,str(Path(__file__).with_name('audit_results.py')),str(destination),'--out',str(a.out)],check=True)
    print(json.dumps(dict(collected=str(destination),audit=str(a.out))))

if __name__=='__main__':main()

"""Launch detached, unlimited solver DAG; relay job only returns launch evidence."""
from pathlib import Path
import argparse,json,subprocess,sys,os,time
def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--max-seconds');a=p.parse_args()
    code=Path(__file__).resolve().parent;out=a.output.parent/'durable';out.mkdir(exist_ok=False)
    with (out/'scheduler.console').open('xb') as log:
        proc=subprocess.Popen([sys.executable,str(code/'continuation_supervisor.py'),'--output',str(out/'results')],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    time.sleep(1)
    launch={'scheduler_pid':proc.pid,'scheduler_alive':proc.poll() is None,'scheduler_session':os.getsid(proc.pid) if proc.poll() is None else None,'started':time.time(),'time_limit_seconds':None,'max_new_parallel':2,'transport_required':False}
    (out/'launch.json').write_text(json.dumps(launch,indent=2));(a.output/'launch.json').write_text(json.dumps(launch,indent=2))
    (a.output/'status.json').write_text(json.dumps({'status':'DETACHED_LAUNCH','stages':[]}))
    return 0 if launch['scheduler_alive'] else 5
if __name__=='__main__':raise SystemExit(main())

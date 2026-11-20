"""Launch only a detached prospective GAA workflow, after scoped precondition checks."""
import argparse,json,os,subprocess,sys,time
from pathlib import Path

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--max-seconds');a=p.parse_args()
    code=Path(__file__).resolve().parent
    base=Path.home()/'gaa_tcad_runs';prior=json.loads((code/'preconditions.json').read_text())['previous_jobs']
    for job in prior:
        root=base/job
        progress=root/'durable/results/progress.json'
        if not progress.exists():raise ValueError('Missing previous GAA state: '+job)
        if any(v['status'] in ['RUNNING','PENDING'] for v in json.loads(progress.read_text())['tasks'].values()):raise ValueError('Existing GAA work active; no new jobs started')
        for proc in Path('/proc').iterdir():
            if not proc.name.isdigit():continue
            try:
                if proc.stat().st_uid!=os.getuid():continue
                (proc/'cwd').resolve(strict=True).relative_to(root.resolve())
            except (OSError,ValueError):continue
            raise ValueError('Existing GAA process remains: '+job)
    out=a.output.parent/'durable';out.mkdir(exist_ok=False)
    with (out/'scheduler.console').open('xb') as log:
        proc=subprocess.Popen([sys.executable,str(code/'explicit_supervisor.py'),'--output',str(out/'results')],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    time.sleep(1)
    launch=dict(scheduler_pid=proc.pid,scheduler_alive=proc.poll() is None,scheduler_session=os.getsid(proc.pid) if proc.poll() is None else None,started=time.time(),time_limit_seconds=None,max_new_parallel=3,transport_required=False,previous_jobs_checked=prior)
    for target in [out,a.output]:(target/'launch.json').write_text(json.dumps(launch,indent=2))
    (a.output/'status.json').write_text(json.dumps(dict(status='DETACHED_LAUNCH',stages=[])))
    if launch['scheduler_alive']:
        subprocess.run([sys.executable,str(code/'presentation_remote_snapshot.py'),'--output',str(a.output)],check=True)
    return 0 if launch['scheduler_alive'] else 5

if __name__=='__main__':raise SystemExit(main())

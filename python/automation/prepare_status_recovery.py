"""Queue only a read-only three-workflow snapshot and resume background collection."""
from datetime import datetime,timezone
import json,os,subprocess,sys,zipfile
from pathlib import Path
import control,relay

ROOT=Path(__file__).resolve().parents[2]

def main():
    runtime=control.current(None)
    session=json.loads((runtime/'session.json').read_text())
    if session.get('deadline_utc') is not None: raise ValueError('Expected unlimited session')
    if (runtime/'session_stopped.json').exists(): raise ValueError('Session stopped')
    job='gaa_status_recovery_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    folder=ROOT/'.local/packages'/job;folder.mkdir(parents=True,exist_ok=False)
    with zipfile.ZipFile(folder/'package.zip','x',zipfile.ZIP_DEFLATED) as z:
        z.write(ROOT/'python/presentation_remote_snapshot.py','run_study.py')
        z.write(ROOT/'.local/continuation_targets.json','targets.json')
    relay.publish(runtime,folder/'package.zip',job)
    relay.write_json(ROOT/'.local/reconnect_runtime.json',dict(runtime=str(runtime),ui_input_allowed=False))
    with (runtime/'presentation_guard.console').open('xb') as stream:
        p=subprocess.Popen([sys.executable,str(ROOT/'python/presentation_connection_guard.py')],stdin=subprocess.DEVNULL,stdout=stream,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    relay.write_json(ROOT/'.local/presentation_guard_pid.json',dict(pid=p.pid,script='python/presentation_connection_guard.py',runtime=str(runtime)))
    relay.write_json(ROOT/'.local/status_recovery_pending.json',dict(job=job,runtime=str(runtime),guard_pid=p.pid,deadline_utc=None,simulators_started=0,registration_required=not control.state(runtime)['live_agent']))
    print(json.dumps(dict(job=job,guard_pid=p.pid,deadline_utc=None,simulators_started=0)))

if __name__=='__main__':main()

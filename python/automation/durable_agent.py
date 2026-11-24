"""Private persistent Linux agent supervisor; no credentials in argv or stdout."""
import argparse,json,os,signal,subprocess,sys,time
from pathlib import Path

def save_config(path,config):
    path=Path(path);path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    os.chmod(path.parent,0o700)
    fd=os.open(str(path),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as f:json.dump(config,f)

def supervise(config_path,legacy_pid=None):
    import fcntl
    root=Path(config_path).parent
    if (root/'stop.request').exists():return 0
    (root/'watchdog_tick.json').write_text(json.dumps(dict(pid=os.getpid(),checked=time.time())))
    with (root/'supervisor.lock').open('a') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:return 0
        if legacy_pid:
            time.sleep(30) # Allow the installing agent to return its receipt first.
            command=Path('/proc')/str(legacy_pid)/'cmdline'
            if command.exists():
                value=command.read_bytes().decode(errors='replace')
                if '/.cache/gaa_tcad_agent/agent_' in value and '--stdin-config' in value:os.kill(legacy_pid,signal.SIGTERM)
        child=None
        def stop(*args):
            if child and child.poll() is None:child.terminate()
            raise SystemExit(0)
        signal.signal(signal.SIGTERM,stop)
        while True:
            with (root/'agent.console').open('ab') as log:
                child=subprocess.Popen([sys.executable,str(root/'agent.py'),'--config',str(config_path)],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT)
                (root/'supervisor_status.json').write_text(json.dumps(dict(supervisor_pid=os.getpid(),agent_pid=child.pid,started=time.time(),deadline_utc=None)))
                rc=child.wait()
            if rc==0:
                (root/'stop.request').write_text('Explicit agent stop respected.\n')
                return 0
            time.sleep(10)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--config',type=Path,required=True);p.add_argument('--legacy-pid',type=int);a=p.parse_args()
    raise SystemExit(supervise(a.config,a.legacy_pid))

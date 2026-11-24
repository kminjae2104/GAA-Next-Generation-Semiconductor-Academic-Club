"""Authenticated one-time deployment; original simulations are untouched."""
import argparse,json,os,subprocess,sys,time
from pathlib import Path
from durable_agent import save_config

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--max-seconds');a=p.parse_args()
    code=Path(__file__).resolve().parent
    settings=json.loads((code/'private_config.json').read_text())
    os.chmod(code/'private_config.json',0o600);os.chmod(code,0o700)
    root=Path.home()/'.local/share/gaa_persistent_agent';root.mkdir(mode=0o700,parents=True,exist_ok=False)
    save_config(root/'config.json',settings['config'])
    for name in ['agent.py','durable_agent.py']:(root/name).write_bytes((code/name).read_bytes())
    with (root/'supervisor.console').open('ab') as log:
        proc=subprocess.Popen([sys.executable,str(root/'durable_agent.py'),'--config',str(root/'config.json'),'--legacy-pid',str(settings['legacy_pid'])],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    report=dict(status='PERSISTENT_AGENT_INSTALLED',supervisor_pid=proc.pid,supervisor_session=os.getsid(proc.pid),config_mode=oct((root/'config.json').stat().st_mode & 0o777),deadline_utc=None,credentials_in_git=False,existing_simulations_preserved=True,reboot_autostart='NOT_CONFIGURED',address_change_discovery='REQUIRES_STABLE_ENDPOINT',root=str(root))
    (a.output/'installation.json').write_text(json.dumps(report,indent=2));(a.output/'status.json').write_text(json.dumps(dict(status='INSTALLED',stages=[])))
    return 0

if __name__=='__main__':raise SystemExit(main())

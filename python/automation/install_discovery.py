"""Install authenticated discovery through the existing private agent channel."""
import argparse,json,os,subprocess,sys
from pathlib import Path
import rendezvous_client
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--max-seconds');a=p.parse_args()
root=Path.home()/'.local/share/gaa_persistent_agent';code=Path(__file__).resolve().parent
private=code/'private_discovery.json';os.chmod(private,0o600);settings=json.loads(private.read_text())
known=root/'github_known_hosts';known.write_text(settings['known_hosts']);os.chmod(known,0o600)
config=json.loads((root/'config.json').read_text());config['discovery']=settings['discovery'];config['discovery']['root']=str(root)
rendezvous_client.refresh(config,True) # Real private Git fetch and signature verification before activation.
for name in ['agent.py','rendezvous_client.py']:(root/name).write_bytes((code/name).read_bytes())
status=json.loads((root/'supervisor_status.json').read_text())
with (root/'discovery_upgrade.console').open('ab') as log:
    subprocess.Popen([sys.executable,str(code/'agent_restart_probe.py'),str(a.output.parent)],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
(a.output/'discovery_installed.json').write_text(json.dumps(dict(private_git_fetch_verified=True,signature_verified=True,branch=config['discovery']['branch'],read_only=True,old_agent_pid=status['agent_pid'],deadline_utc=None)))
(a.output/'status.json').write_text(json.dumps(dict(status='DISCOVERY_INSTALLED',stages=[])))

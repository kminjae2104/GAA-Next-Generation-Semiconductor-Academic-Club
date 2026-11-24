"""Prepare an owner-only read-only GitHub deploy key; export only its public half."""
import argparse,json,os,shutil,socket,subprocess
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--max-seconds');a=p.parse_args()
root=Path.home()/'.local/share/gaa_persistent_agent';key=root/'discovery_key'
for tool in ['git','ssh','ssh-keygen']:
    if not shutil.which(tool):raise RuntimeError('Missing '+tool)
with socket.create_connection(('ssh.github.com',443),timeout=15):pass
if not key.exists():subprocess.run(['ssh-keygen','-q','-t','ed25519','-N','','-f',str(key),'-C','gaa-readonly-discovery'],check=True,capture_output=True)
os.chmod(key,0o600)
(a.output/'discovery_public_key.json').write_text(json.dumps(dict(public_key=key.with_suffix('.pub').read_text().strip(),github_443_reachable=True,key_mode=oct(key.stat().st_mode & 0o777))))
(a.output/'status.json').write_text(json.dumps(dict(status='DISCOVERY_PREFLIGHT',stages=[])))

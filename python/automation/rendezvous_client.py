"""Fetch signed endpoint data with a repository-scoped read-only deploy key."""
import hashlib,hmac,json,os,re,shlex,subprocess,time
from pathlib import Path
_last=0

def verify(value,key,minimum=0):
    payload=value['payload'];raw=json.dumps(payload,sort_keys=True,separators=(',',':')).encode()
    if not hmac.compare_digest(value['signature'],hmac.new(bytes.fromhex(key),raw,hashlib.sha256).hexdigest()):raise ValueError('Discovery signature mismatch')
    if payload.get('protocol')!='gaa-discovery-v1' or not re.fullmatch(r'https://[a-z0-9-]+\.trycloudflare\.com',payload['base_url']):raise ValueError('Invalid discovered endpoint')
    if not isinstance(payload['sequence'],int) or payload['sequence']<minimum:raise ValueError('Discovery replay rejected')
    return payload

def refresh(config,force=False):
    global _last
    d=config.get('discovery')
    if not d:return False
    if not force and time.monotonic()-_last<60:return False
    _last=time.monotonic();root=Path(d['root']);cache=root/'discovery.git'
    if not cache.exists():subprocess.run(['git','init','--bare',str(cache)],check=True,capture_output=True)
    command=['ssh','-i',str(root/'discovery_key'),'-p','443','-o','BatchMode=yes','-o','IdentitiesOnly=yes','-o','StrictHostKeyChecking=yes','-o','UserKnownHostsFile='+str(root/'github_known_hosts'),'-o','ConnectTimeout=15']
    wrapper=root/'git_ssh.sh';wrapper.write_text('#!/bin/sh\nexec '+' '.join(shlex.quote(s) for s in command)+' "$@"\n');os.chmod(wrapper,0o700)
    env=dict(os.environ,GIT_SSH=str(wrapper),GIT_SSH_COMMAND=' '.join(shlex.quote(s) for s in command),GIT_TERMINAL_PROMPT='0')
    fetched=subprocess.run(['git','--git-dir',str(cache),'fetch','--depth=1',d['repository'],'refs/heads/'+d['branch']],env=env,capture_output=True,timeout=40)
    if fetched.returncode:raise RuntimeError('Read-only discovery fetch failed: '+fetched.stderr.decode(errors='replace')[-1200:])
    result=subprocess.run(['git','--git-dir',str(cache),'show','FETCH_HEAD:endpoint.json'],check=True,capture_output=True,timeout=10)
    payload=verify(json.loads(result.stdout),d['mac_key'],d.get('sequence',0))
    changed=config['base_url']!=payload['base_url'];config['base_url']=payload['base_url'];d['sequence']=payload['sequence']
    path=root/'config.json';temp=root/'config.discovery.tmp'
    fd=os.open(str(temp),os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
    with os.fdopen(fd,'w') as f:json.dump(config,f)
    os.chmod(temp,0o600);temp.replace(path)
    (root/'discovery_status.json').write_text(json.dumps(dict(checked=time.time(),sequence=payload['sequence'],base_url=payload['base_url'],endpoint_changed=changed)))
    return changed

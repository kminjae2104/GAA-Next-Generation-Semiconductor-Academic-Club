"""Own a temporary relay/tunnel pair with an explicitly selected lifetime."""
import argparse
import base64
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import ssl
import subprocess
import sys
import time
import urllib.request

import relay

EXPECTED_CF_SHA='2493dbc168923bb3e59e5e7716f71deced92992eea9acd6e9d74f84ac7751343'


def bootstrap_command(url,agent_sha,ca_pem=None,deadline=None):
    ca_b64=base64.b64encode(ca_pem.encode('ascii')).decode('ascii') if ca_pem else ''
    code=('import getpass,urllib.request,hashlib,pathlib,subprocess,sys,json,os,ssl,base64; '
          'u="'+url+'"; t=getpass.getpass("Task token (hidden): "); '
          'ca=base64.b64decode("'+ca_b64+'").decode("ascii") or None; '
          'ctx=ssl.create_default_context(cadata=ca); '
          'r=urllib.request.Request(u+"/agent",headers={"Authorization":"Bearer "+t}); '
          's=urllib.request.urlopen(r,timeout=60,context=ctx).read(); '
          'assert hashlib.sha256(s).hexdigest()=="'+agent_sha+'","Agent hash mismatch"; '
          'd=pathlib.Path.home()/".cache"/"gaa_tcad_agent"; d.mkdir(mode=448,parents=True,exist_ok=True); '
          'f=d/"agent_'+agent_sha[:12]+'.py"; f.write_bytes(s); '
          'log=d/"agent_'+agent_sha[:12]+'.console"; '
          'lf=log.open("ab"); '
          'p=subprocess.Popen([sys.executable,str(f),"--stdin-config"],stdin=subprocess.PIPE,stdout=lf,stderr=subprocess.STDOUT,start_new_session=True); lf.close(); '
          'p.stdin.write(json.dumps({"base_url":u,"token":t,"ca_pem":ca,"max_session_seconds":'+('86400' if deadline else 'None')+',"deadline_utc":'+(json.dumps(deadline) if deadline else 'None')+'}).encode()); p.stdin.close(); '
          'print("AGENT_STARTED",p.pid,"LOG",log)')
    return "python3 -c '"+code+"'"


def stop(proc):
    if proc is not None and proc.poll() is None:
        proc.terminate()
        try:proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill();proc.wait()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,required=True)
    p.add_argument('--cloudflared',type=Path,required=True)
    p.add_argument('--seconds',type=int,default=0,help='0: no scheduled expiry')
    p.add_argument('--ca-pem',type=Path)
    a=p.parse_args()
    if a.seconds<0:raise ValueError('Lifetime must be nonnegative')
    if relay.digest(a.cloudflared)!=EXPECTED_CF_SHA:raise ValueError('Cloudflare official release SHA256 mismatch')
    relay.initialize(a.root)
    ca_pem=a.ca_pem.read_text(encoding='ascii') if a.ca_pem else None
    context=ssl.create_default_context(cadata=ca_pem)
    if ca_pem:(a.root/'task_root_ca.pem').write_bytes(ca_pem.encode('ascii'))
    end=time.monotonic()+a.seconds if a.seconds else float('inf')
    deadline_dt=datetime.now(timezone.utc)+timedelta(seconds=a.seconds) if a.seconds else None
    deadline=deadline_dt.isoformat() if deadline_dt else None
    server=tunnel=awake=None
    flags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
    try:
        with (a.root/'relay.console').open('xb') as log:
            server=subprocess.Popen([sys.executable,str(Path(relay.__file__)),'serve','--root',str(a.root),
                                     '--seconds',str(a.seconds)],stdout=log,stderr=subprocess.STDOUT,
                                    stdin=subprocess.DEVNULL,creationflags=flags)
        state=None
        for i in range(100):
            if server.poll() is not None:raise RuntimeError('Local relay exited; inspect relay.console')
            path=a.root/'state.json'
            if path.is_file():
                state=json.loads(path.read_text())
                if state.get('status')=='LISTENING_LOOPBACK_ONLY':break
            time.sleep(.1)
        if not state or 'port' not in state:raise RuntimeError('Local relay did not become ready')
        origin='http://127.0.0.1:'+str(state['port'])
        with (a.root/'tunnel.console').open('xb') as log:
            tunnel=subprocess.Popen([str(a.cloudflared),'tunnel','--url',origin,'--protocol','http2',
                                     '--no-autoupdate','--logfile',str(a.root/'tunnel.log')],
                                    stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,creationflags=flags)
        url=None
        for i in range(120):
            if tunnel.poll() is not None:raise RuntimeError('Tunnel exited; inspect tunnel.console')
            for path in [a.root/'tunnel.log',a.root/'tunnel.console']:
                if path.is_file():
                    match=re.search(r'https://[a-z0-9-]+\.trycloudflare\.com',path.read_text(errors='replace'))
                    if match:url=match[0];break
            if url:break
            time.sleep(.5)
        if not url:raise RuntimeError('No temporary tunnel URL returned')
        token=(a.root/'token.txt').read_text().strip()
        # Verify the actual public route with normal HTTPS certificate validation.
        last_error=None
        for i in range(60):
            if deadline_dt and datetime.now(timezone.utc)>=deadline_dt:raise TimeoutError('Session expired during startup')
            try:
                req=urllib.request.Request(url+'/health',headers={'Authorization':'Bearer '+token})
                with urllib.request.urlopen(req,timeout=10,context=context) as response:
                    if json.loads(response.read())['ready']:last_error=None;break
            except OSError as exc:last_error=str(exc)
            relay.write_json(a.root/'startup_progress.json',dict(status='WAITING_PUBLIC_HTTPS',
                             attempt=i+1,error=last_error))
            time.sleep(3)
        if last_error:raise RuntimeError('Public route not ready: '+last_error)
        relay.write_json(a.root/'startup_progress.json',dict(status='PUBLIC_HTTPS_VERIFIED'))
        bootstrap=bootstrap_command(url,relay.digest(a.root/'agent.py'),ca_pem,deadline)
        with (a.root/'bootstrap.txt').open('x',encoding='ascii') as stream:stream.write(bootstrap+'\n')
        relay.write_json(a.root/'session.json',dict(status='PUBLIC_ROUTE_VERIFIED_WAITING_FOR_AGENT',
                         base_url=url,deadline_utc=deadline,origin=origin,
                         server_pid=server.pid,tunnel_pid=tunnel.pid,public_health_verified=True,
                         credential_file=str(a.root/'token.txt'),bootstrap_file=str(a.root/'bootstrap.txt')))
        if os.name=='nt':
            with (a.root/'awake.console').open('ab') as log:
                awake=subprocess.Popen([sys.executable,str(Path(__file__).with_name('keep_awake.py')),
                                        '--root',str(a.root)],stdin=subprocess.DEVNULL,stdout=log,
                                       stderr=subprocess.STDOUT,creationflags=flags)
        print('PUBLIC_ROUTE_VERIFIED; bootstrap and token files are in '+str(a.root),flush=True)
        while time.monotonic()<end and (deadline_dt is None or datetime.now(timezone.utc)<deadline_dt):
            if server.poll() is not None or tunnel.poll() is not None:
                raise RuntimeError('Relay/tunnel stopped; artifacts preserved')
            if (a.root/'stop.request').exists():break
            time.sleep(min(5,max(0,end-time.monotonic())))
        return 0
    except Exception as exc:
        relay.write_json(a.root/'session_error.json',dict(error_type=type(exc).__name__,error=str(exc)))
        raise
    finally:
        relay.write_json(a.root/'session_stopped.json',dict(time_utc=datetime.now(timezone.utc).isoformat()))
        stop(tunnel);stop(server)
        if awake is not None:
            try:awake.wait(timeout=7)
            except subprocess.TimeoutExpired:stop(awake)


if __name__=='__main__':raise SystemExit(main())

"""Replace lost Quick Tunnels and publish signed routes at a stable private rendezvous."""
import argparse,json,os,re,ssl,subprocess,sys,time,urllib.request
from pathlib import Path
import relay
from rendezvous_publish import publish
from start_session import EXPECTED_CF_SHA,stop

def healthy(url,token):
    req=urllib.request.Request(url+'/health',headers={'Authorization':'Bearer '+token})
    with urllib.request.urlopen(req,timeout=5,context=ssl.create_default_context()) as response:return json.load(response)['ready']

def run(root,settings):
    root=Path(root);cf=Path(settings['cloudflared']);assert relay.digest(cf)==EXPECTED_CF_SHA
    token=(root/'token.txt').read_text().strip();flags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
    server=tunnel=awake=None;origin=None;url=None;published=None;failures=0;last_health=0
    try:
        while not (root/'stop.request').exists():
            try:
                if server is None or server.poll() is not None:
                    stop(tunnel);tunnel=None;url=None
                    with (root/'relay.console').open('ab') as log:
                        server=subprocess.Popen([sys.executable,str(Path(relay.__file__)),'serve','--root',str(root),'--seconds','0'],stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,creationflags=flags)
                    for _ in range(100):
                        state=json.loads((root/'state.json').read_text())
                        if state.get('status')=='LISTENING_LOOPBACK_ONLY':
                            candidate='http://127.0.0.1:'+str(state['port'])
                            try:
                                if healthy(candidate,token):origin=candidate;break
                            except OSError:pass
                        time.sleep(.1)
                    else:raise RuntimeError('Local relay startup failed')
                if tunnel is None or tunnel.poll() is not None or failures>=3:
                    stop(tunnel);url=None
                    logpath=root/('tunnel_'+str(time.time_ns())+'.log')
                    with (root/'tunnel.console').open('ab') as log:
                        tunnel=subprocess.Popen([str(cf),'tunnel','--url',origin,'--protocol','http2','--no-autoupdate','--logfile',str(logpath)],stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,creationflags=flags)
                    for _ in range(120):
                        if tunnel.poll() is not None:raise RuntimeError('Tunnel startup exited')
                        if logpath.exists():
                            found=re.search(r'https://[a-z0-9-]+\.trycloudflare\.com',logpath.read_text(errors='replace'))
                            if found:url=found[0];break
                        time.sleep(.5)
                    if not url:raise RuntimeError('No new tunnel URL')
                    for _ in range(30):
                        try:
                            if healthy(url,token):break
                        except OSError:pass
                        time.sleep(2)
                    else:raise RuntimeError('New tunnel HTTPS not ready')
                    failures=0;published=None
                if published!=url:
                    result=publish(url,settings['mac_key'])
                    relay.write_json(root/'session.json',dict(status='PUBLIC_ROUTE_VERIFIED',base_url=url,origin=origin,deadline_utc=None,server_pid=server.pid,tunnel_pid=tunnel.pid,public_health_verified=True,discovery_commit=result['commit']))
                    relay.write_json(root/'discovery_publish.json',dict(base_url=url,**result,checked_utc=time.time()))
                    published=url
                    if os.name=='nt' and (awake is None or awake.poll() is not None):
                        with (root/'awake.console').open('ab') as log:
                            awake=subprocess.Popen([sys.executable,str(Path(__file__).with_name('keep_awake.py')),'--root',str(root)],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,creationflags=flags)
                if time.monotonic()-last_health>=30:
                    try:failures=0 if healthy(url,token) else failures+1
                    except OSError:failures+=1
                    last_health=time.monotonic()
                relay.write_json(root/'route_watchdog.json',dict(checked=time.time(),tunnel_pid=tunnel.pid,base_url=url,consecutive_failures=failures,deadline_utc=None))
                time.sleep(5)
            except Exception as exc:
                relay.write_json(root/'route_error.json',dict(error_type=type(exc).__name__,checked=time.time()))
                if url is None or tunnel is None or tunnel.poll() is not None:failures=3
                time.sleep(10)
    finally:
        stop(tunnel);stop(server)
        relay.write_json(root/'session_stopped.json',dict(time_utc=time.time()))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);a=p.parse_args()
    run(a.root,json.loads((a.root/'route_settings.json').read_text()))

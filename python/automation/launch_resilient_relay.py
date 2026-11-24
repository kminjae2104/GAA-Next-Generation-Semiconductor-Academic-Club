"""Start a replacement relay, preserving the agent token and independent simulations."""
import json,os,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
import control,relay
old=control.current(None);settings=json.loads((old/'discovery_settings.json').read_text())
root=old.parent/('gaa_resilient_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
relay.initialize(root)
(root/'token.txt').write_text((old/'token.txt').read_text())
ca=old/'task_root_ca.pem'
if ca.exists():(root/'task_root_ca.pem').write_bytes(ca.read_bytes())
relay.write_json(root/'route_settings.json',dict(mac_key=settings['mac_key'],cloudflared=str(old.parent/'tools/cloudflared-2026.10.7.exe')))
with (root/'controller.console').open('xb') as log:
    process=subprocess.Popen([sys.executable,str(Path(__file__).with_name('resilient_relay.py')),'--root',str(root)],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
relay.write_json(control.LOCAL/'resilient_pending.json',dict(runtime=str(root),previous_runtime=str(old),controller_pid=process.pid,token_preserved=True))
print(json.dumps(dict(runtime=str(root),controller_pid=process.pid)))

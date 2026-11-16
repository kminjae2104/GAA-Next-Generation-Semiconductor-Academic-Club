"""30-second HTTPS checks and periodic read-only result snapshots; no UI input."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import ssl
import time
import urllib.request
import zipfile
import control
import relay


def health(url,token,context):
    req=urllib.request.Request(url+'/health',headers={'Authorization':'Bearer '+token})
    with urllib.request.urlopen(req,timeout=5,context=context) as response:
        return bool(json.loads(response.read()).get('ready'))


def main():
    p=argparse.ArgumentParser();p.add_argument('--runtime',type=Path,required=True);p.add_argument('--target',required=True)
    a=p.parse_args();r=a.runtime;session=json.loads((r/'session.json').read_text());token=(r/'token.txt').read_text().strip()
    context=ssl.create_default_context(cadata=(r/'task_root_ca.pem').read_text() if (r/'task_root_ca.pem').exists() else None)
    deadline=datetime.fromisoformat(session['deadline_utc']);pending=None;last_snapshot=0;latest_summary=None
    while datetime.now(timezone.utc)<deadline and not (r/'stop.request').exists() and not (r/'session_stopped.json').exists():
        state=dict(checked_utc=datetime.now(timezone.utc).isoformat(),interval_seconds=30,display_or_input_changes=False,
            snapshot_interval_seconds=600,latest_snapshot=latest_summary,deadline_utc=session['deadline_utc'])
        for name,url in [('local',session['origin']),('public_https',session['base_url'])]:
            try:state[name]=dict(ready=health(url,token,context))
            except Exception as e:state[name]=dict(ready=False,error_type=type(e).__name__)
        event=r/'latest_event.json'
        if event.exists():
            e=json.loads(event.read_text());state['agent_status']=e.get('status')
            state['agent_heartbeat_age_seconds']=round((datetime.now(timezone.utc)-datetime.fromisoformat(e['received_utc'])).total_seconds(),1)
        if pending and (r/'results'/(pending+'.receipt.json')).exists():
            try:
                folder=control.LOCAL/'collected'/pending
                receipt=json.loads((r/'results'/(pending+'.receipt.json')).read_text())
                if not (folder/'collection_verified.json').is_file():control.collect_archive(r/'results'/(pending+'.zip'),receipt,folder)
                snapshot=json.loads((folder/'snapshot.json').read_text());counts={}
                for v in snapshot['states'].values():counts[v['status']]=counts.get(v['status'],0)+1
                latest_summary=dict(job=pending,collected=str(folder),scheduler_alive=snapshot['scheduler_alive'],task_counts=counts,
                    snapshot_epoch=snapshot['snapshot_epoch']);pending=None
            except Exception as e:state['collection_error_type']=type(e).__name__
        if pending is None and time.monotonic()-last_snapshot>=600 and state['public_https']['ready']:
            queued=json.loads((r/'queue.json').read_text()) if (r/'queue.json').exists() else {}
            previous=queued.get('job')
            if previous is None or (r/'results'/(previous+'.receipt.json')).exists():
                job='gaa_snapshot_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
                local=control.LOCAL/job;local.mkdir(exist_ok=False)
                with zipfile.ZipFile(local/'package.zip','x',zipfile.ZIP_DEFLATED) as z:
                    z.write(Path(__file__).with_name('snapshot_entry.py'),'run_study.py')
                    z.writestr('target.json',json.dumps(dict(job=a.target)))
                relay.publish(r,local/'package.zip',job);pending=job;last_snapshot=time.monotonic()
        state['pending_snapshot']=pending;state['latest_snapshot']=latest_summary
        relay.write_json(r/'connection_guard.json',state)
        time.sleep(30)
    relay.write_json(r/'connection_guard_stopped.json',dict(utc=datetime.now(timezone.utc).isoformat()))


if __name__=='__main__':main()

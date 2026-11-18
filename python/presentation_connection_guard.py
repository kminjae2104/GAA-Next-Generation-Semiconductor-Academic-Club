"""Keep the authorized relay checked and collect both GAA workflows every ten minutes."""
from datetime import datetime, timezone
import json
from pathlib import Path
import ssl
import sys
import time
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'python/automation'))
import relay
import control


def main():
    runtime = Path(json.loads((ROOT / '.local/reconnect_runtime.json').read_text())['runtime'])
    session = json.loads((runtime / 'session.json').read_text())
    deadline = datetime.fromisoformat(session['deadline_utc'])
    token = (runtime / 'token.txt').read_text().strip()
    context = ssl.create_default_context(cadata=(runtime / 'task_root_ca.pem').read_text() if (runtime / 'task_root_ca.pem').exists() else None)
    pending = None
    last = time.monotonic()
    while datetime.now(timezone.utc) < deadline and not (runtime / 'session_stopped.json').exists():
        state = {'checked_utc': datetime.now(timezone.utc).isoformat(), 'health_interval_seconds':30,
                 'collection_interval_seconds':600, 'model_calls':0, 'simulators_started':0}
        try:
            request = urllib.request.Request(session['base_url']+'/health', headers={'Authorization':'Bearer '+token})
            with urllib.request.urlopen(request, timeout=5, context=context) as response:
                state['https_ready'] = bool(json.load(response)['ready'])
        except Exception as error:
            state['https_ready'] = False
            state['error_type'] = type(error).__name__
        event = runtime / 'latest_event.json'
        if event.exists():
            value = json.loads(event.read_text())
            state['agent_status'] = value['status']
            state['agent_age_seconds'] = (datetime.now(timezone.utc)-datetime.fromisoformat(value['received_utc'])).total_seconds()
        if pending and (runtime / 'results' / (pending+'.receipt.json')).exists():
            receipt = json.loads((runtime / 'results' / (pending+'.receipt.json')).read_text())
            destination = ROOT / '.local/collected' / pending
            control.collect_archive(runtime / 'results' / (pending+'.zip'), receipt, destination)
            snapshot=json.loads((destination/'presentation_snapshot.json').read_text())
            summaries={}
            for job,data in snapshot['jobs'].items():
                tasks=data.get('files',{}).get('results/progress.json',{}).get('tasks',{})
                counts={}
                for value in tasks.values():counts[value['status']]=counts.get(value['status'],0)+1
                summaries[job]={'snapshot_epoch':data.get('snapshot_epoch'),'counts':counts,
                    'failed_or_blocked':{k:v for k,v in tasks.items() if v['status'] in ['FAILED','BLOCKED']},
                    'physical_validation':'NOT_VALIDATED'}
            relay.write_json(ROOT / '.local/presentation_guard_latest.json', {'job':pending,'collected':str(destination), 'transport_verified':True,'summaries':summaries})
            pending = None
        if pending is None and time.monotonic()-last >= 600 and state['https_ready']:
            queue = json.loads((runtime / 'queue.json').read_text()) if (runtime / 'queue.json').exists() else {}
            previous = queue.get('job')
            if previous is None or (runtime / 'results' / (previous+'.receipt.json')).exists():
                pending = 'gaa_presentation_auto_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
                folder = ROOT / '.local/packages' / pending
                folder.mkdir(parents=True, exist_ok=False)
                with zipfile.ZipFile(folder / 'package.zip', 'x', zipfile.ZIP_DEFLATED) as archive:
                    archive.write(Path(__file__).with_name('presentation_remote_snapshot.py'), 'run_study.py')
                    targets=ROOT/'.local/continuation_targets.json'
                    if targets.exists():archive.writestr('targets.json',targets.read_text())
                relay.publish(runtime, folder / 'package.zip', pending)
                last = time.monotonic()
        state['pending'] = pending
        relay.write_json(runtime / 'presentation_guard.json', state)
        time.sleep(30)


if __name__ == '__main__':
    main()

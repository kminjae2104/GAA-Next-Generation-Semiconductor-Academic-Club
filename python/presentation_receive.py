"""Wait for one requested snapshot and verify delivery, without model polling."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'python/automation'))
import control


def main():
    pending = json.loads((ROOT / '.local/presentation_pending.json').read_text())
    runtime = Path(pending['runtime'])
    session = json.loads((runtime / 'session.json').read_text())
    deadline = datetime.fromisoformat(session['deadline_utc'])
    job = pending['job']
    receipt = runtime / 'results' / (job + '.receipt.json')
    dest = ROOT / '.local/collected' / job
    while datetime.now(timezone.utc) < deadline:
        if receipt.exists():
            record = control.collect_archive(runtime / 'results' / (job + '.zip'),
                                             json.loads(receipt.read_text()), dest)
            snapshot = json.loads((dest / 'presentation_snapshot.json').read_text())
            summary = {'job': job, 'collected': str(dest), 'transport': record,
                       'received_utc': datetime.now(timezone.utc).isoformat(), 'workflows': {}}
            for name, data in snapshot['jobs'].items():
                states = data.get('files', {}).get('results/progress.json', {}).get('tasks', {})
                counts = {}
                for state in states.values():
                    counts[state['status']] = counts.get(state['status'], 0)+1
                summary['workflows'][name] = {'snapshot_epoch': data.get('snapshot_epoch'),
                                              'counts': counts, 'states': states}
            (ROOT / '.local/presentation_received.json').write_text(json.dumps(summary, indent=2))
            print('SNAPSHOT_RECEIVED_AND_HASH_VERIFIED', flush=True)
            return
        time.sleep(10)
    print('TRANSPORT_DEADLINE_REACHED_WITHOUT_RECEIPT', flush=True)


if __name__ == '__main__':
    main()

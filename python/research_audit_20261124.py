"""Read-only remote snapshot request and local evidence inventory for the GAA review."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'python/automation'))
import control
import relay


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def inventory(out):
    snapshots, other = [], []
    for folder in sorted((ROOT / '.local/collected').iterdir()):
        if not folder.is_dir():
            continue
        item = {'collection': folder.name}
        p = folder / 'presentation_snapshot.json'
        if p.exists():
            data = read(p)
            item.update(snapshot_epoch=data['snapshot_epoch'], jobs={})
            for job, state in data['jobs'].items():
                tasks = state.get('files', {}).get('results/progress.json', {}).get('tasks', {})
                item['jobs'][job] = dict(Counter(x['status'] for x in tasks.values()))
            snapshots.append(item)
        else:
            for filename in ['status.json', 'collection_verified.json']:
                if (folder / filename).exists():
                    item[filename] = read(folder / filename)
            item['top_files'] = sorted(x.name for x in folder.iterdir())
            other.append(item)
    save(out / 'collection_inventory.json', {'snapshots': snapshots, 'other_collections': other})
    print(json.dumps({'snapshots': len(snapshots), 'other_collections': len(other),
                      'latest': sorted(snapshots, key=lambda x: x['snapshot_epoch'])[-1] if snapshots else None,
                      'other_ids': [x['collection'] for x in other]}, ensure_ascii=False))


def request(out):
    runtime = control.current(None)
    state = control.state(runtime)
    safe = {k: state.get(k) for k in ['session_status', 'live_agent', 'heartbeat_age_seconds',
                                     'deadline_utc', 'registration_required']}
    save(out / 'connection_at_request.json', safe)
    if not state['live_agent']:
        raise RuntimeError('No live registered agent; existing evidence remains available')
    queued = runtime / 'queue.json'
    if queued.exists():
        previous = read(queued)['job']
        if not (runtime / 'results' / (previous + '.receipt.json')).exists():
            raise RuntimeError('An outstanding request is preserved; no replacement published')
    job = 'gaa_research_review_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    folder = ROOT / '.local/packages' / job
    folder.mkdir(parents=True, exist_ok=False)
    with zipfile.ZipFile(folder / 'package.zip', 'x', zipfile.ZIP_DEFLATED) as z:
        z.write(ROOT / 'python/presentation_remote_snapshot.py', 'run_study.py')
        z.write(ROOT / '.local/continuation_targets.json', 'targets.json')
    relay.publish(runtime, folder / 'package.zip', job)
    info = dict(job=job, simulators_started=0, read_only_remote=True,
                requested_utc=datetime.now(timezone.utc).isoformat(),
                package_sha256=hashlib.sha256((folder / 'package.zip').read_bytes()).hexdigest())
    save(out / 'snapshot_request.json', info)
    print(json.dumps(info))


def collect(out):
    job = read(out / 'snapshot_request.json')['job']
    runtime = control.current(None)
    receipt = runtime / 'results' / (job + '.receipt.json')
    if not receipt.exists():
        print(json.dumps({'job': job, 'status': 'NOT_RETURNED_NO_WAIT'}))
        return
    destination = ROOT / '.local/collected' / job
    if not destination.exists():
        control.collect_archive(runtime / 'results' / (job + '.zip'), read(receipt), destination)
    save(out / 'snapshot_collection.json', {'source': str(destination), **read(destination / 'collection_verified.json')})
    print(json.dumps({'source': str(destination), 'snapshot': read(destination / 'presentation_snapshot.json')['snapshot_epoch']}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['inventory', 'request', 'collect'])
    parser.add_argument('--out', type=Path, default=ROOT / '검증/전체연구검토_20261124')
    args = parser.parse_args()
    args.out.resolve().relative_to(ROOT)
    globals()[args.action](args.out)

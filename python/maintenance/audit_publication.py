"""Scan reachable Git blobs for common credential formats without printing values.

This is a bounded pattern scan, not proof that all sensitive information is absent.
It does not read credentials, the private runtime, or untracked files.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]
PATTERNS = {
    'github_token': rb'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{50,})',
    'private_key': rb'-----BEGIN (?:OPENSSH |RSA |EC |DSA )?PRIVATE KEY-----',
    'aws_access_key': rb'AKIA[0-9A-Z]{16}',
    'literal_auth_secret': rb'''(?i)["']?(?:token|password|mac_key|api_key|client_secret)["']?\s*[:=]\s*["']([A-Za-z0-9_+/=-]{24,})["']''',
    'credential_in_url': rb'https?://[^\s/:@]+:[^\s/@]{8,}@',
}


def scan():
    lines = subprocess.check_output(['git', 'rev-list', '--objects', '--all'], cwd=ROOT).decode('utf-8').splitlines()
    objects = [(s.split(' ', 1)[0], s.split(' ', 1)[1] if ' ' in s else '') for s in lines]
    proc = subprocess.Popen(['git', 'cat-file', '--batch'], cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    # Communicate one object at a time: avoids pipe buffering deadlocks on large histories.
    findings = []
    blobs = total = 0
    try:
        for sha, path in objects:
            proc.stdin.write((sha+'\n').encode('ascii')); proc.stdin.flush()
            header = proc.stdout.readline().split()
            if len(header) != 3:
                raise RuntimeError('Unexpected git cat-file response')
            size = int(header[2]); data = proc.stdout.read(size)
            if len(data) != size or proc.stdout.read(1) != b'\n':
                raise RuntimeError('Incomplete Git object')
            if header[1] != b'blob':
                continue
            blobs += 1; total += size
            for label, pattern in PATTERNS.items():
                for match in re.finditer(pattern, data):
                    findings.append(dict(kind=label, blob=sha, path=path,
                                         line=data[:match.start()].count(b'\n')+1))
    finally:
        proc.stdin.close(); proc.wait(timeout=30)
    files = subprocess.check_output(['git', '-c', 'core.quotepath=false', 'ls-files', '-z'], cwd=ROOT).decode('utf-8').split('\0')[:-1]
    return dict(checked_utc=datetime.now(timezone.utc).isoformat(),
                refs=subprocess.check_output(['git', 'for-each-ref', '--format=%(refname)'], cwd=ROOT).decode().splitlines(),
                objects=len(objects), blobs=blobs, bytes_scanned=total,
                tracked_files=len(files), top_level_counts=dict(Counter(p.split('/')[0] for p in files)),
                findings=findings, scope='All locally fetched reachable refs and history; credential patterns only. Untracked/private runtime excluded. Manual classification required.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    report = scan()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2); stream.write('\n')
    print(json.dumps({k: report[k] for k in ['objects', 'blobs', 'bytes_scanned', 'tracked_files']}))
    print('candidate_locations='+str(len(report['findings'])))

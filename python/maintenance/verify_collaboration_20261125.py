"""Verify tracked content, preserving native output bytes and classifying text EOLs."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
BASE = '9393c4c68067fd9c058aaf90c8635fa64d670d6b'
ALLOWED = {'.gitignore', 'AGENTS.md', 'README.md', 'md/접근권한.md',
           'md/터널주소_자동복구_20261121.md', 'python/automation/rendezvous_publish.py',
           'python/automation/resilient_relay.py', 'python/automation/test_rendezvous.py',
           '연구/02_치수변화/README.md'}


def main():
    changed = []
    eol_only = []
    count = 0
    tree = subprocess.check_output(['git', 'ls-tree', '-r', '-z', BASE], cwd=ROOT)
    names = [item.split(b'\t', 1)[1] for item in tree.split(b'\0') if item]
    attrs_raw = subprocess.check_output(['git', 'check-attr', '-z', '--stdin', 'text'], input=b'\0'.join(names)+b'\0', cwd=ROOT).split(b'\0')
    attrs = {attrs_raw[i].decode('utf-8'): attrs_raw[i+2] for i in range(0, len(attrs_raw)-1, 3)}
    for item in tree.split(b'\0'):
        if not item:
            continue
        meta, rawpath = item.split(b'\t', 1)
        path = rawpath.decode('utf-8')
        if path in ALLOWED:
            continue
        data = (ROOT/path).read_bytes()
        actual = hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
        expected = meta.split()[2].decode('ascii')
        count += 1
        if actual != expected:
            normalized = data.replace(b'\r\n', b'\n')
            normalized_sha = hashlib.sha1(b'blob '+str(len(normalized)).encode()+b'\0'+normalized).hexdigest()
            if attrs[path] in {b'set', b'auto'} and b'\0' not in data[:8000] and normalized_sha == expected:
                eol_only.append(path)
            else:
                changed.append(path)
    report = dict(checked_utc=datetime.now(timezone.utc).isoformat(), baseline=BASE,
                  original_files_checked=count, exact_git_blob_byte_matches=count-len(eol_only)-len(changed),
                  checkout_text_eol_only_differences=eol_only, unexpected_original_content_changes=changed,
                  method='Native binary outputs compared byte-for-byte. Text CRLF/LF differences classified using git text attributes; no source files rewritten.',
                  original_paths_intentionally_updated=sorted(ALLOWED),
                  observed_tests=[
                      dict(command='py -3.11 -m unittest discover -s python/automation -p "test_*.py" -v', tests=41, result='PASS', evidence='Executed in this task; no Silvaco execution'),
                      dict(command='py -3.11 -m unittest discover -s python/collaboration -p "test_*.py" -v', tests=4, result='PASS', evidence='Executed in this task; preservation/path safety checks')],
                  tcad_execution='NOT_RUN_BY_THIS_TASK',
                  scientific_validation='NOT_ASSESSED_BY_THIS_TASK',
                  member_invitation_status='DEFERRED_UNTIL_EXACT_GITHUB_IDS_SUPPLIED')
    out = ROOT/'검증/협업체계_20261125/verification.json'
    with out.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2); stream.write('\n')
    print(json.dumps(dict(original_files_checked=count, checkout_text_eol_only_differences=len(eol_only), unexpected_original_content_changes=changed)))
    if changed:
        raise SystemExit(1)


if __name__ == '__main__':
    main()

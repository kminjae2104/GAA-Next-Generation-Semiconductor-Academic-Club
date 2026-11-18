"""Integrate a fresh authenticated snapshot into the existing presentation, as requested."""
from pathlib import Path
import hashlib
import json
import shutil
import build_presentation_20261118 as build

root = Path(__file__).resolve().parents[2]
received = json.loads((root / '.local/presentation_received.json').read_text())
source = Path(received['collected'])
report = json.loads((source / 'presentation_snapshot.json').read_text())
original = report['jobs']['gaa_overnight_20261116T080149Z']
recovery = report['jobs']['gaa_autonomous_20261117T064609Z']
assert received['transport']['transport_verified']
work = root / '.local/presentation_input_20261118T0332Z'
shutil.copytree(source / 'gaa_overnight_20261116T080149Z', work)
snapshot = {'snapshot_epoch': original['snapshot_epoch'],
            'states': original['files']['results/progress.json']['tasks'],
            'source': str(source.relative_to(root) / 'presentation_snapshot.json')}
(work / 'snapshot.json').write_text(json.dumps(snapshot, indent=2))
(work / 'recovery.json').write_text(json.dumps(recovery, indent=2))
for name in ['collection_verified.json', 'presentation_snapshot.json']:
    shutil.copy2(source / name, work / name)
build.SNAP = work
build.OUT = root / '검증/GAA_발표_20261118_최신회수'
build.FRESH = True
build.main()
hashfile = build.OUT / '출처해시.json'
hashes = json.loads(hashfile.read_text(encoding='utf-8'))
for subfolder in [source / 'gaa_autonomous_20261117T064609Z/cases']:
    for src in subfolder.rglob('*'):
        if not src.is_file():
            continue
        rel = Path('복구작업') / src.relative_to(subfolder)
        dst = build.OUT / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        hashes[rel.as_posix()] = {'source':src.relative_to(root).as_posix(),
                                 'sha256':hashlib.sha256(src.read_bytes()).hexdigest(), 'bytes':src.stat().st_size}
# The normalization only wraps metadata; original collected bytes remain unchanged.
for rel, data in hashes.items():
    src = root / data['source']
    try:
        inner = src.relative_to(work)
    except ValueError:
        continue
    candidate = source / 'gaa_overnight_20261116T080149Z' / inner
    if candidate.is_file():
        assert src.read_bytes() == candidate.read_bytes()
        data['source'] = candidate.relative_to(root).as_posix()
hashfile.write_text(json.dumps(hashes,ensure_ascii=False,indent=2),encoding='utf-8')
print('INTEGRATED_INTO_EXISTING_MARKDOWN; LIVE_SNAPSHOT_VERIFIED')

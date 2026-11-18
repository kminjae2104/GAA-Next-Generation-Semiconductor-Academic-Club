"""Independent artifact, provenance, and mesh comparison checks."""
from pathlib import Path
import hashlib
import json
import re
import sys

root = Path(__file__).resolve().parents[2]
out = root / ('검증/GAA_발표_20261118_최신회수' if '--latest' in sys.argv else '검증/GAA_발표_20261118')
doc = root / 'md/발표자료/GAA_연구현황_발표자료_20261118.md'
j = json.loads((out / '검증기록.json').read_text(encoding='utf-8'))
hashes = json.loads((out / '출처해시.json').read_text(encoding='utf-8'))
for rel, info in hashes.items():
    p = out / rel
    assert hashlib.sha256(p.read_bytes()).hexdigest() == info['sha256']
    assert p.read_bytes() == (root / info['source']).read_bytes()
for case, check in j['representative_cases'].items():
    deck = out / '덱' / (case + '.in')
    cfg = json.loads((root / '연구/01_GAA_IdVg/tcad/gaa_overnight_20261116T080149Z' / (case + '.json')).read_text())
    assert cfg['sha256'] == hashlib.sha256(deck.read_bytes()).hexdigest(), case
    for key in ['parameters', 'linear_solver', 'mesh_style', 'processors', 'quantum_mode', 'gate_initialization', 'mesh_scale']:
        assert cfg[key] == check['config'][key], (case, key)
a = j['recomputed']['eq_bicgst_full']
b = j['recomputed']['eq_bicgst_fine']
mesh = {}
for bias in ['low', 'high']:
    for metric, limit, relative in [('Ion_A', .05, True), ('Ioff_A', .2, True), ('Vth_V', .01, False), ('SS_mV_dec', 5, False)]:
        av, bv = a['metrics'][bias][metric], b['metrics'][bias][metric]
        difference = abs(bv-av)/abs(av) if relative else abs(bv-av)
        assert difference <= limit
        mesh[bias+'_'+metric] = {'difference': difference, 'limit': limit, 'pass': True}
text = doc.read_text(encoding='utf-8')
links = re.findall(r'\]\(([^)]+)\)', text)
for link in links:
    assert (doc.parent / link).resolve().exists(), link
rows = []
for line in text.splitlines() + ['']:
    if line.startswith('|'):
        rows.append(line.count('|'))
    elif rows:
        assert len(set(rows)) == 1
        rows = []
assert not any(s in text for s in ['![', '<svg', '```mermaid'])
assert len(re.findall(r'^## \d\d\.', text, re.M)) == 12
states = json.loads((out / 'snapshot.json').read_text())['states']
success = [n for n, v in states.items() if v['status'] == 'SUCCEEDED']
counts = {suffix: sum(n.endswith('_'+suffix) for n in success) for suffix in ['smoke', 'screen', 'full', 'fine']}
assert counts == {'smoke': 7, 'screen': 9, 'full': 7, 'fine': 1}
qc = {'input_deck_hashes_match_saved_configs': True, 'evidence_files_match_originals': len(hashes),
      'links_exist': len(links), 'markdown_tables_consistent': True, 'mesh_8_checks_recomputed': mesh,
      'successful_task_stages': counts, 'current_remote_verified': j['current_remote_verified'], 'graphs_created': 0}
(out / '최종검사.json').write_text(json.dumps(qc, ensure_ascii=False, indent=2), encoding='utf-8')
assert hashlib.sha256(doc.read_bytes()).hexdigest() == j['output_sha256']
print(json.dumps({'checks': 'PASS', 'links': len(links), 'evidence': len(hashes), 'mesh_checks': len(mesh), 'sections': 12}))

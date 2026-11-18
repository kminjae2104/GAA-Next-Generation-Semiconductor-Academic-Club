"""One-time reversible moves; active relay and snapshot entry points stay in place."""
from pathlib import Path
import re
ROOT=Path(__file__).resolve().parents[2]
moves={}
for p in (ROOT/'md').glob('*.md'):
    if p.name.startswith(('GAA_연구현황','GAA_입문','TCAD_도구','GAA_발표자료')):moves[p]=p.parent/'발표자료'/p.name
    elif p.name.startswith('후속야간실험_계획'):moves[p]=p.parent/'연구계획'/p.name
for name in ['build_presentation_20261118.py','refresh_presentation_20261118.py','verify_presentation_20261118.py','presentation_log_images.py','tonyplot3d_export_remote.py','tonyplot_diagnostic_remote.py']:
    p=ROOT/'python'/name;moves[p]=p.parent/'presentation'/name
docs={p:p.read_text(encoding='utf-8') for p in ROOT.rglob('*.md') if '.local' not in p.parts and '.git' not in p.parts}
import os
for old,new in moves.items():
    assert old.resolve().is_relative_to(ROOT) and new.resolve().is_relative_to(ROOT)
    assert not new.exists();new.parent.mkdir(exist_ok=True);old.rename(new)
for old,text in docs.items():
    new=moves.get(old,old)
    def fix(match):
        target=match[1]
        if '://' in target or target.startswith('#'):return match[0]
        path,sep,anchor=target.partition('#');resolved=(old.parent/path).resolve();mapped=moves.get(resolved,resolved)
        return ']('+Path(os.path.relpath(mapped,new.parent)).as_posix()+(sep+anchor if sep else '')+')'
    result=re.sub(r'\]\(([^)]+)\)',fix,text)
    if result!=text:new.write_text(result,encoding='utf-8',newline='\n')
for old,new in moves.items():
    if new.suffix=='.py':
        s=new.read_text(encoding='utf-8').replace('parents[2]','parents[2]')
        s=s.replace("ROOT/'md'/OUTPUT_NAME","ROOT/'md/발표자료'/OUTPUT_NAME")
        s=s.replace("root / 'md/GAA_연구현황_발표자료_20261118.md'","root / 'md/발표자료/GAA_연구현황_발표자료_20261118.md'")
        # Draft text was authored relative to md/; shift evidence links at export.
        if new.name=='build_presentation_20261118.py':s=s.replace("output = ROOT/'md/발표자료'/OUTPUT_NAME","text = text.replace('(../', '(../../')\n    output = ROOT/'md/발표자료'/OUTPUT_NAME")
        new.write_text(s,encoding='utf-8',newline='\n')
print('Moved',len(moves),'files; active automation paths preserved')

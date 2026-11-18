"""Render real selected log evidence as readable PNG excerpts; no graphs or invented geometry."""
from pathlib import Path
import json, shutil, hashlib
from PIL import Image, ImageDraw, ImageFont
root=Path(__file__).resolve().parents[2]
source=Path(json.loads((root/'.local/presentation_received.json').read_text())['collected'])/'gaa_overnight_20261116T080149Z/cases'
out=root/'그림/발표선정_20261118'
out.mkdir(parents=True,exist_ok=True)
font=ImageFont.truetype('C:/Windows/Fonts/consola.ttf',25)
title=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',35)
manifest=[]
for case,caption in [('eq_bicgst_fine','Validated baseline: Vd=0.60 V, final Vg=0.80 V'),('wf4p6_fine','Rejected: actual Vd=0.340703125 V, intended 0.60 V'),('bqp_fine','Rejected: final Vg=0.58484375 V, intended 0.80 V')]:
    p=source/case/'idvg_high.log'
    rows=[line.split()[1:] for line in p.read_text().splitlines() if line.startswith('d ')]
    lines=['REAL SILVACO LOG - SELECTED ROWS (not a simulator screenshot)',caption,'','Native terminal layout: gate, source, drain','Vg(V)          Vs(V)          Vd(V)          Id(A)']
    for r in rows[-6:]:lines.append(f'{float(r[0]):.9f}    {float(r[3]):.9f}    {float(r[6]):.9f}    {float(r[8]):.9e}')
    lines+=['','Source: '+case+'/idvg_high.log','Run: gaa_overnight_20261116T080149Z','Collected: 2026-11-18 12:32 KST','Rows selected from native log; all values retained in accompanying .log']
    im=Image.new('RGB',(1680,680),'white');d=ImageDraw.Draw(im);d.text((45,25),case,font=title,fill='#15385b')
    for i,line in enumerate(lines):d.text((45,90+i*35),line,font=font,fill='#152333')
    target=out/(case+'.png');im.save(target);shutil.copy2(p,out/(case+'.log'))
    manifest.append({'case':case,'source':p.relative_to(root).as_posix(),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'png':target.name,'rows_in_native_log':len(rows)})
(out/'선정근거.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
print(out)

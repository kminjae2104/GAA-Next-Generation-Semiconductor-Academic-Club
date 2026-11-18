"""Export actual preserved structures with TonyPlot3D; never use an existing display."""
from pathlib import Path
import argparse,os,json,subprocess,shutil
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--max-seconds');a=p.parse_args()
exe=Path('/users/tools/Silvaco/bin/tonyplot3d');env=dict(os.environ);env.pop('DISPLAY',None)
report={'tonyplot3d':str(exe),'xvfb_run':shutil.which('xvfb-run'),'exports':[]}
def run(cmd,name,timeout=120):
 try:
  r=subprocess.run(cmd,env=env,capture_output=True,timeout=timeout);(a.output/name).write_bytes(r.stdout+r.stderr);return r.returncode
 except Exception as e:(a.output/name).write_text(type(e).__name__+': '+str(e));return -1
report['help_rc']=run([str(exe),'-help'],'help.txt',20)
base=Path.home()/'gaa_tcad_runs/gaa_overnight_20261116T080149Z/durable/results/eq_bicgst_fine'
manifest=list(base.glob('**/retained_structures.json'))
if manifest:
 entries=json.loads(manifest[0].read_text())
 for entry in entries:
  if Path(entry['original_result_path']).name not in ['geometry.str','final_high.str']:continue
  src=Path(entry['remote_preserved_path']);dst=a.output/(src.stem+'.png')
  cmd=[str(exe),str(src),'-nohw','-png',str(dst)]
  if report['xvfb_run']:cmd=[report['xvfb_run'],'-a','-s','-screen 0 1600x1200x24']+cmd
  rc=run(cmd,src.stem+'_export.txt');report['exports'].append({'source':str(src),'returncode':rc,'png_exists':dst.exists(),'bytes':dst.stat().st_size if dst.exists() else 0})
(a.output/'export_report.json').write_text(json.dumps(report,indent=2))
(a.output/'status.json').write_text(json.dumps({'status':'TONYPLOT_EXPORT_ATTEMPT','stages':[]}))

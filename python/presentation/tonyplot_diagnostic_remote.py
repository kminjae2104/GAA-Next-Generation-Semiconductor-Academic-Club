from pathlib import Path
import argparse,shutil,subprocess,json,os
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--max-seconds');a=p.parse_args()
r={'tools':{n:shutil.which(n) for n in ['Xvfb','xvfb-run','Xorg','gs','tonyplot3d']}}
f=Path('/users/tools/Silvaco/bin/tonyplot3d');r['resolved']=str(f.resolve());r['size']=f.stat().st_size
data=f.read_bytes();r['header']=data[:16000].decode(errors='replace') if data.startswith(b'#!') else repr(data[:40])
r['versions']=[str(p) for p in Path('/users/tools/Silvaco').glob('lib/tonyplot3d/*')][:30]
env=dict(os.environ);env.pop('DISPLAY',None)
t=subprocess.run(['/bin/csh','-x',str(f),'-help'],env=env,capture_output=True,timeout=20)
(a.output/'launcher_trace.txt').write_bytes(t.stdout+t.stderr)
import re
matches=re.findall(rb'(/[^\s]+/tonyplot3d\.exe)',t.stderr)
if matches:
 binary=matches[-1].decode();r['binary']=binary
 x=subprocess.run([binary,'-help'],env=env,capture_output=True,timeout=20)
 (a.output/'binary_help.txt').write_bytes(x.stdout+x.stderr);r['binary_rc']=x.returncode
(a.output/'diagnostic.json').write_text(json.dumps(r,indent=2));(a.output/'status.json').write_text('{"stages":[]}')

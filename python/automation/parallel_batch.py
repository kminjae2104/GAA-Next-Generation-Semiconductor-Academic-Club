"""Build/start an immutable three-deck parallel batch without desktop input."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import zipfile
import relay

DRIVER = r'''
import argparse,concurrent.futures,json,pathlib,shutil,subprocess,sys,time
p=argparse.ArgumentParser();p.add_argument('--output',type=pathlib.Path,required=True);p.add_argument('--max-seconds',type=int,required=True);a=p.parse_args()
code=pathlib.Path(__file__).resolve().parent;out=a.output.resolve()
manifest=json.loads((code/'batch.json').read_text());states={}
def run(case):
 name=case['name'];work=out.parent/'cases'/name/'results';work.mkdir(parents=True,exist_ok=False)
 with (work/'batch_console.txt').open('xb') as log:
  proc=subprocess.Popen([sys.executable,str(code/name/'worker.py'),'--output',str(work),'--max-seconds','4860'],stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL)
  states[name]={'status':'RUNNING','pid':proc.pid}
  rc=proc.wait()
 shutil.copytree(work,out/name)
 status=json.loads((work/'status.json').read_text()) if (work/'status.json').exists() else {}
 states[name]={'status':status.get('status','WORKER_FAILED'),'returncode':rc}
 return dict(case=name,returncode=rc,details=status)
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
 futures=[pool.submit(run,c) for c in manifest['cases']]
 while not all(f.done() for f in futures):
  tmp=out/'progress.tmp';tmp.write_text(json.dumps({'stage':'PARALLEL_BATCH','cases':dict(states)}));tmp.replace(out/'progress.json');time.sleep(5)
 results=[f.result() for f in futures]
stages=[]
for result in results:
 for stage in result['details'].get('stages',[]):stage['stage']=result['case'];stages.append(stage)
(out/'status.json').write_text(json.dumps({'status':'PARALLEL_BATCH_RETURNED','stages':stages,'cases':results,'physical_validation':'NOT_VALIDATED'},indent=2))
sys.exit(0 if all(r['returncode']==0 for r in results) else 5)
'''


def main():
    p=argparse.ArgumentParser();p.add_argument('--publish',action='store_true');p.add_argument('--runtime',type=Path);p.add_argument('--package',type=Path);p.add_argument('--job');a=p.parse_args()
    if a.publish:
        end=time.monotonic()+180
        while not (a.runtime/'packages').is_dir() and time.monotonic()<end:time.sleep(1)
        relay.publish(a.runtime,a.package,a.job)
        with (a.package.parent/'watch.console').open('xb') as log:
            subprocess.Popen([sys.executable,str(Path(__file__).with_name('watch_job.py')),'--runtime',str(a.runtime),'--job',a.job],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        return
    root=Path(__file__).resolve().parents[2];study=root/'연구'/'01_GAA_IdVg'
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ');job='gaa_parallel_'+stamp
    local=root/'.local'/job;local.mkdir(parents=True,exist_ok=False)
    package=local/'package.zip';manifest=dict(job=job,parallel_cases=3,per_deck_timeout_seconds=4800,cases=[])
    cases=[('smoke','gaa_coarse_smoke.in'),('coarse','gaa_coarse.in'),('fine','gaa_fine.in')]
    with zipfile.ZipFile(package,'x',zipfile.ZIP_DEFLATED) as z:
        z.writestr('run_study.py',DRIVER)
        for name,filename in cases:
            deck=study/'tcad'/'v2_common_gate'/filename
            data=deck.read_bytes()
            manifest['cases'].append(dict(name=name,source=str(deck.relative_to(root)),sha256=hashlib.sha256(data).hexdigest()))
            z.writestr(name+'/gaa.in',data)
            z.write(study/'python'/'run_study.py',name+'/worker.py')
            required=['geometry.str','equilibrium.str','idvg_low.log','low_drain.dat','low_source.dat','low_gate.dat']
            if name!='smoke':required+=['idvg_high.log','high_drain.dat','high_source.dat','high_gate.dat']
            z.writestr(name+'/config.json',json.dumps(dict(mode=name,stage_timeout=4800,required={'gaa':required})))
        z.writestr('batch.json',json.dumps(manifest,indent=2))
    compile(DRIVER,'parallel_driver','exec')
    with zipfile.ZipFile(package) as z:
        assert len([n for n in z.namelist() if n.endswith('/gaa.in')])==3
        for c in manifest['cases']:assert hashlib.sha256(z.read(c['name']+'/gaa.in')).hexdigest()==c['sha256']
    runtime=Path(os.environ['LOCALAPPDATA'])/'TCAD_PRIVATE'/job
    cf=Path(os.environ['LOCALAPPDATA'])/'TCAD_PRIVATE'/'tools'/'cloudflared-2026.10.7.exe'
    ca=Path(os.environ['LOCALAPPDATA'])/'TCAD_PRIVATE'/'cau_session_tls_20261109T233135'/'task_root_ca.pem'
    flags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
    with (local/'controller.console').open('xb') as log:
        proc=subprocess.Popen([sys.executable,str(Path(__file__).with_name('start_session.py')),'--root',str(runtime),'--cloudflared',str(cf),'--seconds','21600','--ca-pem',str(ca)],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,creationflags=flags)
    relay.write_json(root/'.local'/'runtime.json',dict(runtime=str(runtime),controller_pid=proc.pid,ui_input_allowed=False))
    with (local/'publisher.console').open('xb') as log:
        publisher=subprocess.Popen([sys.executable,__file__,'--publish','--runtime',str(runtime),'--package',str(package),'--job',job],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,creationflags=flags)
    relay.write_json(local/'batch.json',manifest)
    print(json.dumps(dict(job=job,per_deck_minutes=80,parallel_cases=3,package_validated=True,runtime=str(runtime),state='PREPARED_REGISTRATION_REQUIRED',publisher_pid=publisher.pid),ensure_ascii=False))


if __name__=='__main__':main()

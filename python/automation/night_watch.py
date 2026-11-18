"""Periodic headless collection and compact status, without any model calls."""
from datetime import datetime, timezone
import json
from pathlib import Path
import time
import zipfile
import control
import relay


def main():
    root=Path(__file__).resolve().parents[2]
    pointer=json.loads((root/'.local/latest_autonomous.json').read_text())
    runtime=Path(pointer['runtime']);session=json.loads((runtime/'session.json').read_text())
    pending=None;last=0
    while datetime.now(timezone.utc)<datetime.fromisoformat(session['deadline_utc']):
        if pending:
            receipt=runtime/'results'/(pending+'.receipt.json')
            if receipt.exists():
                dest=root/'.local/collected'/pending
                control.collect_archive(runtime/'results'/(pending+'.zip'),json.loads(receipt.read_text()),dest)
                original=json.loads((dest/'snapshot.json').read_text());counts={}
                for v in original['states'].values():counts[v['status']]=counts.get(v['status'],0)+1
                report=dict(collected=str(dest),snapshot_epoch=original['snapshot_epoch'],original_counts=counts,
                    recovery=json.loads((dest/'recovery.json').read_text()),transport_verified=True,
                    physical_validation='NOT_VALIDATED',ui_input_used=False)
                relay.write_json(root/'.local/night_latest.json',report);pending=None
        if pending is None and time.monotonic()-last>=600:
            job='gaa_night_snapshot_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
            package=root/'.local'/(job+'.zip')
            source=Path(__file__).with_name('snapshot_entry.py').read_text()
            source=source[:source.rfind('if __name__==')]+"main()\n"
            wrapper='''import runpy,json,pathlib,sys,shutil,time
runpy.run_path(str(pathlib.Path(__file__).with_name('snapshot.py')),run_name='__main__')
out=pathlib.Path(sys.argv[sys.argv.index('--output')+1])
target=json.loads(pathlib.Path(__file__).with_name('recovery_target.json').read_text())['job']
base=pathlib.Path.home()/'gaa_tcad_runs'/target/'durable'
report={'snapshot_epoch':time.time(),'job':target}
for name in ['launch.json','complete.json','results/progress.json']:
 p=base/name
 if p.exists():report[name]=json.loads(p.read_text())
for case in (base/'results').glob('*'):
 if not case.is_dir():continue
 selection=case/'selected_attempt.json'
 selected=case/json.loads(selection.read_text())['directory'] if selection.exists() else case
 dest=out/'recovery_cases'/case.name;dest.mkdir(parents=True,exist_ok=True)
 for name in ['validated_metrics.json','status.json','progress.json']:
  f=selected/name
  if f.exists():shutil.copy2(f,dest/name)
 f=case/'scheduler_console.txt'
 if f.exists():
  with f.open('rb') as stream:stream.seek(max(0,f.stat().st_size-4096));(dest/'scheduler_tail.txt').write_bytes(stream.read())
(out/'recovery.json').write_text(json.dumps(report,indent=2))
'''
            with zipfile.ZipFile(package,'x',zipfile.ZIP_DEFLATED) as archive:
                archive.writestr('run_study.py',wrapper);archive.writestr('snapshot.py',source)
                archive.writestr('target.json',json.dumps(dict(job='gaa_overnight_20261116T080149Z')))
                archive.writestr('recovery_target.json',json.dumps(dict(job=pointer['job'])))
            relay.publish(runtime,package,job);pending=job;last=time.monotonic()
        relay.write_json(root/'.local/night_watch.json',dict(pending=pending,
            checked_utc=datetime.now(timezone.utc).isoformat(),deadline=session['deadline_utc'],model_calls=0))
        time.sleep(15)


if __name__=='__main__':main()

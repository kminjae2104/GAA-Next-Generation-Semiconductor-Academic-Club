"""Background-only local control. No UI, input injection, or clipboard APIs."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import stat
import subprocess
import sys
import time
import zipfile

import relay

ROOT=Path(__file__).resolve().parents[2]
STUDY=ROOT/'연구'/'01_GAA_IdVg'
LOCAL=ROOT/'.local'


def current(explicit):
    if explicit:return Path(explicit).resolve()
    return Path(json.loads((LOCAL/'runtime.json').read_text())['runtime'])


def state(runtime):
    def get(name):
        p=runtime/name
        return json.loads(p.read_text(encoding='utf-8')) if p.is_file() else None
    session=get('session.json') or {}
    event=get('latest_event.json') or {}
    stopped=get('session_stopped.json')
    age=None
    if event.get('received_utc'):
        age=(datetime.now(timezone.utc)-datetime.fromisoformat(event['received_utc'])).total_seconds()
    expired=bool(session.get('deadline_utc') and datetime.fromisoformat(session['deadline_utc'])<=datetime.now(timezone.utc))
    label='STOPPED' if stopped else 'EXPIRED' if expired else session.get('status','STARTING')
    if not stopped and not expired and event:
        label=('AGENT_RUNNING' if event.get('status') in ['STUDY_START','STUDY_RUNNING']
               else 'AGENT_IDLE' if event.get('status') in ['AGENT_READY','AWAITING_NEXT_PACKAGE','RESULT_RETURNED']
               else event.get('status','AGENT_STATUS_UNKNOWN'))
        if age is None or age>=90:label='AGENT_LIVENESS_UNVERIFIED'
    return dict(runtime=str(runtime),session_status=label,
                live_agent=bool(not stopped and not expired and age is not None and age<90
                                and event.get('status') not in ['AGENT_STOPPED_BY_CONTROL','AGENT_EXPIRED']),
                heartbeat_age_seconds=round(age,1) if age is not None else None,
                event=event,deadline_utc=session.get('deadline_utc'),
                registration_required=not bool(event),
                bootstrap_file=str(runtime/'bootstrap.txt'),token_file=str(runtime/'token.txt'),
                public_route_verified=bool(session.get('public_health_verified')),
                startup_error=get('session_error.json'))


def start(a):
    LOCAL.mkdir(exist_ok=True)
    previous=LOCAL/'runtime.json'
    if previous.is_file():
        old=Path(json.loads(previous.read_text())['runtime'])
        if old.exists() and not (old/'session_stopped.json').exists():
            raise RuntimeError('Existing controller remains active; inspect status before starting another')
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    runtime=Path(os.environ.get('LOCALAPPDATA',str(Path.home())))/'TCAD_PRIVATE'/('gaa_background_'+stamp)
    if runtime.exists():raise FileExistsError('Session exists')
    exe=Path(a.cloudflared).resolve()
    command=[sys.executable,str(Path(__file__).with_name('start_session.py')),'--root',str(runtime),
             '--cloudflared',str(exe),'--seconds',str(a.seconds)]
    if a.ca_pem:command+=['--ca-pem',str(Path(a.ca_pem).resolve())]
    flags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
    log=LOCAL/('controller_'+stamp+'.console')
    with log.open('xb') as stream:
        proc=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=stream,stderr=subprocess.STDOUT,creationflags=flags)
    relay.write_json(previous,dict(runtime=str(runtime),controller_pid=proc.pid,ui_input_allowed=False))
    # Wait for startup only; never open an app or inject remote input.
    for _ in range(60):
        if (runtime/'session.json').is_file() or (runtime/'session_error.json').is_file() or proc.poll() is not None:break
        time.sleep(.5)
    print(json.dumps(state(runtime),ensure_ascii=False,indent=2))


def queue(a,runtime):
    if (runtime/'session_stopped.json').exists():raise RuntimeError('Controller stopped')
    queued=runtime/'queue.json'
    if queued.exists():
        old=json.loads(queued.read_text())['job']
        if not (runtime/'results'/(old+'.receipt.json')).is_file():
            raise RuntimeError('Previous queued job has not returned; refusing replacement')
    directory=LOCAL/'packages'/a.job
    directory.mkdir(parents=True,exist_ok=False)
    files=[STUDY/'python'/'run_study.py']
    config=dict(mode=a.mode,stage_timeout=a.stage_timeout,required={})
    if a.mode!='preflight':
        generator=STUDY/'python'/'generate.py'
        spec=importlib.util.spec_from_file_location('gaa_generate',generator)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        config['model_revision']='v2_explicit_common_gate'
        config['parameters']=module.PARAMETERS
        config['diagnostic_mesh_scale']=2 if a.mode=='smoke' else None
        config['linear_solver']=a.linear_solver
        config['mesh_style']=a.mesh_style
        config['processors']=a.processors
        config['quantum_mode']=a.quantum_mode
        config['gate_initialization']=a.gate_initialization
        deck=module.deck(module.PARAMETERS,fine=a.mode=='fine',smoke=a.mode=='smoke',linear_solver=a.linear_solver,mesh_style=a.mesh_style,processors=a.processors,quantum_mode=a.quantum_mode,gate_initialization=a.gate_initialization)
        name='gaa'
        deckpath=directory/(name+'.in');deckpath.write_text(deck,encoding='ascii',newline='\n');files.append(deckpath)
        outputs=['geometry.str','equilibrium.str','idvg_low.log','low_drain.dat','low_source.dat','low_gate.dat']
        if a.mode!='smoke':outputs+=['idvg_high.log','high_drain.dat','high_source.dat','high_gate.dat']
        config['required'][name]=outputs
    package=directory/'package.zip'
    with zipfile.ZipFile(package,'x',zipfile.ZIP_DEFLATED) as z:
        for f in files:z.write(f,f.name)
        z.writestr('config.json',json.dumps(config,indent=2))
    relay.publish(runtime,package,a.job)
    print(json.dumps(dict(job=a.job,mode=a.mode,package_sha256=relay.digest(package),
                         remote_execution='QUEUED_NOT_CONFIRMED',ui_input_used=False),indent=2))


def collect_archive(archive,receipt,destination):
    archive=Path(archive);destination=Path(destination)
    if hashlib.sha256(archive.read_bytes()).hexdigest()!=receipt['sha256']:raise ValueError('Archive transport hash mismatch')
    with zipfile.ZipFile(archive) as z:
        infos=z.infolist();names=[i.filename for i in infos]
        if len(set(names))!=len(names) or len(names)>2000:raise ValueError('Duplicate or excessive entries')
        if sum(i.file_size for i in infos)>512*1024*1024:raise ValueError('Oversized uncompressed result')
        for i in infos:
            path=PurePosixPath(i.filename)
            if i.is_dir() or path.is_absolute() or '..' in path.parts or '\\' in i.filename or ':' in i.filename or stat.S_ISLNK(i.external_attr>>16):
                raise ValueError('Unsafe result path')
        manifest=json.loads(z.read('output_hashes.json'))
        if set(names)!=(set(manifest)|{'output_hashes.json'}):raise ValueError('Manifest membership mismatch')
        for name,expected in manifest.items():
            if hashlib.sha256(z.read(name)).hexdigest()!=expected:raise ValueError('Member hash mismatch: '+name)
        destination.mkdir(parents=True,exist_ok=False)
        for i in infos:
            target=destination.joinpath(*PurePosixPath(i.filename).parts);target.parent.mkdir(parents=True,exist_ok=True)
            with target.open('xb') as stream:stream.write(z.read(i))
    record=dict(archive_sha256=receipt['sha256'],files_verified=len(manifest),transport_verified=True,
                simulator_success='REQUIRES_LOG_REVIEW',physical_validation='NOT_VALIDATED')
    relay.write_json(destination/'collection_verified.json',record)
    return record


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--runtime',type=Path)
    s=p.add_subparsers(dest='action',required=True)
    a=s.add_parser('start');a.add_argument('--cloudflared',type=Path,required=True);a.add_argument('--ca-pem',type=Path)
    a.add_argument('--seconds',type=int,default=14400)
    s.add_parser('status')
    a=s.add_parser('queue');a.add_argument('--job',required=True);a.add_argument('--mode',choices=['preflight','smoke','full','fine'],required=True);a.add_argument('--stage-timeout',type=int,default=4800)
    a.add_argument('--linear-solver',choices=['default','bicgst','direct'],default='default')
    a.add_argument('--mesh-style',choices=['isotropic','anisotropic'],default='isotropic')
    a.add_argument('--processors',type=int,choices=[1,2,4],default=1)
    a.add_argument('--quantum-mode',choices=['none','bqp'],default='none')
    a.add_argument('--gate-initialization',choices=['biased','equilibrium'],default='biased')
    a=s.add_parser('collect');a.add_argument('--job',required=True)
    s.add_parser('request-stop');s.add_parser('close')
    a=p.parse_args()
    if a.action=='start':return start(a)
    runtime=current(a.runtime)
    if a.action=='status':print(json.dumps(state(runtime),ensure_ascii=False,indent=2))
    elif a.action=='queue':
        if not relay.JOB.fullmatch(a.job):raise ValueError('Invalid job id')
        queue(a,runtime)
    elif a.action=='collect':
        if not relay.JOB.fullmatch(a.job):raise ValueError('Invalid job id')
        receipt=json.loads((runtime/'results'/(a.job+'.receipt.json')).read_text())
        record=collect_archive(runtime/'results'/(a.job+'.zip'),receipt,LOCAL/'collected'/a.job)
        print(json.dumps(record,indent=2))
    elif a.action=='request-stop':
        relay.write_json(runtime/'control.json',dict(stop=True));print('Stop requested for this agent only; inspect status and collect returned files.')
    elif a.action=='close':
        (runtime/'stop.request').write_text('Controller closure requested.\n');print('Relay closure requested; remote process state must be verified separately.')


if __name__=='__main__':main()

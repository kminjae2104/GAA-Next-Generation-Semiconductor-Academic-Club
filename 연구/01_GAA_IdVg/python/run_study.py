"""One GAA package runner. Only its own new directory and children are modified."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import signal
import subprocess
import time


def write(path, value):
    path = Path(path)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding='utf-8')
    temp.replace(path)


def retain_large_structures(root):
    """Preserve large raw structures beside results; return hashes instead of huge ZIPs."""
    root=Path(root).resolve()
    scope=root.parent if root.name=='results' or root.name.startswith('attempt_') else root.parent.parent
    retained=scope/'retained_structures'
    if root.name!='results':retained=retained/root.name
    retained.resolve().relative_to(scope.resolve())
    records=[]
    for source in sorted(root.rglob('*.str')):
        if source.is_symlink():raise ValueError('Symlink cannot be a retained raw structure')
        if source.stat().st_size<=8*1024*1024:continue
        relative=source.relative_to(root)
        target=retained/relative
        target.resolve().relative_to(scope.resolve())
        target.parent.mkdir(parents=True,exist_ok=True)
        if target.exists():raise FileExistsError('Preserve existing raw structure')
        digest=hashlib.sha256()
        with source.open('rb') as stream:
            for part in iter(lambda:stream.read(1024*1024),b''):digest.update(part)
        record=dict(original_result_path=relative.as_posix(),remote_preserved_path=str(target),
                    bytes=source.stat().st_size,sha256=digest.hexdigest(),
                    local_byte_verification='NOT_DOWNLOADED')
        source.replace(target)
        records.append(record)
    write(root/'retained_structures.json',records)


def run(argv, folder, timeout, env=None):
    folder.mkdir(parents=True, exist_ok=False)
    start = time.monotonic()
    with (folder / 'console.txt').open('xb') as stream:
        proc = subprocess.Popen(argv, cwd=str(folder), env=env, stdin=subprocess.DEVNULL,
                                stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
        timed_out = False
        try:
            proc.wait(timeout=max(1, timeout))
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(proc.pid, signal.SIGTERM)
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()
    status = dict(argv=argv, returncode=proc.returncode, timeout=timed_out,
                  seconds=round(time.monotonic()-start, 3))
    write(folder/'process.json', status)
    return status


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--max-seconds', type=int, default=None)
    args = p.parse_args()
    owned=[]
    if os.name=='posix':
        def terminate_owned(signum,frame):
            for child in owned:
                if child.poll() is not None:continue
                try:os.killpg(child.pid,signal.SIGTERM)
                except ProcessLookupError:continue
                try:child.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    try:os.killpg(child.pid,signal.SIGKILL)
                    except ProcessLookupError:pass
            raise SystemExit(128+signum)
        signal.signal(signal.SIGTERM,terminate_owned)
    root = args.output.resolve()
    code = Path(__file__).resolve().parent
    config = json.loads((code/'config.json').read_text())
    write(root/'run_config.json',config)
    end = time.monotonic()+args.max_seconds-30 if args.max_seconds is not None else float('inf')
    deckbuild = shutil.which('deckbuild') or '/users/tools/Silvaco/bin/deckbuild'
    envinfo = dict(utc=datetime.now(timezone.utc).isoformat(), mode=config['mode'],
                   deckbuild=deckbuild, executable=os.access(deckbuild, os.X_OK),
                   tool_paths={n: shutil.which(n) for n in ['devedit','devedit3d','atlas','lmutil']},
                   existing_processes=[])  # Process contents are read only, never stopped.
    ps = subprocess.run(['ps','-u',str(os.getuid()),'-o','pid,comm'], capture_output=True, text=True)
    envinfo['existing_processes'] = ps.stdout.splitlines()
    for key in ['SFLM','SFLM_SERVER','LM_LICENSE_FILE','SILVACO_LICENSE_FILE']:
        if os.environ.get(key): envinfo[key] = os.environ[key]
    # Record tool-tree entries to select installed binaries; never read license contents.
    base=Path('/users/tools/Silvaco')
    envinfo['tool_root_entries'] = sorted(x.name for x in base.iterdir()) if base.is_dir() else []
    if config['mode']=='preflight':
        mem={}
        if Path('/proc/meminfo').is_file():
            for line in Path('/proc/meminfo').read_text().splitlines():
                if line.startswith(('MemTotal:','MemAvailable:')):
                    key,value,*_=line.split();mem[key.rstrip(':')]=int(value)
        envinfo['available_resources']=dict(logical_cpus=os.cpu_count(),memory_kB=mem)
        examples=base/'examples';hints=[];examined=0
        if examples.is_dir():
            for example in examples.rglob('*.in'):
                if example.is_symlink() or example.stat().st_size>200000:continue
                examined+=1
                if examined>2500:break
                content=example.read_text(errors='replace')
                if 'bqp' not in content.lower():continue
                selected=[line[:250] for line in content.splitlines()
                          if any(s in line.lower() for s in ['go atlas','bqp','method ','qdir'])
                          or re.search(r'^\s*set\s+(gamma|alpha)\b',line,re.I)]
                item=dict(path=str(example),settings=selected[:15])
                if example.name=='quantumex08.in':
                    item['header']=content.splitlines()[:18]
                hints.append(item)
                if len(hints)>=12:break
        write(root/'installed_quantum_examples.json',dict(examined=examined,examples=hints))
    write(root/'environment.json', envinfo)
    write(root/'progress.json', dict(stage='PREFLIGHT', executable=envinfo['executable']))
    if not envinfo['executable']:
        write(root/'status.json', dict(status='NO_DECKBUILD', simulator_execution='NOT_RUN'))
        return 4
    decks = sorted(code.glob('*.in'))
    if not decks:
        # A preflight package deliberately does not end the persistent agent.
        write(root/'status.json', dict(status='PREFLIGHT_COMPLETE', simulator_execution='NOT_RUN'))
        return 3
    stage_results=[]
    for source in decks:
        stage = source.stem
        write(root/'progress.json', dict(stage=stage, status='RUNNING'))
        folder=root/stage
        # Explicitly create per-attempt workspace, refusing any old directory.
        folder.mkdir(exist_ok=False)
        for f in code.glob('*.in'): shutil.copy2(f, folder/f.name)
        # The runner's console capture lives in a separate child folder.
        execution=folder/'execution'
        execution.mkdir()
        for f in folder.glob('*.in'): shutil.copy2(f,execution/f.name)
        # Installed DeckBuild usage: -ascii -run <deck>; no legacy -as option.
        executable_cmd=[deckbuild,'-ascii','-run',source.name,'-outfile','solver.out']
        capture=folder/'capture'
        capture.mkdir()
        remaining=min(config.get('stage_timeout') or float('inf'),max(1,end-time.monotonic()))
        started=time.monotonic()
        with (execution/'console.txt').open('xb') as stream:
            proc=subprocess.Popen(executable_cmd,cwd=str(execution),stdin=subprocess.DEVNULL,
                                  stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
            owned.append(proc)
            timed_out=False
            stage_deadline=time.monotonic()+remaining
            while proc.poll() is None and time.monotonic()<stage_deadline:
                diagnostic=[]
                sizes={}
                last_solver_lines=[]
                last_bias=[]
                for log in [execution/'console.txt',execution/'solver.out']:
                    if log.is_file():
                        sizes[log.name]=log.stat().st_size
                        with log.open('rb') as tail:
                            tail.seek(max(0,sizes[log.name]-8192))
                            lines=tail.read().decode('utf-8',errors='replace').splitlines()
                        if log.name=='solver.out':
                            last_solver_lines=[s[:180] for s in lines if s.strip()][-4:]
                            last_bias=[s.strip()[:150] for s in lines if re.search(r'V\(.*\)\s*=',s)][-2:]
                        diagnostic.extend(s[:400] for s in lines if any(k in s.lower() for k in ['error','license','logged in','fatal','converg']))
                write(root/'progress.json',dict(stage=stage,status='RUNNING',
                      elapsed_seconds=round(time.monotonic()-started,1),
                      diagnostic_tail=diagnostic[-3:],last_solver_lines=last_solver_lines,last_bias=last_bias,output_sizes=sizes))
                try:proc.wait(timeout=min(5,max(.1,stage_deadline-time.monotonic())))
                except subprocess.TimeoutExpired:pass
            if proc.poll() is None:
                timed_out=True
                os.killpg(proc.pid,signal.SIGTERM)
                try: proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(proc.pid,signal.SIGKILL); proc.wait()
        texts='\n'.join(f.read_text(errors='replace') for f in execution.glob('*.out'))
        texts+='\n'+(execution/'console.txt').read_text(errors='replace')
        errors=[]
        fatal=[]
        for line in texts.splitlines():
            if any(s in line.lower() for s in ['error','license','not logged in','fatal','signal','converg']):
                errors.append(line[:500])
            if 'transport error: no error' not in line.lower() and any(s in line.lower() for s in ['error #','error:','syntax error','not logged in',
                                               'fatal','segmentation fault','failed to converge']):
                fatal.append(line[:500])
        required=config.get('required',{}).get(stage,[])
        missing=[n for n in required if not (execution/n).is_file() or (execution/n).stat().st_size==0]
        normal_finish=bool(re.search(r'ATLAS version[^\n]*finished',texts,re.I))
        license_diagnostics=[]
        # Keep license errors visible. With a normal finish and complete outputs,
        # a separate numerical validator decides whether the produced data is usable.
        if proc.returncode==0 and normal_finish and not missing:
            license_diagnostics=[s for s in fatal if 'sflm programmer error: this job is not logged in.' in s.lower()]
            fatal=[s for s in fatal if s not in license_diagnostics]
        result=dict(stage=stage,returncode=proc.returncode,timeout=timed_out,
                    seconds=round(time.monotonic()-started,3),missing=missing,
                    normal_atlas_finish=normal_finish,license_diagnostics=license_diagnostics,
                    diagnostic_lines=errors[-40:],fatal_lines=fatal[-20:],
                    outputs={f.name:f.stat().st_size for f in execution.iterdir() if f.is_file()})
        write(folder/'process.json',result); stage_results.append(result)
        # Nonempty output alone is never a success claim; local analysis is still required.
        if timed_out or proc.returncode!=0 or missing or fatal:
            retain_large_structures(root)
            write(root/'status.json',dict(status='EXECUTION_FAILED',stages=stage_results,
                                         physical_validation='NOT_VALIDATED'))
            return 5
        if time.monotonic()>=end: break
    retain_large_structures(root)
    hashes={f.relative_to(root).as_posix():hashlib.sha256(f.read_bytes()).hexdigest()
            for f in root.rglob('*') if f.is_file() and f.name!='hashes.json'}
    write(root/'hashes.json',hashes)
    write(root/'progress.json',dict(stage='OUTPUTS_COLLECTED',status='AWAITING_LOCAL_ANALYSIS'))
    write(root/'status.json',dict(status='OUTPUTS_COLLECTED',stages=stage_results,
                                 physical_validation='NOT_VALIDATED'))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

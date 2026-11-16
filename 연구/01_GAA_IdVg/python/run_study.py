"""One GAA package runner. Only its own new directory and children are modified."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
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
    p.add_argument('--max-seconds', type=int, required=True)
    args = p.parse_args()
    root = args.output.resolve()
    code = Path(__file__).resolve().parent
    config = json.loads((code/'config.json').read_text())
    write(root/'run_config.json',config)
    end = time.monotonic()+args.max_seconds-30
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
        executable_cmd=[deckbuild,'-run','-ascii','-as',source.name,'-outfile','solver.out']
        capture=folder/'capture'
        capture.mkdir()
        remaining=max(1,min(config.get('stage_timeout',240),int(end-time.monotonic())))
        started=time.monotonic()
        with (execution/'console.txt').open('xb') as stream:
            proc=subprocess.Popen(executable_cmd,cwd=str(execution),stdin=subprocess.DEVNULL,
                                  stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
            timed_out=False
            try: proc.wait(timeout=remaining)
            except subprocess.TimeoutExpired:
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
            if any(s in line.lower() for s in ['error #','error:','syntax error','not logged in',
                                               'fatal','segmentation fault','failed to converge']):
                fatal.append(line[:500])
        required=config.get('required',{}).get(stage,[])
        missing=[n for n in required if not (execution/n).is_file() or (execution/n).stat().st_size==0]
        result=dict(stage=stage,returncode=proc.returncode,timeout=timed_out,
                    seconds=round(time.monotonic()-started,3),missing=missing,
                    diagnostic_lines=errors[-40:],fatal_lines=fatal[-20:],
                    outputs={f.name:f.stat().st_size for f in execution.iterdir() if f.is_file()})
        write(folder/'process.json',result); stage_results.append(result)
        # Nonempty output alone is never a success claim; local analysis is still required.
        if timed_out or proc.returncode!=0 or missing or fatal:
            write(root/'status.json',dict(status='EXECUTION_FAILED',stages=stage_results,
                                         physical_validation='NOT_VALIDATED'))
            return 5
        if time.monotonic()>=end: break
    hashes={f.relative_to(root).as_posix():hashlib.sha256(f.read_bytes()).hexdigest()
            for f in root.rglob('*') if f.is_file() and f.name!='hashes.json'}
    write(root/'hashes.json',hashes)
    write(root/'progress.json',dict(stage='OUTPUTS_COLLECTED',status='AWAITING_LOCAL_ANALYSIS'))
    write(root/'status.json',dict(status='OUTPUTS_COLLECTED',stages=stage_results,
                                 physical_validation='NOT_VALIDATED'))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

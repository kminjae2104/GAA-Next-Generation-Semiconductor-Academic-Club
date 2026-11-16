"""Linux-side one-task agent, launched once in the existing MobaXterm session.

The relay token is held in memory, never passed in argv or written to output.
Only the fixed study entry point in an authenticated, hashed package is run.
"""
import getpass
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import signal
import ssl
import stat
import subprocess
import sys
import time
import urllib.request
import zipfile


def request(config, path, content=None, digest=None):
    headers = {'Authorization': 'Bearer ' + config['token']}
    if digest:
        headers['X-SHA256'] = digest
    req = urllib.request.Request(config['base_url'].rstrip('/') + path, data=content, headers=headers)
    last = None
    for attempt in range(3):
        try:
            context=ssl.create_default_context(cadata=config.get('ca_pem'))
            with urllib.request.urlopen(req, timeout=15, context=context) as response:
                return response.read()
        except (OSError, ValueError) as exc:
            last = exc
            if attempt < 2:
                time.sleep(2 ** attempt)
    raise RuntimeError('Relay request failed: ' + str(last))


def post_event(config, **value):
    request(config, '/event', json.dumps(value).encode('utf-8'))


def extract_package(content, destination):
    destination = Path(destination)
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        total, names = 0, set()
        members = archive.infolist()
        for info in members:
            name = PurePosixPath(info.filename)
            if (info.is_dir() or name.is_absolute() or '..' in name.parts or '\\' in info.filename
                    or ':' in info.filename or info.filename in names
                    or stat.S_ISLNK(info.external_attr >> 16)):
                raise ValueError('Unsafe/duplicate package entry')
            total += info.file_size
            names.add(info.filename)
            if total > 20 * 1024 * 1024 or len(names) > 200:
                raise ValueError('Code package exceeds limit')
        if 'run_study.py' not in names:
            raise ValueError('Missing fixed study entry point')
        destination.mkdir(parents=True, exist_ok=False)
        for info in members:
            target = destination.joinpath(*PurePosixPath(info.filename).parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('xb') as stream:
                stream.write(archive.read(info))


def make_result(root):
    root = Path(root)
    manifest = {}
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(root.rglob('*')):
            if path.is_symlink():
                raise ValueError('Symlink in result directory')
            if path.is_file():
                name = path.relative_to(root).as_posix()
                if name == 'output_hashes.json':
                    continue
                content = path.read_bytes()
                manifest[name] = hashlib.sha256(content).hexdigest()
                archive.writestr(name, content)
        archive.writestr('output_hashes.json', json.dumps(manifest, indent=2))
    content = buffer.getvalue()
    if len(content) > 64 * 1024 * 1024:
        raise ValueError('Result exceeds relay limit; remote files preserved')
    return content


def stop_own_process(proc):
    if proc.poll() is not None:
        return
    os.killpg(proc.pid, signal.SIGTERM)
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        proc.wait()


def run_package(config,descriptor,end):
    job=descriptor['job']
    if not re.fullmatch(r'[a-zA-Z0-9_-]{1,80}', job):
        raise ValueError('Invalid job ID')
    content = request(config, '/package/' + job)
    if hashlib.sha256(content).hexdigest() != descriptor['sha256']:
        raise ValueError('Downloaded package SHA256 mismatch')
    root = Path.home() / 'gaa_tcad_runs' / job
    if root.exists():
        raise ValueError('Existing job directory; refuse duplicate execution')
    root.mkdir(parents=True, mode=0o700)
    package, output = root / 'code', root / 'results'
    extract_package(content, package)
    output.mkdir()
    (output/'input_provenance.json').write_text(json.dumps(dict(job=job,
        package_sha256=descriptor['sha256'],host=platform.node(),user=getpass.getuser(),
        python=sys.version,entry_point='run_study.py')),encoding='utf-8')
    timeout = max(1, int(end - time.monotonic()))
    post_event(config, status='STUDY_START', job=job, root=str(root))
    command = [sys.executable, str(package / 'run_study.py'), '--output', str(output),
               '--max-seconds', str(timeout)]
    with (output / 'worker.console').open('xb') as stream:
        proc = subprocess.Popen(command, cwd=str(package), stdin=subprocess.DEVNULL,
                                stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            while proc.poll() is None and time.monotonic() < end:
                try:
                    if json.loads(request(config, '/control')).get('stop'):
                        post_event(config, status='STOPPING_OWN_JOB', job=job)
                        break
                    progress_path=output/'progress.json'
                    progress=json.loads(progress_path.read_text()) if progress_path.is_file() else {}
                    post_event(config, status='STUDY_RUNNING', job=job,progress=progress)
                except RuntimeError:
                    pass  # Transport failures must not resubmit or alter the study.
                time.sleep(min(15, max(0, end - time.monotonic())))
        finally:
            stop_own_process(proc)
    (output / 'agent_exit.json').write_text(json.dumps(dict(returncode=proc.returncode)), encoding='utf-8')
    result = make_result(output)
    request(config, '/result/' + job, result, hashlib.sha256(result).hexdigest())
    post_event(config, status='RESULT_RETURNED', job=job, returncode=proc.returncode)
    print('Result returned to the originating PC. Study exit code: ' + str(proc.returncode), flush=True)
    return proc.returncode


def main(config):
    if os.name != 'posix':
        raise ValueError('Run the agent inside the Linux MobaXterm SSH session')
    if not re.fullmatch(r'https://[a-z0-9.-]+(?::[0-9]+)?', config['base_url']):
        raise ValueError('A verified HTTPS relay URL is required')
    if not re.fullmatch(r'[0-9a-f]{64}', config['token']):
        raise ValueError('Invalid task token')
    lifetime=min(86400,int(config.get('max_session_seconds',21600)))
    if config.get('deadline_utc'):
        left=(datetime.fromisoformat(config['deadline_utc'])-datetime.now(timezone.utc)).total_seconds()
        if left<=0:
            print('Session deadline already passed; no remote work started.',flush=True)
            return 2
        lifetime=min(lifetime,left)
    end=time.monotonic()+lifetime
    post_event(config,status='AGENT_READY',hostname=platform.node(),user=getpass.getuser(),
               python=sys.version,executable=sys.executable,
               deckbuild_exists=os.access('/users/tools/Silvaco/bin/deckbuild',os.X_OK))
    print('Agent connected. Session lifetime seconds: '+str(int(lifetime)),flush=True)
    seen=set();last_heartbeat=0
    while time.monotonic()<end:
        try:
            if json.loads(request(config,'/control')).get('stop'):
                post_event(config,status='AGENT_STOPPED_BY_CONTROL')
                return 0
            descriptor=json.loads(request(config,'/next').decode('utf-8'))
            job=descriptor.get('job')
            if job and job not in seen:
                seen.add(job)
                rc=run_package(config,descriptor,end)
                if rc==0 and descriptor.get('final',False):return 0
                post_event(config,status='AWAITING_NEXT_PACKAGE',previous_job=job,returncode=rc)
            if time.monotonic()-last_heartbeat>=30:
                post_event(config,status='AGENT_HEARTBEAT',agent_pid=os.getpid(),completed_or_seen_jobs=len(seen))
                last_heartbeat=time.monotonic()
        except RuntimeError:
            print('Temporary transport failure; retrying existing connection.',flush=True)
        time.sleep(min(15,max(0,end-time.monotonic())))
    print('Agent deadline reached. Remote artifacts preserved.',flush=True)
    return 2


if __name__ == '__main__':
    if sys.argv[1:]==['--stdin-config']:
        BOOTSTRAP_CONFIG=json.load(sys.stdin)
        sys.stdin.close()
    if 'BOOTSTRAP_CONFIG' not in globals():
        raise SystemExit('Use the reviewed bootstrap command; no credentials in CLI arguments.')
    sys.exit(main(BOOTSTRAP_CONFIG))

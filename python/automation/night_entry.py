"""Handoff transport and detach a finite recovery plan; never alter old simulations."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--max-seconds')
    a = p.parse_args()
    code = Path(__file__).resolve().parent
    config = json.loads((code/'connection.json').read_text())
    assert hashlib.sha256((code/'agent.py').read_bytes()).hexdigest() == config.pop('agent_sha256')
    with (a.output/'connection.console').open('xb') as log:
        agent = subprocess.Popen([sys.executable, str(code/'agent.py'), '--stdin-config'],
            stdin=subprocess.PIPE, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    agent.stdin.write(json.dumps(config).encode()); agent.stdin.close()
    with (a.output/'night.console').open('xb') as log:
        daemon = subprocess.Popen([sys.executable, str(code/'night_supervisor.py'),
            '--output', str(a.output.parent/'durable')], stdin=subprocess.DEVNULL,
            stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    time.sleep(1)
    (a.output/'handoff.json').write_text(json.dumps(dict(agent_pid=agent.pid,
        supervisor_pid=daemon.pid, supervisor_alive=daemon.poll() is None,
        deadline_utc=config['deadline_utc'], detached=True, old_simulations_changed=False)))
    (a.output/'status.json').write_text(json.dumps(dict(status='NIGHT_HANDOFF', stages=[])))


if __name__ == '__main__':
    main()

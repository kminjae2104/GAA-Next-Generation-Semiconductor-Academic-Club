"""One-time local relay reload for the explicitly authorized public transition.

Preserves the runtime, token, queue and remote agent/solver jobs. No desktop input.
Only processes whose command lines match this GAA runtime are eligible to stop.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'python/automation'))
import control
import relay


def processes(runtime):
    # The environment variable is data, never interpolated as PowerShell source.
    script = "$r=$env:GAA_TRANSITION_RUNTIME; @(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and $_.CommandLine.Contains($r) } | Select-Object ProcessId,ParentProcessId,Name,CommandLine) | ConvertTo-Json -Compress"
    result = subprocess.run(['powershell', '-NoProfile', '-Command', script], env=dict(os.environ, GAA_TRANSITION_RUNTIME=str(runtime)), capture_output=True, text=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
    value = json.loads(result.stdout or '[]')
    return value if isinstance(value, list) else [value]


def health(url, token=None):
    request = urllib.request.Request(url+'/health', headers={'Authorization': 'Bearer '+token} if token else {})
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            return response.status, json.load(response).get('ready', False)
    except urllib.error.HTTPError as exc:
        return exc.code, False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if os.name != 'nt':
        raise RuntimeError('Windows-only local migration')
    runtime = control.current(None).resolve()
    private_root = (Path(os.environ['LOCALAPPDATA']) / 'TCAD_PRIVATE').resolve()
    if not runtime.is_relative_to(private_root):
        raise RuntimeError('Unexpected credential runtime')
    if (runtime/'stop.request').exists() or (runtime/'session_stopped.json').exists():
        raise RuntimeError('Explicit stop must not be overridden')
    script_path = ROOT / 'python/automation/resilient_relay.py'
    found = processes(runtime)
    controllers = [p for p in found if str(script_path).lower() in p['CommandLine'].lower()]
    if len(controllers) != 1:
        raise RuntimeError('Expected exactly one GAA relay controller')
    controller_id = controllers[0]['ProcessId']
    children = [p for p in found if p['ParentProcessId'] == controller_id and (
        str(ROOT / 'python/automation/relay.py').lower() in p['CommandLine'].lower() or
        str(ROOT / 'python/automation/keep_awake.py').lower() in p['CommandLine'].lower())]
    # cloudflared has no runtime argument; select it by verified parent and exact configured executable.
    settings = json.loads((runtime/'route_settings.json').read_text())
    expected_cf = str(Path(settings['cloudflared']).resolve())
    cf_script = "$p=Get-CimInstance Win32_Process | Where-Object { $_.ParentProcessId -eq [int]$env:GAA_TRANSITION_PARENT -and $_.ExecutablePath -eq $env:GAA_TRANSITION_CF }; @($p | Select-Object ProcessId) | ConvertTo-Json -Compress"
    cf_result = subprocess.run(['powershell', '-NoProfile', '-Command', cf_script], env=dict(os.environ, GAA_TRANSITION_PARENT=str(controller_id), GAA_TRANSITION_CF=expected_cf), capture_output=True, text=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
    cf = json.loads(cf_result.stdout or '[]'); cf = cf if isinstance(cf, list) else [cf]
    ids = [controller_id] + [p['ProcessId'] for p in children] + [p['ProcessId'] for p in cf]
    if not args.apply:
        print(json.dumps(dict(mode='PREFLIGHT_ONLY', matched_local_processes=ids, remote_processes_touched=False))); return
    if args.out.exists():
        raise FileExistsError('Use a fresh verification report path')
    before_token_hash = relay.digest(runtime/'token.txt')
    queue = (runtime/'queue.json').read_bytes() if (runtime/'queue.json').exists() else None
    settings['allow_public_discovery'] = True
    relay.write_json(runtime/'route_settings.json', settings)
    # Controller first: prevents it from replacing a child during the handoff.
    for pid in ids:
        subprocess.run(['powershell', '-NoProfile', '-Command', f'Stop-Process -Id {int(pid)} -Force -ErrorAction SilentlyContinue'], capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
    started = datetime.now(timezone.utc)
    with (runtime/'public_transition.console').open('ab') as log:
        process = subprocess.Popen([sys.executable, str(script_path), '--root', str(runtime)], stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
    relay.write_json(ROOT/'.local/runtime.json', dict(runtime=str(runtime), controller_pid=process.pid, ui_input_allowed=False))
    report = dict(started_utc=started.isoformat(), controller_pid=process.pid,
                  replaced_local_processes=ids, remote_processes_touched=False,
                  token_preserved=before_token_hash == relay.digest(runtime/'token.txt'),
                  queue_preserved=queue == ((runtime/'queue.json').read_bytes() if (runtime/'queue.json').exists() else None),
                  public_discovery_opt_in=True, scheduled_expiry=None)
    # Connectivity verification only; does not wait for any TCAD computation.
    token = (runtime/'token.txt').read_text().strip()
    end = time.monotonic()+150
    while time.monotonic() < end:
        if process.poll() is not None:
            raise RuntimeError('Replacement relay exited; inspect private transition console')
        try:
            session = json.loads((runtime/'session.json').read_text())
            event = json.loads((runtime/'latest_event.json').read_text())
            received = datetime.fromisoformat(event['received_utc'])
            if session['server_pid'] not in ids and received > started:
                authenticated, ready = health(session['base_url'], token)
                unauthenticated, _ = health(session['base_url'])
                report.update(checked_utc=datetime.now(timezone.utc).isoformat(),
                              authenticated_http=authenticated, ready=ready,
                              unauthenticated_http=unauthenticated,
                              agent_event=event.get('status'), agent_received_utc=event['received_utc'],
                              deadline_utc=session.get('deadline_utc'))
                if authenticated == 200 and ready and unauthenticated == 401:
                    break
        except (OSError, ValueError, KeyError):
            pass
        time.sleep(2)
    else:
        report['verification'] = 'CONNECTIVITY_NOT_CONFIRMED_WITHIN_CHECK_WINDOW'
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(report, stream, indent=2); stream.write('\n')
    print(json.dumps(report))
    if not report.get('ready'):
        raise SystemExit(1)


if __name__ == '__main__':
    main()

"""Authenticated, loopback-only TCAD file relay; stdlib, no general shell API.

Public tunneling is a separate, explicitly authorized action. This module never
starts a tunnel, changes firewall rules, or installs a service.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import secrets
import threading
import time
import os
import tempfile

JOB = re.compile(r'[a-zA-Z0-9_-]{1,80}')
MAX_RESULT = 64 * 1024 * 1024


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def write_json(path, value):
    path = Path(path)
    fd, name = tempfile.mkstemp(prefix=path.name+'.', suffix='.tmp', dir=path.parent)
    temp = Path(name)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as stream:
            json.dump(value, stream, indent=2)
            stream.write('\n')
        for attempt in range(8):
            try:
                temp.replace(path)
                break
            except PermissionError:
                if attempt == 7: raise
                time.sleep(.05 * (attempt+1))
    finally:
        temp.unlink(missing_ok=True)


class Relay(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, root, port, seconds):
        self.root = Path(root).resolve()
        self.token = (self.root / 'token.txt').read_text(encoding='ascii').strip()
        self.end = time.monotonic() + seconds if seconds else float('inf')
        self.wall_end = time.time() + seconds if seconds else float('inf')
        self.lock = threading.Lock()
        super().__init__(('127.0.0.1', port), Handler)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # Never log Authorization or URLs containing credentials.

    def authenticated(self):
        if time.monotonic() >= self.server.end or time.time() >= self.server.wall_end:
            self.send_error(410)
            return False
        expected = 'Bearer ' + self.server.token
        if not hmac.compare_digest(self.headers.get('Authorization', ''), expected):
            self.send_error(401)
            return False
        return True

    def respond(self, body, content_type='application/json'):
        self.send_response(200)
        self.send_header('Content-Type', content_type)
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if not self.authenticated():
            return
        root = self.server.root
        if self.path == '/health':
            return self.respond(b'{"service":"gaa-tcad-relay","ready":true}')
        if self.path == '/agent':
            return self.respond((root / 'agent.py').read_bytes(), 'text/x-python')
        if self.path == '/next':
            queue = root / 'queue.json'
            return self.respond(queue.read_bytes() if queue.exists() else b'{"job":null}')
        if self.path == '/control':
            control = root / 'control.json'
            return self.respond(control.read_bytes() if control.exists() else b'{"stop":false}')
        match = re.fullmatch(r'/package/([a-zA-Z0-9_-]{1,80})', self.path)
        if match:
            package = root / 'packages' / (match[1] + '.zip')
            if package.is_file():
                return self.respond(package.read_bytes(), 'application/zip')
        self.send_error(404)

    def do_POST(self):
        if not self.authenticated():
            return
        try:
            length = int(self.headers.get('Content-Length', '-1'))
        except ValueError:
            return self.send_error(400)
        event = self.path == '/event'
        match = re.fullmatch(r'/result/([a-zA-Z0-9_-]{1,80})', self.path)
        if not event and not match:
            return self.send_error(404)
        if not 0 <= length <= (65536 if event else MAX_RESULT):
            return self.send_error(413)
        content = self.rfile.read(length)
        if len(content) != length:
            return self.send_error(400)
        root = self.server.root
        if event:
            try:
                value = json.loads(content.decode('utf-8'))
            except (ValueError, UnicodeError):
                return self.send_error(400)
            if not isinstance(value, dict):
                return self.send_error(400)
            value['received_utc'] = datetime.now(timezone.utc).isoformat()
            with self.server.lock:
                with (root / 'events.jsonl').open('a', encoding='utf-8') as stream:
                    stream.write(json.dumps(value) + '\n')
                write_json(root / 'latest_event.json', value)
            return self.respond(b'{"stored":true}')
        queue = root / 'queue.json'
        if not queue.is_file() or json.loads(queue.read_text())['job'] != match[1]:
            return self.send_error(409)
        actual = hashlib.sha256(content).hexdigest()
        if not hmac.compare_digest(actual, self.headers.get('X-SHA256', '')):
            return self.send_error(400)
        target = root / 'results' / (match[1] + '.zip')
        with self.server.lock:
            if target.exists():
                if digest(target) != actual:
                    return self.send_error(409)
            else:
                with target.open('xb') as stream:
                    stream.write(content)
                write_json(target.with_suffix('.receipt.json'), dict(job=match[1], sha256=actual,
                           transport_verified=True, scientific_validation='PENDING_LOCAL_ANALYSIS'))
        return self.respond(b'{"stored":true}')


def initialize(root):
    root = Path(root).resolve()
    if any((p / '.git').exists() for p in [root] + list(root.parents)):
        raise ValueError('Relay runtime and credentials must be outside Git')
    root.mkdir(parents=True, exist_ok=False)
    (root / 'packages').mkdir()
    (root / 'results').mkdir()
    with (root / 'token.txt').open('x', encoding='ascii') as stream:
        stream.write(secrets.token_hex(32))
    (root / 'agent.py').write_bytes(Path(__file__).with_name('agent.py').read_bytes())
    write_json(root / 'state.json', dict(status='PREPARED_LOCAL_ONLY', public_tunnel_started=False))


def serve(root, port, seconds):
    if seconds < 0:
        raise ValueError('Relay lifetime must be nonnegative; zero means unlimited')
    server = Relay(root, port, seconds)
    write_json(Path(root) / 'state.json', dict(status='LISTENING_LOOPBACK_ONLY',
               address=server.server_address[0], port=server.server_address[1], seconds=seconds))
    timer = threading.Timer(seconds, server.shutdown) if seconds else None
    if timer:
        timer.daemon = True
        timer.start()
    try:
        server.serve_forever(poll_interval=0.5)
    finally:
        if timer: timer.cancel()
        server.server_close()
        write_json(Path(root) / 'state.json', dict(status='STOPPED'))


def publish(root, package, job):
    root, package = Path(root), Path(package)
    if not JOB.fullmatch(job):
        raise ValueError('Invalid job ID')
    target = root / 'packages' / (job + '.zip')
    with target.open('xb') as stream:
        stream.write(package.read_bytes())
    write_json(root / 'queue.json', dict(job=job, sha256=digest(target)))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='action', required=True)
    for action in ['init', 'serve', 'publish']:
        q = sub.add_parser(action)
        q.add_argument('--root', type=Path, required=True)
        if action == 'serve':
            q.add_argument('--port', type=int, default=0)
            q.add_argument('--seconds', type=int, default=0)
        if action == 'publish':
            q.add_argument('--package', type=Path, required=True)
            q.add_argument('--job', required=True)
    a = p.parse_args()
    if a.action == 'init':
        initialize(a.root)
    elif a.action == 'serve':
        serve(a.root, a.port, a.seconds)
    else:
        publish(a.root, a.package, a.job)


if __name__ == '__main__':
    main()

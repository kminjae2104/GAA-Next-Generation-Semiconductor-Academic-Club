"""Export the root from a successfully verified live TLS chain; retain verification."""
import hashlib,json,socket,ssl,urllib.request
from urllib.parse import urlparse
from pathlib import Path
import control,relay,start_session

def main():
    runtime=control.current(None);session=json.loads((runtime/'session.json').read_text())
    host=urlparse(session['base_url']).hostname
    with ssl.create_default_context().wrap_socket(socket.create_connection((host,443),timeout=15),server_hostname=host) as conn:
        # Windows Python 3.11 exposes the verified chain on its OpenSSL socket.
        chain=conn._sslobj.get_verified_chain()
        root=chain[-1];info=root.get_info();pem=root.public_bytes()
        if info['subject']!=info['issuer']:raise ValueError('Verified chain did not end in a root')
    context=ssl.create_default_context(cadata=pem)
    request=urllib.request.Request(session['base_url']+'/health',headers={'Authorization':'Bearer '+(runtime/'token.txt').read_text().strip()})
    with urllib.request.urlopen(request,context=context,timeout=15) as response:
        if not json.load(response)['ready']:raise ValueError('Public route not ready')
    ca=runtime/'task_root_ca.pem'
    with ca.open('x',encoding='ascii') as f:f.write(pem)
    command=start_session.bootstrap_command(session['base_url'],relay.digest(runtime/'agent.py'),pem,session.get('deadline_utc'))
    path=runtime/'bootstrap_ca_verified.txt'
    with path.open('x',encoding='ascii') as f:f.write(command+'\n')
    relay.write_json(runtime/'ca_verification.json',dict(root_subject=info['subject'],sha256_der=hashlib.sha256(ssl.PEM_cert_to_DER_cert(pem)).hexdigest(),live_tls_chain_verified=True,public_authenticated_health_verified_with_exported_ca=True,bootstrap_file=str(path),deadline_utc=session.get('deadline_utc')))
    print(json.dumps(dict(bootstrap_file=str(path),root_subject=info['subject'],tls_verified=True,deadline_utc=session.get('deadline_utc'))))

if __name__=='__main__':main()

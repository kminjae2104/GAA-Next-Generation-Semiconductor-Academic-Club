"""Publish a signed endpoint manifest; public discovery requires explicit opt-in."""
import base64,hashlib,hmac,json,os,re,subprocess,time,urllib.request,urllib.error
REPO='kminjae2104/GAA-Next-Generation-Semiconductor-Academic-Club'
BRANCH='gaa-agent-rendezvous'

def api(path,data=None,method=None):
    r=subprocess.run(['git','credential','fill'],input='protocol=https\nhost=github.com\n\n',text=True,capture_output=True,env=dict(os.environ,GCM_INTERACTIVE='Never',GIT_TERMINAL_PROMPT='0'),timeout=30)
    credentials=dict(x.split('=',1) for x in r.stdout.splitlines() if '=' in x)
    if not credentials.get('password'):raise RuntimeError('Noninteractive GitHub credential unavailable')
    request=urllib.request.Request('https://api.github.com'+path,data=json.dumps(data).encode() if data is not None else None,method=method,headers={'Authorization':'Bearer '+credentials['password'],'Accept':'application/vnd.github+json','Content-Type':'application/json'})
    with urllib.request.urlopen(request,timeout=30) as response:return json.load(response)

def signed_manifest(url,key,sequence=None):
    if not re.fullmatch(r'https://[a-z0-9-]+\.trycloudflare\.com',url):raise ValueError('Invalid discovery endpoint')
    if not re.fullmatch(r'[a-fA-F0-9]{64}',key):raise ValueError('Invalid discovery key')
    payload=dict(base_url=url,sequence=sequence or time.time_ns(),protocol='gaa-discovery-v1')
    raw=json.dumps(payload,sort_keys=True,separators=(',',':')).encode()
    return dict(payload=payload,signature=hmac.new(bytes.fromhex(key),raw,hashlib.sha256).hexdigest())

def publish(url,key,allow_public=False):
    # Construct a fixed schema locally: never publish runtime settings or auth keys.
    value=signed_manifest(url,key)
    if not api('/repos/'+REPO)['private'] and allow_public is not True:raise RuntimeError('Public discovery requires explicit opt-in')
    refpath='/repos/'+REPO+'/git/refs/heads/'+BRANCH
    try:parent=api('/repos/'+REPO+'/git/ref/heads/'+BRANCH)['object']['sha']
    except urllib.error.HTTPError as exc:
        if exc.code!=404:raise
        parent=None
    blob=api('/repos/'+REPO+'/git/blobs',dict(content=base64.b64encode(json.dumps(value).encode()).decode(),encoding='base64'))['sha']
    tree=api('/repos/'+REPO+'/git/trees',dict(tree=[dict(path='endpoint.json',mode='100644',type='blob',sha=blob)]))['sha']
    commit=api('/repos/'+REPO+'/git/commits',dict(message='Update signed GAA relay endpoint',tree=tree,parents=[parent] if parent else []))['sha']
    if parent:api(refpath,dict(sha=commit,force=False),'PATCH')
    else:api('/repos/'+REPO+'/git/refs',dict(ref='refs/heads/'+BRANCH,sha=commit))
    return dict(commit=commit,sequence=value['payload']['sequence'],branch=BRANCH)

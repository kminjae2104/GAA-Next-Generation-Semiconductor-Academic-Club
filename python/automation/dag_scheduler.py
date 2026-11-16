"""Dependency scheduler with optional time limits. No desktop APIs or model calls."""
import argparse
import concurrent.futures as futures
import json
import hashlib
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time


def validate(plan):
    tasks=plan['tasks'];ids=[t['id'] for t in tasks]
    if not tasks or len(ids)!=len(set(ids)):raise ValueError('Empty/duplicate task IDs')
    if not 1<=plan.get('max_parallel',3)<=3:raise ValueError('Maximum parallelism is three')
    for t in tasks:
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',t['id']):raise ValueError('Unsafe task ID')
        if not set(t.get('after',[]))<=set(ids):raise ValueError('Unknown dependency')
        limit=t.get('timeout_seconds')
        if limit is not None and (not isinstance(limit,(int,float)) or limit<=0):raise ValueError('Invalid task time limit')
        for cmd in [t['command']]+t.get('checks',[]):
            if not isinstance(cmd,list) or not cmd or not all(isinstance(x,str) for x in cmd):raise ValueError('Use argv arrays')
    remaining={t['id']:set(t.get('after',[])) for t in tasks};done=set()
    while remaining:
        ready={k for k,v in remaining.items() if v<=done}
        if not ready:raise ValueError('Dependency cycle')
        done|=ready;remaining={k:v for k,v in remaining.items() if k not in ready}


def write(path,value):
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(value,indent=2),encoding='utf-8');temp.replace(path)


def run_plan(plan,base,output,budget_seconds=None):
    validate(plan);base=Path(base).resolve();output=Path(output).resolve();output.mkdir(parents=True,exist_ok=True)
    states={t['id']:{'status':'PENDING'} for t in plan['tasks']};running={};processes={}
    end=time.monotonic()+budget_seconds if budget_seconds is not None else float('inf')
    def stop_owned(*unused):
        for proc in list(processes.values()):
            if proc.poll() is None:proc.terminate()
    old=None
    if os.name=='posix':old=signal.signal(signal.SIGTERM,lambda *a:(stop_owned(),sys.exit(143)))
    def execute(task):
        name=task['id'];folder=output/name;folder.mkdir(exist_ok=False)
        if task.get('input_sha256'):
            source=(base/task['input_file']).resolve();source.relative_to(base)
            if hashlib.sha256(source.read_bytes()).hexdigest()!=task['input_sha256']:raise ValueError('Input deck hash changed')
        mapping={'{python}':sys.executable,'{base}':str(base),'{output}':str(folder)}
        mapping.update({'{dependency:'+d+'}':str(output/d) for d in task.get('after',[])})
        def argv(cmd):
            result=[]
            for arg in cmd:
                for key,value in mapping.items():arg=arg.replace(key,value)
                result.append(arg)
            return result
        limit=min(task.get('timeout_seconds') or float('inf'),max(0,end-time.monotonic()))
        deadline=time.monotonic()+limit;timed_out=False;rc=-1
        with (folder/'scheduler_console.txt').open('xb') as log:
            for command in [task['command']]+task.get('checks',[]):
                if time.monotonic()>=deadline:timed_out=True;break
                proc=subprocess.Popen(argv(command),cwd=str(base),stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,
                    start_new_session=os.name=='posix',creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
                processes[name]=proc
                try:rc=proc.wait(timeout=None if deadline==float('inf') else max(.01,deadline-time.monotonic()))
                except subprocess.TimeoutExpired:
                    timed_out=True;proc.terminate()
                    try:proc.wait(timeout=10)
                    except subprocess.TimeoutExpired:proc.kill();proc.wait()
                    rc=proc.returncode
                if timed_out or rc!=0:break
        processes.pop(name,None)
        return dict(status='SUCCEEDED' if rc==0 and not timed_out else 'TIMED_OUT' if timed_out else 'FAILED',
                    returncode=rc,timeout=timed_out,finished=time.time())
    try:
        with futures.ThreadPoolExecutor(max_workers=plan.get('max_parallel',3)) as pool:
            while True:
                for task in plan['tasks']:
                    name=task['id'];deps=task.get('after',[])
                    if states[name]['status']!='PENDING':continue
                    if any(states[d]['status'] in ['FAILED','TIMED_OUT','BLOCKED','DEADLINE'] for d in deps):
                        states[name]={'status':'BLOCKED','reason':'Dependency did not pass validation'}
                    elif time.monotonic()>=end:states[name]={'status':'DEADLINE'}
                    elif all(states[d]['status']=='SUCCEEDED' for d in deps) and len(running)<plan.get('max_parallel',3):
                        states[name]={'status':'RUNNING','started':time.time()};running[pool.submit(execute,task)]=name
                snapshot={name:dict(state,worker_pid=proc.pid) if (proc:=processes.get(name)) is not None else dict(state)
                          for name,state in states.items()}
                write(output/'progress.json',dict(stage='DEPENDENCY_WORKFLOW',tasks=snapshot))
                if not running:
                    if all(v['status']!='PENDING' for v in states.values()):break
                    continue
                completed,_=futures.wait(running,timeout=.25,return_when=futures.FIRST_COMPLETED)
                for future in completed:
                    name=running.pop(future)
                    try:states[name].update(future.result())
                    except Exception as error:states[name].update(status='FAILED',error=str(error),finished=time.time())
        success=all(s['status']=='SUCCEEDED' for s in states.values())
        write(output/'workflow_status.json',dict(tasks=states,all_succeeded=success,physical_validation='NOT_VALIDATED'))
        write(output/'status.json',dict(status='WORKFLOW_COMPLETED' if success else 'WORKFLOW_FAILED',physical_validation='NOT_VALIDATED',
            stages=[dict(stage=name,returncode=s.get('returncode',-1),timeout=s['status'] in ['TIMED_OUT','DEADLINE'],seconds=round(s.get('finished',0)-s.get('started',0),2) if s.get('finished') else None,
                         missing=[],fatal_lines=[s.get('error',s.get('reason',s['status']))] if s['status']!='SUCCEEDED' else []) for name,s in states.items()]))
        return states
    finally:
        stop_owned()
        if old is not None:signal.signal(signal.SIGTERM,old)


def main():
    p=argparse.ArgumentParser();p.add_argument('--plan',type=Path,default=Path(__file__).with_name('workflow.json'))
    p.add_argument('--output',type=Path,required=True);p.add_argument('--max-seconds',type=int,default=None);a=p.parse_args()
    states=run_plan(json.loads(a.plan.read_text()),a.plan.parent,a.output,None if a.max_seconds is None else max(1,a.max_seconds-20))
    return 0 if all(s['status']=='SUCCEEDED' for s in states.values()) else 5


if __name__=='__main__':raise SystemExit(main())

"""Prepare 34 distinct decks and an unattended, detached three-slot workflow."""
from datetime import datetime,timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import zipfile
from dag_scheduler import validate


def main():
    root=Path(__file__).resolve().parents[2];study=root/'연구'/'01_GAA_IdVg'
    spec=importlib.util.spec_from_file_location('generate',study/'python'/'generate.py')
    g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
    name='gaa_overnight_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    local=root/'.local'/name;local.mkdir(parents=True,exist_ok=False)
    decks=study/'tcad'/name;decks.mkdir(exist_ok=False)
    tasks=[];cases=[]
    def add(variant,solver,initial,stage,after=None,wf=4.5,quantum='none'):
        params=dict(g.PARAMETERS,workfunction_eV=wf)
        mode='smoke' if stage=='smoke' else 'fine' if stage=='fine' else 'full'
        scale={'smoke':2,'screen':2,'full':1,'fine':.5}[stage]
        task_id=variant+'_'+stage
        data=g.deck(params,smoke=mode=='smoke',fine=mode=='fine',linear_solver=solver,
            mesh_style='anisotropic',processors=4,quantum_mode=quantum,gate_initialization=initial,mesh_scale=scale)
        config=dict(mode=mode,stage_timeout=None,required={'gaa':['geometry.str','equilibrium.str','idvg_low.log','low_drain.dat','low_source.dat','low_gate.dat']+
            ([] if mode=='smoke' else ['idvg_high.log','high_drain.dat','high_source.dat','high_gate.dat'])},
            parameters=params,linear_solver=solver,mesh_style='anisotropic',processors=4,quantum_mode=quantum,gate_initialization=initial,
            mesh_scale=scale,diagnostic_mesh=scale==2,engineering_targets_unchanged=True)
        digest=hashlib.sha256(data.encode()).hexdigest()
        (decks/(task_id+'.in')).write_text(data,encoding='utf-8',newline='\n')
        (decks/(task_id+'.json')).write_text(json.dumps(dict(config,sha256=digest,simulator_execution='NOT_RUN'),indent=2))
        tasks.append(dict(id=task_id,after=[after] if after else [],timeout_seconds=None,
            command=['{python}','{base}/run_case.py','--worker','{base}/'+task_id+'/worker.py','--output','{output}'],
            checks=[['{python}','{base}/validate_case.py','{output}','--mode',mode]],
            input_file=task_id+'/gaa.in',input_sha256=digest,mesh_scale=scale,variant=variant))
        if stage in ['full','fine']:
            tasks[-1]['checks'][0]+= ['--compare','{dependency:'+after+'}']
        cases.append((task_id,data,config));return task_id
    variants=[('eq_bicgst','bicgst','equilibrium'),('bias_direct','direct','biased'),('bias_bicgst','bicgst','biased'),
        ('eq_direct','direct','equilibrium'),('eq_default','default','equilibrium'),('bias_default','default','biased')]
    # All short numerical probes have priority, then fast full-range screens, then mesh refinement.
    parents={v:add(v,s,i,'smoke') for v,s,i in variants}
    for stage in ['screen','full','fine']:
        for v,s,i in variants:parents[v]=add(v,s,i,stage,parents[v])
    for wf in [4.55,4.6]:
        previous='eq_bicgst_smoke';v='wf'+str(wf).replace('.','p')
        for stage in ['screen','full','fine']:previous=add(v,'bicgst','equilibrium',stage,previous,wf=wf)
    previous='eq_bicgst_screen'
    for stage in ['smoke','screen','full','fine']:previous=add('bqp','bicgst','equilibrium',stage,previous,quantum='bqp')
    rank={'smoke':0,'screen':1,'full':2,'fine':3};tasks.sort(key=lambda t:rank[t['id'].rsplit('_',1)[1]])
    plan=dict(job=name,max_parallel=3,calculation_time_limit_seconds=None,tasks=tasks,
        target_changes=False,physical_validation='NOT_VALIDATED',license_retries=2,
        notes=['2nm screens are diagnostic; mesh convergence is required before performance claims.',
               'BQP coefficients are vendor starting values, not calibrated device parameters.',
               '34 finite prepared decks; no model calls or desktop automation are needed to dispatch successors.'])
    validate(plan)
    with zipfile.ZipFile(local/'package.zip','x',zipfile.ZIP_DEFLATED) as z:
        z.write(Path(__file__).with_name('durable_launch.py'),'run_study.py')
        for f in ['dag_scheduler.py','validate_case.py','run_case.py']:z.write(Path(__file__).with_name(f),f)
        z.write(study/'python'/'analyze.py','analyze.py')
        for case,data,config in cases:
            z.writestr(case+'/gaa.in',data);z.writestr(case+'/config.json',json.dumps(config))
            z.write(study/'python'/'run_study.py',case+'/worker.py')
        z.writestr('workflow.json',json.dumps(plan,indent=2))
    (local/'workflow.json').write_text(json.dumps(plan,indent=2))
    with zipfile.ZipFile(local/'package.zip') as z:
        assert len(z.namelist())<=200 and len(cases)==34
        for t in tasks:assert hashlib.sha256(z.read(t['input_file'])).hexdigest()==t['input_sha256']
    (root/'.local'/'latest_overnight.json').write_text(json.dumps(dict(job=name,package=str(local/'package.zip'),decks=str(decks))))
    print(json.dumps(dict(job=name,package=str(local/'package.zip'),deck_count=len(cases),max_parallel=3,calculation_time_limit_seconds=None)))


if __name__=='__main__':main()

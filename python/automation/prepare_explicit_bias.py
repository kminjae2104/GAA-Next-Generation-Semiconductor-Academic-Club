"""Package prospective explicit-bias experiments; never rewrite previous decks."""
from datetime import datetime,timezone
import hashlib,importlib.util,json,zipfile
from pathlib import Path
from dag_scheduler import validate

ROOT=Path(__file__).resolve().parents[2];STUDY=ROOT/'연구/01_GAA_IdVg'

def deck(g,p,scale,quantum):
    old=g.deck(p,linear_solver='bicgst',mesh_style='anisotropic',processors=4,quantum_mode=quantum,mesh_scale=scale)
    lines=[old.split('method gummel newton')[0].rstrip(),'method gummel newton bicgst carriers=2 trap maxtrap=15 itlimit=80','solve init','save outf=equilibrium.str']
    lines+=['solve vgate=%.9g previous'%(.02*i) for i in range(1,41)]
    lines+=['save outf=on_zero.str'];required=['geometry.str','equilibrium.str','on_zero.str']
    for bias,vd in [('low',.05),('high',.6)]:
        lines+=['load infile=on_zero.str','solve vdrain=0.001 previous']
        values=[.001+.002*i for i in range(1,301) if .001+.002*i<vd-1e-9]+[vd]
        lines+=['solve vdrain=%.9g previous'%v for v in values]
        lines+=['save outf=drain_'+bias+'.str']
        for rev in [True,False]:
            suffix='_rev' if rev else '';log='idvg_'+bias+suffix+'.log'
            lines+=['log outf='+log,'solve previous']
            targets=[(.8-.02*i) if rev else (-.2+.02*i) for i in range(1,51)]
            lines+=['solve vgate=%.9g previous'%v for v in targets]
            lines+=['log off','save outf=final_'+bias+suffix+'.str','extract init infile="'+log+'"'];required.append(log)
            for terminal in ['drain','source','gate']:
                name=bias+suffix+'_'+terminal
                lines+=['extract name="'+name+'" curve(v."gate",i."'+terminal+'") outfile="'+name+'.dat"'];required.append(name+'.dat')
    return '\n'.join(lines+['quit','']),required

def main():
    spec=importlib.util.spec_from_file_location('generate',STUDY/'python/generate.py');g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
    job='gaa_continuation_explicit_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    decks=STUDY/'tcad'/job;decks.mkdir(exist_ok=False)
    package=ROOT/'.local/packages'/job/'package.zip';package.parent.mkdir(parents=True,exist_ok=False)
    plan=dict(job=job,max_parallel=3,calculation_time_limit_seconds=None,physical_validation='NOT_VALIDATED',tasks=[])
    old_jobs=['gaa_overnight_20261116T080149Z','gaa_autonomous_20261117T064609Z','gaa_continuation_20261118T053927Z']
    targets=ROOT/'.local/continuation_targets.json'
    if targets.exists():old_jobs=list(dict.fromkeys(old_jobs+json.loads(targets.read_text())['jobs']))
    with zipfile.ZipFile(package,'x',zipfile.ZIP_DEFLATED) as z:
        z.write(Path(__file__).with_name('explicit_entry.py'),'run_study.py')
        for f in ['explicit_supervisor.py','dag_scheduler.py','run_case.py','validate_case.py','validate_explicit_bias.py']:z.write(Path(__file__).with_name(f),f)
        z.write(STUDY/'python/analyze.py','analyze.py')
        z.write(ROOT/'python/presentation_remote_snapshot.py','presentation_remote_snapshot.py')
        z.writestr('targets.json',json.dumps(dict(jobs=['gaa_continuation_20261118T053927Z',job])))
        z.writestr('preconditions.json',json.dumps(dict(previous_jobs=old_jobs)))
        for branch,wf,q in [('dd455',4.55,'none'),('dd46',4.6,'none'),('dd45',4.5,'none'),('bqp45',4.5,'bqp')]:
            previous=None
            for mode,scale in [('screen',2),('full',1),('fine',.5)]:
                name=branch+'_'+mode;params=dict(g.PARAMETERS,workfunction_eV=wf)
                text,required=deck(g,params,scale,q);digest=hashlib.sha256(text.encode()).hexdigest()
                config=dict(mode=mode,stage_timeout=None,required={'gaa':required},parameters=params,linear_solver='bicgst',mesh_style='anisotropic',processors=4,quantum_mode=q,mesh_scale=scale,gate_initialization='explicit_previous_roundtrip',acquisition_revision='explicit_bias_v1',engineering_targets_unchanged=True,sha256=digest)
                (decks/(name+'.in')).write_text(text,encoding='ascii',newline='\n');(decks/(name+'.json')).write_text(json.dumps(config,indent=2))
                z.writestr(name+'/gaa.in',text);z.writestr(name+'/config.json',json.dumps(config));z.write(STUDY/'python/run_study.py',name+'/worker.py')
                check=['{python}','{base}/validate_explicit_bias.py','{output}','--mode',mode]
                if previous:check+=['--compare','{dependency:'+previous+'}']
                plan['tasks'].append(dict(id=name,after=[previous] if previous else [],timeout_seconds=None,input_file=name+'/gaa.in',input_sha256=digest,command=['{python}','{base}/run_case.py','--worker','{base}/'+name+'/worker.py','--output','{output}'],checks=[check]))
                previous=name
        validate(plan);z.writestr('workflow.json',json.dumps(plan,indent=2))
    (decks/'workflow.json').write_text(json.dumps(plan,indent=2))
    pointer=dict(job=job,package=str(package),decks=str(decks),package_sha256=hashlib.sha256(package.read_bytes()).hexdigest())
    (ROOT/'.local/explicit_pending.json').write_text(json.dumps(pointer,indent=2));print(json.dumps(pointer))

if __name__=='__main__':main()

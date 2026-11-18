"""Build immutable gate-first roundtrip experiments; this does not submit them."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,importlib.util,json,zipfile
from dag_scheduler import validate
ROOT=Path(__file__).resolve().parents[2]
STUDY=ROOT/'연구/01_GAA_IdVg'
def main():
    spec=importlib.util.spec_from_file_location('generate',STUDY/'python/generate.py');g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
    job='gaa_continuation_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    folder=STUDY/'tcad'/job;folder.mkdir(exist_ok=False)
    package=ROOT/'.local/packages'/job/'package.zip';package.parent.mkdir(parents=True,exist_ok=False)
    plan={'job':job,'max_parallel':2,'calculation_time_limit_seconds':None,'physical_validation':'NOT_VALIDATED','tasks':[]}
    with zipfile.ZipFile(package,'x',zipfile.ZIP_DEFLATED) as z:
        z.write(Path(__file__).with_name('continuation_entry.py'),'run_study.py')
        for f in ['dag_scheduler.py','run_case.py','validate_case.py','validate_continuation.py','continuation_supervisor.py']:z.write(Path(__file__).with_name(f),f)
        z.write(STUDY/'python/analyze.py','analyze.py')
        for branch,wf,q in [('dd45',4.5,'none'),('dd455',4.55,'none'),('dd46',4.6,'none'),('bqp45',4.5,'bqp')]:
            previous=None
            for mode,scale in [('screen',2),('full',1),('fine',.5)]:
                name=branch+'_'+mode;p=dict(g.PARAMETERS,workfunction_eV=wf)
                old=g.deck(p,linear_solver='bicgst',mesh_style='anisotropic',processors=4,quantum_mode=q,mesh_scale=scale)
                prefix=old.split('method gummel newton')[0]
                lines=[prefix.rstrip(),'method gummel newton bicgst carriers=2 trap maxtrap=15 itlimit=80','solve init','save outf=equilibrium.str',
                       'solve name=gate vstep=0.02 vfinal=0.8','save outf=on_zero.str']
                required=['geometry.str','equilibrium.str','on_zero.str']
                for bias,vd in [('low',.05),('high',.6)]:
                    lines+=['load infile=on_zero.str','solve vdrain=0.001','solve name=drain vstep=0.002 vfinal=%.9g'%vd]
                    for direction,start,step,stop in [('rev',.8,-.02,-.2),('fwd',-.2,.02,.8)]:
                        log='idvg_'+bias+('_rev' if direction=='rev' else '')+'.log'
                        lines+=['log outf='+log,'solve vgate=%.9g'%start,'solve name=gate vstep=%.9g vfinal=%.9g'%(step,stop),'log off',
                                'save outf=final_'+bias+'_'+direction+'.str','extract init infile="'+log+'"']
                        required.append(log)
                        for t in ['drain','source','gate']:
                            base=bias+('_rev' if direction=='rev' else '')+'_'+t
                            lines+=['extract name="'+base+'" curve(v."gate",i."'+t+'") outfile="'+base+'.dat"'];required.append(base+'.dat')
                data='\n'.join(lines+['quit','']);digest=hashlib.sha256(data.encode()).hexdigest()
                (folder/(name+'.in')).write_text(data,encoding='ascii',newline='\n')
                config={'mode':mode,'stage_timeout':None,'required':{'gaa':required},'parameters':p,'linear_solver':'bicgst','mesh_style':'anisotropic','processors':4,
                        'quantum_mode':q,'mesh_scale':scale,'gate_initialization':'two_carrier_gate_first_roundtrip','sha256':digest,'engineering_targets_unchanged':True}
                (folder/(name+'.json')).write_text(json.dumps(config,indent=2))
                z.writestr(name+'/gaa.in',data);z.writestr(name+'/config.json',json.dumps(config));z.write(STUDY/'python/run_study.py',name+'/worker.py')
                check=['{python}','{base}/validate_continuation.py','{output}','--mode',mode]
                if previous:check+=['--compare','{dependency:'+previous+'}']
                plan['tasks'].append({'id':name,'after':[previous] if previous else [],'timeout_seconds':None,'input_file':name+'/gaa.in','input_sha256':digest,
                    'command':['{python}','{base}/run_case.py','--worker','{base}/'+name+'/worker.py','--output','{output}'],'checks':[check]})
                previous=name
        validate(plan);z.writestr('workflow.json',json.dumps(plan,indent=2))
    (folder/'workflow.json').write_text(json.dumps(plan,indent=2))
    pointer={'job':job,'package':str(package),'decks':str(folder),'package_sha256':hashlib.sha256(package.read_bytes()).hexdigest()}
    (ROOT/'.local/continuation_pending.json').write_text(json.dumps(pointer,indent=2));print(json.dumps(pointer))
if __name__=='__main__':main()

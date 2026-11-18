"""Package two new numeric recovery decks plus a same-scope transport handoff."""
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import zipfile
from dag_scheduler import validate


def main():
    root=Path(__file__).resolve().parents[2];here=Path(__file__).parent
    study=next(p for p in root.iterdir() if (p/'01_GAA_IdVg/python/generate.py').is_file())/'01_GAA_IdVg'
    spec=importlib.util.spec_from_file_location('generate',study/'python/generate.py')
    g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
    runtime=Path(json.loads((root/'.local/night_runtime.json').read_text())['runtime'])
    session=json.loads((runtime/'session.json').read_text())
    urls=json.loads((runtime/'routes.json').read_text())['urls']
    connection=dict(base_url=urls[0],fallback_urls=urls[1:],token=(runtime/'token.txt').read_text().strip(),
        ca_pem=(runtime/'task_root_ca.pem').read_text(),max_session_seconds=86400,
        deadline_utc=session['deadline_utc'],agent_sha256=hashlib.sha256((runtime/'agent.py').read_bytes()).hexdigest())
    job='gaa_autonomous_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    folder=root/'.local'/job;folder.mkdir()
    decks=study/'tcad'/job;decks.mkdir()
    plan=dict(job=job,max_parallel=1,tasks=[],physical_validation='NOT_VALIDATED',
        recovery_budget=2,reason='Actual high Vds fell below 0.6V; finer ramp without target/model changes')
    with zipfile.ZipFile(folder/'package.zip','x',zipfile.ZIP_DEFLATED) as z:
        z.write(here/'night_entry.py','run_study.py')
        for f in ['night_supervisor.py','dag_scheduler.py','run_case.py','validate_case.py']:
            z.write(here/f,f)
        z.write(runtime/'agent.py','agent.py');z.writestr('connection.json',json.dumps(connection))
        z.write(study/'python/analyze.py','analyze.py')
        for wf in [4.55,4.6]:
            name='wf'+str(wf).replace('.','p')+'_fine_ramp002'
            parameters=dict(g.PARAMETERS,workfunction_eV=wf)
            data=g.deck(parameters,fine=True,linear_solver='bicgst',mesh_style='anisotropic',
                processors=4,gate_initialization='equilibrium',mesh_scale=.5)
            data=data.replace('name=drain vstep=0.01','name=drain vstep=0.002')
            config=dict(mode='fine',stage_timeout=None,parameters=parameters,required={'gaa':[
                'geometry.str','equilibrium.str','idvg_low.log','idvg_high.log',
                *[bias+'_'+terminal+'.dat' for bias in ['low','high'] for terminal in ['drain','source','gate']]]},
                linear_solver='bicgst',mesh_style='anisotropic',processors=4,quantum_mode='none',
                gate_initialization='equilibrium',mesh_scale=.5,engineering_targets_unchanged=True)
            (decks/(name+'.in')).write_text(data,encoding='utf-8')
            z.writestr(name+'/gaa.in',data);z.writestr(name+'/config.json',json.dumps(config))
            z.write(study/'python/run_study.py',name+'/worker.py')
            plan['tasks'].append(dict(id=name,after=[],timeout_seconds=None,
                command=['{python}','{base}/run_case.py','--worker','{base}/'+name+'/worker.py','--output','{output}'],
                checks=[['{python}','{base}/validate_case.py','{output}','--mode','fine']],
                input_file=name+'/gaa.in',input_sha256=hashlib.sha256(data.encode()).hexdigest()))
        validate(plan);z.writestr('workflow.json',json.dumps(plan,indent=2))
    (decks/'workflow.json').write_text(json.dumps(plan,indent=2))
    pointer=dict(job=job,package=str(folder/'package.zip'),runtime=str(runtime),decks=str(decks))
    (root/'.local/latest_autonomous.json').write_text(json.dumps(pointer))
    print(json.dumps(pointer))


if __name__=='__main__':main()

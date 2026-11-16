"""Prepare next workflow only. Does not queue or start a remote job."""
from datetime import datetime,timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import zipfile
from dag_scheduler import validate


def main():
    root=Path(__file__).resolve().parents[2];study=root/'연구'/'01_GAA_IdVg'
    spec=importlib.util.spec_from_file_location('generate',study/'python'/'generate.py');g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
    name='gaa_workflow_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    folder=root/'.local'/name;folder.mkdir(parents=True,exist_ok=False)
    plan=dict(max_parallel=3,tasks=[],physical_validation='NOT_VALIDATED')
    variants=[('direct','direct','biased'),('bicgst','bicgst','biased'),('equilibrium','bicgst','equilibrium')]
    with zipfile.ZipFile(folder/'package.zip','x',zipfile.ZIP_DEFLATED) as z:
        z.writestr('run_study.py','from dag_scheduler import main\nraise SystemExit(main())\n')
        for f in ['dag_scheduler.py','validate_case.py']:z.write(Path(__file__).with_name(f),f)
        z.write(study/'python'/'analyze.py','analyze.py')
        for variant,solver,initial in variants:
            previous=None
            for mode in ['smoke','full','fine']:
                task_id=variant+'_'+mode
                data=g.deck(g.PARAMETERS,fine=mode=='fine',smoke=mode=='smoke',linear_solver=solver,mesh_style='anisotropic',processors=4,gate_initialization=initial)
                z.writestr(task_id+'/gaa.in',data)
                z.write(study/'python'/'run_study.py',task_id+'/worker.py')
                required=['geometry.str','equilibrium.str','idvg_low.log','low_drain.dat','low_source.dat','low_gate.dat']
                if mode!='smoke':required+=['idvg_high.log','high_drain.dat','high_source.dat','high_gate.dat']
                config=dict(mode=mode,stage_timeout=4800,required={'gaa':required},parameters=g.PARAMETERS,linear_solver=solver,mesh_style='anisotropic',processors=4,gate_initialization=initial)
                z.writestr(task_id+'/config.json',json.dumps(config))
                plan['tasks'].append(dict(id=task_id,after=[previous] if previous else [],timeout_seconds=4800,
                    command=['{python}','{base}/'+task_id+'/worker.py','--output','{output}','--max-seconds','4800'],
                    checks=[['{python}','{base}/validate_case.py','{output}','--mode',mode]],
                    input_file=task_id+'/gaa.in',input_sha256=hashlib.sha256(data.encode()).hexdigest()))
                previous=task_id
        validate(plan);z.writestr('workflow.json',json.dumps(plan,indent=2))
    (folder/'workflow.json').write_text(json.dumps(plan,indent=2))
    print(json.dumps(dict(package=str(folder/'package.zip'),tasks=len(plan['tasks']),max_parallel=3,per_task_minutes=80,remote_submitted=False)))


if __name__=='__main__':main()

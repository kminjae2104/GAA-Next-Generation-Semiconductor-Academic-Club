"""Read-only proof of private settings and watchdog recovery; never export secrets."""
import argparse,json,os,time
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--max-seconds');a=p.parse_args()
root=Path.home()/'.local/share/gaa_persistent_agent'
report=dict(snapshot_epoch=time.time(),config_mode=oct((root/'config.json').stat().st_mode & 0o777),config_owner_matches=(root/'config.json').stat().st_uid==os.getuid())
for name in ['supervisor_status.json','watchdog_tick.json','restart_test.json','discovery_status.json']:
    f=root/name
    if f.exists():report[name]=json.loads(f.read_text())
status=report.get('supervisor_status.json',{})
for label in ['supervisor_pid','agent_pid']:
    pid=status.get(label);cmd=Path('/proc')/str(pid)/'cmdline'
    report[label+'_alive']=cmd.exists()
    if cmd.exists():report[label+'_cmdline']=cmd.read_bytes().decode(errors='replace').replace('\0',' ')
report['automatic_recovery_verified']=bool(report.get('restart_test.json') and status.get('supervisor_pid')!=report['restart_test.json']['old_supervisor_pid'] and report.get('supervisor_pid_alive') and report.get('agent_pid_alive'))
report['discovery_configured']=bool(json.loads((root/'config.json').read_text()).get('discovery'))
(a.output/'persistent_status.json').write_text(json.dumps(report,indent=2));(a.output/'status.json').write_text(json.dumps(dict(status='READ_ONLY_PERSISTENCE_CHECK',stages=[])))

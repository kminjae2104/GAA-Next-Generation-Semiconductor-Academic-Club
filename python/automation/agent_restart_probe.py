"""One authorized recovery test, scoped to our supervisor, after result preservation."""
import json,os,signal,sys,time
from pathlib import Path
root=Path.home()/'.local/share/gaa_persistent_agent'
job=Path(sys.argv[1]);end=time.monotonic()+120
while not (job/'pending_result.zip').exists() and time.monotonic()<end:time.sleep(1)
if not (job/'pending_result.zip').exists():raise SystemExit('No saved result; restart test skipped')
time.sleep(15)
status=json.loads((root/'supervisor_status.json').read_text());pid=status['supervisor_pid']
command=(Path('/proc')/str(pid)/'cmdline').read_bytes().decode(errors='replace')
if str(root/'durable_agent.py') not in command:raise SystemExit('Supervisor identity mismatch')
(root/'restart_test.json').write_text(json.dumps(dict(old_supervisor_pid=pid,old_agent_pid=status['agent_pid'],triggered=time.time(),simulations_untouched=True)))
os.kill(pid,signal.SIGTERM)

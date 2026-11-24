"""Add one scoped per-user cron watchdog, preserving existing crontab entries."""
import argparse,json,shlex,shutil,subprocess,sys,os
from pathlib import Path

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--max-seconds');a=p.parse_args()
    root=Path.home()/'.local/share/gaa_persistent_agent'
    if not (root/'config.json').is_file():raise ValueError('Persistent installation missing')
    # Update only supervisor source. Running agent and simulations are preserved.
    (root/'durable_agent.py').write_bytes(Path(__file__).with_name('durable_agent.py').read_bytes())
    cron=shutil.which('crontab');report=dict(cron_available=bool(cron),existing_simulations_preserved=True)
    if cron:
        old=subprocess.run([cron,'-l'],capture_output=True,text=True)
        if old.returncode not in [0,1]:raise RuntimeError('Cannot read own crontab')
        if old.returncode==1 and old.stderr.strip() and 'no crontab' not in old.stderr.lower():raise RuntimeError('Own crontab unavailable')
        marker='# GAA persistent agent watchdog'
        command=' '.join(shlex.quote(str(x)) for x in [sys.executable,root/'durable_agent.py','--config',root/'config.json'])
        line='* * * * * '+command+' >> '+shlex.quote(str(root/'cron.console'))+' 2>&1'
        prior=old.stdout if old.returncode==0 else ''
        if marker not in prior:
            subprocess.run([cron,'-'],input=prior.rstrip()+'\n'+marker+'\n'+line+'\n',text=True,check=True,capture_output=True)
        saved=subprocess.run([cron,'-l'],capture_output=True,text=True,check=True)
        report.update(cron_entry_verified=marker in saved.stdout and line in saved.stdout,watchdog_interval_seconds=60,reboot_recovery='USER_CRON_AFTER_CROND_STARTS',cron_daemon_execution='REQUIRES_WATCHDOG_HEARTBEAT_VERIFICATION')
        if report['cron_entry_verified']:
            with (root/'restart_probe.console').open('ab') as log:
                probe=subprocess.Popen([sys.executable,str(Path(__file__).with_name('agent_restart_probe.py')),str(a.output.parent)],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            report['supervisor_restart_probe_pid']=probe.pid
    else:report['reboot_recovery']='UNAVAILABLE_NO_CRONTAB'
    report['config_mode']=oct((root/'config.json').stat().st_mode & 0o777)
    (a.output/'autostart.json').write_text(json.dumps(report,indent=2));(a.output/'status.json').write_text(json.dumps(dict(status='AUTOSTART_CONFIGURED' if cron else 'SUPERVISOR_ONLY',stages=[])))

if __name__=='__main__':main()

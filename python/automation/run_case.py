"""Preserve every attempt; retry only identifiable license failures, at most twice."""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time


def main():
    p=argparse.ArgumentParser();p.add_argument('--worker',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    child=None
    def stop(*unused):
        if child is not None and child.poll() is None:child.terminate();child.wait()
        raise SystemExit(143)
    if os.name=='posix':signal.signal(signal.SIGTERM,stop)
    for attempt in range(1,4):
        out=a.output/('attempt_%02d'%attempt);out.mkdir(exist_ok=False)
        (a.output/'selected_attempt.json').write_text(json.dumps({'directory':out.name,'attempt':attempt}))
        with (out/'worker_console.txt').open('xb') as log:
            child=subprocess.Popen([sys.executable,str(a.worker),'--output',str(out)],
                stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT)
            rc=child.wait()
        if rc==0:return 0
        status=out/'status.json'
        if not status.is_file():return rc or 5
        stages=json.loads(status.read_text()).get('stages',[])
        fatal=[s for stage in stages for s in stage.get('fatal_lines',[])]
        diagnostics='\n'.join(s for stage in stages for s in stage.get('diagnostic_lines',[])).lower()
        license_failure=any(s in diagnostics for s in ['can not log into license server','not logged in','can not get license'])
        other_error=any('sflm' not in s.lower() and 'license' not in s.lower() for s in fatal)
        if not license_failure or other_error or attempt==3:return rc or 5
        # This delay is process-local, consumes no model calls, and sets no calculation deadline.
        time.sleep(60)
    return 5


if __name__=='__main__':raise SystemExit(main())

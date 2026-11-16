"""Keep the relay PC awake only until this already-authorized session ends."""
import argparse
import ctypes
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
import time

import relay


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,required=True)
    a=p.parse_args()
    if sys.platform!='win32':p.error('Windows relay host only')
    deadline=datetime.fromisoformat(json.loads((a.root/'session.json').read_text())['deadline_utc'])
    deadline=min(deadline,datetime.now(timezone.utc)+timedelta(hours=6))
    set_state=ctypes.windll.kernel32.SetThreadExecutionState
    set_state.argtypes=[ctypes.c_uint32]
    set_state.restype=ctypes.c_uint32
    continuous=0x80000000
    try:
        if not set_state(continuous|1):raise OSError('SetThreadExecutionState failed')
        relay.write_json(a.root/'awake_state.json',dict(active=True,temporary_system_request=True,
                         display_required=False,deadline_utc=deadline.isoformat()))
        while datetime.now(timezone.utc)<deadline:
            if (a.root/'session_stopped.json').exists() or (a.root/'stop.request').exists():break
            time.sleep(5)
        return 0
    finally:
        set_state(continuous)
        relay.write_json(a.root/'awake_state.json',dict(active=False,
                         ended_utc=datetime.now(timezone.utc).isoformat()))


if __name__=='__main__':raise SystemExit(main())

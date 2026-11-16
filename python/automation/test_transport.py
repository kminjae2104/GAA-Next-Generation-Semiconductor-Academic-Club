"""Loopback-only transport tests. No remote simulation or desktop APIs."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

import control
import relay
import watch_job


class Transport(unittest.TestCase):
    def test_compact_summary_filters_no_error_without_claiming_physics(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            relay.write_json(root/'status.json',dict(status='EXECUTION_FAILED',stages=[dict(
                stage='gaa',returncode=1,timeout=False,seconds=1,missing=['idvg_low.log'],
                fatal_lines=['SFLM Transport Error: No Error','syntax error in test'])]))
            summary=watch_job.summarize(root)
            self.assertEqual(summary['stages'][0]['errors'],['syntax error in test'])
            self.assertEqual(summary['physical_validation'],'NOT_VALIDATED')

    def test_authenticated_status_and_stop(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'runtime';relay.initialize(root)
            server=relay.Relay(root,0,60)
            worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
            base='http://127.0.0.1:'+str(server.server_address[1])
            token=(root/'token.txt').read_text()
            def request(path,body=None,authorized=True):
                headers={'Authorization':'Bearer '+token} if authorized else {}
                return urllib.request.urlopen(urllib.request.Request(base+path,data=body,headers=headers),timeout=3)
            try:
                self.assertEqual(server.server_address[0],'127.0.0.1')
                with self.assertRaises(urllib.error.HTTPError) as denied:request('/health',authorized=False)
                self.assertEqual(denied.exception.code,401)
                with request('/control') as response:self.assertFalse(json.load(response)['stop'])
                relay.write_json(root/'control.json',dict(stop=True))
                with request('/control') as response:self.assertTrue(json.load(response)['stop'])
                with request('/event',json.dumps(dict(status='AGENT_READY')).encode()) as response:
                    self.assertTrue(json.load(response)['stored'])
                self.assertEqual(json.loads((root/'latest_event.json').read_text())['status'],'AGENT_READY')
                with self.assertRaises(urllib.error.HTTPError) as denied:request('/shell')
                self.assertEqual(denied.exception.code,404)
            finally:server.shutdown();server.server_close();worker.join(timeout=3)

    def test_stopped_and_stale_events_not_live(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            relay.write_json(root/'session.json',dict(deadline_utc=(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()))
            relay.write_json(root/'latest_event.json',dict(status='AGENT_READY',received_utc=(datetime.now(timezone.utc)-timedelta(minutes=5)).isoformat()))
            self.assertFalse(control.state(root)['live_agent'])
            self.assertEqual(control.state(root)['session_status'],'AGENT_LIVENESS_UNVERIFIED')
            relay.write_json(root/'latest_event.json',dict(status='STUDY_RUNNING',received_utc=datetime.now(timezone.utc).isoformat()))
            self.assertTrue(control.state(root)['live_agent'])
            self.assertEqual(control.state(root)['session_status'],'AGENT_RUNNING')
            relay.write_json(root/'latest_event.json',dict(status='AGENT_STOPPED_BY_CONTROL',received_utc=datetime.now(timezone.utc).isoformat()))
            self.assertFalse(control.state(root)['live_agent'])

    def test_credentials_runtime_refuses_git(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'.git').mkdir()
            with self.assertRaises(ValueError):relay.initialize(root/'runtime')


if __name__=='__main__':unittest.main()

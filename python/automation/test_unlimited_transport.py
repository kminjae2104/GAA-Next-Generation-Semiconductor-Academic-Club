"""No-deadline transport must remain authenticated and explicitly stoppable."""
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
import urllib.request
import urllib.error
import agent
import control
import relay
import start_session


class UnlimitedTransport(unittest.TestCase):
    def test_unlimited_relay_survives_future_clock_and_requires_auth(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'runtime'; relay.initialize(root)
            server=relay.Relay(root,0,0)
            thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
            url='http://127.0.0.1:%d/health'%server.server_port
            try:
                with patch.object(relay.time,'time',return_value=4102444800), patch.object(relay.time,'monotonic',return_value=1e10):
                    with self.assertRaises(urllib.error.HTTPError) as denied: urllib.request.urlopen(url,timeout=3)
                    self.assertEqual(denied.exception.code,401)
                    req=urllib.request.Request(url,headers={'Authorization':'Bearer '+server.token})
                    with urllib.request.urlopen(req,timeout=3) as response: self.assertTrue(json.load(response)['ready'])
            finally:
                server.shutdown();server.server_close();thread.join(3)

    def test_unlimited_agent_accepts_explicit_stop(self):
        config=dict(base_url='https://example.com',token='0'*64,max_session_seconds=None,deadline_utc=None)
        with patch.object(agent.os,'name','posix'),patch.object(agent,'post_event'),patch.object(agent,'request',return_value=b'{"stop":true}'):
            self.assertEqual(agent.main(config),0)

    def test_bootstrap_and_status_have_no_hidden_expiry(self):
        command=start_session.bootstrap_command('https://example.com','a'*64)
        self.assertIn('"max_session_seconds":None',command)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);relay.write_json(root/'session.json',dict(deadline_utc=None))
            self.assertIsNone(control.state(root)['deadline_utc'])
            self.assertNotEqual(control.state(root)['session_status'],'EXPIRED')

if __name__=='__main__': unittest.main()

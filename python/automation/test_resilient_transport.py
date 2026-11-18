import concurrent.futures
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import agent
import relay


class ResilientTransport(unittest.TestCase):
    def test_concurrent_json_writers_leave_valid_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'state.json'
            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
                list(pool.map(lambda i:relay.write_json(path,dict(sequence=i)),range(100)))
            self.assertIn(json.loads(path.read_text())['sequence'],range(100))
            self.assertEqual(list(Path(tmp).glob('*.tmp')),[])

    def test_fallback_preserves_auth_and_tls(self):
        class Response:
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self):return b'ok'
        with patch.object(agent.urllib.request,'urlopen',side_effect=[OSError('route down'),Response()]) as request:
            value=agent.request(dict(base_url='https://primary.example',fallback_urls=['https://backup.example'],token='a'*64),'/health')
            self.assertEqual(value,b'ok')
            args=request.call_args
            self.assertEqual(args.args[0].full_url,'https://backup.example/health')
            self.assertIsNotNone(args.kwargs['context'])
            self.assertEqual(args.args[0].get_header('Authorization'),'Bearer '+'a'*64)


if __name__=='__main__':unittest.main()

import json,tempfile,unittest
from pathlib import Path
from durable_agent import save_config

class PersistenceTests(unittest.TestCase):
    def test_private_config_roundtrip_without_stdout(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'private/config.json';value=dict(base_url='https://example.com',token='test-only',deadline_utc=None)
            save_config(p,value)
            self.assertEqual(json.loads(p.read_text()),value)
    def test_existing_config_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'private/config.json';save_config(p,dict(token='original'))
            with self.assertRaises(FileExistsError):save_config(p,dict(token='replacement'))
            self.assertEqual(json.loads(p.read_text())['token'],'original')

if __name__=='__main__':unittest.main()

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import run_case
import agent


class Overnight(unittest.TestCase):
    def test_agent_retries_transport_failure_without_exiting(self):
        config=dict(base_url='https://example.com',token='0'*64)
        with patch.object(agent.os,'name','posix'),patch.object(agent,'post_event'),patch.object(agent.time,'sleep'),patch.object(agent,'request',side_effect=[RuntimeError('temporary'),b'{"stop":true}']) as request:
            self.assertEqual(agent.main(config),0)
        self.assertEqual(request.call_count,2)

    def test_heartbeat_does_not_repeat_a_seen_job(self):
        config=dict(base_url='https://example.com',token='0'*64)
        responses=[b'{"stop":false}',b'{"job":"same"}',b'{"stop":false}',b'{"job":"same"}',b'{"stop":true}']
        with patch.object(agent.os,'name','posix'),patch.object(agent,'post_event'),patch.object(agent.time,'sleep'),patch.object(agent,'request',side_effect=responses),patch.object(agent,'run_package',return_value=0) as run:
            self.assertEqual(agent.main(config),0)
        self.assertEqual(run.call_count,1)

    def run_fake(self,diagnostic,fatal):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);out=root/'out';out.mkdir();worker=root/'worker.py'
            worker.write_text("import argparse,json,pathlib\np=argparse.ArgumentParser();p.add_argument('--output',type=pathlib.Path);a=p.parse_args()\n"
                +"status="+repr(dict(stages=[dict(diagnostic_lines=[diagnostic],fatal_lines=[fatal])]))+"\n"
                +"(a.output/'status.json').write_text(json.dumps(status))\nraise SystemExit(5 if a.output.name=='attempt_01' else 0)\n")
            with patch.object(sys,'argv',['run_case','--worker',str(worker),'--output',str(out)]),patch.object(run_case.time,'sleep'):
                rc=run_case.main()
            return rc,[p.name for p in out.glob('attempt_*')]

    def test_license_failure_retries_in_separate_directory(self):
        rc,attempts=self.run_fake('SFLM: Can not log into license server.','SFLM Programmer Error: This job is not logged in.')
        self.assertEqual(rc,0);self.assertEqual(sorted(attempts),['attempt_01','attempt_02'])

    def test_syntax_error_does_not_repeat_unchanged_deck(self):
        rc,attempts=self.run_fake('Can not get license.','Syntax Error: invalid MODEL')
        self.assertEqual(rc,5);self.assertEqual(attempts,['attempt_01'])

    def test_nested_attempt_structures_do_not_collide(self):
        study=Path(__file__).resolve().parents[2]/'연구'/'01_GAA_IdVg'/'python'/'run_study.py'
        spec=importlib.util.spec_from_file_location('worker',study);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        with tempfile.TemporaryDirectory() as tmp:
            for name in ['a','b']:
                folder=Path(tmp)/name/'attempt_01';folder.mkdir(parents=True)
                source=folder/'state.str'
                with source.open('wb') as f:f.truncate(8*1024*1024+1)
                m.retain_large_structures(folder)
                record=json.loads((folder/'retained_structures.json').read_text())[0]
                self.assertTrue(Path(record['remote_preserved_path']).is_file())
                self.assertIn(name,Path(record['remote_preserved_path']).parts)


if __name__=='__main__':unittest.main()

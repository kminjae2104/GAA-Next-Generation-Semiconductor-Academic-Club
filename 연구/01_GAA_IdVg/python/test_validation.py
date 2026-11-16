"""Synthetic corruption/metric/security tests; never a Silvaco validation."""
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

import analyze
import generate

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'python'/'automation'))
import control


def curves():
    gate=[round(-.2+i*.02,8) for i in range(51)]
    drain=[(v,.04*1e-10*10**((v-.04)/.08)) for v in gate]
    return dict(drain=drain,source=[(v,-i) for v,i in drain],gate=[(v,0.0) for v in gate])


class Validation(unittest.TestCase):
    def test_reference_slope_and_kcl(self):
        value=analyze.metric(curves(),.04)
        self.assertAlmostEqual(value['SS_mV_dec'],80,places=7)
        self.assertAlmostEqual(value['Vth_V'],.28,places=7)
        self.assertTrue(value['kcl_pass'])

    def test_missing_step_rejected(self):
        c=curves()
        for t in c:del c[t][10]
        with self.assertRaises(ValueError):analyze.metric(c,.04)

    def test_zero_current_not_infinite_ratio(self):
        c=curves();c['drain'][10]=(0,0)
        with self.assertRaises(ValueError):analyze.metric(c,.04)

    def test_kcl_failure_detected(self):
        c=curves();c['source']=[(v,i*.9) for v,i in c['source']]
        self.assertFalse(analyze.metric(c,.04)['kcl_pass'])

    def test_nonfinite_and_corrupt_rows(self):
        for corruption in ['0.2 NaN','bad middle line','0.1 1e-9']:
            with self.subTest(corruption=corruption),tempfile.TemporaryDirectory() as tmp:
                f=Path(tmp)/'x.dat';f.write_text('0 1e-12\n0.1 1e-11\n'+corruption+'\n')
                with self.assertRaises(ValueError):analyze.read_curve(f)

    def test_terminal_alignment_rejected(self):
        c=curves();c['source'][5]=(.123,1e-12)
        with self.assertRaises(ValueError):analyze.metric(c,.04)

    def test_missing_ss_window_explicit(self):
        c={t:[(v,i*1e20) for v,i in rows] for t,rows in curves().items()}
        self.assertIsNone(analyze.metric(c,.04)['SS_mV_dec'])

    def test_geometry_faces_and_volume(self):
        g=generate.geometry(generate.PARAMETERS)
        self.assertEqual(len(g),13)
        channel=next(r for r in g if r['name']=='channel')
        self.assertEqual(channel['nm'],[0,10,0,10,20,60])
        self.assertEqual(sum(r['electrode']==1 for r in g),4)

    def test_full_three_dimensional_output(self):
        text=generate.deck(generate.PARAMETERS)
        self.assertIn('z.plane',text)
        self.assertIn('go devedit simflags="-3d"',text)
        self.assertIn('mesh infile=geometry.str',text)
        self.assertNotIn('cylindrical',text.lower())

    def test_result_hashes_and_path_escape(self):
        for name,corrupt in [('result.txt',False),('../escape.txt',False),('result.txt',True)]:
            with self.subTest(name=name,corrupt=corrupt),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);archive=root/'x.zip';content=b'only synthetic test data'
                with zipfile.ZipFile(archive,'w') as z:
                    z.writestr(name,content)
                    z.writestr('output_hashes.json',json.dumps({name:hashlib.sha256(content if not corrupt else b'wrong').hexdigest()}))
                receipt=dict(sha256=hashlib.sha256(archive.read_bytes()).hexdigest())
                if name.startswith('..') or corrupt:
                    with self.assertRaises(ValueError):control.collect_archive(archive,receipt,root/'out')
                    self.assertFalse((root/'out').exists())
                else:
                    result=control.collect_archive(archive,receipt,root/'out')
                    self.assertTrue(result['transport_verified'])
                    self.assertEqual(result['physical_validation'],'NOT_VALIDATED')


if __name__=='__main__':unittest.main()

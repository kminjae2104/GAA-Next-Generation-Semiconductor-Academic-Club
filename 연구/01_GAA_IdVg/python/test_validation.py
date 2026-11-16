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
import run_study

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'python'/'automation'))
import control


def curves():
    gate=[round(-.2+i*.02,8) for i in range(51)]
    drain=[(v,.04*1e-10*10**((v-.04)/.08)) for v in gate]
    return dict(drain=drain,source=[(v,-i) for v,i in drain],gate=[(v,0.0) for v in gate])


class Validation(unittest.TestCase):
    def test_equilibrium_gate_restores_both_carriers_before_drain_bias(self):
        lines=generate.deck(generate.PARAMETERS,gate_initialization='equilibrium').splitlines()
        zero=next(i for i,s in enumerate(lines) if 'carriers=0' in s)
        two=next(i for i,s in enumerate(lines) if 'carriers=2' in s)
        drain=next(i for i,s in enumerate(lines) if s=='solve vdrain=0.01')
        self.assertLess(zero,two);self.assertLess(two,drain)
        self.assertFalse(any('vdrain' in s for s in lines[zero:two]))
        self.assertEqual(sum(s.startswith('solve name=gate vstep=-0.02') for s in lines),1)

    def test_anisotropic_mesh_preserves_oxide_normal_spacing(self):
        a=generate.deck(generate.PARAMETERS).splitlines()
        b=generate.deck(generate.PARAMETERS,mesh_style='anisotropic').splitlines()
        changed=[(x,y) for x,y in zip(a,b) if x!=y]
        self.assertEqual(len(changed),4)
        for x,y in changed:
            self.assertTrue(x.startswith('constr.mesh region='));self.assertIn('0.00025',y)

    def test_native_log_checks_bias_and_terminal_short(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'native.log';exports=dict(gate=[(0,0)],source=[(0,-1e-9)],drain=[(0,1e-9)])
            p.write_text('f 3 "gate" "source" "drain"\nd 0 0 0 0 0 -1e-9 0.05 0.05 1e-9\n')
            self.assertTrue(analyze.validate_native_log(p,.05,exports)['native_export_match'])
            with self.assertRaises(ValueError):analyze.validate_native_log(p,.6,exports)
            p.write_text('f 4 "gate" "source" "drain" "unlinked_gate"\n')
            with self.assertRaises(ValueError):analyze.validate_native_log(p,.05,exports)

    def test_solver_selection_changes_only_method_statements(self):
        a=generate.deck(generate.PARAMETERS).splitlines()
        b=generate.deck(generate.PARAMETERS,linear_solver='bicgst').splitlines()
        self.assertEqual(len(a),len(b))
        for x,y in zip(a,b):
            if x!=y:
                self.assertTrue(x.startswith('method '));self.assertIn('bicgst',y)
        with self.assertRaises(ValueError):generate.deck(generate.PARAMETERS,linear_solver='unknown')

    def test_large_structure_is_preserved_with_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'job'/'results';root.mkdir(parents=True)
            source=root/'sample.str';data=b'x'*(8*1024*1024+1);source.write_bytes(data)
            run_study.retain_large_structures(root)
            record=json.loads((root/'retained_structures.json').read_text())[0]
            self.assertFalse(source.exists())
            self.assertEqual(Path(record['remote_preserved_path']).read_bytes(),data)
            self.assertEqual(record['sha256'],hashlib.sha256(data).hexdigest())
            self.assertEqual(record['local_byte_verification'],'NOT_DOWNLOADED')

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
        self.assertEqual(sum(r['name'].startswith('gate') for r in g),4)
        self.assertEqual({r['electrode'] for r in g if r['electrode']},{1,2,3,4,5,6})

    def test_full_three_dimensional_output(self):
        text=generate.deck(generate.PARAMETERS)
        self.assertIn('z.plane',text)
        self.assertIn('go devedit simflags="-3d"',text)
        self.assertIn('mesh infile=geometry.str',text)
        self.assertNotIn('cylindrical',text.lower())
        self.assertEqual(text.count('common=gate short'),3)

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

"""Synthetic acquisition tests; these do not prove Silvaco syntax or device physics."""
import hashlib,importlib.util,json,math,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'연구/01_GAA_IdVg/python'))
from validate_explicit_bias import canonical_curve,validate_folder
from prepare_explicit_bias import deck,STUDY

class ExplicitBiasTests(unittest.TestCase):
    def fixture(self,p,reverse=False,extra=None,missing=None,vd=.05,bad_current=False):
        vg=[-.2+.02*i for i in range(51) if i!=missing]
        if extra is not None:vg.append(extra)
        vg.sort(reverse=reverse);suffix='_rev' if reverse else ''
        lines=['f 3 "gate" "source" "drain"'];exports={t:[] for t in ['gate','source','drain']}
        for v in vg:
            current=1e-9*math.exp(v)
            source=-current if not (bad_current and extra is not None and abs(v-extra)<1e-9) else 0
            lines.append('d %.12g 0 0 0 0 %.12g %.12g 0 %.12g'%(v,source,vd,current))
            for terminal,i in [('gate',0),('source',source),('drain',current)]:exports[terminal].append('%.12g %.12g'%(v,i))
        log=p/('idvg_low'+suffix+'.log');log.write_text('\n'.join(lines))
        for t,data in exports.items():(p/('low'+suffix+'_'+t+'.dat')).write_text('\n'.join(data))
        return log
    def test_adaptive_rows_preserved_and_exact_targets_selected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);log=self.fixture(p,reverse=True,extra=-.17);before=hashlib.sha256(log.read_bytes()).hexdigest();out=p/'out';out.mkdir()
            result=canonical_curve(p,out,'low',True)
            self.assertEqual(result['native_points'],52);self.assertEqual(result['target_points'],51)
            self.assertEqual(result['adaptive_gate_V'],[-.17]);self.assertEqual(before,hashlib.sha256(log.read_bytes()).hexdigest())
            self.assertEqual(len([s for s in (out/'idvg_low.log').read_text().splitlines() if s.startswith('d ')]),51)
    def test_missing_requested_endpoint_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);self.fixture(p,extra=-.19,missing=0);out=p/'out';out.mkdir()
            with self.assertRaisesRegex(ValueError,'Missing/duplicate'):canonical_curve(p,out,'low')
    def test_wrong_drain_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);self.fixture(p,vd=.043);out=p/'out';out.mkdir()
            with self.assertRaisesRegex(ValueError,'intended Vds'):canonical_curve(p,out,'low')
    def test_error_on_extra_point_cannot_be_hidden(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);self.fixture(p,extra=-.17,bad_current=True);out=p/'out';out.mkdir()
            with self.assertRaisesRegex(ValueError,'KCL'):canonical_curve(p,out,'low')
    def test_duplicate_target_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);self.fixture(p,extra=.4);out=p/'out';out.mkdir()
            with self.assertRaises(ValueError):canonical_curve(p,out,'low')
    def test_native_export_disagreement_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);self.fixture(p);f=p/'low_drain.dat';f.write_text(f.read_text().replace('1e-09','2e-09'));out=p/'out';out.mkdir()
            with self.assertRaisesRegex(ValueError,'Native/export'):canonical_curve(p,out,'low')
    def test_deck_has_explicit_targets_previous_and_unchanged_geometry(self):
        spec=importlib.util.spec_from_file_location('generate',STUDY/'python/generate.py');g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
        text,required=deck(g,dict(g.PARAMETERS,workfunction_eV=4.55),.5,'none')
        self.assertEqual(text.count('\nsolve previous\n'),4)
        self.assertNotIn('vstep=',text);self.assertIn('solve vdrain=0.6 previous',text)
        self.assertEqual(text.count('solve vgate='),240);self.assertIn('idvg_low_rev.log',required)
        original=g.deck(dict(g.PARAMETERS,workfunction_eV=4.55),linear_solver='bicgst',mesh_style='anisotropic',processors=4,quantum_mode='none',mesh_scale=.5)
        self.assertEqual(text.split('method gummel newton')[0],original.split('method gummel newton')[0])
    def test_full_validation_writes_separate_synthetic_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);execution=p/'gaa/execution';execution.mkdir(parents=True)
            (p/'gaa/process.json').write_text(json.dumps(dict(returncode=0,timeout=False,missing=[],fatal_lines=[])))
            (execution/'solver.out').write_text('ATLAS version synthetic finished\n')
            for bias,vd in [('low',.05),('high',.6)]:
                for rev in [False,True]:
                    suffix='_rev' if rev else '';xs=[-.2+.02*i for i in range(51)];xs.sort(reverse=rev)
                    lines=['f 3 "gate" "source" "drain"'];exports={t:[] for t in ['gate','source','drain']}
                    for v in xs:
                        i=4e-9*10**((v-.2)/.065)
                        lines.append('d %.12g 0 0 0 0 %.16g %.12g 0 %.16g'%(v,-i,vd,i))
                        for t,current in [('gate',0),('source',-i),('drain',i)]:exports[t].append('%.12g %.16g'%(v,current))
                    (execution/('idvg_'+bias+suffix+'.log')).write_text('\n'.join(lines))
                    for t,data in exports.items():(execution/(bias+suffix+'_'+t+'.dat')).write_text('\n'.join(data))
            result=validate_folder(p)
            self.assertEqual(result['acquisition_revision'],'explicit_bias_v1')
            self.assertEqual(result['physical_validation'],'NOT_VALIDATED')
            self.assertAlmostEqual(result['metrics']['low']['Vth_V'],.2)
            self.assertTrue((p/'canonical_forward/idvg_low.log').exists())
            self.assertTrue((p/'canonical_reverse/idvg_low.log').exists())

if __name__=='__main__':unittest.main()

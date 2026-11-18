"""Reject truncated/reordered/malformed reverse evidence before it can pass."""
from pathlib import Path
import tempfile,unittest,sys
sys.path.insert(0,str(next(p for p in Path(__file__).resolve().parents[2].glob('*/01_GAA_IdVg/python') if (p/'analyze.py').exists())))
from validate_continuation import canonical

class EvidenceTests(unittest.TestCase):
    def fixture(self,root,count=51):
        for bias in ['low','high']:
            rows=['f 3 "gate" "source" "drain"']
            data=[]
            for n in range(count):
                v=.8-.02*n;rows.append('d %.12g 0 0 0 0 0 0 0 0'%v);data.append('%.12g 1e-9'%v)
            (root/('idvg_'+bias+'_rev.log')).write_text('\n'.join(rows))
            for t in ['drain','source','gate']:(root/(bias+'_rev_'+t+'.dat')).write_text('\n'.join(data))
    def test_valid_reverse_preserved(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);self.fixture(p);raw=(p/'idvg_high_rev.log').read_bytes();canonical(p,p/'canon')
            self.assertEqual(raw,(p/'idvg_high_rev.log').read_bytes());self.assertTrue((p/'canon/high_drain.dat').read_text().startswith('-0.2 '))
    def test_truncated_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);self.fixture(p,50)
            with self.assertRaises(ValueError):canonical(p,p/'canon')
    def test_duplicate_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);self.fixture(p);f=p/'low_rev_drain.dat';s=f.read_text().splitlines();s[5]=s[4];f.write_text('\n'.join(s))
            with self.assertRaises(ValueError):canonical(p,p/'canon')
if __name__=='__main__':unittest.main()

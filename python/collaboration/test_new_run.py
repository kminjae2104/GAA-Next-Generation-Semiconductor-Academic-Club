"""Meaningful safety checks for preservation and path containment."""
from pathlib import Path
import shutil
import tempfile
import unittest

from new_run import ROOT, create_run


class NewRunTests(unittest.TestCase):
    def setUp(self):
        local = ROOT / '.local'
        local.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=local)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        shutil.copytree(ROOT / 'md/양식/실험', self.root / 'md/양식/실험')
        owner = self.root / '연구/팀원실험/권도현'
        owner.mkdir(parents=True)
        (owner / 'README.md').write_text('Registered member', encoding='utf-8')

    def test_scaffold_is_not_simulation_and_has_required_layout(self):
        path = create_run('권도현', 'gate_length', '20261125_lg40_r01', self.root)
        self.assertTrue((path / 'tcad').is_dir())
        self.assertTrue((path / '검증/raw').is_dir())
        self.assertIn('NOT_RUN', (path / 'README.md').read_text(encoding='utf-8'))
        self.assertEqual(list((path / 'tcad').glob('*.in')), [])

    def test_existing_result_unchanged(self):
        path = create_run('권도현', 'gate_length', 'r01', self.root)
        raw = path / '검증/raw/result.log'
        raw.write_bytes(b'original\r\n')
        with self.assertRaises(FileExistsError):
            create_run('권도현', 'gate_length', 'r01', self.root)
        self.assertEqual(raw.read_bytes(), b'original\r\n')

    def test_existing_empty_directory_also_rejected(self):
        path = self.root / '연구/팀원실험/권도현/gate_length/r01'
        path.mkdir(parents=True)
        with self.assertRaises(FileExistsError):
            create_run('권도현', 'gate_length', 'r01', self.root)

    def test_unregistered_and_unsafe_components_rejected(self):
        for member, topic, run_id in [('unknown', 'gate_length', 'r01'), ('권도현', '../escape', 'r01'),
                                      ('../권도현', 'gate_length', 'r01'), ('권도현', 'gate_length', 'C:\\escape'),
                                      ('권도현', 'gate_length', 'CON')]:
            with self.subTest(values=(member, topic, run_id)), self.assertRaises(ValueError):
                create_run(member, topic, run_id, self.root)


if __name__ == '__main__':
    unittest.main()

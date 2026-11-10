import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from measure_final_claims import check_frozen, run
from population_analysis import fingerprint


class FinalMeasurementGateTests(unittest.TestCase):
    def test_signed_artifact_is_checked_and_mutation_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            project = Path(folder)
            source = project / 'frozen.txt'
            source.write_text('accepted')
            signoff = {'artifact_sha256': {'frozen.txt': fingerprint(source)}}
            self.assertEqual(check_frozen(project, signoff), 1)
            source.write_text('changed')
            with self.assertRaisesRegex(ValueError, 'Signed build changed'):
                check_frozen(project, signoff)

    def test_missing_artifact_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(FileNotFoundError):
                check_frozen(Path(folder), {'artifact_sha256': {'missing.txt': 'unused'}})

    def test_unsigned_build_cannot_measure_or_create_claim_output(self):
        with tempfile.TemporaryDirectory() as folder:
            project = Path(folder)
            output = project / 'outputs'
            output.mkdir()
            (output / 'gate_d_signoff_20261028.json').write_text(json.dumps({
                'status': 'pending', 'gate': 'D', 'final_cv_measurement': 'not_permitted'}))
            with self.assertRaisesRegex(ValueError, 'Gate D must be signed first'):
                run(project)
            self.assertFalse((output / 'final_claim_measurements_20261028.json').exists())


if __name__ == '__main__':
    unittest.main()

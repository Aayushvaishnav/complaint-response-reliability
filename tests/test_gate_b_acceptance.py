"""Gate acceptance must reject failed, stale or incomplete upstream evidence."""

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('gate_b_acceptance', ROOT / 'scripts/validate_gate_b.py')
acceptance = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(acceptance)


class GateAcceptanceTests(unittest.TestCase):
    def test_missing_evidence_is_recorded_as_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            with self.assertRaises(FileNotFoundError):
                acceptance.validate(project)
            report = json.loads((project / 'outputs/gate_b_acceptance.json').read_text())
            self.assertEqual(report['status'], 'failed')
            self.assertEqual(report['final_cv_measurement'], 'not_permitted')

    def test_failed_preparation_cannot_run_acceptance_tests(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / 'outputs').mkdir()
            (project / 'config').mkdir()
            (project / 'outputs/typed_preparation_validation.json').write_text(json.dumps({'status': 'failed'}))
            (project / 'config/source.json').write_text('{}')
            with patch.object(acceptance.subprocess, 'run') as runner:
                with self.assertRaisesRegex(ValueError, 'full_preparation_passed'):
                    acceptance.validate(project)
                runner.assert_not_called()
            report = json.loads((project / 'outputs/gate_b_acceptance.json').read_text())
            self.assertFalse(report['checks']['full_preparation_passed'])

    def test_stale_artifact_rejected_before_test_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / 'outputs').mkdir()
            (project / 'config').mkdir()
            scopes = {name: {} for name in ['all', '2023', 'Debt collection', 'CA']}
            paths = ['scripts/prepare_complaints.py', 'sql/prepare_complaints.sql',
                     'config/source.json', 'outputs/source_validation.json',
                     'data/processed/complaints_typed.parquet']
            for relative in paths:
                path = project / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('synthetic artifact')
            (project / 'config/source.json').write_text(json.dumps({'scope_rows': 9469257, 'source_rows': 18590360}))
            prep = {'status': 'passed', 'rows': 9469257,
                    'staging_conservation': {'reconciled': True, 'raw_rows': 18590360,
                                             'scoped_rows': 9469257, 'excluded_rows': 9121103},
                    'source_projection_difference_rows': 0, 'frozen_csv_projection_difference_rows': 0,
                    'parquet_difference_rows': 0,
                    'independent': scopes, 'sql_metrics': scopes,
                    'group_conservation': {name: {'full_csv_match': True, 'rows': 9469257}
                                           for name in ['month', 'product', 'state']},
                    'artifact_sha256': {relative: 'stale' for relative in paths}}
            (project / 'outputs/typed_preparation_validation.json').write_text(json.dumps(prep))
            with patch.object(acceptance.subprocess, 'run') as runner:
                with self.assertRaisesRegex(ValueError, 'current_artifact'):
                    acceptance.validate(project)
                runner.assert_not_called()
            report = json.loads((project / 'outputs/gate_b_acceptance.json').read_text())
            self.assertEqual(report['status'], 'failed')


if __name__ == '__main__':
    unittest.main()

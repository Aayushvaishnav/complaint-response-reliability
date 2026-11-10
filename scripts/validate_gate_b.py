"""Validate current Gate B artifacts and run normal/optimized behavior suites."""

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import duckdb

PROJECT = Path(__file__).resolve().parents[1]


def fingerprint(path):
    with path.open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def validate(project=PROJECT):
    output = project / 'outputs/gate_b_acceptance.json'
    report = {'status': 'failed', 'checked_at_utc': datetime.now(timezone.utc).isoformat(),
              'checks': {}, 'artifact_sha256': {},
              'scope': 'Gate B preparation and synthetic contract mechanics; no full-population priority findings or Power BI acceptance',
              'gate_d_signoff': 'not_granted', 'final_cv_measurement': 'not_permitted'}

    def check(name, condition):
        report['checks'][name] = bool(condition)
        if not condition:
            raise ValueError(f'Gate B acceptance failed: {name}')

    try:
        prep = json.loads((project / 'outputs/typed_preparation_validation.json').read_text(encoding='utf-8'))
        source = json.loads((project / 'config/source.json').read_text(encoding='utf-8'))
        check('full_preparation_passed', prep['status'] == 'passed')
        check('scoped_population_preserved', prep['rows'] == source['scope_rows'] == 9469257)
        conservation = prep['staging_conservation']
        check('raw_retained_excluded_conservation', conservation['reconciled']
              and conservation['raw_rows'] == source['source_rows'] == 18590360
              and conservation['scoped_rows'] == prep['rows']
              and conservation['excluded_rows'] == conservation['raw_rows'] - prep['rows'])
        check('raw_fields_preserved', prep['source_projection_difference_rows'] == 0)
        check('frozen_csv_fields_preserved', prep['frozen_csv_projection_difference_rows'] == 0)
        check('typed_parquet_roundtrip', prep['parquet_difference_rows'] == 0)
        check('independent_four_scope_kpis', set(prep['independent']) == {'all', '2023', 'Debt collection', 'CA'}
              and prep['independent'] == prep['sql_metrics'])
        check('monthly_product_state_conservation', set(prep['group_conservation']) == {'month', 'product', 'state'}
              and all(value['full_csv_match'] and value['rows'] == prep['rows']
                      for value in prep['group_conservation'].values()))
        expected_paths = {'scripts/prepare_complaints.py', 'sql/prepare_complaints.sql',
                          'config/source.json', 'outputs/source_validation.json',
                          'data/processed/complaints_typed.parquet'}
        recorded = prep['artifact_sha256']
        check('preparation_identity_inventory', expected_paths <= recorded.keys())
        for relative, expected in recorded.items():
            actual = fingerprint(project / relative)
            check(f'current_artifact:{relative}', actual == expected)
            report['artifact_sha256'][relative] = actual
        previous = json.loads((project / 'outputs/source_validation.json').read_text(encoding='utf-8'))
        csv_relative = previous['export']['path']
        csv_hash = fingerprint(project / csv_relative)
        check('current_frozen_csv_identity', csv_hash == prep['scoped_csv_sha256'] == previous['export']['sha256'])
        report['artifact_sha256'][csv_relative] = csv_hash
        with duckdb.connect(str(project / 'data/processed/prepared.duckdb'), read_only=True) as connection:
            table_schema = [(row[0], row[1]) for row in connection.execute('DESCRIBE complaints').fetchall()]
            parquet_schema = [(row[0], row[1]) for row in connection.execute(
                'DESCRIBE SELECT * FROM read_parquet(?)',
                [str(project / 'data/processed/complaints_typed.parquet')]).fetchall()]
        check('parquet_field_names_and_types', table_schema == parquet_schema)
        report['typed_schema'] = table_schema

        sys.path.insert(0, str(project / 'scripts'))
        from review_contract import load_rule
        rule = load_rule(project / 'config/review_rule.json')
        check('approved_review_rule', rule['contract_status'] == 'approved_analyst_screening')
        for optimized in (False, True):
            name = 'gate_b_tests_optimized.txt' if optimized else 'gate_b_tests.txt'
            command = [sys.executable, *(['-O'] if optimized else []), '-m', 'unittest',
                       'discover', '-s', str(project / 'tests'), '-v']
            with (project / 'outputs' / name).open('w', encoding='utf-8') as log:
                result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=False)
            check('optimized_behavior_tests' if optimized else 'behavior_tests', result.returncode == 0)
            report['artifact_sha256']['outputs/' + name] = fingerprint(project / 'outputs' / name)
        for relative in ['config/review_rule.json', 'scripts/review_contract.py',
                         'sql/longitudinal_contract.sql', 'tests/test_prepare_complaints.py',
                         'tests/test_review_contract.py', 'tests/test_review_reference.py',
                         'tests/test_gate_b_acceptance.py', 'outputs/review_reference_checks.json',
                         'scripts/validate_gate_b.py', 'docs/metric_dictionary.md',
                         'docs/data_dictionary.md', 'docs/business_requirements.md',
                         'outputs/typed_preparation_validation.json']:
            report['artifact_sha256'][relative] = fingerprint(project / relative)
        report['status'] = 'passed'
    except Exception as error:
        report['error'] = f'{type(error).__name__}: {error}'
        raise
    finally:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, default=PROJECT)
    validate(parser.parse_args().project.resolve())

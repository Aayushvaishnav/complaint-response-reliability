"""Accept current offline Gate C outputs and normal/optimized behavioral suites."""
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys

from population_analysis import check_identity, fingerprint

PROJECT = Path(__file__).resolve().parents[1]


def validate(project=PROJECT):
    report = dict(status='failed', checked_at_utc=datetime.now(timezone.utc).isoformat(),
                  scope='Offline full-population analysis, three volume minima and three filtered base-rule reruns',
                  gate_d_signoff='not_granted', final_cv_measurement='not_permitted', checks={}, artifact_sha256={})

    def check(name, condition):
        report['checks'][name] = bool(condition)
        if not condition:
            raise ValueError(f'Gate C acceptance failed: {name}')

    try:
        analysis = json.loads((project / 'outputs/gate_c_analysis.json').read_text())
        check('analysis_passed', analysis['status'] == 'passed')
        check('current_accepted_inputs', check_identity(project) == analysis['input_sha256'])
        for inventory in ('input_sha256', 'output_sha256', 'implementation_sha256'):
            for path, expected in analysis[inventory].items():
                actual = fingerprint(project / path)
                check('current_artifact:' + path, actual == expected)
                report['artifact_sha256'][path] = actual
        check('four_recomputed_scopes', set(analysis['scopes']) == {'all', '2023', 'Debt collection', 'CA'})
        products = json.loads((project / 'outputs/product_reference_validation.json').read_text())
        gate_b = json.loads((project / 'outputs/gate_b_acceptance.json').read_text())
        check('independent_csv_product_headlines', products['status'] == 'passed'
              and products['rows'] == 9469257 and len(products['products']) == 14
              and products['scoped_csv_sha256'] == gate_b['artifact_sha256']['data/processed/complaints_2023_2025.csv']
              and products['product_overview_sha256'] == fingerprint(project / 'outputs/product_overview.csv')
              and products['implementation_sha256'] == fingerprint(project / 'scripts/verify_product_findings.py'))
        for scope, result in analysis['scopes'].items():
            minima = [50, 100, 200] if scope == 'all' else [100]
            check(f'{scope}:minimum_coverage', [run['minimum'] for run in result['runs']] == minima)
            check(f'{scope}:overview_and_routing_reconciliation', all(result['checks'][name] for name in
                  ['gate_b_independent_csv_counts_match', 'response_mix_reconciles', 'routing_distribution_medians_match']))
            for run in result['runs']:
                reference = run['reference']
                check(f'{scope}:{run["minimum"]}:independent_all_months',
                      reference['rows'] == reference['segments']*reference['months']
                      and reference['persistent_rows'] == run['persistent_windows']
                      and reference['comparisons'] >= reference['rows']*30)
                check(f'{scope}:{run["minimum"]}:measured_exact_ranking',
                      run['exact_rank_replay']['seconds'] >= 0 and run['sql_seconds'] > 0)
        with (project / 'outputs/review_queue.csv').open(newline='', encoding='utf-8') as handle:
            rows = list(csv.DictReader(handle))
        keys = ('company', 'product', 'issue', 'month')
        sets = {n: {tuple(r[k] for k in keys) for r in rows if r['scope'] == 'all' and int(r['minimum']) == n}
                for n in (50, 100, 200)}
        check('nested_volume_minima', sets[200] <= sets[100] <= sets[50])
        for row in rows:
            if row['scope'] != 'all':
                continue
            key = tuple(row[k] for k in keys)
            passing = '/'.join(str(n) for n in (50, 100, 200) if key in sets[n])
            check('passing_minima_and_stability:' + '|'.join(key),
                  row['passing_minima'] == passing and (row['stable_across_volume_minima'] == 'True') == (passing == '50/100/200'))
        for scope, result in analysis['scopes'].items():
            for run in result['runs']:
                check(f'{scope}:{run["minimum"]}:exported_queue_count',
                      sum(r['scope'] == scope and int(r['minimum']) == run['minimum'] for r in rows) == run['persistent_windows'])
        for optimized in (False, True):
            name = 'gate_c_tests_optimized.txt' if optimized else 'gate_c_tests.txt'
            command = [sys.executable, *(['-O'] if optimized else []), '-m', 'unittest',
                       'discover', '-s', str(project / 'tests'), '-v']
            with (project / 'outputs' / name).open('w', encoding='utf-8') as log:
                process = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=False)
            check('optimized_behavior_tests' if optimized else 'behavior_tests', process.returncode == 0)
            report['artifact_sha256']['outputs/' + name] = fingerprint(project / 'outputs' / name)
        for path in ['outputs/gate_c_analysis.json', 'scripts/validate_gate_c.py',
                     'tests/test_analysis_reference.py', 'tests/test_population_analysis.py',
                     'scripts/verify_product_findings.py', 'tests/test_product_reference.py',
                     'outputs/product_reference_validation.json']:
            report['artifact_sha256'][path] = fingerprint(project / path)
        report['status'] = 'passed'
    except Exception as error:
        report['error'] = f'{type(error).__name__}: {error}'
        raise
    finally:
        (project / 'outputs/gate_c_acceptance.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    validate()

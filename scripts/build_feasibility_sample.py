"""Extract and independently check a nonrepresentative, real-data SQL smoke sample."""

import argparse
import csv
import json
import math
import platform
import statistics
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path

import duckdb

from validate_source import COLUMNS, PROJECT, fingerprint, rows


SCOPES = {
    'all': ('TRUE', lambda row: True),
    'received_2023': ("received_date < DATE '2024-01-01'", lambda row: row['Date received'][:4] == '2023'),
    'debt_collection': ('"Product" = \'Debt collection\'', lambda row: row['Product'] == 'Debt collection'),
    'california': ('"State" = \'CA\'', lambda row: row['State'] == 'CA'),
}


def reference_metrics(records):
    yes = sum(record['Timely response?'] == 'Yes' for record in records)
    no = sum(record['Timely response?'] == 'No' for record in records)
    count = len(records)
    unknown = count - yes - no
    lags = []
    for record in records:
        try:
            lag = (date.fromisoformat(record['Date sent to company'])
                   - date.fromisoformat(record['Date received'])).days
        except ValueError:
            continue
        if lag >= 0:
            lags.append(lag)
    return {'complaints': count, 'timely': yes, 'untimely': no, 'unknown': unknown,
            'known': yes + no, 'timely_rate': yes / (yes + no) if yes + no else None,
            'untimely_rate': no / (yes + no) if yes + no else None,
            'unknown_rate': unknown / count if count else None,
            'valid_lags': len(lags),
            'median_routing_days': statistics.median(lags) if lags else None}


def reconcile_metrics(connection, records):
    query = (PROJECT / 'sql/sample_metric_smoke.sql').read_text(encoding='utf-8')
    results = []
    for name, (filter_sql, predicate) in SCOPES.items():
        observed = rows(connection, query.format(filter_sql=filter_sql))[0]
        expected = reference_metrics([record for record in records if predicate(record)])
        for key, value in expected.items():
            actual = observed[key]
            matches = actual == value if value is None or actual is None else math.isclose(
                actual, value, rel_tol=1e-12, abs_tol=1e-12)
            if not matches:
                raise ValueError(f'Independent metric mismatch: {name}/{key}: {actual} != {value}')
        results.append({'filter': name, 'sql': observed, 'reference': expected, 'passed': True})
    return results


def build_sample(connection, directory, rows_per_stratum):
    if isinstance(rows_per_stratum, bool) or not isinstance(rows_per_stratum, int) or rows_per_stratum < 1:
        raise ValueError('rows_per_stratum must be a positive integer')
    directory.mkdir(parents=True, exist_ok=True)
    query = (PROJECT / 'sql/select_feasibility_sample.sql').read_text(encoding='utf-8')
    selected = rows(connection, query, {'rows_per_stratum': rows_per_stratum})
    if not selected:
        raise ValueError('No eligible source rows for the feasibility sample')
    if len({record['Complaint ID'] for record in selected}) != len(selected):
        raise ValueError('Sample contains duplicate complaint IDs')
    expected_strata = {
        (month, product, flag): min(count, rows_per_stratum)
        for month, product, flag, count in connection.execute('''
            SELECT strftime(received_date, '%Y-%m'), "Product", "Timely response?", COUNT(*)
            FROM scoped_source GROUP BY 1, 2, 3''').fetchall()
    }
    strata = Counter((record['Date received'][:7], record['Product'], record['Timely response?'])
                     for record in selected)
    if dict(strata) != expected_strata:
        raise ValueError('Sample does not preserve the specified coverage of every source stratum')
    destination = directory / 'gate_a_sample.csv'
    with destination.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(selected)
    database = directory / 'gate_a_sample.duckdb'
    with duckdb.connect(str(database)) as sample:
        sample.execute('''CREATE OR REPLACE TABLE raw_complaints AS
            SELECT * FROM read_csv(?, header=true, all_varchar=true,
                force_not_null=?, strict_mode=true, ignore_errors=false)''', [str(destination), COLUMNS])
        sample.execute((PROJECT / 'sql/validate_source.sql').read_text(encoding='utf-8'))
        imported = rows(sample, 'SELECT * FROM raw_complaints ORDER BY "Date received", "Complaint ID"')
        if imported != selected:
            raise ValueError('Sample CSV import did not preserve selected source field values')
        results = reconcile_metrics(sample, imported)
        sample.execute('COPY raw_complaints TO ? (FORMAT PARQUET)',
                       [str(directory / 'gate_a_sample.parquet')])
        differences = sample.execute('''SELECT COUNT(*) FROM (
            (SELECT * FROM raw_complaints EXCEPT ALL SELECT * FROM read_parquet(?))
            UNION ALL
            (SELECT * FROM read_parquet(?) EXCEPT ALL SELECT * FROM raw_complaints))''',
            [str(directory / 'gate_a_sample.parquet')] * 2).fetchone()[0]
        if differences:
            raise ValueError('Parquet smoke export changed sample values')
    return {
        'rows': len(selected), 'strata': len(strata), 'rows_per_stratum': rows_per_stratum,
        'received_months': sorted({record['Date received'][:7] for record in selected}),
        'products': sorted({record['Product'] for record in selected}),
        'timely_flags': dict(Counter(record['Timely response?'] for record in selected)),
        'field_values_preserved': True, 'source_stratum_coverage_verified': True,
        'parquet_value_differences': differences,
        'metric_filter_checks': results,
        'sample_csv_sha256': fingerprint(destination),
        'sample_parquet_sha256': fingerprint(directory / 'gate_a_sample.parquet'),
    }


def run(project):
    config = json.loads((project / 'config/source.json').read_text(encoding='utf-8'))
    validation = json.loads((project / 'outputs/source_validation.json').read_text(encoding='utf-8'))
    if validation['status'] != 'passed' or not all(validation['checks'].values()):
        raise ValueError('Prior full source/export validation is required')
    if validation['source']['sha256'] != config['source_sha256']:
        raise ValueError('Source identity differs from the frozen configuration')
    if (config['scope']['received_from_inclusive'], config['scope']['received_until_exclusive']) != (
            validation['scope']['received_from_inclusive'], validation['scope']['received_until_exclusive']):
        raise ValueError('Date scope differs from the validated baseline')
    database = project / config['staging_database']
    with duckdb.connect(str(database), read_only=True) as source:
        source.execute("SET memory_limit = '4GB'")
        source.execute('SET threads = 4')
        source.execute('SET temp_directory = ?', [str(project / 'data/processed/gate_a_temp')])
        full_count = source.execute('SELECT COUNT(*) FROM raw_complaints').fetchone()[0]
        scope_count = source.execute('SELECT COUNT(*) FROM scoped_source').fetchone()[0]
        if (full_count, scope_count) != (config['source_rows'], config['scope_rows']):
            raise ValueError('Staging counts differ from the validated source')
        result = build_sample(source, project / 'data/processed', config['sample']['rows_per_stratum'])
    report = {
        'checked_at_utc': datetime.now(timezone.utc).isoformat(), 'status': 'passed',
        'purpose': config['sample']['purpose'], 'selection': config['sample']['selection'],
        'source_sha256': config['source_sha256'], 'source_rows': full_count, 'scope_rows': scope_count,
        'config_sha256': fingerprint(project / 'config/source.json'),
        'environment': {'python': platform.python_version(), 'duckdb': duckdb.__version__},
        **result,
        'power_bi_desktop_load': 'not_performed; connector route is documented, not refresh-tested',
    }
    (project / 'outputs/gate_a_sample_validation.json').write_text(
        json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, default=PROJECT)
    run(parser.parse_args().project.resolve())

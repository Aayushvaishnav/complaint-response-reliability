"""Validate a supplied CFPB export; preserve raw values and a fixed date cohort."""

import argparse
import csv
import hashlib
import json
import platform
import shutil
from datetime import datetime, timezone
from pathlib import Path

import duckdb


PROJECT = Path(__file__).resolve().parents[1]
COLUMNS = [
    'Date received', 'Product', 'Sub-product', 'Issue', 'Sub-issue',
    'Company public response', 'Company', 'State', 'ZIP code', 'Tags',
    'Submitted via', 'Date sent to company', 'Company response to consumer',
    'Timely response?', 'Complaint ID',
]


def fingerprint(path):
    with path.open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def snapshot(source, destination):
    before = source.stat()
    digest = fingerprint(source)
    if destination.exists():
        if fingerprint(destination) != digest:
            raise ValueError('Existing raw snapshot differs; use a separate project snapshot')
    else:
        shutil.copyfile(source, destination)
    after = source.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError('Source changed during snapshot creation')
    if fingerprint(destination) != digest:
        raise ValueError('Snapshot checksum differs from source')
    return {'bytes': before.st_size, 'sha256': digest,
            'source_modified_utc': datetime.fromtimestamp(before.st_mtime, timezone.utc).isoformat()}


def rows(connection, query, parameters=()):
    result = connection.execute(query, parameters)
    names = [item[0] for item in result.description]
    return [dict(zip(names, values)) for values in result.fetchall()]


def quality(connection, relation):
    count = connection.execute(f'SELECT COUNT(*) FROM {relation}').fetchone()[0]
    missing = rows(connection, 'SELECT ' + ', '.join(
        f'COUNT(*) FILTER (WHERE trim("{name}") = \'\') AS "{name}"'
        for name in COLUMNS) + f' FROM {relation}')[0]
    summary = rows(connection, f"""
        SELECT COUNT(DISTINCT "Complaint ID") AS distinct_complaint_ids,
            COUNT(*) FILTER (WHERE trim("Complaint ID") = '') AS missing_ids,
            COUNT(*) FILTER (WHERE NOT regexp_full_match("Complaint ID", '[0-9]+')) AS non_numeric_ids,
            COUNT(*) FILTER (WHERE received_date IS NULL) AS invalid_or_missing_received_dates,
            COUNT(*) FILTER (WHERE sent_date IS NULL) AS invalid_or_missing_sent_dates,
            COUNT(*) FILTER (WHERE sent_date < received_date) AS negative_routing_lags,
            COUNT(*) FILTER (WHERE received_date > CURRENT_DATE) AS future_received_dates,
            COUNT(*) FILTER (WHERE sent_date > CURRENT_DATE) AS future_sent_dates,
            COUNT(*) FILTER (WHERE timely_response_status = 'Unknown') AS unknown_timely_flags,
            MIN(received_date)::VARCHAR AS min_received_date,
            MAX(received_date)::VARCHAR AS max_received_date
        FROM {relation}
    """)[0]
    duplicates = rows(connection, f"""
        SELECT COUNT(*) AS duplicate_id_groups,
            COALESCE(SUM(n - 1), 0)::BIGINT AS duplicate_extra_rows
        FROM (SELECT "Complaint ID", COUNT(*) AS n FROM {relation}
              GROUP BY "Complaint ID" HAVING COUNT(*) > 1)
    """)[0]
    return {'rows': count, **summary, **duplicates, 'blank_fields': missing}


def export_csv(connection, query, destination):
    connection.execute(f'COPY ({query}) TO ? (HEADER, DELIMITER \',\')', [str(destination)])


def run(source, project):
    raw = project / 'data/raw/complaints.csv'
    processed = project / 'data/processed'
    outputs = project / 'outputs'
    for path in (raw.parent, processed, outputs):
        path.mkdir(parents=True, exist_ok=True)
    print('Preserving and hashing the supplied source', flush=True)
    identity = snapshot(source, raw)
    with raw.open(encoding='utf-8-sig', newline='') as handle:
        header = next(csv.reader(handle))
    if header != COLUMNS:
        raise ValueError(f'Unexpected source columns: {header!r}')
    database = processed / 'source_validation.duckdb'
    with duckdb.connect(str(database)) as connection:
        connection.execute("SET memory_limit = '4GB'")
        connection.execute('SET threads = 4')
        connection.execute('SET temp_directory = ?', [str(processed / 'temp')])
        print('Importing every record with strict CSV parsing', flush=True)
        connection.execute('''CREATE OR REPLACE TABLE raw_complaints AS
            SELECT * FROM read_csv(?, header=true, all_varchar=true,
                force_not_null=?, strict_mode=true, ignore_errors=false)''', [str(raw), COLUMNS])
        connection.execute((PROJECT / 'sql/validate_source.sql').read_text(encoding='utf-8'))
        print('Checking keys, dates, missingness and response categories', flush=True)
        full = quality(connection, 'validated_source')
        scoped = quality(connection, 'scoped_source')
        dispositions = rows(connection, """
            SELECT CASE WHEN received_date IS NULL THEN 'invalid_or_missing_received_date'
                WHEN received_date < DATE '2023-01-01' THEN 'before_2023'
                WHEN received_date >= DATE '2026-01-01' THEN 'after_2025'
                ELSE 'retained_2023_2025' END AS disposition, COUNT(*) AS rows
            FROM validated_source GROUP BY 1 ORDER BY 1
        """)
        for label, relation in [('full', 'validated_source'), ('scoped', 'scoped_source')]:
            for name, columns in [('product_counts', '"Product"'),
                                  ('timely_flags', '"Timely response?"'),
                                  ('response_categories', '"Company response to consumer"'),
                                  ('monthly_counts', "strftime(received_date, '%Y-%m')")]:
                export_csv(connection, f'SELECT {columns} AS category, COUNT(*) AS rows '
                           f'FROM {relation} GROUP BY 1 ORDER BY 1',
                           outputs / f'{label}_{name}.csv')
        checks = {
            'all_records_accounted_for': sum(item['rows'] for item in dispositions) == full['rows'],
            'retained_count_matches_disposition': sum(item['rows'] for item in dispositions
                if item['disposition'] == 'retained_2023_2025') == scoped['rows'],
            'unique_nonblank_numeric_source_ids': full['duplicate_extra_rows'] == 0
                and full['missing_ids'] == 0 and full['non_numeric_ids'] == 0,
            'all_received_dates_parse': full['invalid_or_missing_received_dates'] == 0,
            'nonempty_date_cohort': scoped['rows'] > 0,
        }
        export_state = 'blocked'
        export_info = {}
        if all(checks.values()):
            print('Exporting the date-scoped CSV without changing raw field values', flush=True)
            destination = processed / 'complaints_2023_2025.csv'
            projection = ', '.join(f'"{column}"' for column in COLUMNS)
            export_csv(connection, f'SELECT {projection} FROM scoped_source', destination)
            exported = connection.execute('''SELECT COUNT(*) FROM read_csv(?,
                header=true, all_varchar=true, force_not_null=?, strict_mode=true)''',
                [str(destination), COLUMNS]).fetchone()[0]
            checks['export_count_matches_scope'] = exported == scoped['rows']
            differences = connection.execute(f'''SELECT COUNT(*) FROM (
                (SELECT {projection} FROM scoped_source EXCEPT ALL
                    SELECT * FROM read_csv(?, header=true, all_varchar=true, force_not_null=?))
                UNION ALL
                (SELECT * FROM read_csv(?, header=true, all_varchar=true, force_not_null=?)
                    EXCEPT ALL SELECT {projection} FROM scoped_source))''',
                [str(destination), COLUMNS, str(destination), COLUMNS]).fetchone()[0]
            checks['export_values_match_scope'] = differences == 0
            export_info = {'path': destination.relative_to(project).as_posix(),
                           'rows': exported, 'bytes': destination.stat().st_size,
                           'sha256': fingerprint(destination), 'value_difference_rows': differences}
            export_state = 'passed' if all(checks.values()) else 'failed'
        report = {
            'validated_at_utc': datetime.now(timezone.utc).isoformat(),
            'status': export_state,
            'scope': {'received_from_inclusive': '2023-01-01',
                      'received_until_exclusive': '2026-01-01', 'products': 'all',
                      'field_values': 'preserved; no deduplication or imputation'},
            'source': {'supplied_path': source.as_posix(),
                       'snapshot_path': raw.relative_to(project).as_posix(), **identity,
                       'origin_verification': 'user-supplied; official-download byte identity unverified'},
            'environment': {'python': platform.python_version(), 'duckdb': duckdb.__version__},
            'columns': COLUMNS, 'full': full, 'scoped': scoped,
            'dispositions': dispositions, 'checks': checks, 'export': export_info,
        }
        (outputs / 'source_validation.json').write_text(
            json.dumps(report, indent=2) + '\n', encoding='utf-8')
        print(json.dumps(report, indent=2), flush=True)
        if not all(checks.values()):
            raise ValueError('Source/export validation failed; inspect source_validation.json')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=PROJECT.parents[1] / 'complaints/complaints.csv')
    parser.add_argument('--project', type=Path, default=PROJECT)
    args = parser.parse_args()
    run(args.source.resolve(), args.project.resolve())

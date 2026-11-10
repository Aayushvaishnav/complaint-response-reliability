"""SQL-authoritative typed preparation and independent full CSV reconciliation."""
import csv
import hashlib
import json
import re
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
import duckdb

PROJECT = Path(__file__).resolve().parents[1]
COLUMNS = ['Date received', 'Product', 'Sub-product', 'Issue', 'Sub-issue',
           'Company public response', 'Company', 'State', 'ZIP code', 'Tags',
           'Submitted via', 'Date sent to company', 'Company response to consumer',
           'Timely response?', 'Complaint ID']
FILTERS = {'all': '', '2023': "WHERE received_date < DATE '2024-01-01'",
           'Debt collection': "WHERE Product = 'Debt collection'", 'CA': "WHERE State = 'CA'"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def fingerprint(path):
    with path.open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def parse_date(value):
    if not isinstance(value, str) or not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', value):
        return None
    try:
        return date.fromisoformat(value)
    except (ValueError, TypeError):
        return None


def median(counter):
    n = counter.total()
    if not n:
        return None
    targets = ((n - 1) // 2, n // 2)
    found = []
    cumulative = 0
    for value, count in sorted(counter.items()):
        for target in targets:
            if cumulative <= target < cumulative + count:
                found.append(value)
        cumulative += count
    return sum(found) / 2


def metrics(counts, lags):
    n = counts.total()
    known = counts['Yes'] + counts['No']
    return dict(rows=n, yes=counts['Yes'], no=counts['No'], unknown=counts['Unknown'],
                known=known, timely_rate=counts['Yes'] / known if known else None,
                untimely_rate=counts['No'] / known if known else None,
                unknown_rate=counts['Unknown'] / n if n else None,
                valid_lags=lags.total(), median_routing_days=median(lags))


def audit_csv(path):
    counts = {key: Counter() for key in FILTERS}
    lags = {key: Counter() for key in FILTERS}
    routing = {key: Counter() for key in FILTERS}
    groups = {key: Counter() for key in ('month', 'product', 'state')}
    with path.open(encoding='utf-8-sig', newline='') as handle:
        reader = csv.reader(handle)
        require(next(reader) == COLUMNS, 'Unexpected scoped CSV header')
        for values in reader:
            require(len(values) == len(COLUMNS), 'Invalid CSV row width')
            row = dict(zip(COLUMNS, values))
            received, sent = parse_date(values[0]), parse_date(values[11])
            require(received is not None and date(2023, 1, 1) <= received < date(2026, 1, 1), 'CSV date outside scope')
            flag = values[13] if values[13] in ('Yes', 'No') else 'Unknown'
            lag = (sent - received).days if sent else None
            status = 'missing_or_invalid' if lag is None else 'negative' if lag < 0 else 'valid'
            selected = ['all']
            if received.year == 2023:
                selected.append('2023')
            if row['Product'] == 'Debt collection':
                selected.append('Debt collection')
            if row['State'] == 'CA':
                selected.append('CA')
            for key in selected:
                counts[key][flag] += 1
                routing[key][status] += 1
                if status == 'valid':
                    lags[key][lag] += 1
            for key, value in [('month', received.strftime('%Y-%m-01')), ('product', values[1]), ('state', values[7])]:
                groups[key][value] += 1
    return {key: {**metrics(counts[key], lags[key]), 'routing': dict(routing[key])} for key in FILTERS}, groups


def sql_metrics(connection, where):
    n, yes, no, unknown, valid, med = connection.execute(f'''SELECT count(*),
        count(*) FILTER (WHERE timely_response_status='Yes'),
        count(*) FILTER (WHERE timely_response_status='No'),
        count(*) FILTER (WHERE timely_response_status='Unknown'),
        count(routing_days), median(routing_days) FROM complaints {where}''').fetchone()
    result = dict(rows=n, yes=yes, no=no, unknown=unknown, known=yes+no,
                  timely_rate=yes/(yes+no) if yes+no else None,
                  untimely_rate=no/(yes+no) if yes+no else None,
                  unknown_rate=unknown/n if n else None, valid_lags=valid, median_routing_days=med)
    result['routing'] = dict(connection.execute(f'SELECT routing_status,count(*) FROM complaints {where} GROUP BY 1').fetchall())
    return result


def validate_table(connection):
    n, ids, bad, dates, scope = connection.execute('''SELECT count(*),count(DISTINCT complaint_id),
        count(*) FILTER (WHERE complaint_id IS NULL OR trim(complaint_id)=''),
        count(*) FILTER (WHERE received_date IS NULL),
        count(*) FILTER (WHERE received_date < DATE '2023-01-01' OR received_date >= DATE '2026-01-01') FROM complaints''').fetchone()
    require(n == ids and bad == 0, 'Duplicate or missing complaint IDs')
    require(dates == 0 and scope == 0, 'Invalid received dates or scope')
    return n


def difference(connection, left, right):
    return connection.execute(f'SELECT count(*) FROM ((({left}) EXCEPT ALL ({right})) UNION ALL (({right}) EXCEPT ALL ({left})))').fetchone()[0]


def partitioned_difference(connection, left, right):
    # Exact full-field multiset comparison; month partitions bound hash-table memory
    counts = []
    for query in (left, right):
        count, covered = connection.execute(f'''SELECT count(*), count(*) FILTER (WHERE
            regexp_full_match("Date received", '[0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}}')
            AND TRY_STRPTIME("Date received", '%Y-%m-%d')::DATE >= DATE '2023-01-01'
            AND TRY_STRPTIME("Date received", '%Y-%m-%d')::DATE < DATE '2026-01-01')
            FROM ({query})''').fetchone()
        require(count == covered, 'Equality partition coverage failed; malformed or out-of-scope raw date')
        counts.append(count)
    require(counts[0] == counts[1], 'Equality relation counts differ')
    total = 0
    for year in range(2023, 2026):
        for month in range(1, 13):
            prefix = f'{year}-{month:02d}'
            where = f" WHERE left(\"Date received\", 7) = '{prefix}'"
            total += difference(connection, left + where, right + where)
    return total


def run(project=PROJECT):
    output = project / 'outputs/typed_preparation_validation.json'
    evidence = {'status': 'failed', 'started_at_utc': datetime.now(timezone.utc).isoformat(),
                'gate_signoff': 'not_performed', 'joins': 'none',
                'taxonomy_limit': 'Timing proxy only; not certified schema; August 2023 excluded only from longitudinal comparisons; no crosswalk',
                'provenance_limit': 'Scoped CSV fully hashed against prior evidence; full raw CSV and staging database not rehashed; source/config identity is metadata linkage plus full scoped field equivalence, not fresh official-source verification'}
    try:
        config_path = project / 'config/source.json'
        previous_path = project / 'outputs/source_validation.json'
        config = json.loads(config_path.read_text())
        previous = json.loads(previous_path.read_text())
        evidence['identity'] = {'config_sha256': fingerprint(config_path), 'source_evidence_sha256': fingerprint(previous_path), 'sql_sha256': fingerprint(PROJECT / 'sql/prepare_complaints.sql')}
        require(previous['status'] == 'passed', 'Prior source validation failed')
        require(config['source_sha256'] == previous['source']['sha256'] and config['source_rows'] == previous['full']['rows'] and config['scope_rows'] == previous['scoped']['rows'], 'Source/config identity mismatch')
        require(config['scope']['received_from_inclusive'] == '2023-01-01' and config['scope']['received_until_exclusive'] == '2026-01-01' and config['scope']['historical_category_boundary'] == '2023-08-24', 'Unexpected scope configuration')
        csv_path = project / previous['export']['path']
        print('Hashing scoped CSV', flush=True)
        evidence['scoped_csv_sha256'] = fingerprint(csv_path)
        require(evidence['scoped_csv_sha256'] == previous['export']['sha256'], 'Scoped CSV hash changed')
        print('Independent full CSV streaming audit', flush=True)
        independent, groups = audit_csv(csv_path)
        evidence['independent'] = independent
        processed = project / 'data/processed'
        with duckdb.connect(str(processed / 'prepared.duckdb')) as connection:
            connection.execute("SET memory_limit='4GB'")
            connection.execute('SET threads=4')
            staging = (project / config['staging_database']).resolve().as_posix().replace("'", "''")
            connection.execute(f"ATTACH '{staging}' AS source (READ_ONLY)")
            connection.execute('CREATE OR REPLACE TEMP VIEW scoped_input AS SELECT * FROM source.scoped_source')
            full, scoped = connection.execute('SELECT (SELECT count(*) FROM source.raw_complaints), (SELECT count(*) FROM scoped_input)').fetchone()
            excluded = connection.execute("SELECT count(*) FROM source.validated_source WHERE received_date IS NULL OR received_date < DATE '2023-01-01' OR received_date >= DATE '2026-01-01'").fetchone()[0]
            require(full == previous['full']['rows'] == config['source_rows'] and scoped == previous['scoped']['rows'] == config['scope_rows'] and full == scoped + excluded, 'Staging population conservation failed')
            evidence['staging_conservation'] = dict(raw_rows=full, scoped_rows=scoped, excluded_rows=excluded, reconciled=True)
            print('Building SQL typed table', flush=True)
            connection.execute((PROJECT / 'sql/prepare_complaints.sql').read_text())
            n = validate_table(connection)
            require(n == config['scope_rows'] == independent['all']['rows'], 'Population mismatch')
            projection = ','.join('"'+name+'"' for name in COLUMNS)
            evidence['source_projection_difference_rows'] = partitioned_difference(connection, f'SELECT {projection} FROM complaints', f'SELECT {projection} FROM scoped_input')
            require(evidence['source_projection_difference_rows'] == 0, 'Raw field projection changed')
            connection.execute('CREATE OR REPLACE TEMP TABLE frozen_csv AS SELECT * FROM read_csv(?, header=true, all_varchar=true, force_not_null=?, strict_mode=true, ignore_errors=false)', [str(csv_path), COLUMNS])
            evidence['frozen_csv_projection_difference_rows'] = partitioned_difference(connection, f'SELECT {projection} FROM complaints', f'SELECT {projection} FROM frozen_csv')
            require(evidence['frozen_csv_projection_difference_rows'] == 0, 'Frozen CSV raw field projection changed')
            evidence['sql_metrics'] = {key: sql_metrics(connection, where) for key, where in FILTERS.items()}
            require(evidence['sql_metrics'] == independent, 'Independent headline reconciliation failed')
            for key, column in [('month', 'received_month::VARCHAR'), ('product', 'Product'), ('state', 'State')]:
                sql_groups = dict(connection.execute(f'SELECT {column},count(*) FROM complaints GROUP BY 1').fetchall())
                require(sql_groups == dict(groups[key]) and sum(sql_groups.values()) == n, f'{key} conservation failed')
            evidence['group_conservation'] = {key: {'groups': len(value), 'rows': sum(value.values()), 'full_csv_match': True} for key, value in groups.items()}
            evidence['diagnostics'] = {column: dict(connection.execute(f'SELECT {column}::VARCHAR,count(*) FROM complaints GROUP BY 1').fetchall()) for column in ['taxonomy_era', 'longitudinal_eligible', 'routing_status', 'issue_missing', 'state_missing', 'response_missing']}
            parquet = (processed / 'complaints_typed.parquet').as_posix().replace("'", "''")
            connection.execute(f"COPY complaints TO '{parquet}' (FORMAT PARQUET, COMPRESSION ZSTD)")
            evidence['parquet_difference_rows'] = partitioned_difference(connection, 'SELECT * FROM complaints', f"SELECT * FROM read_parquet('{parquet}')")
            require(evidence['parquet_difference_rows'] == 0, 'Parquet roundtrip changed typed fields')
            evidence['rows'] = n
            evidence['duckdb_version'] = duckdb.__version__
        require(fingerprint(config_path) == evidence['identity']['config_sha256'] and fingerprint(previous_path) == evidence['identity']['source_evidence_sha256'], 'Evidence changed during preparation')
        artifact_paths = ['scripts/prepare_complaints.py', 'sql/prepare_complaints.sql', 'config/source.json', 'outputs/source_validation.json', 'data/processed/complaints_typed.parquet', 'config/review_rule.json']
        evidence['artifact_sha256'] = {path: fingerprint(project / path) for path in artifact_paths if (project / path).is_file()}
        evidence['equality_method'] = 'Full-field bidirectional EXCEPT ALL partitioned by raw received YYYY-MM; every scoped record is in exactly one partition; no hash-based field comparison'
        evidence['status'] = 'passed'
    except Exception as error:
        evidence['error'] = f'{type(error).__name__}: {error}'
        raise
    finally:
        evidence['finished_at_utc'] = datetime.now(timezone.utc).isoformat()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(evidence, indent=2) + '\n')


if __name__ == '__main__':
    run()

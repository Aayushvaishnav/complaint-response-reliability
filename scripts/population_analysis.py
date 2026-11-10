"""Run frozen SQL screening and independent aggregate checks; no report or CV claims."""
import csv
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
from time import perf_counter

import duckdb

from analysis_reference import validate_analysis
from review_contract import load_rule

PROJECT = Path(__file__).resolve().parents[1]
SCOPES = {
    'all': ('TRUE', '2026-01-01', [50, 100, 200]),
    '2023': ("received_date < DATE '2024-01-01'", '2024-01-01', [100]),
    'Debt collection': ("Product = 'Debt collection'", '2026-01-01', [100]),
    'CA': ("State = 'CA'", '2026-01-01', [100]),
}
KEY = ('company', 'product', 'issue', 'month')
QUEUE_FIELDS = [*KEY, 'priority_rank', 'elevated_months', 'window_complaints',
                'window_known', 'window_no', 'window_peer_known', 'window_peer_no',
                'window_unknown', 'window_peer_complaints', 'window_peer_unknown',
                'segment_untimely_pct', 'peer_untimely_pct', 'pooled_excess_pp',
                'passing_minima', 'stable_across_volume_minima']


def require(condition, message):
    if not condition:
        raise ValueError(message)


def fingerprint(path):
    with path.open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def records(cursor):
    names = [column[0] for column in cursor.description]
    while batch := cursor.fetchmany(4096):
        for row in batch:
            yield dict(zip(names, row))


def query_rows(connection, sql, parameters=None):
    cursor = connection.execute(sql) if parameters is None else connection.execute(sql, parameters)
    return list(records(cursor))


def export_csv(path, rows, fields):
    with path.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)


def check_identity(project):
    accepted = json.loads((project / 'outputs/gate_b_acceptance.json').read_text())
    require(accepted['status'] == 'passed' and all(accepted['checks'].values()), 'Gate B is not accepted')
    paths = ['data/processed/complaints_typed.parquet', 'config/review_rule.json',
             'sql/longitudinal_contract.sql', 'scripts/review_contract.py',
             'outputs/typed_preparation_validation.json', 'config/source.json']
    hashes = {path: fingerprint(project / path) for path in paths}
    for path, digest in hashes.items():
        require(digest == accepted['artifact_sha256'][path], f'Gate B artifact changed: {path}')
    load_rule(project / 'config/review_rule.json')
    return hashes


def ranking_replay(connection):
    connection.execute('''CREATE OR REPLACE TEMP TABLE rank_keys AS
        WITH fractions AS (SELECT month,elevated_months,window_no,window_complaints,
        window_no::HUGEINT*window_peer_known-window_peer_no::HUGEINT*window_known n,
        window_known::HUGEINT*window_peer_known d FROM evaluated WHERE persistent)
        SELECT DISTINCT month,elevated_months,window_no,window_complaints,
        n // gcd(abs(n),d) num, d // gcd(abs(n),d) den FROM fractions''')
    volumes = query_rows(connection, '''SELECT month,count(*) distinct_rank_tuples,
        count(*)::HUGEINT*count(*) potential_tuple_pairs FROM rank_keys GROUP BY month ORDER BY month''')
    started = perf_counter()
    ranked = query_rows(connection, '''SELECT a.*, 1+count(b.month) priority_rank
        FROM rank_keys a LEFT JOIN rank_keys b ON a.month=b.month AND
        (b.elevated_months>a.elevated_months OR (b.elevated_months=a.elevated_months AND
        (b.num*a.den>a.num*b.den OR (b.num*a.den=a.num*b.den AND
        (b.window_no>a.window_no OR (b.window_no=a.window_no AND b.window_complaints>a.window_complaints))))))
        GROUP BY ALL''')
    return dict(seconds=perf_counter()-started, distinct_tuples=len(ranked),
                maximum_tuples_per_month=max((r['distinct_rank_tuples'] for r in volumes), default=0),
                potential_tuple_pairs=sum(r['potential_tuple_pairs'] for r in volumes), by_month=volumes)


def reconcile_overview(overview, counts, routing, response, expected):
    for field, source in [('complaints', 'rows'), ('timely', 'yes'), ('untimely', 'no'),
                          ('known', 'known'), ('unknown', 'unknown'), ('valid_routing', 'valid_lags')]:
        require(sum(r[field] for r in overview) == expected[source], f'Overview {field} differs from independent Gate B CSV audit')
    require(sum(r['complaints'] for r in counts) == expected['rows'], 'Segment aggregation lost complaints')
    for row in overview:
        month = row['month']
        members = [r for r in response if r['month'] == month]
        for field in ['complaints', 'timely', 'untimely', 'unknown']:
            require(sum(r[field] for r in members) == row[field], f'Response mix {field} failed')
        lag_counts = sorted((r['routing_days'], r['complaints']) for r in routing
                            if r['month'] == month and r['routing_status'] == 'valid')
        size = sum(n for _, n in lag_counts)
        require(size == row['valid_routing'], 'Routing count failed')
        values, seen = [], 0
        for lag, n in lag_counts:
            values.extend(lag for pos in ((size-1)//2, size//2) if seen <= pos < seen+n)
            seen += n
        median = sum(values)/2 if size else None
        require(median == row['median_routing_days'], 'Routing median failed')
        require(row['complaints'] == row['known']+row['unknown'] == row['timely']+row['untimely']+row['unknown'], 'Flag conservation failed')
    return {'monthly_groups': len(overview), 'complaints': expected['rows'],
            'gate_b_independent_csv_counts_match': True, 'response_mix_reconciles': True,
            'routing_distribution_medians_match': True}


def evaluate_scope(connection, scope, end_date, minima, project, output):
    overview = query_rows(connection, (project / 'sql/monthly_overview.sql').read_text())
    counts = query_rows(connection, (project / 'sql/segment_month_counts.sql').read_text())
    response = query_rows(connection, (project / 'sql/response_mix.sql').read_text())
    routing = query_rows(connection, (project / 'sql/routing_distribution.sql').read_text())
    prior = json.loads((project / 'outputs/typed_preparation_validation.json').read_text())
    checks = reconcile_overview(overview, counts, routing, response, prior['independent'][scope])
    for row in overview:
        row.update(scope=scope, timely_pct=100*row['timely']/row['known'] if row['known'] else None,
                   untimely_pct=100*row['untimely']/row['known'] if row['known'] else None)
    output['overview'].extend(overview)
    if scope == 'all':
        for name, rows in [('response_mix', response), ('routing_distribution', routing)]:
            export_csv(project / f'outputs/{name}.csv', rows, list(rows[0]))
        products = query_rows(connection, (project / 'sql/product_overview.sql').read_text())
        require(sum(r['complaints'] for r in products) == prior['rows'], 'Product reconciliation failed')
        export_csv(project / 'outputs/product_overview.csv', products, list(products[0]))
    runs, queues, month_summaries, history = [], {}, [], []
    sql = (project / 'sql/longitudinal_contract.sql').read_text().rstrip().rstrip(';')
    for minimum in minima:
        print(f'{scope}: minimum {minimum}; executing full longitudinal SQL', flush=True)
        params = dict(start=date(2023, 1, 1), end=date.fromisoformat(end_date), minimum=minimum,
                      companies=None, products=None, states=None, issues=None)
        started = perf_counter()
        connection.execute('CREATE OR REPLACE TEMP TABLE evaluated AS ' + sql, params)
        sql_seconds = perf_counter()-started
        rank_runtime = ranking_replay(connection)
        summary = query_rows(connection, '''SELECT month,count(*) dense_segment_months,
            count(*) FILTER(WHERE complaints>0) observed_segment_months,
            count(*) FILTER(WHERE eligible_month) eligible_segments,
            count(*) FILTER(WHERE window_eligible) eligible_windows,
            count(*) FILTER(WHERE persistent) persistent_windows,
            coalesce(max(priority_rank),0) maximum_dense_rank
            FROM evaluated GROUP BY month ORDER BY month''')
        for row in summary:
            row.update(scope=scope, minimum=minimum)
        month_summaries.extend(summary)
        queue = query_rows(connection, """WITH pooled AS (SELECT *,
            sum(peer_complaints) OVER (PARTITION BY company,product,issue ORDER BY month
                ROWS BETWEEN 2 PRECEDING AND CURRENT ROW) window_peer_complaints FROM evaluated)
            SELECT company,product,issue,month,priority_rank,elevated_months,
            window_complaints,window_known,window_no,window_peer_known,window_peer_no,
            window_complaints-window_known window_unknown,window_peer_complaints,
            window_peer_complaints-window_peer_known window_peer_unknown,
            100.0*window_no/window_known segment_untimely_pct,
            100.0*window_peer_no/window_peer_known peer_untimely_pct,pooled_excess_pp
            FROM pooled WHERE persistent ORDER BY month,priority_rank,company,product,issue""")
        queues[minimum] = queue
        print(f'{scope}: minimum {minimum}; {len(queue)} persistent windows; independent reference', flush=True)
        started = perf_counter()
        reference = validate_analysis(counts, records(connection.execute('SELECT * FROM evaluated')),
                                      start_date='2023-01-01', end_date=end_date, minimum=minimum)
        reference_seconds = perf_counter()-started
        runs.append(dict(minimum=minimum, sql_seconds=sql_seconds, exact_rank_replay=rank_runtime,
                         reference_seconds=reference_seconds, reference=reference,
                         persistent_windows=len(queue), unique_segments=len({tuple(r[k] for k in KEY[:3]) for r in queue})))
        # Monthly evidence for every segment that qualifies at this minimum
        histories = query_rows(connection, '''SELECT e.company,e.product,e.issue,e.month,e.complaints,e.known,e.untimely,
            e.complaints-e.known unknown,e.peer_complaints,e.peer_known,e.peer_untimely,
            e.issue_share,e.prior_issue_share,e.issue_share_change_pp,e.complete_month,e.era,
            e.eligible_month,e.elevated,e.window_eligible,e.persistent,e.priority_rank
            FROM evaluated e WHERE EXISTS(SELECT 1 FROM evaluated p WHERE p.persistent
            AND e.company IS NOT DISTINCT FROM p.company AND e.product IS NOT DISTINCT FROM p.product
            AND e.issue IS NOT DISTINCT FROM p.issue)
            ORDER BY e.company,e.product,e.issue,e.month''')
        for row in histories:
            row.update(scope=scope, minimum=minimum)
        history.extend(histories)
    memberships = {}
    for minimum, queue in queues.items():
        for row in queue:
            memberships.setdefault(tuple(row[k] for k in KEY), []).append(minimum)
    for minimum, queue in queues.items():
        for row in queue:
            passing = memberships[tuple(row[k] for k in KEY)]
            row.update(scope=scope, minimum=minimum, passing_minima='/'.join(map(str, passing)),
                       stable_across_volume_minima=passing == [50, 100, 200])
            output['queue'].append(row)
    if scope == 'all':
        sets = {n: {tuple(row[k] for k in KEY) for row in q} for n, q in queues.items()}
        require(sets[200] <= sets[100] <= sets[50], 'Sensitivity is not nested')
        checks['nested_volume_sensitivity'] = True
        checks['stable_windows'] = len(sets[200])
    output['summary'].extend(month_summaries)
    output['history'].extend(history)
    return dict(checks=checks, runs=runs)


def run(project=PROJECT):
    result = dict(status='failed', started_at_utc=datetime.now(timezone.utc).isoformat(),
                  gate_d_signoff='not_granted', final_cv_measurement='not_permitted')
    destination = project / 'outputs/gate_c_analysis.json'
    try:
        result['input_sha256'] = check_identity(project)
        result['source_sha256'] = json.loads((project / 'config/source.json').read_text())['source_sha256']
        result['environment'] = dict(duckdb=duckdb.__version__, threads=4, memory_limit='4GB')
        result['limits'] = ['No fresh raw/scoped CSV hash or live official export comparison; typed Parquet hash matches Gate B.',
                            'Timing-era proxy; August retained in descriptions and excluded from longitudinal windows.',
                            'Offline descriptive screening; no exposure adjustment, significance or causal claim.',
                            'Timings are single local development runs with warm/cold caches uncontrolled; no UI latency claim.',
                            'Filtered queues are recomputed at minimum 100; volume sensitivity 50/100/200 is full-population only.']
        output = {key: [] for key in ('overview', 'queue', 'summary', 'history')}
        with duckdb.connect() as connection:
            connection.execute("SET memory_limit='4GB'")
            connection.execute('SET threads=4')
            connection.read_parquet(str(project / 'data/processed/complaints_typed.parquet')).create_view('complaints')
            result['scopes'] = {}
            for scope, (where, end_date, minima) in SCOPES.items():
                connection.execute('CREATE OR REPLACE TEMP VIEW selected_complaints AS SELECT * FROM complaints WHERE ' + where)
                connection.execute('''CREATE OR REPLACE TEMP VIEW contract_input AS SELECT complaint_id,received_date,
                    Company company,Product product,Issue issue,State state,"Timely response?" timely_flag FROM selected_complaints''')
                result['scopes'][scope] = evaluate_scope(connection, scope, end_date, minima, project, output)
        fields = {'overview': ['scope', *[k for k in output['overview'][0] if k != 'scope']],
                  'queue': ['scope', 'minimum', *QUEUE_FIELDS],
                  'summary': ['scope', 'minimum', *[k for k in output['summary'][0] if k not in ('scope', 'minimum')]],
                  'history': ['scope', 'minimum', *[k for k in output['history'][0] if k not in ('scope', 'minimum')]]}
        names = dict(overview='monthly_overview', queue='review_queue', summary='review_monthly_summary', history='review_segment_history')
        for key, rows in output.items():
            export_csv(project / f'outputs/{names[key]}.csv', rows, fields[key])
        result['output_sha256'] = {f'outputs/{name}.csv': fingerprint(project / f'outputs/{name}.csv')
                                   for name in [*names.values(), 'response_mix', 'routing_distribution', 'product_overview']}
        code = ['scripts/population_analysis.py', 'scripts/analysis_reference.py', *[str(p.relative_to(project)).replace('\\', '/') for p in sorted((project / 'sql').glob('*.sql'))]]
        result['implementation_sha256'] = {path: fingerprint(project / path) for path in code}
        require(check_identity(project) == result['input_sha256'], 'Inputs changed during analysis')
        result['status'] = 'passed'
    except Exception as error:
        result['error'] = f'{type(error).__name__}: {error}'
        raise
    finally:
        result['finished_at_utc'] = datetime.now(timezone.utc).isoformat()
        destination.write_text(json.dumps(result, indent=2, default=str)+'\n')
    print(json.dumps(result, indent=2, default=str), flush=True)


if __name__ == '__main__':
    run()

"""Fresh canonical SQL expectations; development reconciliation, not CV measurement."""
import datetime as dt
import csv
import hashlib
import json
from pathlib import Path
from time import perf_counter

import duckdb
from review_contract import load_rule

ROOT = Path(__file__).resolve().parents[1]
MEASURES = {'eligible_windows': 'Eligible Window Count',
            'qualifying_windows': 'Qualifying Window Count',
            'qualifying_segments': 'Qualifying Segment Count',
            'stable_windows': 'Stable Window Count'}
SCOPES = {
    'all': ('2026-01-01', None, None, []),
    'received_2023': ('2024-01-01', None, None, ["'Date'[Year] = 2023"]),
    'debt_collection': ('2026-01-01', ['Debt collection'], None, ["FILTER(ALL('Product'), 'Product'[Product] = \"Debt collection\")"]),
    'california': ('2026-01-01', None, ['CA'], ["FILTER(ALL('Geography'), 'Geography'[State] = \"CA\")"]),
}


def query(measures, filters):
    row = 'ROW(' + ', '.join(f'"{k}", [{v}]' for k, v in measures.items()) + ')'
    return 'EVALUATE CALCULATETABLE(' + ', '.join([row, *filters]) + ')'


def parameters(end='2026-01-01', minimum=100, products=None, states=None, start='2023-01-01'):
    return dict(start=dt.date.fromisoformat(start), end=dt.date.fromisoformat(end),
                minimum=minimum, companies=None, products=products, states=states, issues=None)


def canonical_sql(project=ROOT):
    load_rule(project / 'config/review_rule.json')
    return (project / 'sql/longitudinal_contract.sql').read_text().strip().rstrip(';')


def summary(connection, sql, params):
    """Fetch one aggregate row only; canonical ranking remains unchanged."""
    cursor = connection.execute('''SELECT count(*) FILTER(WHERE window_eligible) eligible_windows,
        count(*) FILTER(WHERE persistent) qualifying_windows,
        count(DISTINCT (company,product,issue)) FILTER(WHERE persistent) qualifying_segments
        FROM (''' + sql + ') canonical', params)
    return dict(zip([c[0] for c in cursor.description], cursor.fetchall()[0]))


def build_plan(connection, source, project=ROOT, scopes=SCOPES):
    connection.read_parquet(str(source)).create_view('typed_input', replace=True)
    connection.execute('''CREATE OR REPLACE TEMP VIEW contract_input AS
        SELECT complaint_id,received_date,Company company,Product product,Issue issue,State state,
        timely_response_status timely_flag FROM typed_input''')
    sql = canonical_sql(project)
    cases = []
    for scope, (end, products, states, filters) in scopes.items():
        scope_cases = []
        for minimum in (50, 100, 200):
            started = perf_counter()
            expected = summary(connection, sql, parameters(end, minimum, products, states))
            scope_cases.append(dict(id=f'{scope}_{minimum}', scope=scope, minimum=minimum,
                expected=expected, sql_seconds=perf_counter()-started,
                query=query(MEASURES, [f"'Review Minimum'[Minimum] = {minimum}", *filters])))
        # Monotone inclusive volume constraints; 200 qualifies at all three minima
        stable = scope_cases[-1]['expected']['qualifying_windows']
        for case in scope_cases:
            case['expected']['stable_windows'] = stable
        cases.extend(scope_cases)
    return cases


def focal(connection, project=ROOT):
    with (project / 'outputs/review_queue.csv').open(newline='', encoding='utf-8') as stream:
        matches = [r for r in csv.DictReader(stream) if r['scope'] == 'all' and r['minimum'] == '100'
                   and r['company'] == 'MOHELA' and r['month'] == '2025-12-01'
                   and r['issue'] == 'Dealing with your lender or servicer']
    if len(matches) != 1:
        raise ValueError('Require one Gate C focal issue row')
    row = matches[0]
    keys = connection.execute('''SELECT selection_key,segment_key FROM read_parquet(?)
        WHERE company_raw=? AND product_raw=? AND issue_raw=? AND window_end=DATE '2025-12-01' ''',
        [str(project / 'data/processed/model-input/review_selection.parquet'), row['company'], row['product'], row['issue']]).fetchall()
    if len(keys) != 1:
        raise ValueError('Require one focal selection identity')
    fields = ['complaints','known','untimely','peer_complaints','peer_known','peer_untimely',
              'eligible_month','elevated','window_eligible','persistent','elevated_months',
              'window_complaints','window_known','window_no','window_peer_known','window_peer_no',
              'pooled_excess_pp','priority_rank']
    cursor = connection.execute('SELECT month,' + ','.join(fields) + ' FROM (' + canonical_sql(project) + ''') c
        WHERE company=$fcompany AND product=$fproduct AND issue=$fissue
        AND month >= DATE '2025-10-01' ORDER BY month''',
        dict(parameters(), fcompany=row['company'], fproduct=row['product'], fissue=row['issue']))
    diagnostics = [dict(zip([c[0] for c in cursor.description], r)) for r in cursor.fetchall()]
    return dict(company=row['company'], product=row['product'], issue=row['issue'],
                selection_key=keys[0][0], segment_key=keys[0][1], minimum=100, diagnostics=diagnostics)


def main():
    started = perf_counter()
    accepted = json.loads((ROOT / 'outputs/model_foundation_readback.json').read_text())
    if accepted['status'] != 'passed':
        raise ValueError('Foundation source identity is not accepted')
    hashes = {}
    for relative in ('data/processed/complaints_typed.parquet', 'sql/longitudinal_contract.sql',
                     'config/review_rule.json', 'data/processed/model-input/review_selection.parquet'):
        with (ROOT / relative).open('rb') as stream:
            hashes[relative] = hashlib.file_digest(stream, 'sha256').hexdigest()
        if hashes[relative] != accepted['current_projection_hashes'][relative]:
            raise ValueError(f'Accepted artifact changed: {relative}')
    with duckdb.connect() as connection:
        connection.execute("SET threads=4")
        connection.execute("SET memory_limit='4GB'")
        cases = build_plan(connection, ROOT / 'data/processed/complaints_typed.parquet')
        focus = focal(connection)
    result = dict(status='expectations_generated', scope='Development reconciliation; not CV measurement; live DAX not executed',
        created_at_utc=dt.datetime.now(dt.timezone.utc).isoformat(), input_sha256=hashes,
        dax_reference='https://learn.microsoft.com/en-us/dax/calculatetable-function-dax',
        cases=cases, focal=focus, seconds=perf_counter()-started)
    destination = ROOT / 'outputs/live_priority_plan.json'
    destination.write_text(json.dumps(result, indent=2, default=str)+'\n', encoding='utf-8')
    print(json.dumps(dict(path=str(destination), seconds=result['seconds'], counts={c['id']:c['expected'] for c in cases}), indent=2))


if __name__ == '__main__':
    main()

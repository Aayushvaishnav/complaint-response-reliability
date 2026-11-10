"""Canonical queue expectations; development reconciliation, not CV measurement."""
import datetime as dt
import hashlib
import json
from time import perf_counter

import duckdb
from live_priority_plan import ROOT, SCOPES, canonical_sql, parameters

REFERENCES = ['https://learn.microsoft.com/en-us/dax/summarizecolumns-function-dax',
              'https://learn.microsoft.com/en-us/dax/addcolumns-function-dax']
FIELDS = {
    'rank': ('priority_rank', 'Priority Rank'),
    'window_no': ('window_no', 'Window No Count'),
    'window_known': ('window_known', 'Window Known Count'),
    'window_peer_no': ('window_peer_no', 'Window Peer No Count'),
    'window_peer_known': ('window_peer_known', 'Window Peer Known Count'),
    'window_complaints': ('window_complaints', 'Window Complaint Count'),
    'elevated_months': ('elevated_months', 'Elevated Months'),
    'pooled_gap_pp': ('pooled_excess_pp', 'Pooled Gap pp'),
}


def queue_query(filters):
    additions = ', '.join(f'"{key}", [{measure}]' for key, (_, measure) in FIELDS.items() if key != 'rank')
    additions += ', "passing_minima", [Passing Minima]'
    columns = ', '.join(f'"{key}", [{key}]' for key in [*FIELDS, 'passing_minima'])
    return ('EVALUATE CALCULATETABLE(SELECTCOLUMNS(ADDCOLUMNS('
            'FILTER(SUMMARIZECOLUMNS(\'Review Selection\'[Selection Key], '
            '"rank", [Priority Rank]), NOT ISBLANK([rank])), ' + additions + '), '
            '"selection_key", \'Review Selection\'[Selection Key], ' + columns + '), '
            + ', '.join(filters) + ') ORDER BY [selection_key]')


def build_plan(connection, source, project=ROOT, selection_source=None):
    connection.read_parquet(str(source)).create_view('typed_input', replace=True)
    connection.execute('''CREATE OR REPLACE TEMP VIEW contract_input AS
        SELECT complaint_id,received_date,Company company,Product product,Issue issue,State state,
        timely_response_status timely_flag FROM typed_input''')
    selection_source = selection_source or project / 'data/processed/model-input/review_selection.parquet'
    connection.read_parquet(str(selection_source)).create_view('selection_input', replace=True)
    sql = canonical_sql(project)
    cases = []
    for scope, (end, products, states, filters) in SCOPES.items():
        scope_cases = []
        for minimum in (50, 100, 200):
            started = perf_counter()
            projection = ', '.join(f'c.{column} AS {key}' for key, (column, _) in FIELDS.items())
            cursor = connection.execute('''SELECT s.selection_key, ''' + projection + '''
                FROM (''' + sql + ''') c LEFT JOIN selection_input s
                ON c.company IS NOT DISTINCT FROM s.company_raw
                AND c.product IS NOT DISTINCT FROM s.product_raw
                AND c.issue IS NOT DISTINCT FROM s.issue_raw AND c.month=s.window_end
                WHERE c.persistent ORDER BY s.selection_key''', parameters(end, minimum, products, states))
            rows = [dict(zip([c[0] for c in cursor.description], row)) for row in cursor.fetchall()]
            keys = [row['selection_key'] for row in rows]
            if None in keys or len(set(keys)) != len(keys):
                raise ValueError('Persistent canonical rows require unique selection identities')
            scope_cases.append(dict(id=f'{scope}_{minimum}', scope=scope, minimum=minimum,
                keyColumns=['selection_key'], expectedRows=rows,
                query=queue_query([f"'Review Minimum'[Minimum] = {minimum}", *filters]),
                sql_seconds=perf_counter()-started))
        memberships = {case['minimum']: {r['selection_key'] for r in case['expectedRows']} for case in scope_cases}
        for case in scope_cases:
            for row in case['expectedRows']:
                row['passing_minima'] = '/'.join(str(m) for m, keys in memberships.items() if row['selection_key'] in keys)
        cases.extend(scope_cases)
    return cases


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
        connection.execute('SET threads=4')
        connection.execute("SET memory_limit='4GB'")
        cases = build_plan(connection, ROOT / 'data/processed/complaints_typed.parquet')
    result = dict(status='expectations_generated',
        scope='Development reconciliation; not CV measurement; live DAX not executed',
        created_at_utc=dt.datetime.now(dt.timezone.utc).isoformat(), input_sha256=hashes,
        dax_references=REFERENCES, keyColumns=['selection_key'], cases=cases,
        seconds=perf_counter()-started)
    destination = ROOT / 'outputs/live_queue_plan.json'
    destination.write_text(json.dumps(result, indent=2, default=str)+'\n', encoding='utf-8')
    print(json.dumps(dict(path=str(destination), seconds=result['seconds'],
        counts={c['id']: len(c['expectedRows']) for c in cases}), indent=2))


if __name__ == '__main__':
    main()

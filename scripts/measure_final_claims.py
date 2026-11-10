"""Measure final F1 claims only after signed Gate D; preserve analytical outputs."""
from datetime import datetime, timezone
import json
from pathlib import Path

import duckdb
from analysis_reference import validate_analysis
from live_priority_plan import canonical_sql, parameters
from population_analysis import fingerprint, query_rows, records, require
from verify_product_findings import product_counts

PROJECT = Path(__file__).resolve().parents[1]


def check_frozen(project, signoff):
    changed = [name for name, digest in signoff['artifact_sha256'].items()
               if fingerprint(project / name) != digest]
    require(not changed, f'Signed build changed: {changed}')
    return len(signoff['artifact_sha256'])


def run(project=PROJECT):
    signoff_path = project / 'outputs/gate_d_signoff_20261028.json'
    signoff = json.loads(signoff_path.read_text())
    require(signoff['status'] == 'passed' and signoff['gate'] == 'D' and
            signoff['final_cv_measurement'] == 'permitted_after_this_signoff', 'Gate D must be signed first')
    result = dict(status='running', started_at_utc=datetime.now(timezone.utc).isoformat(),
                  gate_d_signed_at_utc=signoff['signed_at_utc'], gate_d_sha256=fingerprint(signoff_path))
    destination = project / 'outputs/final_claim_measurements_20261028.json'
    try:
        result['frozen_artifacts_checked_before'] = check_frozen(project, signoff)
        with duckdb.connect() as connection:
            connection.execute('SET threads=4')
            connection.read_parquet(str(project / 'data/processed/complaints_typed.parquet')).create_view('selected_complaints')
            result['population'] = query_rows(connection, '''SELECT count(*) complaints,
                count(DISTINCT complaint_id) distinct_ids, count(DISTINCT Product) raw_product_labels,
                count(DISTINCT date_trunc('month',received_date)) received_months,
                min(received_date) first_received, max(received_date) last_received,
                count(*) FILTER(WHERE timely_response_status='Yes') yes,
                count(*) FILTER(WHERE timely_response_status='No') no,
                count(*) FILTER(WHERE timely_response_status NOT IN ('Yes','No') OR timely_response_status IS NULL) unknown
                FROM selected_complaints''')[0]
            counts = query_rows(connection, (project / 'sql/segment_month_counts.sql').read_text())
            connection.execute('''CREATE VIEW contract_input AS SELECT complaint_id,received_date,
                Company company,Product product,Issue issue,State state,
                timely_response_status timely_flag FROM selected_complaints''')
            sql = canonical_sql(project)
            result['screening'] = []
            queues = {}
            for minimum in (50, 100, 200):
                connection.execute('CREATE OR REPLACE TEMP TABLE evaluated AS ' + sql, parameters(minimum=minimum))
                summary = query_rows(connection, '''SELECT count(*) FILTER(WHERE window_eligible) eligible_windows,
                    count(*) FILTER(WHERE persistent) qualifying_windows,
                    count(DISTINCT (company,product,issue)) FILTER(WHERE persistent) qualifying_segments
                    FROM evaluated''')[0]
                reference = validate_analysis(counts, records(connection.execute('SELECT * FROM evaluated')),
                    start_date='2023-01-01', end_date='2026-01-01', minimum=minimum)
                queue = query_rows(connection, '''SELECT company,product,issue,month FROM evaluated WHERE persistent''')
                queues[minimum] = {(r['company'], r['product'], r['issue'], r['month']) for r in queue}
                result['screening'].append(dict(minimum=minimum, **summary, independent_reference=reference))
                print(f'Final minimum {minimum}: {summary}', flush=True)
            require(queues[200] <= queues[100] <= queues[50], 'Sensitivity sets must nest')
            result['stable_windows'] = len(queues[50] & queues[100] & queues[200])
            focus = []
            for minimum in (50, 100, 200):
                focus.extend(query_rows(connection, '''SELECT $minimum minimum,month,complaints,known,untimely,
                    peer_complaints,peer_known,peer_untimely,window_eligible,persistent,elevated_months,
                    window_no,window_known,window_peer_no,window_peer_known,pooled_excess_pp,priority_rank
                    FROM (''' + sql + ''') c WHERE company='MOHELA' AND product='Student loan'
                    AND issue='Dealing with your lender or servicer' AND month=DATE '2025-12-01' ''', parameters(minimum=minimum)))
            result['mohela_december_2025'] = focus
        print('Starting independent full-CSV product/flag audit', flush=True)
        with (project / 'data/processed/complaints_2023_2025.csv').open(encoding='utf-8-sig', newline='') as handle:
            independent = product_counts(handle)
        result['independent_csv'] = dict(products=independent,
            complaints=sum(x['complaints'] for x in independent.values()),
            yes=sum(x['timely'] for x in independent.values()),
            no=sum(x['untimely'] for x in independent.values()),
            unknown=sum(x['unknown'] for x in independent.values()))
        for key in ('complaints', 'yes', 'no', 'unknown'):
            require(result['population'][key] == result['independent_csv'][key], f'CSV disagrees on {key}')
        require(len(independent) == result['population']['raw_product_labels'], 'CSV product count differs')
        acceptance = json.loads((project / 'outputs/clean_refresh_reconciliation_20261028.json').read_text())
        require(acceptance['status'] == 'passed', 'Clean-copy reconciliation must pass')
        result['live_reconciliation'] = dict(operations=len(acceptance['operations']),
            field_comparisons=sum(x.get('reconciliation', {}).get('fields', 0) for x in acceptance['operations']),
            evidence_sha256=fingerprint(project / 'outputs/clean_refresh_reconciliation_20261028.json'))
        result['report_pages'] = len(json.loads((project / 'reports/powerbi/F1.Report/definition/pages/pages.json').read_text())['pageOrder'])
        result['model_inventory'] = json.loads((project / 'outputs/final_live_model_inventory_20261028.json').read_text())
        result['frozen_artifacts_checked_after'] = check_frozen(project, signoff)
        result['scope'] = 'Frozen received-date cohorts 2023-01-01 through 2025-12-31; original raw product/issue labels; three complete same-era months; 1pp elevation in at least two months; monthly volume minima 50/100/200'
        result['limits'] = ['Windows overlap; counts are not independent events or distinct complaints',
            'Analyst screening thresholds, not regulatory standards or significance tests',
            'Original download date and current official-export identity unverified; no fresh full raw-source hash',
            'Routing lag is not resolution time; no exposure denominator or achieved service improvement',
            'Model inventory is live MCP readback; UI interactions are separately owner-reported']
        result['status'] = 'measured'
    except Exception as error:
        result.update(status='failed', error=f'{type(error).__name__}: {error}')
        raise
    finally:
        result['finished_at_utc'] = datetime.now(timezone.utc).isoformat()
        destination.write_text(json.dumps(result, indent=2, default=str) + '\n', encoding='utf-8')
    print(f'Final measurements: {destination}', flush=True)


if __name__ == '__main__':
    run()

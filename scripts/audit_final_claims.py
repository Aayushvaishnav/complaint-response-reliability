"""Independently audit post-build claims, including focal monthly rational arithmetic."""
from datetime import datetime, timezone
from fractions import Fraction
import json
from pathlib import Path

import duckdb
from measure_final_claims import check_frozen
from population_analysis import fingerprint, query_rows, require

PROJECT = Path(__file__).resolve().parents[1]


def monthly_screen(monthly, minimum):
    eligible = [r['segment_complaints'] >= minimum and r['peer_complaints'] >= minimum
                and r['segment_known'] > 0 and r['peer_known'] > 0 for r in monthly]
    elevated = sum(ok and Fraction(r['segment_no'], r['segment_known']) -
                   Fraction(r['peer_no'], r['peer_known']) >= Fraction(1, 100)
                   for r, ok in zip(monthly, eligible))
    volume_ok = len(monthly) == 3 and all(eligible)
    return dict(volume_eligible=volume_ok, elevated_months=elevated,
                persistent=volume_ok and elevated >= 2)


def audit(project=PROJECT):
    measured_path = project / 'outputs/final_claim_measurements_20261028.json'
    measured = json.loads(measured_path.read_text())
    signed = json.loads((project / 'outputs/gate_d_signoff_20261028.json').read_text())
    require(measured['status'] == 'measured', 'Final measurement must complete')
    require(datetime.fromisoformat(measured['started_at_utc']) > datetime.fromisoformat(signed['signed_at_utc']),
            'Final measurement must follow Gate D')
    require(measured['gate_d_sha256'] == fingerprint(project / 'outputs/gate_d_signoff_20261028.json'), 'Sign-off changed')
    population = measured['population']
    require(population['complaints'] == population['distinct_ids'] == measured['independent_csv']['complaints'], 'Population identity/count mismatch')
    require(population['yes'] + population['no'] + population['unknown'] == population['complaints'], 'Flag conservation failed')
    for case in measured['screening']:
        require(case['independent_reference']['persistent_rows'] == case['qualifying_windows'], 'Independent screening count mismatch')
        require(case['independent_reference']['comparisons'] > 0, 'Reference checks missing')
    with duckdb.connect() as connection:
        connection.read_parquet(str(project / 'data/processed/complaints_typed.parquet')).create_view('complaints')
        monthly = query_rows(connection, '''SELECT date_trunc('month',received_date)::DATE AS month,
            count(*) FILTER(WHERE Issue='Dealing with your lender or servicer') segment_complaints,
            count(*) FILTER(WHERE Issue='Dealing with your lender or servicer' AND timely_response_status IN ('Yes','No')) segment_known,
            count(*) FILTER(WHERE Issue='Dealing with your lender or servicer' AND timely_response_status='No') segment_no,
            count(*) FILTER(WHERE Issue IS DISTINCT FROM 'Dealing with your lender or servicer') peer_complaints,
            count(*) FILTER(WHERE Issue IS DISTINCT FROM 'Dealing with your lender or servicer' AND timely_response_status IN ('Yes','No')) peer_known,
            count(*) FILTER(WHERE Issue IS DISTINCT FROM 'Dealing with your lender or servicer' AND timely_response_status='No') peer_no
            FROM complaints WHERE Company='MOHELA' AND Product='Student loan'
            AND received_date>=DATE '2025-10-01' AND received_date<DATE '2026-01-01'
            GROUP BY month ORDER BY month''')
    require([str(r['month']) for r in monthly] == ['2025-10-01', '2025-11-01', '2025-12-01'], 'Focal month coverage differs')
    segment_no = sum(r['segment_no'] for r in monthly)
    segment_known = sum(r['segment_known'] for r in monthly)
    peer_no = sum(r['peer_no'] for r in monthly)
    peer_known = sum(r['peer_known'] for r in monthly)
    gap = (Fraction(segment_no, segment_known) - Fraction(peer_no, peer_known)) * 100
    elevated = sum(Fraction(r['segment_no'], r['segment_known']) - Fraction(r['peer_no'], r['peer_known']) >= Fraction(1, 100) for r in monthly)
    sensitivity = {}
    for case in measured['mohela_december_2025']:
        screen = monthly_screen(monthly, case['minimum'])
        sensitivity[case['minimum']] = screen
        require(case['window_no'] == segment_no and case['window_known'] == segment_known and
                case['window_peer_no'] == peer_no and case['window_peer_known'] == peer_known, 'Focal denominator mismatch')
        require(case['elevated_months'] == screen['elevated_months'] and
                case['persistent'] == screen['persistent'], 'Focal rule mismatch')
        require(abs(case['pooled_excess_pp'] - float(gap)) <= 1e-12, 'Focal gap mismatch')
    unchanged = check_frozen(project, signed)
    result = dict(status='verified', reviewed_at_utc=datetime.now(timezone.utc).isoformat(),
        measurement_sha256=fingerprint(measured_path), frozen_artifacts_unchanged=unchanged,
        independent_method='Standalone complaint-grain monthly SQL plus Fraction arithmetic; no canonical window/rank SQL used for focal audit',
        monthly=monthly, focal=dict(segment_no=segment_no, segment_known=segment_known, peer_no=peer_no,
            peer_known=peer_known, gap_pp_fraction=str(gap), gap_pp=float(gap), elevated_months=elevated, sensitivity=sensitivity),
        claims=dict(F1_01='verified', F1_02='verified', F1_03='verified'),
        limits='Historical overlapping screening windows; no causal, current-operational, overall-service-quality or achieved-improvement inference')
    (project / 'outputs/final_claim_audit_20261028.json').write_text(json.dumps(result, indent=2, default=str) + '\n')
    print(json.dumps(result, indent=2, default=str))


if __name__ == '__main__':
    audit()

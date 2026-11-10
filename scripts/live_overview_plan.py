"""Independent complaint-grain SQL expectations and live DAX overview query plan."""
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
SCOPES = {
    'all': ('TRUE', []),
    'received_2023': ("received_date < DATE '2024-01-01'", ["'Date'[Year] = 2023"]),
    'debt_collection': ("product = 'Debt collection'", ["FILTER(ALL('Product'), 'Product'[Product] = \"Debt collection\")"]),
    'california': ("state = 'CA'", ["FILTER(ALL('Geography'), 'Geography'[State] = \"CA\")"]),
    'partial_months': ("received_date >= DATE '2025-10-15' AND received_date < DATE '2025-12-16'",
                       ["'Date'[Date] >= DATE(2025, 10, 15)", "'Date'[Date] <= DATE(2025, 12, 15)"]),
    'empty': ('FALSE', ["'Date'[Date] < DATE(2023, 1, 1)"]),
}
MEASURES = {
    'complaints': 'Complaint Count', 'yes': 'Timely Yes Count', 'no': 'Untimely No Count',
    'unknown': 'Unknown Flag Count', 'known': 'Known Flag Count',
    'timely_rate': 'Timely Response Rate', 'untimely_share': 'Untimely Share',
    'unknown_rate': 'Unknown Flag Rate', 'valid_routing': 'Valid Routing Count',
    'invalid_routing': 'Invalid Routing Count', 'median_routing_days': 'Median Routing Days',
}


def overview_query(filters):
    row = 'ROW(' + ', '.join(f'"{field}", [{measure}]' for field, measure in MEASURES.items()) + ')'
    return 'EVALUATE ' + ('CALCULATETABLE(' + row + ', ' + ', '.join(filters) + ')' if filters else row)


def build_plan(connection, source, scopes=SCOPES):
    """Read original typed complaints; never reconstruct SQL expectations from the model."""
    connection.read_parquet(str(source)).create_view('overview_input', replace=True)
    cases = []
    for scope, (where, filters) in scopes.items():
        cursor = connection.execute(f'''SELECT count(*) complaints,
            count(*) FILTER (WHERE timely_response_status = 'Yes') yes,
            count(*) FILTER (WHERE timely_response_status = 'No') no,
            count(*) FILTER (WHERE timely_response_status NOT IN ('Yes', 'No') OR timely_response_status IS NULL) unknown,
            count(*) FILTER (WHERE timely_response_status IN ('Yes', 'No')) known,
            count(*) FILTER (WHERE routing_status = 'valid') valid_routing,
            count(*) FILTER (WHERE routing_status <> 'valid' OR routing_status IS NULL) invalid_routing,
            median(routing_days) FILTER (WHERE routing_status = 'valid') median_routing_days
            FROM overview_input WHERE {where}''')
        expected = dict(zip((col[0] for col in cursor.description), cursor.fetchall()[0]))
        expected['timely_rate'] = expected['yes'] / expected['known'] if expected['known'] else None
        expected['untimely_share'] = expected['no'] / expected['known'] if expected['known'] else None
        expected['unknown_rate'] = expected['unknown'] / expected['complaints'] if expected['complaints'] else None
        cases.append(dict(id=scope, query=overview_query(filters), expected=expected))
    return cases


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'outputs/live_overview_plan.json')
    args = parser.parse_args()
    source = ROOT / 'data/processed/complaints_typed.parquet'
    with source.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    accepted = json.loads((ROOT / 'outputs/model_foundation_readback.json').read_text())
    if digest != accepted['current_projection_hashes']['data/processed/complaints_typed.parquet']:
        raise ValueError('Typed source differs from accepted foundation input')
    with duckdb.connect() as connection:
        cases = build_plan(connection, source)
    args.output.write_text(json.dumps(dict(status='expectations_generated',
        created_at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
        source_sha256=digest, scope='Independent SQL expectations; DAX execution not performed by this script',
        cases=cases), indent=2) + '\n', encoding='utf-8')
    print(f'Generated {len(cases)} independent overview cases')


if __name__ == '__main__':
    main()

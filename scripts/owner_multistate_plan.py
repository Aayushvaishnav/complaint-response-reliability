"""Generate independent CA+NY expectations for the remaining owner interaction check."""
import datetime as dt
import hashlib
import json
from pathlib import Path

import duckdb
from live_overview_plan import build_plan as overview_plan
from live_priority_plan import build_plan as priority_plan

ROOT = Path(__file__).resolve().parents[1]


def main():
    source = ROOT / 'data/processed/complaints_typed.parquet'
    with source.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    accepted = json.loads((ROOT / 'outputs/model_foundation_readback.json').read_text())
    if digest != accepted['current_projection_hashes']['data/processed/complaints_typed.parquet']:
        raise ValueError('Typed source differs from accepted projection')
    filters = ["FILTER(ALL('Geography'), 'Geography'[State] IN {\"CA\", \"NY\"})"]
    with duckdb.connect() as connection:
        connection.execute('SET threads=4')
        overview = overview_plan(connection, source, scopes={'CA_NY': ("state IN ('CA', 'NY')", filters)})
        priorities = priority_plan(connection, source, scopes={'CA_NY': ('2026-01-01', None, ['CA', 'NY'], filters)})
    result = dict(status='expectations_generated', created_at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
                  source_sha256=digest, states=['CA', 'NY'], overview=overview, priorities=priorities,
                  scope='Independent SQL expectations; UI acceptance and live DAX remain separate')
    output = ROOT / 'outputs/owner_multistate_expectations_20261028.json'
    output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()

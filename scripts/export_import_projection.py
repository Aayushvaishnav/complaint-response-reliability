"""Reproducible compact Import inputs; source labels are identities, never sentinels."""
from datetime import datetime, timezone
import json
from pathlib import Path

import duckdb

from population_analysis import check_identity, fingerprint, require

PROJECT = Path(__file__).resolve().parents[1]
DIMENSIONS = {'company': 'Company', 'product': 'Product', 'issue': 'Issue', 'geography': 'State'}
TABLES = ['complaint_cohorts', 'date', *DIMENSIONS, 'review_minimum',
          'sensitivity_minimum', 'review_window', 'review_selection']


def build(connection):
    """Read canonical typed relation projection_input; leave source untouched."""
    for name, raw in DIMENSIONS.items():
        connection.execute(f'''CREATE OR REPLACE TEMP TABLE {name} AS
            SELECT row_number() OVER (ORDER BY raw_value NULLS FIRST)::BIGINT {name}_key,
            raw_value, coalesce(raw_value='',true) is_missing,
            CASE WHEN raw_value IS NULL THEN 'sql_null' WHEN raw_value='' THEN 'empty'
                 ELSE 'value' END missingness,
            CASE WHEN raw_value IS NULL THEN '[SQL NULL]' WHEN raw_value='' THEN '[Empty]'
                 ELSE raw_value END display_label
            FROM (SELECT DISTINCT "{raw}" raw_value FROM projection_input)''')
    connection.execute((PROJECT / 'sql/import_projection.sql').read_text())


def weighted_median(connection, where='TRUE'):
    return connection.execute(f'''WITH frequencies AS (
        SELECT routing_days,sum(complaint_rows)::BIGINT n FROM complaint_cohorts
        WHERE routing_status='valid' AND ({where}) GROUP BY routing_days),
        cumulative AS (SELECT *,sum(n) OVER (ORDER BY routing_days) hi,
            sum(n) OVER () total FROM frequencies)
        SELECT avg(routing_days::DOUBLE) FROM (
            SELECT routing_days FROM cumulative
            WHERE hi-n < (total+1)//2 AND hi >= (total+1)//2
            UNION ALL SELECT routing_days FROM cumulative
            WHERE hi-n < (total+2)//2 AND hi >= (total+2)//2)''').fetchone()[0]


def validate(connection):
    dimension_checks = {}
    for name in DIMENSIONS:
        rows, keys, raw_identities = connection.execute(f'''SELECT count(*),
            count(DISTINCT {name}_key),count(DISTINCT struct_pack(raw := raw_value))
            FROM {name}''').fetchone()
        require(rows == keys == raw_identities, f'Dimension identity collision: {name}')
        dimension_checks[name] = dict(rows=rows, unique_keys=keys, raw_identities=raw_identities)
    source = connection.execute('''SELECT count(*),
        count(*) FILTER(WHERE timely_response_status='Yes'),
        count(*) FILTER(WHERE timely_response_status='No'),
        count(*) FILTER(WHERE timely_response_status='Unknown') FROM projection_input''').fetchone()
    projected = connection.execute('''SELECT coalesce(sum(complaint_rows),0),
        coalesce(sum(yes_rows),0),coalesce(sum(no_rows),0),coalesce(sum(unknown_rows),0)
        FROM complaint_cohorts''').fetchone()
    require(source == projected, 'Frequency conservation failed')
    require(connection.execute('''SELECT count(*) FROM complaint_cohorts
        WHERE complaint_rows<>yes_rows+no_rows+unknown_rows''').fetchone()[0] == 0,
        'Flag partition failed')
    # Reverse projection checks identities and every sufficient statistic, not only totals
    difference = connection.execute('''WITH reconstructed AS (
        SELECT f.received_date,c.raw_value Company,p.raw_value Product,i.raw_value Issue,
        g.raw_value State,f.routing_status,f.routing_days,
        f.complaint_rows,f.yes_rows,f.no_rows,f.unknown_rows
        FROM complaint_cohorts f JOIN company c USING(company_key)
        JOIN product p USING(product_key) JOIN issue i USING(issue_key)
        JOIN geography g USING(geography_key) JOIN "date" d ON f.received_date=d.date),
        expected AS (SELECT received_date,Company,Product,Issue,State,routing_status,routing_days,
        count(*)::BIGINT complaint_rows,
        count(*) FILTER(WHERE timely_response_status='Yes') yes_rows,
        count(*) FILTER(WHERE timely_response_status='No') no_rows,
        count(*) FILTER(WHERE timely_response_status='Unknown') unknown_rows
        FROM projection_input GROUP BY ALL)
        SELECT count(*) FROM ((SELECT * FROM reconstructed EXCEPT ALL SELECT * FROM expected)
        UNION ALL (SELECT * FROM expected EXCEPT ALL SELECT * FROM reconstructed))''').fetchone()[0]
    require(difference == 0, 'Dimension join or raw identity changed')
    selection_difference = connection.execute('''WITH expected AS (
        SELECT DISTINCT c.company_key,p.product_key,i.issue_key,
        date_trunc('month',s.received_date)::DATE window_end
        FROM projection_input s JOIN company c ON s.Company IS NOT DISTINCT FROM c.raw_value
        JOIN product p ON s.Product IS NOT DISTINCT FROM p.raw_value
        JOIN issue i ON s.Issue IS NOT DISTINCT FROM i.raw_value), actual AS (
        SELECT company_key,product_key,issue_key,window_end FROM review_selection)
        SELECT count(*) FROM ((SELECT * FROM expected EXCEPT ALL SELECT * FROM actual)
        UNION ALL (SELECT * FROM actual EXCEPT ALL SELECT * FROM expected))''').fetchone()[0]
    require(selection_difference == 0, 'Observed selection identities changed')
    return dict(source_counts=dict(zip(['complaint_rows','yes_rows','no_rows','unknown_rows'],source)),
                projected_counts=dict(zip(['complaint_rows','yes_rows','no_rows','unknown_rows'],projected)),
                reconstruction_difference_rows=difference, selection_difference_rows=selection_difference,
                dimension_checks=dimension_checks)


def main():
    output = PROJECT / 'outputs/import_projection_validation.json'
    evidence = {'status': 'running', 'started_at_utc': datetime.now(timezone.utc).isoformat(),
                'model_dax_rendering_acceptance': 'not_performed'}
    try:
        evidence['source_sha256'] = check_identity(PROJECT)
        connection = duckdb.connect()
        connection.execute('SET threads=4')
        connection.read_parquet(str(PROJECT / 'data/processed/complaints_typed.parquet')).create_view('projection_input')
        build(connection)
        evidence.update(validate(connection))
        groups = connection.execute('SELECT count(*) FROM complaint_cohorts').fetchone()[0]
        require(groups == 1883868, 'Accepted cohort group target changed')
        evidence['cohort_groups'] = groups
        evidence['overview_checks'] = {}
        for name, predicate in {'all':'TRUE', '2023':"received_date<DATE '2024-01-01'",
                                'Debt collection':"product_key IN (SELECT product_key FROM product WHERE raw_value='Debt collection')",
                                'CA':"geography_key IN (SELECT geography_key FROM geography WHERE raw_value='CA')"}.items():
            raw_predicate = predicate.replace("product_key IN (SELECT product_key FROM product WHERE raw_value='Debt collection')", "Product='Debt collection'").replace("geography_key IN (SELECT geography_key FROM geography WHERE raw_value='CA')", "State='CA'")
            raw = connection.execute(f"SELECT count(*),median(routing_days) FILTER(WHERE routing_status='valid') FROM projection_input WHERE {raw_predicate}").fetchone()
            count = connection.execute(f'SELECT sum(complaint_rows) FROM complaint_cohorts WHERE {predicate}').fetchone()[0]
            median = weighted_median(connection, predicate)
            require((count,median) == raw, f'Overview differs: {name}')
            evidence['overview_checks'][name] = {'complaint_rows':count,'median_routing_days':median}
        folder = PROJECT / 'data/processed/model-input'
        folder.mkdir(parents=True, exist_ok=True)
        evidence['exports'] = {}
        for table in TABLES:
            path = folder / f'{table}.parquet'
            connection.execute(f'COPY (SELECT * FROM "{table}") TO ? (FORMAT PARQUET, COMPRESSION ZSTD)', [str(path)])
            require(connection.execute(f'''SELECT count(*) FROM (
                (SELECT * FROM "{table}" EXCEPT ALL SELECT * FROM read_parquet(?)) UNION ALL
                (SELECT * FROM read_parquet(?) EXCEPT ALL SELECT * FROM "{table}"))''', [str(path),str(path)]).fetchone()[0] == 0, f'Round trip failed: {table}')
            evidence['exports'][table] = {'path':str(path.relative_to(PROJECT)), 'sha256':fingerprint(path),
                'rows':connection.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0],
                'schema':[{'name':r[0],'type':r[1]} for r in connection.execute(f'DESCRIBE "{table}"').fetchall()]}
        evidence['implementation_sha256'] = {p:fingerprint(PROJECT/p) for p in
            ['scripts/export_import_projection.py','sql/import_projection.sql']}
        evidence['status'] = 'passed'
    except Exception as error:
        evidence.update(status='failed', error=f'{type(error).__name__}: {error}')
        raise
    finally:
        output.write_text(json.dumps(evidence,indent=2,default=str)+'\n')


if __name__ == '__main__':
    main()

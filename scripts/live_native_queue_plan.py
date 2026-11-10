"""Native-shaped blank-suppressed queue queries and canonical SQL expectations."""
import json
from pathlib import Path
from live_priority_plan import SCOPES
from live_queue_plan import FIELDS
from queue_measures import build_queue_measures

ROOT = Path(__file__).resolve().parents[1]
GROUPS = ('Window End', 'Company Key', 'Product Key', 'Issue Key', 'Selection Key', 'Company', 'Product', 'Issue')


def native_query(filters, define=False):
    names = [name for name in FIELDS if name != 'window_complaints'] + ['passing_minima']
    measures = {name: ('Priority Rank' if name == 'rank' else 'Queue ' + FIELDS[name][1])
                for name in names if name != 'passing_minima'}
    measures['passing_minima'] = 'Queue Passing Minima'
    groups = ', '.join(f"'Review Selection'[{name}]" for name in GROUPS)
    measures_text = ', '.join(f'"{name}", [{measure}]' for name, measure in measures.items())
    columns = ', '.join(f'"{name}", [{name}]' for name in names)
    body = f'''SELECTCOLUMNS(SUMMARIZECOLUMNS({groups}, {measures_text},
        "review_reason", [Queue Review Reason]),
        "selection_key", 'Review Selection'[Selection Key], {columns})'''
    query = 'EVALUATE CALCULATETABLE(' + body + ', ' + ', '.join(filters) + ') ORDER BY [selection_key]'
    if define:
        query = 'DEFINE\n' + '\n'.join(f"MEASURE 'Complaint Cohorts'[{m['name']}] = {m['expression']}" for m in build_queue_measures()) + '\n' + query
    return query


def build_cases(plan):
    cases = []
    for case in plan['cases']:
        filters = [f"'Review Minimum'[Minimum] = {case['minimum']}", *SCOPES[case['scope']][3]]
        rows = [{key: value for key, value in row.items() if key != 'window_complaints'} for row in case['expectedRows']]
        cases.append(dict(id=case['id'], query=native_query(filters), expectedRows=rows,
                          keyColumns=case['keyColumns']))
    return cases


def main():
    plan = json.loads((ROOT / 'outputs/live_queue_plan.json').read_text())
    (ROOT / 'outputs/live_native_queue_plan.json').write_text(json.dumps(dict(cases=build_cases(plan)), indent=2) + '\n')


if __name__ == '__main__':
    main()

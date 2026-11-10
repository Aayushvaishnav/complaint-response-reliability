"""Synthetic-testable longitudinal contract; no source preparation dependency."""
import datetime as dt
from enum import Enum
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Selection(Enum):
    ALL = 'all'


def load_rule(path=ROOT / 'config/review_rule.json'):
    rule = json.loads(Path(path).read_text(encoding='utf-8'))
    expected = {
        'contract_status': 'approved_analyst_screening',
        'minimum_total_complaints': 100,
        'allowed_minima': [50, 100, 200],
        'window_months': 3,
        'required_elevated_months': 2,
        'excess_share': '0.01',
        'taxonomy_boundary': '2023-08-24',
        'excluded_longitudinal_month': '2023-08-01',
        'rank_tuple': ['elevated_months DESC', 'pooled_excess_pp DESC', 'window_no DESC', 'window_complaints DESC'],
        'rank_interpretation': 'Secondary analytical ordering; not a user-validated performance score',
        'interpretation': 'Analyst screening; not statistically validated or regulatory',
    }
    if rule.keys() != expected.keys():
        raise ValueError('Unexpected contract fields')
    for key, value in expected.items():
        if type(rule[key]) is not type(value) or rule[key] != value:
            raise ValueError(f'Unsupported contract value: {key}')
    if any(type(x) is not int for x in rule['allowed_minima']):
        raise ValueError('Minima must be integers')
    return rule


def evaluate(connection, *, start_date, end_date, minimum=100,
             companies=Selection.ALL, products=Selection.ALL,
             states=Selection.ALL, issues=Selection.ALL,
             config_path=ROOT / 'config/review_rule.json'):
    """Return monthly diagnostics and end-month windows as dictionaries.

    Dates are inclusive start/exclusive end; Selection.ALL is unrestricted,
    [] selects no rows, and [None] explicitly selects SQL NULL. Issue selection
    controls output only; all other filters apply before aggregation. Input is
    the caller's canonical contract_input relation; raw strings stay unchanged.
    Ineligible/partial windows are diagnostics, not reportable priorities;
    use window_eligible for eligible windows and persistent for the ranked queue.
    """
    rule = load_rule(config_path)
    if type(minimum) is not int or minimum not in rule['allowed_minima']:
        raise ValueError('minimum must be 50, 100 or 200')
    start, end = (dt.date.fromisoformat(x) if isinstance(x, str) else x for x in (start_date, end_date))
    if type(start) is not dt.date or type(end) is not dt.date or start >= end:
        raise ValueError('Require start_date < end_date')
    filters = (companies, products, states, issues)
    if any(f is not Selection.ALL and (not isinstance(f, list) or any(x is not None and not isinstance(x, str) for x in f)) for f in filters):
        raise ValueError('Filters require Selection.ALL or lists of raw strings/None')
    companies, products, states, issues = (None if f is Selection.ALL else f for f in filters)
    params = dict(start=start, end=end, minimum=minimum,
                  companies=companies, products=products, states=states, issues=issues)
    cursor = connection.execute((ROOT / 'sql/longitudinal_contract.sql').read_text(encoding='utf-8'), params)
    names = [c[0] for c in cursor.description]
    return [dict(zip(names, row)) for row in cursor.fetchall()]

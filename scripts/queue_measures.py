"""Queue-only sparse projections; retain full diagnostics for rejected windows."""
from priority_population import optimized_population

QUEUE_COLUMNS = {
    'Elevated Months': '__elevated', 'Window No Count': '__no',
    'Window Known Count': '__knownCount', 'Window Peer No Count': '__peerNo',
    'Window Peer Known Count': '__peerKnown',
}
QUEUE_FIELDS = (*QUEUE_COLUMNS, 'Pooled Gap pp', 'Passing Minima', 'Review Reason')


def build_queue_measures():
    """Return MCP definitions; all fields are BLANK outside qualifying selectors."""
    prefix = optimized_population() + '''VAR _single = HASONEVALUE('Review Selection'[Selection Key])
VAR _key = SELECTEDVALUE('Review Selection'[Selection Key])
VAR _row = FILTER(_qualified, _single && [__key] == _key)
'''
    expressions = {name: f'MAXX(_row, [{column}])' for name, column in QUEUE_COLUMNS.items()}
    expressions['Pooled Gap pp'] = '''IF(COUNTROWS(_row) = 1,
        100 * (DIVIDE(MAXX(_row, [__no]), MAXX(_row, [__knownCount])) -
            DIVIDE(MAXX(_row, [__peerNo]), MAXX(_row, [__peerKnown]))), BLANK())'''
    expressions['Passing Minima'] = '''IF(COUNTROWS(_row) = 1,
        VAR _volume = MAXX(_row, [__volume])
        RETURN CONCATENATEX(FILTER({50,100,200}, [Value] <= _volume), [Value], "/", [Value], ASC), BLANK())'''
    expressions['Review Reason'] = '''IF(COUNTROWS(_row) = 1,
        "Qualifies: at least two monthly gaps of 1pp; pooled gap is descriptive", BLANK())'''
    return [dict(tableName='Complaint Cohorts', name='Queue ' + name,
        expression=prefix + 'RETURN ' + expressions[name],
        formatString='@' if name in ('Passing Minima', 'Review Reason') else '0.00' if name == 'Pooled Gap pp' else '#,##0',
        displayFolder='Queue Display', isHidden=False,
        description=f'Qualifying queue display of {name}; BLANK outside qualifying windows. Use the original diagnostic measure for rejected-window audits.')
        for name in QUEUE_FIELDS]

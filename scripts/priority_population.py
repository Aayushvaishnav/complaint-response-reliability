"""Sparse Tier 1 population expression; focused diagnostics retain the full path.

Only eligible/stable populations are preserved; monthly pruning is lossless for
supported minima 50/100/200, not for diagnostic reasons on rejected windows.
"""


def optimized_population():
    """Return DAX variable declarations compatible with priority rank consumers."""
    sums = {
        'c': "SUM('Complaint Cohorts'[Complaint Rows])",
        'k': "SUM('Complaint Cohorts'[Yes Rows]) + SUM('Complaint Cohorts'[No Rows])",
        'n': "SUM('Complaint Cohorts'[No Rows])",
    }
    aggregates = ',\n        '.join(
        [f'"__f{k}", {v}' for k, v in sums.items()] +
        [f'"__t{k}", IGNORE(CALCULATE({v}, REMOVEFILTERS(\'Issue\')))' for k, v in sums.items()])
    shifts = []
    for offset in range(3):
        fields = [f'"__{dim.lower()}", \'{dim}\'[{dim} Key] + 0'
                  for dim in ('Company', 'Product', 'Issue')]
        fields.append(f'"__end", EDATE(\'Date\'[Month Start], {offset})')
        fields += [f'"__m{offset}{field}", [__{field}]'
                   for field in ('fc', 'fk', 'fn', 'pc', 'pk', 'pn', 'elevated')]
        shifts.append(f'VAR _shift{offset} = SELECTCOLUMNS(_monthly, ' + ',\n    '.join(fields) + ')')
    volumes = [f'MIN([__m{i}fc], [__m{i}pc])' for i in range(3)]
    volume = f'MIN({volumes[0]}, MIN({volumes[1]}, {volumes[2]}))'
    def total(field):
        return ' + '.join(f'[__m{i}{field}]' for i in range(3))
    return f'''VAR _selectedDates = CALCULATETABLE(VALUES('Date'[Date]), ALLSELECTED('Date'))
VAR _monthCounts = CALCULATETABLE(
    SUMMARIZECOLUMNS('Date'[Month Start], "__selectedDays", COUNTROWS('Date')),
    REMOVEFILTERS('Date'), TREATAS(_selectedDates, 'Date'[Date]))
VAR _completeMonths = SELECTCOLUMNS(FILTER(_monthCounts,
    'Date'[Month Start] <> DATE(2023,8,1) &&
    [__selectedDays] = DAY(EOMONTH('Date'[Month Start], 0))),
    "__completeMonth", 'Date'[Month Start])
VAR _ends = VALUES('Review Window'[Window End])
VAR _minimum = IF(NOT ISFILTERED('Review Minimum'), 100,
    IF(HASONEVALUE('Review Minimum'[Minimum]), SELECTEDVALUE('Review Minimum'[Minimum]), BLANK()))
VAR _companies = VALUES('Company'[Company Key])
VAR _products = VALUES('Product'[Product Key])
VAR _issues = VALUES('Issue'[Issue Key])
VAR _identities = SELECTCOLUMNS(ALL('Review Selection'),
    "__key", 'Review Selection'[Selection Key], "__segment", 'Review Selection'[Segment Key],
    "__company", 'Review Selection'[Company Key] + 0,
    "__product", 'Review Selection'[Product Key] + 0,
    "__issue", 'Review Selection'[Issue Key] + 0,
    "__end", EDATE('Review Selection'[Window End], 0))
VAR _candidates = FILTER(_identities, [__end] IN _ends && [__company] IN _companies &&
    [__product] IN _products && [__issue] IN _issues)
VAR _grouped = CALCULATETABLE(
    SUMMARIZECOLUMNS('Company'[Company Key], 'Product'[Product Key],
        'Issue'[Issue Key], 'Date'[Month Start],
        {aggregates}),
    REMOVEFILTERS('Review Selection'), REMOVEFILTERS('Date'),
    TREATAS(_completeMonths, 'Date'[Month Start]))
VAR _withPeers = ADDCOLUMNS(_grouped,
    "__pc", [__tc] - [__fc], "__pk", [__tk] - [__fk], "__pn", [__tn] - [__fn])
VAR _sparse = FILTER(_withPeers,
    [__fc] >= 50 && [__pc] >= 50 && [__fk] > 0 && [__pk] > 0)
VAR _monthly = ADDCOLUMNS(_sparse, "__elevated",
    INT(100 * ([__fn] * [__pk] - [__pn] * [__fk]) >= [__fk] * [__pk]))
{chr(10).join(shifts)}
VAR _windows = NATURALINNERJOIN(NATURALINNERJOIN(_shift0, _shift1), _shift2)
VAR _joined = NATURALINNERJOIN(_candidates, _windows)
VAR _statistics = ADDCOLUMNS(_joined,
    "__complete", TRUE(), "__era", TRUE(), "__known", TRUE(),
    "__volume", {volume}, "__elevated", {total('elevated')},
    "__no", {total('fn')}, "__knownCount", {total('fk')},
    "__peerNo", {total('pn')}, "__peerKnown", {total('pk')},
    "__complaints", {total('fc')})
VAR _evaluated = ADDCOLUMNS(_statistics,
    "__eligible", NOT ISBLANK(_minimum) && [__volume] >= _minimum,
    "__stable", [__volume] >= 200 && [__elevated] >= 2)
VAR _qualified = FILTER(_evaluated, [__eligible] && [__elevated] >= 2)
'''

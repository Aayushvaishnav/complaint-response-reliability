"""Dynamic priority measure definitions; no model writes or engine validation.

Grounding: Microsoft Learn DAX ALLSELECTED, KEEPFILTERS and TREATAS;
exact comparison domain and proof live in docs/model-rank-arithmetic.md.
"""
if __package__:
    from .rank_arithmetic import ArithmeticPlan
    from .priority_population import optimized_population
else:
    from rank_arithmetic import ArithmeticPlan
    from priority_population import optimized_population


def _minimum(table):
    return (f"IF(NOT ISFILTERED('{table}'), 100, "
            f"IF(HASONEVALUE('{table}'[Minimum]), SELECTEDVALUE('{table}'[Minimum]), BLANK()))")


def _count(measure, peer=False):
    filters = ["REMOVEFILTERS('Review Selection')", "REMOVEFILTERS('Date')",
               "TREATAS(_monthDates, 'Date'[Date])"]
    for dim, var in [('Company', '_company'), ('Product', '_product')]:
        filters.append(f"KEEPFILTERS(TREATAS({{{var}}}, '{dim}'[{dim} Key]))")
    if peer:
        filters += ["REMOVEFILTERS('Issue')", "'Issue'[Issue Key] <> _issue"]
    else:
        filters.append("KEEPFILTERS(TREATAS({_issue}, 'Issue'[Issue Key]))")
    return f"CALCULATE([{measure}], " + ', '.join(filters) + ')'


def _population(focused=False):
    if not focused:
        return optimized_population()
    counts = [('fc', 'Complaint Count', False), ('fk', 'Known Flag Count', False),
              ('fn', 'Untimely No Count', False), ('pc', 'Complaint Count', True),
              ('pk', 'Known Flag Count', True), ('pn', 'Untimely No Count', True)]
    monthly = ',\n'.join(f'"__{alias}", {_count(base, peer)}' for alias, base, peer in counts)
    focus_filter = ' && _singlePrune && [__key] == _focusKeyPrune' if focused else ''
    focus_variables = '''VAR _singlePrune = HASONEVALUE('Review Selection'[Selection Key])
VAR _focusKeyPrune = SELECTEDVALUE('Review Selection'[Selection Key])
''' if focused else ''
    identity_table = ("CALCULATETABLE('Review Selection', REMOVEFILTERS('Review Selection'), "
                      "TREATAS({_focusKeyPrune}, 'Review Selection'[Selection Key]))")
    return f'''VAR _selectedDates = CALCULATETABLE(VALUES('Date'[Date]), ALLSELECTED('Date'))
VAR _ends = VALUES('Review Window'[Window End])
VAR _minimum = {_minimum('Review Minimum')}
VAR _companies = VALUES('Company'[Company Key])
VAR _products = VALUES('Product'[Product Key])
VAR _issues = VALUES('Issue'[Issue Key])
{focus_variables}VAR _identities = SELECTCOLUMNS({identity_table},
    "__key", 'Review Selection'[Selection Key], "__segment", 'Review Selection'[Segment Key],
    "__company", 'Review Selection'[Company Key], "__product", 'Review Selection'[Product Key],
    "__issue", 'Review Selection'[Issue Key], "__end", 'Review Selection'[Window End])
VAR _candidates = FILTER(_identities, [__end] IN _ends && [__company] IN _companies &&
    [__product] IN _products && [__issue] IN _issues{focus_filter})
VAR _statistics = GENERATE(_candidates,
    VAR _company = [__company]
    VAR _product = [__product]
    VAR _issue = [__issue]
    VAR _end = [__end]
    VAR _start = EDATE(_end, -2)
    VAR _months = SELECTCOLUMNS(GENERATESERIES(0, 2), "__month", EDATE(_start, [Value]))
    VAR _monthly = GENERATE(_months,
        VAR _month = [__month]
        VAR _next = EDATE(_month, 1)
        VAR _monthDates = FILTER(_selectedDates, 'Date'[Date] >= _month && 'Date'[Date] < _next)
        RETURN ROW("__complete", COUNTROWS(_monthDates) = DAY(EOMONTH(_month, 0)),
            {monthly}))
    VAR _complete = COUNTROWS(FILTER(_monthly, NOT [__complete])) = 0
    VAR _era = _end < DATE(2023,8,1) || _start >= DATE(2023,9,1)
    VAR _known = MINX(_monthly, [__fk]) > 0 && MINX(_monthly, [__pk]) > 0
    VAR _volume = MINX(_monthly, MIN([__fc], [__pc]))
    VAR _elevated = COUNTROWS(FILTER(_monthly, [__fk] > 0 && [__pk] > 0 &&
        100 * ([__fn] * [__pk] - [__pn] * [__fk]) >= [__fk] * [__pk]))
    RETURN ROW("__complete", _complete, "__era", _era, "__known", _known,
        "__volume", _volume, "__elevated", _elevated,
        "__no", SUMX(_monthly, [__fn]), "__knownCount", SUMX(_monthly, [__fk]),
        "__peerNo", SUMX(_monthly, [__pn]), "__peerKnown", SUMX(_monthly, [__pk]),
        "__complaints", SUMX(_monthly, [__fc])))
VAR _evaluated = ADDCOLUMNS(_statistics,
    "__eligible", [__complete] && [__era] && [__known] && NOT ISBLANK(_minimum) && [__volume] >= _minimum,
    "__stable", [__complete] && [__era] && [__known] && [__volume] >= 200 && [__elevated] >= 2)
VAR _qualified = FILTER(_evaluated, [__eligible] && [__elevated] >= 2)
'''


def _focus():
    return '''VAR _focusKey = SELECTEDVALUE('Review Selection'[Selection Key])
VAR _single = HASONEVALUE('Review Selection'[Selection Key])
VAR _row = FILTER(_evaluated, _single && [__key] == _focusKey)
'''


def _compare(left, right):
    bindings = []
    for names, prefix in [(('_a', '_n', '_b', '_m'), left), (('_c', '_p', '_d', '_q'), right)]:
        bindings += [f'VAR {name} = {prefix}{suffix}' for name, suffix in
                     zip(names, ('No', 'Known', 'PeerNo', 'PeerKnown'))]
    return '\n'.join(bindings) + '\n' + ArithmeticPlan().dax()


def _rank():
    compare = _compare('_left', '_right')
    return f'''VAR _targetEnd = MAXX(_row, [__end])
VAR _ranked = FILTER(_qualified, [__end] = _targetEnd)
VAR _classes = FILTER(_ranked,
    VAR _rightKey = [__key]
    VAR _rightElevated = [__elevated]
    VAR _rightNo = [__no]
    VAR _rightKnown = [__knownCount]
    VAR _rightPeerNo = [__peerNo]
    VAR _rightPeerKnown = [__peerKnown]
    VAR _rightComplaints = [__complaints]
    RETURN COUNTROWS(FILTER(_ranked,
        VAR _leftNo = [__no]
        VAR _leftKnown = [__knownCount]
        VAR _leftPeerNo = [__peerNo]
        VAR _leftPeerKnown = [__peerKnown]
        VAR _comparison = ({compare})
        RETURN [__key] < _rightKey && [__elevated] = _rightElevated &&
            [__no] = _rightNo && [__complaints] = _rightComplaints && _comparison = 0)) = 0)
VAR _rightElevated = MAXX(_row, [__elevated])
VAR _rightNo = MAXX(_row, [__no])
VAR _rightKnown = MAXX(_row, [__knownCount])
VAR _rightPeerNo = MAXX(_row, [__peerNo])
VAR _rightPeerKnown = MAXX(_row, [__peerKnown])
VAR _rightComplaints = MAXX(_row, [__complaints])
VAR _better = COUNTROWS(FILTER(_classes,
        VAR _leftNo = [__no]
        VAR _leftKnown = [__knownCount]
        VAR _leftPeerNo = [__peerNo]
        VAR _leftPeerKnown = [__peerKnown]
        VAR _comparison = ({compare})
        RETURN SWITCH(TRUE(),
            [__elevated] > _rightElevated, TRUE(),
            [__elevated] < _rightElevated, FALSE(),
            _comparison > 0, TRUE(), _comparison < 0, FALSE(),
            [__no] > _rightNo, TRUE(), [__no] < _rightNo, FALSE(),
            [__complaints] > _rightComplaints)))
RETURN IF(COUNTROWS(FILTER(_row, [__eligible] && [__elevated] >= 2)) = 1,
    1 + _better, BLANK())'''


def _reason(minimum='_minimum'):
    return f'''SWITCH(TRUE(), NOT _single, "Select exactly one review row",
        COUNTROWS(_row) <> 1, "Window unavailable in selected ending months",
        ISBLANK({minimum}), "Unavailable: select exactly one minimum",
        NOT MAXX(_row, INT([__complete])), "Incomplete selected calendar months",
        NOT MAXX(_row, INT([__era])), "August 2023 boundary or mixed timing eras",
        MAXX(_row, [__volume]) < {minimum}, "Monthly focal or peer volume below minimum",
        NOT MAXX(_row, INT([__known])), "Monthly focal or peer known denominator unavailable",
        MAXX(_row, [__elevated]) < 2, "Fewer than two elevated months",
        "Qualifies: at least two monthly gaps of 1pp; pooled gap is descriptive")'''


def build_priority_measures():
    """Return fresh MCP measureDefinitions; append to the foundation definitions."""
    measures = []

    def add(name, expression, fmt='#,##0', folder='Review Priorities', description=None):
        measures.append(dict(tableName='Complaint Cohorts', name=name, expression=expression,
                             formatString=fmt, displayFolder=folder, isHidden=False,
                             description=description or (name + '; dynamic selected population; undefined is BLANK.')))

    add('Selected Review Minimum', _minimum('Review Minimum'))
    for name, result in [
        ('Eligible Window Count', 'COUNTROWS(FILTER(_evaluated, [__eligible]))'),
        ('Qualifying Window Count', 'COUNTROWS(_qualified)'),
        ('Qualifying Segment Count', 'COUNTROWS(DISTINCT(SELECTCOLUMNS(_qualified, "segment", [__segment])))'),
        ('Stable Window Count', 'COUNTROWS(FILTER(_evaluated, [__stable]))')]:
        add(name, _population() + f'RETURN IF(NOT ISBLANK(_minimum), COALESCE({result}, 0), BLANK())')
    fields = {'Elevated Months': '__elevated', 'Window No Count': '__no',
              'Window Known Count': '__knownCount', 'Window Peer No Count': '__peerNo',
              'Window Peer Known Count': '__peerKnown', 'Window Complaint Count': '__complaints'}
    for name, field in fields.items():
        add(name, _population(focused=True) + _focus() + f'RETURN IF(_single, MAXX(_row, [{field}]), BLANK())')
    add('Window Eligible', _population(focused=True) + _focus() + 'RETURN IF(COUNTROWS(_row) = 1 && NOT ISBLANK(_minimum), MAXX(_row, INT([__eligible])), BLANK())')
    add('Window Qualifies', _population(focused=True) + _focus() + 'RETURN IF(COUNTROWS(_row) = 1 && NOT ISBLANK(_minimum), MAXX(_row, INT([__eligible] && [__elevated] >= 2)), BLANK())')
    add('Pooled Gap pp', _population(focused=True) + _focus() + '''RETURN IF(_single && MAXX(_row, [__knownCount]) > 0 && MAXX(_row, [__peerKnown]) > 0,
        100 * (DIVIDE(MAXX(_row, [__no]), MAXX(_row, [__knownCount])) -
        DIVIDE(MAXX(_row, [__peerNo]), MAXX(_row, [__peerKnown]))), BLANK())''', '0.00')
    add('Passing Minima', _population(focused=True) + _focus() + '''RETURN IF(COUNTROWS(_row) = 1,
        VAR _passing = FILTER({50,100,200}, VAR _test = [Value]
            RETURN MAXX(_row, INT([__complete] && [__era] && [__known] && [__elevated] >= 2 && [__volume] >= _test)) = 1)
        RETURN IF(COUNTROWS(_passing) = 0, "None", CONCATENATEX(_passing, [Value], "/", [Value], ASC)),
        "Select exactly one review row")''', '@')
    add('Review Reason', _population(focused=True) + _focus() + 'RETURN ' + _reason(), '@')
    add('Priority Rank', _population() + _focus() + _rank())
    sensitivity = "VAR _sensitivity = IF(HASONEVALUE('Sensitivity Minimum'[Minimum]), SELECTEDVALUE('Sensitivity Minimum'[Minimum]), BLANK())\n"
    add('Sensitivity Reason', _population(focused=True) + _focus() + sensitivity + 'RETURN ' + _reason('_sensitivity'), '@', 'Sensitivity')
    add('Sensitivity Result', _population(focused=True) + _focus() + sensitivity + '''RETURN IF(NOT _single || COUNTROWS(_row) <> 1 || ISBLANK(_sensitivity), "Unavailable",
        IF(MAXX(_row, INT([__complete] && [__era] && [__known] && [__volume] >= _sensitivity && [__elevated] >= 2)) = 1,
        "Qualifies", "Does not qualify"))''', '@', 'Sensitivity')
    add('Review Context', '''VAR _dates = CALCULATETABLE(VALUES('Date'[Date]), ALLSELECTED('Date'))
VAR _minimum = [Selected Review Minimum]
VAR _ends = VALUES('Review Window'[Window End])
VAR _endCount = COUNTROWS(_ends)
VAR _allEndCount = CALCULATE(COUNTROWS('Review Window'), REMOVEFILTERS('Review Window'))
VAR _endingText = IF(_endCount = _allEndCount, "all " & FORMAT(_endCount, "0"),
    CONCATENATEX(_ends, FORMAT('Review Window'[Window End], "yyyy-MM"), ", ", 'Review Window'[Window End], ASC))
RETURN "Received " & FORMAT(MINX(_dates, 'Date'[Date]), "yyyy-MM-dd") & " to " &
    FORMAT(MAXX(_dates, 'Date'[Date]), "yyyy-MM-dd") & "; minimum " &
    IF(ISBLANK(_minimum), "unavailable: select one minimum", FORMAT(_minimum, "0")) &
    "; ending months: " & _endingText &
    "; 3 complete same-era months; August 2023 excluded; at least 2 monthly gaps >=1pp. Pooled gap is descriptive."''', '@')
    _add_monthly(add)
    return measures


def _add_monthly(add):
    prefix = '''VAR _single = HASONEVALUE('Review Selection'[Selection Key])
VAR _company = SELECTEDVALUE('Review Selection'[Company Key])
VAR _product = SELECTEDVALUE('Review Selection'[Product Key])
VAR _issue = SELECTEDVALUE('Review Selection'[Issue Key])
VAR _end = SELECTEDVALUE('Review Selection'[Window End])
VAR _selectedDates = CALCULATETABLE(VALUES('Date'[Date]), ALLSELECTED('Date'))
VAR _month = SELECTEDVALUE('Date'[Month Start])
VAR _monthDates = FILTER(_selectedDates, 'Date'[Date] >= _month && 'Date'[Date] < EDATE(_month, 1))
VAR _visible = _single && NOT ISBLANK(_month) && _month >= EDATE(_end, -2) && _month <= _end
'''
    for name, base, peer, fmt in [
        ('Focused Monthly Complaint Count', 'Complaint Count', False, '#,##0'),
        ('Focused Monthly No Count', 'Untimely No Count', False, '#,##0'),
        ('Focused Monthly Known Count', 'Known Flag Count', False, '#,##0'),
        ('Focused Monthly Peer No Count', 'Untimely No Count', True, '#,##0'),
        ('Focused Monthly Peer Known Count', 'Known Flag Count', True, '#,##0'),
        ('Focused Monthly Untimely Share', 'Untimely Share', False, '0.00%'),
        ('Focused Monthly Peer Untimely Share', 'Untimely Share', True, '0.00%')]:
        add(name, prefix + f'RETURN IF(_visible, {_count(base, peer)}, BLANK())', fmt, 'Focused Evidence')
    add('Focused Monthly Issue Share', prefix + f'''VAR _focal = {_count('Complaint Count')}
VAR _peer = {_count('Complaint Count', True)}
RETURN IF(_visible, DIVIDE(_focal, _focal + _peer), BLANK())''', '0.00%', 'Focused Evidence')
    current = _count('Complaint Count')
    peer = _count('Complaint Count', True)
    add('Issue Share Change pp', prefix + f'''VAR _prior = EDATE(_month, -1)
VAR _priorDates = FILTER(_selectedDates, 'Date'[Date] >= _prior && 'Date'[Date] < _month)
VAR _sameEra = _month < DATE(2023,8,1) || _prior >= DATE(2023,9,1)
VAR _currentFocal = {current}
VAR _currentPeer = {peer}
VAR _priorFocal = CALCULATE([{ 'Complaint Count' }], REMOVEFILTERS('Date'), TREATAS(_priorDates, 'Date'[Date]),
    KEEPFILTERS(TREATAS({{_company}}, 'Company'[Company Key])), KEEPFILTERS(TREATAS({{_product}}, 'Product'[Product Key])),
    KEEPFILTERS(TREATAS({{_issue}}, 'Issue'[Issue Key])))
VAR _priorTotal = CALCULATE([Complaint Count], REMOVEFILTERS('Date'), TREATAS(_priorDates, 'Date'[Date]),
    KEEPFILTERS(TREATAS({{_company}}, 'Company'[Company Key])), KEEPFILTERS(TREATAS({{_product}}, 'Product'[Product Key])), REMOVEFILTERS('Issue'))
RETURN IF(_visible && _sameEra && COUNTROWS(_monthDates) = DAY(EOMONTH(_month,0)) &&
    COUNTROWS(_priorDates) = DAY(EOMONTH(_prior,0)) && _currentFocal + _currentPeer > 0 && _priorTotal > 0,
    100 * (DIVIDE(_currentFocal, _currentFocal + _currentPeer) - DIVIDE(_priorFocal, _priorTotal)), BLANK())''', '0.00', 'Focused Evidence')

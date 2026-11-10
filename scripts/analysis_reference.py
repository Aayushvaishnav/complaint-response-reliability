"""Independent exact-arithmetic validation of compact longitudinal aggregates."""
from collections import defaultdict, deque
from datetime import date
from fractions import Fraction
from math import isclose


def _next_month(month):
    return date(month.year + (month.month == 12), month.month % 12 + 1, 1)


def validate_analysis(counts, actual, *, start_date, end_date, minimum):
    """Validate unfiltered SQL output against already context-filtered counts.

    Counts cover the inclusive-start/exclusive-end interval, including partial
    months. Raw nullable labels are keys; unknown flags contribute only complaints.
    Returns row, segment, month, persistent-row and field comparison counters.
    """
    start, end = (date.fromisoformat(x) if isinstance(x, str) else x
                  for x in (start_date, end_date))
    if type(start) is not date or type(end) is not date or start >= end:
        raise ValueError('Require start_date < end_date')
    if type(minimum) is not int or minimum not in (50, 100, 200):
        raise ValueError('minimum must be 50, 100 or 200')
    months = []
    month = start.replace(day=1)
    while month < end:
        months.append(month)
        month = _next_month(month)
    month_set = set(months)
    compact = defaultdict(lambda: [0, 0, 0])
    totals = defaultdict(lambda: [0, 0, 0])
    segments = set()
    for row in counts:
        segment = tuple(row[k] for k in ('company', 'product', 'issue'))
        month = row['month']
        values = [row[k] for k in ('complaints', 'known', 'untimely')]
        if (type(month) is not date or month not in month_set or
                any(type(v) is not int for v in values) or
                not 0 <= values[2] <= values[1] <= values[0]):
            raise ValueError('Invalid aggregate counts')
        segments.add(segment)
        for i, value in enumerate(values):
            compact[segment, month][i] += value
            totals[segment[:2], month][i] += value
    def expected_row(segment, index):
        history = deque(maxlen=3)
        previous = None
        for month in months[max(0, index-2):index+1]:
            complaints, known, no = compact.get((segment, month), (0, 0, 0))
            total, total_known, total_no = totals.get((segment[:2], month), (0, 0, 0))
            peers, peer_known, peer_no = total-complaints, total_known-known, total_no-no
            share = Fraction(complaints, total) if total else None
            complete = month >= start and _next_month(month) <= end
            era = 'pre' if month < date(2023, 8, 1) else 'post' if month >= date(2023, 9, 1) else 'excluded'
            eligible = complaints >= minimum and peers >= minimum and known > 0 and peer_known > 0 and complete and era != 'excluded'
            elevated = known > 0 and peer_known > 0 and era != 'excluded' and Fraction(no, known)-Fraction(peer_no, peer_known) >= Fraction(1, 100)
            row = dict(zip(('company', 'product', 'issue'), segment))
            row.update(month=month, complaints=complaints, known=known, untimely=no,
                       total_complaints=total, total_known=total_known, total_untimely=total_no,
                       peer_complaints=peers, peer_known=peer_known, peer_untimely=peer_no,
                       issue_share=share, complete_month=complete, era=era,
                       eligible_month=eligible, elevated=elevated)
            history.append(row)
            allowed = [r for r in history if r['era'] != 'excluded']
            row.update(months_in_window=len(history), eligible_months=sum(r['eligible_month'] for r in history),
                       first_era=min(r['era'] for r in history), last_era=max(r['era'] for r in history),
                       elevated_months=sum(r['eligible_month'] and r['elevated'] for r in history))
            for field, source in (('window_complaints', 'complaints'), ('window_known', 'known'),
                                  ('window_no', 'untimely'), ('window_peer_known', 'peer_known'),
                                  ('window_peer_no', 'peer_untimely')):
                row[field] = sum(r[source] for r in allowed) if allowed else None
            window_ok = len(history) == 3 and row['eligible_months'] == 3 and row['first_era'] == row['last_era']
            prior_ok = previous is not None and complete and previous['complete_month'] and era == previous['era'] and era != 'excluded'
            prior = previous['issue_share'] if prior_ok else None
            wk, pk = row['window_known'], row['window_peer_known']
            excess = Fraction(row['window_no'], wk)-Fraction(row['window_peer_no'], pk) if wk and pk else None
            persistent = window_ok and row['elevated_months'] >= 2
            row.update(window_eligible=window_ok, pooled_excess_pp=100*excess if excess is not None else None,
                       previous_share=previous['issue_share'] if previous else None,
                       previous_era=previous['era'] if previous else None,
                       previous_complete=previous['complete_month'] if previous else None,
                       prior_issue_share=prior,
                       issue_share_change_pp=100*(share-prior) if share is not None and prior is not None else None,
                       issue_missing=segment[2] in (None, ''),
                       issue_key={'is_null': segment[2] is None, 'raw_label': segment[2]},
                       persistent=persistent, priority_rank=None)
            key = segment + (month,)
            previous = row
        return row
    rank_groups = defaultdict(list)
    seen = defaultdict(int)
    month_indices = {month: i for i, month in enumerate(months)}
    row_count = 0
    comparisons = 0
    for row in actual:
        key = tuple(row[k] for k in ('company', 'product', 'issue', 'month'))
        segment, month = key[:3], key[3]
        index = month_indices.get(month)
        if segment not in segments or index is None or seen[segment] & (1 << index):
            raise ValueError(f'Duplicate or unexpected segment/month: {key!r}')
        seen[segment] |= 1 << index
        row_count += 1
        expected = expected_row(segment, index)
        if expected['persistent']:
            rank_key = (expected['elevated_months'], expected['pooled_excess_pp'],
                        expected['window_no'], expected['window_complaints'])
            rank_groups[month].append((rank_key, row.get('priority_rank')))
        for field, value in expected.items():
            if field == 'priority_rank' and expected['persistent']:
                continue
            if field not in row:
                raise ValueError(f'Missing field {field} at {key!r}')
            observed = row[field]
            equal = (observed is not None and isclose(float(value), float(observed), rel_tol=0, abs_tol=1e-10)
                     if isinstance(value, Fraction) else observed == value)
            if not equal:
                raise ValueError(f'Mismatch {field} at {key!r}: expected {value!r}, got {observed!r}')
            comparisons += 1
    if row_count != len(segments)*len(months):
        raise ValueError(f'Missing segment/month rows: got {row_count}')
    for entries in rank_groups.values():
        ranks = {key: i for i, key in enumerate(sorted({key for key, _ in entries}, reverse=True), 1)}
        for key, observed in entries:
            if observed != ranks[key]:
                raise ValueError(f'Mismatch priority_rank: expected {ranks[key]}, got {observed}')
    return dict(rows=row_count, segments=len(segments), months=len(months),
                persistent_rows=sum(map(len, rank_groups.values())), comparisons=comparisons)

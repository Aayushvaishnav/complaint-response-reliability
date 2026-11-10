# F1 metric dictionary: Gate B contract

## Shared population and evaluation context
- Baseline: received date **2023-01-01 inclusive to 2026-01-01 exclusive**, all raw products/companies/states; **9,469,257** complaint IDs. See [requirements](business_requirements.md) and [field rules](data_dictionary.md).
- Grain: one complaint per unique ID. Counts must reconcile to rows; duplicate IDs block acceptance, not trigger silent distinct-count masking or deduplication.
- Metrics respect selected received period, company, raw product, raw issue and geography unless a denominator override is explicit below. Received month is the cohort date basis.
- Exact raw Yes and No are known timely flags; all other values are Unknown. Response categories never determine timely eligibility.
- Missing issue/geography/category values use explicit unknown display buckets without complaint deletion or raw-value replacement.
- Empty cohorts return **zero counts**; a rate or median without eligible observations returns **null/BLANK**, never a fabricated zero. Display the applicable denominator beside rates and lag summaries.

## Initial metrics
| Metric | Definition | Denominator / empty handling |
|---|---|---|
| Complaint count | Number of complaint rows in context, verified against unique complaint IDs | No denominator; empty = 0 |
| Known Yes/No eligible count | Count where raw timely flag is exactly Yes or No | Empty = 0; display as timely/untimely denominator |
| Timely Yes count | Count where timely flag = Yes | Empty = 0 |
| Untimely No count | Count where timely flag = No | Empty = 0 |
| Unknown response-flag count | Count where timely flag is neither exact Yes nor exact No, including blank | Empty = 0; not unknown company-response category count |
| Timely-response rate | Timely Yes count / known Yes/No eligible count | Null if known = 0; show percent |
| Untimely-response share | Untimely No count / known Yes/No eligible count | Null if known = 0; show percent |
| Unknown response-flag rate | Unknown response-flag count / complaint count | Null if complaint count = 0; show percent |
| Valid routing-lag count | Count with both dates valid and sent date − received date >= 0 | Empty = 0; display with routing median |
| Median routing days | Median calendar-day difference (sent − received) among valid nonnegative lags | Null if valid-lag count = 0; even-sized groups use arithmetic mean of middle two values |
| Invalid routing-lag count | Complaint count − valid routing-lag count; split missing/invalid dates and negative lag reasons for diagnostics | Empty = 0; complaints stay in count and flag denominators |
| Monthly issue share | Issue-bucket complaint count / all complaints in selected company × raw product × received month | Denominator includes every issue bucket, including unknown; remove only issue/sub-issue filtering from denominator; retain other selections; null if denominator = 0 |
| Issue-share change (percentage points) | 100 × (current monthly issue share − prior calendar-month share) | Null if either share undefined or taxonomy comparability not approved; never substitute previous available month |

## Interpretation and reconciliation
- Timely is the **source-recorded flag**, not independently verified compliance or a measured 15-day resolution outcome. In progress, blank categories and Untimely response are separate response labels, not flag replacements.
- Routing lag measures CFPB-to-company routing, not response duration, handling time or resolution. Valid-lag denominator can differ from known-flag denominator.
- Baseline checks: **9,431,474 Yes + 37,783 No + 0 unknown = 9,469,257**; scoped valid-lag count is 9,469,257. These are source-readiness counts, not analytical findings.
- Preserve **6 blank issues**, **19 blank response categories**, **279 In progress** and **17,967 blank states**. Unknown issues contribute to issue shares and reconciliation.
- Within each selected company/raw-product/month, all issue-bucket counts sum to complaint count and all issue shares sum to 1 for a nonempty cohort. Selecting displayed issues must not renormalize their shares.
- Known count = Yes + No; complaint count = known + unknown. For known > 0, timely rate + untimely share = 1. Month totals must reconcile to the selected population.
- There is no exposure denominator; rates describe published complaint portfolios, not customer incidence or overall service quality. Changes may reflect submission mix, updates and taxonomy changes, not process effects.

## Taxonomy and complete-month contract

The user approved the proposed investigation rule on 2026-10-23 before any full-population rankings. Its parameters are analyst-set screening choices, instead of regulatory standards, statistical significance tests or validated company-performance targets. Machine-readable parameters: [review rule](../config/review_rule.json).

- **Date-based taxonomy eras:** received before 2023-08-24 is `pre_2023_08_24`; received on/after that date is `post_2023_08_24`. These are conservative timing proxies, instead of proof of the form version used for an individual complaint. Preserve raw product, issue and sub-issue strings; no label consolidation or crosswalk.
- **Boundary month:** retain every August 2023 complaint in overview counts, flags, routing summaries and reconciliation. Exclude the entire month from issue-share changes and persistent-priority windows, rather than comparing a partial old/new taxonomy month with a full month.
- **Complete month:** its first date and exclusive next-month date must lie inside the selected received-date interval. A selection starting mid-month or ending before the next month starts cannot contribute that month to a priority window. A calendar-complete cohort still does not prove source publication completeness or final outcomes.
- **Comparable windows:** three consecutive complete calendar months within one era, fully inside the selected date range. The baseline permits window ends March–July 2023 and November 2023–December 2025. August breaks continuity; September and October alone cannot establish post-boundary persistence.
- **Monthly issue share:** numerator includes the selected raw issue, with blank issue as its own explicit key; denominator retains every issue in the same company/product/month and selected geography. Display buckets never become join keys. An absent issue in a nonempty cohort has zero count/share; a missing cohort denominator remains undefined.
- **Prior share:** use the immediately previous calendar month, not the previous observed row. Change is undefined across August, across eras, outside complete selected months, or if either company/product cohort denominator is zero. Show the boundary month as a descriptive cohort only, with no comparable-change value.

## Review eligibility, comparator and persistence

| Component | Frozen rule |
|---|---|
| Review grain | Company × raw product × raw issue; each window has three monthly observations. Unknown issue remains a distinct key. |
| Volume basis | Total complaints, including unknown timely flags, **per segment per month**, rather than the pooled three-month count. Each month must have count **>=100**; rerun the entire rule at **50 and 200**, including comparator eligibility. |
| Known flag eligibility | At least one exact Yes or No in each segment-month. Show known and unknown counts; the volume minimum is not a minimum known-denominator rule. |
| Comparator | All **other issues** in the same company, raw product, received month and selected geography, excluding the segment's own issue. Aggregate peer counts and flags before computing rates; do not average issue percentages. |
| Comparator eligibility | In every window month, comparator total complaints must meet the same inclusive minimum and comparator known flags must exceed zero. A company/product with only one issue has no eligible comparator. |
| Elevated month | Segment No/(Yes+No) minus comparator No/(Yes+No) **>=0.01**, equivalent to **1 percentage point**. Use an inclusive comparison without rounding displayed percentages first. |
| Persistence | At least **2 elevated months out of 3**, with **all 3 months eligible** for both segment and comparator. Missing months, zero known denominators and ineligible comparator months fail the window; never carry observations forward. |
| Window pooled rates | Sum No over the three months divided by sum Yes+No for segment and comparator separately. Show counts and denominators next to both pooled rates. |
| Priority and ties | Rank only eligible persistent windows, separately per window end. Descending elevated-month count, pooled segment-minus-peer excess, window No count, then window complaint count. Equal full tuples share a dense rank; raw labels provide stable display order only. This is an analytical ordering, instead of a calibrated risk score. |
| Selection context | Company/product/state and received-date filters apply before aggregation. Peer denominators ignore issue/sub-issue display selection only. Recompute peers, eligibility and ranks under geography selections, instead of filtering a global rank table. |

### Sensitivity and interpretation

- Apply the same effect, window and persistence choices at all three volume minima. A segment is **stable across volume minima** for a given window only if it qualifies at 50, 100 and 200; otherwise disclose the passing minima instead of calling it robust.
- A failure to qualify is a useful non-finding under this rule; it does not establish reliable customer service. A large complaint segment may lack sufficient peers, known flags or comparable monthly history.
- Unknown flags remain outside rate denominators but inside volume eligibility. Report unknown share alongside the known denominator; high unknown coverage limits interpretation even if the screening rule passes.
- These checks do not adjust for market share, product exposure, submission mix, multiple comparisons or causal explanations. No significance, wrongdoing or achieved process improvement is implied.
- Contract tests can exercise rankings on synthetic fixtures in Gate B. Full-population rankings, sensitivity results and investigation recommendations belong to Gate C after preparation acceptance.

### Numerical ordering

Monthly elevation uses integer cross-products for the inclusive 1 percentage-point boundary. Priority ordering compares reduced rational pooled excesses with integer cross-products, instead of ranking binary floating-point display values. This preserves equal ranks for mathematically equal rates with different known denominators. The remaining rank fields use integer counts.

The exact rank implementation counts distinct strictly better tuples within each ending month. Its comparison cost is quadratic in the number of distinct qualifying tuples; Gate C must measure this on the full scope before report integration. No runtime improvement or scalability result is claimed from synthetic tests. For the frozen 9,469,257-record population, the count cross-products fit DuckDB's 128-bit `HUGEINT`; the bound depends on the frozen population rather than rounding tolerances.

## Verification scope and future implementation
- Gate A feasibility sample uses three lexicographically lowest complaint IDs per received-month/raw-product/raw-timely-flag stratum, capped by available rows; it is deliberately nonrepresentative.
- Sample metrics test calculation mechanics only; do not extrapolate counts/rates, compare segment performance or infer population priorities from it.
- Dedicated tests must cover empty/all-unknown cohorts, zero denominators, raw flag distinctions, invalid/missing/negative dates, even/odd medians, unknown issue reconciliation and filter-context denominator overrides.
- Gate B requires taxonomy/boundary rules, threshold boundaries and persistence/sensitivity tests; future SQL/DAX headline checks must agree under at least two meaningful filters and preserve rows across joins.
- The initial count/flag/rate/routing smoke metrics are implemented and independently checked in the feasibility sample. Gate B preparation and synthetic contract evidence are recorded separately in [gate status](../completion.md). Full-population longitudinal analysis, DAX, the model, Power BI load/refresh evidence and final CV measurements remain future work.

# F1 findings and proposed investigations

The frozen 2023–2025 population produces **36 qualifying segment-windows across 13 segments at minimum 100; five of those windows qualify at all three volume minima**. This is descriptive screening of published complaint portfolios, instead of a company service-quality ranking.

**Recommended option:** Start with a historical response-record audit of MOHELA's student-loan “Dealing with your lender or servicer” segment, using its October–December 2025 window and explicit disclosure that it passes minima 50/100 but fails 200 because the other-issue comparator is too small.

## 1. The overall recorded timely rate masks a concentrated investigation question

Across all **9,469,257 complaints**, **9,431,474** have a recorded Yes flag and **37,783** have No: a **99.601%** timely-response rate with zero unknown flags in this snapshot. Student loans separately have **8,186 No flags / 46,573 known flags**, or **17.577%** untimely. These are different complaint portfolios; the comparison does not adjust for customer exposure or establish a process cause.

The pre-approved within-company comparator supplies a narrower review question. For MOHELA × Student loan × Dealing with your lender or servicer, the latest snapshot window, **October–December 2025**, has:

| Measure | Segment | Other student-loan issues at MOHELA |
|---|---:|---:|
| Complaints / known flags | 972 / 972 | 452 / 452 |
| Recorded No flags | 590 | 253 |
| Pooled untimely share | 60.700% | 55.973% |
| Unknown flags | 0 | 0 |

The pooled difference is **4.726 percentage points** and all three monthly gaps exceed 1pp. At minimum 100 this is the only qualifying segment in the December-2025 ending-month queue. The same segment qualifies in **10 ending months, March–December 2025**, but these are overlapping windows, instead of independent events.

The October/November/December segment counts are **340 / 245 / 387** and peer counts are **129 / 131 / 192**. Thus the latest window fails minimum 200 solely on peer volume, despite every segment month exceeding 200. Only its March–May 2025 ending windows pass all minima.

**Proposed investigation:** Reconstruct the historical response-record workflow for this issue and its comparator. Request receipt/routing/response-event timestamps, status revisions, internal queue assignment, case complexity and staffing records. Test whether the flag differences persist within comparable channels and case types, and whether recording changes explain the pattern. Use a fresh authorised extract before any present-day operational decision. Routing lag in this dataset cannot answer the response-duration question.

**Evidence:** [Monthly overview](../outputs/monthly_overview.csv), scope `all`; [product overview](../outputs/product_overview.csv), `Student loan`; [independent CSV product check](../outputs/product_reference_validation.json); [review queue](../outputs/review_queue.csv), scope `all`, minimum `100`, MOHELA/Student loan, month `2025-12-01`; [monthly segment history](../outputs/review_segment_history.csv), the same key and October–December 2025. [Exact reference checks](../outputs/gate_c_analysis.json) validate every monthly count, peer denominator and queue decision.

## 2. Most base-rule windows are volume-sensitive, and persistence is monthly

| Monthly minimum for segment and comparator | Qualifying segment-windows | Distinct qualifying segments |
|---|---:|---:|
| 50 | 112 | 30 |
| 100, base | 36 | 13 |
| 200 | 5 | 3 |

The qualifying sets are nested. Exactly **five of the 36 base-rule windows** qualify at 50, 100 and 200. The historical stable windows cover three raw segments:

| Segment | Ending month(s) stable across all minima | Example pooled No / known: segment versus peers |
|---|---|---|
| LEXISNEXIS × Credit reporting or other personal consumer reports × Incorrect information on your report | March 2024 | 45/1,155 versus 30/1,019 |
| Block, Inc. × Money transfer, virtual currency, or money service × Fraud or scam | March 2025 | 48/1,409 versus 36/33,853 |
| MOHELA × Student loan × Dealing with your lender or servicer | March, April and May 2025 | May: 1,517/1,895 versus 581/831 |

“Fraud or scam” is a source issue label, instead of independently verified fraud. These historical windows do not establish that a problem is still present.

The frozen rule asks for monthly elevation in at least two months; it does **not** require a pooled three-month gap of 1pp. **Seven** base-rule windows have a pooled gap below 1pp. For example, LEXISNEXIS × the same credit-reporting product × Improper use of your report, ending January 2024, passes two monthly tests even though its pooled **8/530 versus 16/1,051** gap is **−0.01293pp**. This is expected under the approved rule; changing eligibility after seeing this result would change the analytical contract.

**Proposed investigation:** Audit the monthly observations behind historical screen admissions before allocating case-review capacity. For the three stable segments, request channel/case-type mix and response-status histories; for the January-2024 LEXISNEXIS example, examine monthly volume weights and comparator mix. Keep monthly elevated-count and pooled gap visible as distinct fields in the report. If the owner later wants a pooled-positive condition, treat it as a separately approved scenario and rerun all sensitivities.

**Evidence:** [Queue with passing minima](../outputs/review_queue.csv), scope `all`; [monthly segment histories](../outputs/review_segment_history.csv); [per-month eligibility summary](../outputs/review_monthly_summary.csv). Distinct segment keys exclude month; segment-window keys include it. [Analysis checks](../outputs/gate_c_analysis.json), `scopes.all`, verify nesting, exact rational ties and all three minima.

## 3. California has no qualifying priorities under the base rule

Recomputing the entire rule inside California yields **zero persistent priorities** across the 2023–2025 scope, despite **906,980 complaints** and **279 eligible segment-windows**. “Eligible” here means all three segment/comparator months meet volume, known-flag and comparability conditions; none also meets the two-of-three elevation condition. Overlapping windows remain counted separately.

The latest California month has **nine eligible windows and zero persistent priorities**. The all-geography base queue instead contains one December-2025 priority. Filtering global ranks to California would misrepresent the selected population and its comparator.

This is a useful non-finding under minimum 100 and the fixed effect/persistence rule, instead of evidence of reliable service, absence of untimely responses or a California advantage. California still has **3,701 No flags / 906,980 known flags**, or **0.4081%** untimely. California sensitivity at minima 50/200 has not been run; stability across all minima is therefore unassessed for this filtered scope.

**Proposed investigation:** Keep the California priority table empty with a visible rule explanation. If the owner needs a California-specific review, first inspect monthly volumes, issue composition and comparator eligibility, then obtain approval for additional sensitivity scenarios. Request customer/account exposure and updated response records before making any geography-performance comparison. Do not substitute a global company rank.

**Evidence:** [California overview](../outputs/monthly_overview.csv), scope `CA`; [California monthly screening summary](../outputs/review_monthly_summary.csv), scope `CA`, minimum `100`; [recomputed California reference](../outputs/gate_c_analysis.json), `scopes.CA`. The California rows are a full recomputation from state-filtered complaints, rather than a filtered global queue.

## Runtime and delivery boundary

The full-scope canonical SQL takes **2.99–3.12 seconds per minimum** in this single local development run. The 50-minimum run has at most **nine distinct rank tuples per ending month**, with **618 potential tuple pairs summed across months**; its isolated exact-rank replay takes **0.0033 seconds**. The independent reference checks **5,849,172 monthly diagnostic rows across six executed scope/minimum combinations**, with the full run finishing in about **257 seconds**. Most time is independent verification, instead of ranking.

These are local development measurements with uncontrolled cache state, instead of a general scalability result or Power BI interaction target. Canonical exact SQL still has quadratic rank-key comparison cost. The [final build review](../outputs/final_build_acceptance_20261028.json) separately records slicer acceptance and a completed clean-folder refresh; no refresh-speed achievement is claimed.

Source identity is frozen; original download metadata and live official-export agreement remain limited as recorded in [completion](../completion.md). All findings are historical, descriptive and hypothesis-generating. Power BI import, DAX, screenshots, clean-folder refresh and owner interaction checks now pass in the [final build record](../outputs/final_build_acceptance_20261028.json). Final CV claims require the separate post-build evidence review.

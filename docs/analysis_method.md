# F1 population analysis method

## Decision and frozen inputs

The analysis screens company × raw product × raw issue complaint portfolios for process investigation. It uses the accepted 2023–2025 typed preparation and the [pre-approved review contract](metric_dictionary.md). The minimum monthly volume is 100 for both the segment and its same-company/product other-issue comparator; sensitivity reruns use 50 and 200. Each three-month window requires three eligible complete calendar months within one timing era and at least two monthly untimely-share gaps of 1 percentage point or more.

All 9,469,257 complaints remain in descriptive totals. August 2023 remains descriptive but cannot enter comparable issue-share changes or persistence windows. Raw labels are separate keys, including blank issues. These timing eras are proxies for the August-2023 taxonomy change, instead of certified complaint-level form versions.

[Gate C analysis evidence](../outputs/gate_c_analysis.json) records input, implementation and output hashes. The current typed Parquet, rule and canonical SQL must match Gate B before execution and again at completion. This run does not rehash the original CSV or obtain a fresh official export. Gate B's source-access and provenance limits remain in force.

## SQL and independent checks

| Query | Decision or check |
|---|---|
| [Monthly overview](../sql/monthly_overview.sql) | Received-month volume, exact recorded flags, known denominator and routing median |
| [Product overview](../sql/product_overview.sql) | Raw-product portfolio composition and recorded timeliness |
| [Segment-month counts](../sql/segment_month_counts.sql) | Compact aggregate input for independent longitudinal validation |
| [Response mix](../sql/response_mix.sql) | Response categories and timely flags remain separate fields |
| [Routing distribution](../sql/routing_distribution.sql) | Reconcile monthly routing medians from discrete lag counts |
| [Canonical longitudinal contract](../sql/longitudinal_contract.sql) | Dense calendar grid, issue-share changes, comparator eligibility, persistent windows and rational dense ranks |

The [runner](../scripts/population_analysis.py) executes SQL, writes compact aggregate CSVs and records development timings. Python orchestrates the SQL workflow and validation; it is instead of a separate analytical-tool deliverable.

The [independent reference](../scripts/analysis_reference.py) reads sparse segment-month aggregates and streamed SQL diagnostics. It independently reconstructs every segment/calendar-month combination, peer totals, prior-month changes, rolling windows and eligibility. Fraction arithmetic determines the inclusive effect boundary and rank tuples. Sorted distinct rational tuples supply an independent dense-rank algorithm, instead of replaying the SQL self-join. A tolerance of 1e-10 applies only to floating-point display values; eligibility and rank decisions are exact.

The compact counts and SQL diagnostics both read the hash-verified typed Parquet. This reference is algorithmically independent of the longitudinal SQL, rather than an independently acquired source. The earlier full-CSV audit supplies independent count/flag reconciliation for all, 2023, debt collection and California scopes. New monthly response-mix totals and routing-distribution medians also reconcile.

A separate [product-headline verifier](../scripts/verify_product_findings.py) freshly hashes and streams the entire frozen scoped CSV with the standard-library CSV reader. It independently reconciles complaints, Yes, No, known and unknown counts for all 14 product labels against the SQL product output. [Product reference evidence](../outputs/product_reference_validation.json) supports the student-loan finding without using the same Parquet aggregation as its only verification path. This additional verifier rehashes the scoped CSV; the main population runner itself does not.

Full 50/100/200 sensitivity uses the all-state/all-product baseline. Received-2023, debt-collection and California queues are separately recalculated at minimum 100. These filtered outputs demonstrate context-specific comparators and ranks; they are instead of geography filters applied to the global rank table. Filtered 50/200 sensitivity and arbitrary interactive selections remain report-build work.

## Outputs and interpretation

- `monthly_overview.csv`: all 36 baseline months plus three filtered scopes, with counts beside rates.
- `product_overview.csv`, `response_mix.csv`, `routing_distribution.csv`: descriptive portfolios and quality reconciliation.
- `review_queue.csv`: each qualifying segment-window at each executed minimum and scope; pooled own/peer numerators, known denominators, total volumes, unknown counts and exact-ranking result.
- `review_monthly_summary.csv`: eligible monthly segments, eligible windows and persistent windows per ending month, scope and minimum.
- `review_segment_history.csv`: complete monthly history for every qualifying segment at the corresponding scope/minimum, including excluded and non-qualifying months and issue-share changes.
- `gate_c_analysis.json`: reference counters, reconciliation, hashes and runtime/candidate-volume evidence.
- `product_reference_validation.json`: separate fresh scoped-CSV hash and independent product count/flag verification.
- `gate_c_acceptance.json`: current-artifact checks and normal/optimized behavioral-suite results.

Windows overlap. Counts of segment-windows are screening opportunities, instead of distinct complaints, independent events or additional cases. Sensitivity stability means the same segment and ending month qualify at all three minima; ranks can change as competitors enter or leave. Filtered scopes run at one minimum are never labelled stable across all minima.

Every queue row describes a published complaint portfolio, instead of overall company service quality. The source lacks customer exposure, market share and verified handling/resolution events. Unknown flags, when present, remain in total volume and outside rate denominators. No statistical-significance, regulatory-compliance, wrongdoing or achieved-improvement claim follows from screening.

## Runtime boundary

The unchanged SQL ranks distinct qualifying tuples with exact integer cross-products. Its comparison work is quadratic per ending month. The runner records both complete SQL evaluation time and an isolated rank-key replay time, together with distinct candidate tuples, maximum tuples per month and the sum of squared tuple counts. The reference independently validates the resulting ranks.

These are single local development measurements with four DuckDB threads and a 4GB SQL memory limit. Cache state is uncontrolled. They are instead of a benchmark across machines, a Power BI latency guarantee or evidence that arbitrary slicer combinations will refresh quickly. The SQL memory limit follows the existing laptop preparation environment; no scalability improvement is inferred from it.

## Reproduction

From the workspace root, use the project's existing audited environment:

```bash
projects/f1-complaint-response-reliability/.venv/bin/python projects/f1-complaint-response-reliability/scripts/population_analysis.py
projects/f1-complaint-response-reliability/.venv/bin/python projects/f1-complaint-response-reliability/scripts/verify_product_findings.py
projects/f1-complaint-response-reliability/.venv/bin/python projects/f1-complaint-response-reliability/scripts/validate_gate_c.py
```

The population command requires the accepted local typed Parquet and Gate B evidence. The product verifier additionally requires the frozen scoped CSV. Acceptance requires both commands to pass, rechecks recorded hashes and runs all behavior tests normally and under optimized Python. It writes new Gate C logs while preserving Gate B logs. No new dependencies are required. Refresh from the original raw source and actual Power BI import/render/interaction acceptance belong to Gate D.

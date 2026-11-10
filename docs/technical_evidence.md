# F1 technical evidence

## Build boundary

The local SQL + Power BI build has ten model tables, five relationships, 53 measures and two baseline-rendered pages. [Live acceptance](../outputs/native_queue_acceptance_results.json) records 2,194 compared fields across 49 operations. These are development checks, instead of final CV measurements. [Final build acceptance](../outputs/final_build_acceptance_20261028.json) records the completed relocated refresh, owner interaction acceptance and corrected-palette render review on 2026-10-28; see [completion](../completion.md).

## Six analytical SQL responsibilities

The [population runner](../scripts/population_analysis.py) executes these queries against the accepted typed complaints. `selected_complaints` is the scoped complaint-grain relation; the longitudinal evaluator supplies the separate `contract_input` relation and bound date, population and minimum parameters.

| Query | Implemented technique | Output and verification |
|---|---|---|
| [Monthly overview](../sql/monthly_overview.sql) | Conditional flag counts, known denominators and valid routing medians by received month; August 2023 stays descriptive | [Monthly output](../outputs/monthly_overview.csv); count and median reconciliation in [Gate C analysis](../outputs/gate_c_analysis.json) |
| [Product overview](../sql/product_overview.sql) | Preserve all raw product labels; aggregate counts before deriving rates | [Product output](../outputs/product_overview.csv); separate full scoped-CSV [product audit](../outputs/product_reference_validation.json) |
| [Segment-month counts](../sql/segment_month_counts.sql) | Aggregate company × raw product × raw issue × calendar month without dropping blank issues | Input to the independent [reference evaluator](../scripts/analysis_reference.py); [5,849,172 diagnostic comparisons](../outputs/gate_c_analysis.json) across six executed scope/minimum runs |
| [Response mix](../sql/response_mix.sql) | Keep response-category missingness and recorded timely flags separate | [Response mix](../outputs/response_mix.csv); monthly response totals reconcile to complaint counts. This field is excluded from the compact report model |
| [Routing distribution](../sql/routing_distribution.sql) | Discrete lag frequencies, including routing-status exceptions, support median reconstruction | [Routing distribution](../outputs/routing_distribution.csv); reconciled with complaint-grain medians rather than a median of grouped medians |
| [Longitudinal contract](../sql/longitudinal_contract.sql) | CTEs build a dense calendar, subtract focal issue counts from company/product totals, evaluate consecutive windows and compare reduced rational rank tuples | [Queue](../outputs/review_queue.csv), [monthly screening totals](../outputs/review_monthly_summary.csv) and [segment histories](../outputs/review_segment_history.csv); independent `Fraction` comparisons verify eligibility and ties |

The contract admits three complete same-era months, monthly segment and peer volumes at the selected 50/100/200 minimum, known flags in every month and at least two monthly gaps of 1 percentage point. Ranks compare elevated-month count, rational pooled gap, No count and complaint count, in that order. Tied tuples share a dense rank within the ending month. The [metric dictionary](metric_dictionary.md) is the rule authority.

## Compact model and calculation examples

| Implementation | Technical decision | Evidence |
|---|---|---|
| [SQL projection](../sql/import_projection.sql) and [export runner](../scripts/export_import_projection.py) | Preserve arbitrary-day filtering and routing medians in 1,883,868 frequency groups conserving 9,469,257 complaints | [Projection checks](../outputs/import_projection_validation.json): reverse identity/frequency differences are zero; all ten Parquet files round-trip |
| [Foundation definitions](../scripts/model_definition.py) | Five single-direction dimension-to-fact relationships; disconnected review utilities; one source-folder parameter | [Model inventory](../outputs/model_foundation_validation.json), [metadata readback](../outputs/model_foundation_readback.json) and [current model guide](model.md) |
| Keyed labels | Keep SQL NULL, empty strings and colliding display labels distinct with integer identity keys and grouping metadata | [Projection identity rules](../outputs/import_projection_notes.md#identities-and-observed-month-losslessness); [projection tests](../tests/test_import_projection.py) |
| Weighted routing median | Sum valid-lag frequencies, locate both middle positions and average them for even populations; undefined results remain BLANK | [Overview query plan](../scripts/live_overview_plan.py), [live reconciliation](../outputs/live_acceptance_results.json), odd/even/empty [projection fixtures](../tests/test_import_projection.py) |
| [Dynamic population](../scripts/priority_population.py) | Group monthly frequencies and join keyed three-month shifts; preserve complete selected months, the August boundary and same-company/product other-issue peers | [Population tests](../tests/test_priority_population.py), [current acceptance](../outputs/native_queue_acceptance_results.json) |
| [Overflow-safe rank comparator](../scripts/rank_arithmetic.py) | Use bounded limb arithmetic instead of copying SQL 128-bit cross-products into DAX 64-bit arithmetic | [Bounds and proof](model-rank-arithmetic.md); [104 live comparator cases](../outputs/live_edge_results.json) against a separate `Fraction` oracle |
| [Sparse queue projections](../scripts/queue_measures.py) | Return BLANK outside qualifying selectors so the native table suppresses rejected rows without a broad measure filter; retain separate rejected-window diagnostics | [Captured problematic query](../outputs/native_queue_query_52.dax), [current queue parity](../outputs/native_queue_acceptance_results.json), [queue regression tests](../tests/test_queue_measures.py) |
| [Report builder](../scripts/build_report.cjs) | Synced population slicers; queue focus targets only monthly evidence and sensitivity; preserve manual edits through manifest guards | [Builder tests](../tests/test_build_report.test.cjs), [baseline rendered review](../outputs/render_repair_review.json); owner-reported UI interaction acceptance is recorded separately in [final build evidence](../outputs/final_build_acceptance_20261028.json) |

## Validation layers and limits

1. **Source/preparation:** [Gate B](../outputs/gate_b_acceptance.json) verifies complaint keys, original-field preservation, explicit exclusions and independent CSV metrics. Official origin is user-confirmed; original download metadata and live official-export identity remain unverified.
2. **Analytical contract:** [Gate C](../outputs/gate_c_acceptance.json) verifies full-scope sensitivities and filtered base-rule recomputation against an independent algorithm. Overlapping windows remain separate screening opportunities, instead of independent events.
3. **Live engine:** [Current acceptance](../outputs/native_queue_acceptance_results.json) compares identities, counts, ranks, gaps and passing minima across overview, priority and native-shaped queries. Programmatic filtering is distinct from mouse/keyboard acceptance.
4. **Rendered report:** [Dated baseline review](../outputs/render_repair_review.json) and [current-window checkpoint](../outputs/interaction_acceptance_checkpoint.json) cover baseline, December-2025 MOHELA focus/sensitivity and California overview/empty-queue data. The owner separately confirmed reset, minimum selection and CA navigation. [Final baseline previews](../README.md#report) confirm the corrected navy product bars. Long product labels truncate and supporting queue fields require scrolling; the owner accepted readability at Fit to page.
5. **Refresh and release:** the [2026-10-28 clean-copy run](../outputs/final_build_acceptance_20261028.json) completes Full refresh from ten NoData partitions, reconciles all imported counts and repeats 2,194 live field comparisons. [Owner checks](../reports/owner_review.md) pass at Fit to page. The earlier timed-out refresh remains a separate, unresolved historical attempt.

## Post-build claim measurement

[Gate D sign-off](../outputs/gate_d_signoff_20261028.json) precedes [final measurement](../outputs/final_claim_measurements_20261028.json). The measurement runner verifies 138 frozen artifacts before and after, independently streams the scoped CSV and repeats the full-population screening at all three minima against the Fraction reference. The [separate focal audit](../outputs/final_claim_audit_20261028.json) reconstructs October–December 2025 counts directly from typed complaints, without using canonical window/ranking SQL, and checks the pooled gap with rational arithmetic. The [evidence register](../evidence_register.md) links the resulting claims, caveats and original CV wording.

Full-scope native-shaped queue queries took roughly 19–21 seconds in the recorded local development run. This is a latency caveat, instead of a general performance benchmark. No cloud publication, achieved improvement, regulatory breach or overall company-quality claim is made.

## Reproduction

Use [environment.md](environment.md) for the audited Python/DuckDB environment, [analysis_method.md](analysis_method.md#reproduction) for the SQL pipeline and [model.md](model.md#reproduction) for model construction. The foundation builder refuses to overwrite an existing model export. Preserve manual model/report changes rather than regenerating over them. [Walkthroughs](../walkthrough.md) explain the result and its technical basis.

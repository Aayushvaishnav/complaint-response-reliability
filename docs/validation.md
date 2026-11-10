# F1 source validation and filtering

The initial source task validated the user-supplied CSV while R2 was active. H1 and R2 remain Complete; F1 is now [Complete through Gates A–E on 2026-10-28](../completion.md#gate-e-portfolio-complete-passed-on-2026-10-28), with three independently approved CV-ready claims. Source/preparation evidence and earlier dated checkpoints are preserved below. The [final build acceptance](../outputs/final_build_acceptance_20261028.json) supersedes earlier pending refresh, interaction and palette checkpoints without expanding their historical verification scope.

## Validation contract

- Grain: one record per complaint ID. IDs remain text; duplicate, blank or non-numeric IDs block the date-scoped export instead of triggering automatic deletion.
- Schema: the supplied 15-column export, including the eight core F1 fields. Narrative text is absent from this export. No narrative-dependent analysis is possible.
- Parsing: strict UTF-8 CSV ingestion with every column retained as text. Blank strings remain blank strings, including quoted blanks. ZIP codes retain leading zeroes and masking characters.
- Dates: parse received and sent-to-company dates separately. An unparseable received date blocks automatic cohort extraction because eligibility is unknown. Missing or invalid sent dates and negative routing lags remain in the data and are counted.
- Timeliness: preserve the source flag. SQL classifies only exact `Yes` and `No` as known; all other values are `Unknown`. Future timely-response rates must use `Yes / (Yes + No)`, with unknowns shown separately.
- Filtering: received date from 2023-01-01 inclusive to 2026-01-01 exclusive, following the source plan. Keep all products, companies, states, response outcomes and original category labels. This is a complete observed date cohort from the supplied file, instead of a random sample or an independently certified census of published complaints.
- Preservation: keep the supplied original and a byte-identical project-local snapshot. The filtered CSV preserves all 15 field values. CSV quoting and row order are not contractual; contents are checked as multisets in both directions with `EXCEPT ALL`.
- Reconciliation: raw records equal retained records plus mutually exclusive date exclusions. Re-read the final CSV, check its count and compare every exported field with the scoped SQL relation. Save SHA-256 hashes for the source and final CSV.

`passed` in the machine-readable report means the ingestion, key, received-date, cohort and export checks passed. It does not certify consumer allegations, source completeness, cross-year taxonomy comparability or readiness of a Power BI model. Optional-field missingness and retained routing/timeliness exceptions are reported separately.

## Reproduce

Run from the workspace root using F1's independently installed, audited SQL environment:

```bash
projects/f1-complaint-response-reliability/.venv/bin/python -m unittest discover -s projects/f1-complaint-response-reliability/tests -v
projects/f1-complaint-response-reliability/.venv/bin/python projects/f1-complaint-response-reliability/scripts/validate_source.py
```

The initial full-source run used Python 3.14.7 and DuckDB 2.0.0 from R2's existing environment without installing packages. Gate A installed the same DuckDB version in F1's own `.venv/`; [environment](environment.md). SQL performs ingestion, profiling, date selection and export reconciliation; Python orchestrates copying, checksums, checks and evidence. This utility does not add a separate analytical Python deliverable to F1's planned SQL + Power BI stack.

Use `--source <path>` for the supplied file and `--project <folder>` for a separate output location. A different source cannot overwrite an existing raw snapshot. The script rebuilds generated validation artifacts when rerun against the same snapshot. It caps DuckDB memory at 4 GB and uses four threads; spill files stay inside ignored project data storage.

Tests cover date boundaries, leap-day failure, unknown timeliness, missing sent dates, negative lag retention, multiline/quoted values, leading-zero ZIP codes, duplicate and invalid IDs, empty cohorts, schema changes, snapshot preservation and repeat execution. Test fixtures are synthetic and separate from source measurements.

The committed suite also checks UTF-8 BOM handling, literal `NULL`, whitespace and CRLF preservation, and rejection of short/long records. All 10 tests pass under normal and optimized Python; [normal run](../outputs/source_validation_tests.txt), [optimized run](../outputs/source_validation_tests_optimized.txt).

An additional [independent check](../outputs/independent_csv_validation.json) scanned every retained CSV record with Python's standard CSV reader and date parser. It confirmed record widths, date eligibility, the 9,469,257-record count, all monthly totals and timely-flag counts against the SQL profiles. This was a separate one-time audit, instead of part of the rebuild utility.

## Interpretation safeguards

- `Date sent to company - Date received` is routing lag, instead of company response duration or resolution time. Negative lags must be flagged and excluded from valid-lag summaries, while retaining their complaint records.
- Company response category and timely-response flag are separate fields. An `In progress` category does not establish a final resolution; a blank response category remains unknown rather than becoming an untimely response. Preserve each field independently.
- Category options changed on 2023-08-24, inside this cohort. Preserve original labels until an explicit, documented crosswalk is approved; merging similar-looking product labels can create unsupported comparisons.
- Public complaint data are mutable, and publication and response updates can lag. A completed calendar year in this file does not prove complete collection or a final outcome for every record.
- Complaint portfolios have no customer-exposure denominator. Counts and recorded response flags cannot rank overall service quality, prevalence or verified wrongdoing.
- Optional state, ZIP, tag, subcategory and public-response blanks are not automatic row exclusions. Review core-field blanks before defining analytical eligibility.

## Official-source references and verification limits

The user confirmed direct official CFPB origin during Gate A. The original download URL/time and an official-export checksum were not recorded. Identity is established locally by hashing and comparing the supplied file with the copied snapshot; byte identity with a fresh official download remains unverified. Filesystem modification time is recorded separately from download time.

The [official CFPB database landing page](https://www.consumerfinance.gov/data-research/consumer-complaints/), single-record API route and PDF requests returned HTTP 403. Accessible first-party [field reference](https://cfpb.github.io/api/ccdb/fields.html), [pinned 15-field export source](https://raw.githubusercontent.com/cfpb/ccdb5-api/9bf8c3e8b013d846394dd285bb49470a23ead628/complaint_search/defaults.py) and [release notes](https://cfpb.github.io/api/ccdb/release-notes.html) corroborate schema and release-dependent classifications. The publisher warns older API docs are not updated; the pinned current header source provides separate corroboration. Explicitly reviewed official search excerpts support the public-reuse and August-2023 effective-date notes below. No fresh official complaint download, current data-use-policy page, complete PDF or live-record comparison was verified.

- [CFPB database webinar, November 2022, slide 18](https://files.consumerfinance.gov/f/documents/cfpb_finex-consumer-complaints-webinar_slides_2022-11.pdf): published data are freely available for use, analysis and building on; consider company/market size and population when interpreting volume. No specific named dataset licence is asserted.
- [CFPB product and issue options, effective 2023-08-24](https://files.consumerfinance.gov/f/documents/cfpb_consumer_complaint_form_product_issue_options_August_2023_FINAL.pdf): version boundary for form categories.
- [CFPB database fact sheet, March 2013](https://files.consumerfinance.gov/f/201303_cfpb_Consumer-Complaint-Database-Fact-Sheet.pdf): historical field definitions, including received date, sent date and unique complaint identifier.

The initial source report and manifest contain the full-file preparation measurements. They did not themselves sign off a gate. The later [Gate A record](../completion.md) separately accepts real-sample feasibility, contracts, environment and the documented user-mediated-source basis; [source evidence](../outputs/source_access_verification.json), [reviewed publisher excerpts](../config/publisher_evidence.json), [sample results](../outputs/gate_a_sample_validation.json) and [28 passing tests](../outputs/gate_a_tests.txt), also [passed under optimized Python](../outputs/gate_a_tests_optimized.txt). No report refresh, report render or analytical finding is signed off.

## Gate B contracts and numerical regression

The user approved the [review rule](../config/review_rule.json) before rankings. The [metric dictionary](metric_dictionary.md) defines complete selected months, the August 2023 break, per-month volume eligibility, other-issue peers, the inclusive 1 percentage-point gap, 2-of-3 persistence and ties. Synthetic fixtures test mechanics, instead of establishing population findings.

An independent standard-library `Fraction` reference checks counts, shares, prior calendar-month changes, eligible windows, persistence and ranks under two meaningful company/product/state/date contexts and all three volume minima. It includes raw NULL/empty/whitespace/literal-unknown labels and partial selections. [Reference code](../tests/test_review_reference.py), [reference verification](../outputs/review_reference_checks.json).

The oracle reproduced a numerical ranking defect: `6/10 − 42/165` and `6/11 − 2/10` both equal `19/55`, but ranking their binary floating-point differences split an otherwise equal tuple. The [pre-fix regression](../outputs/gate_b_reference_regression_before.txt) records the rank failures. [SQL](../sql/longitudinal_contract.sql) now reduces exact integer fractions and counts distinct strictly better tuples. Display percentages remain floating point; eligibility and rank comparisons use integer arithmetic. The oracle passes after the fix. Full-scope runtime and candidate-key volume still require Gate C benchmarking because exact pairwise rank comparison has quadratic cost per ending month.

## Gate B full preparation evidence

The [preparation runner](../scripts/prepare_complaints.py) and [SQL](../sql/prepare_complaints.sql) preserve the 15 raw fields and add typed dates, flag/routing states, timing eras and non-colliding category keys. The prior scoped CSV is rehashed and independently streamed in full with Python's CSV/date implementation. SQL builds a separate complaint-grain table from read-only source staging; full raw-field equivalence against both current staging and the frozen CSV, unique keys, month/product/state conservation and typed Parquet equality are checked. The independent path recalculates counts, known/unknown rates and routing medians under all/2023/debt-collection/California scopes.

Generated evidence: [typed preparation](../outputs/typed_preparation_validation.json), [Gate B acceptance](../outputs/gate_b_acceptance.json). Only a passed current report, matching recorded artifact hashes and passing normal/optimized tests permit Gate B sign-off. The [environment guide](environment.md#gate-b-preparation-and-contract-checks) provides the commands. Neither report substitutes for a future Power BI load, DAX reconciliation or clean-folder report refresh.

**Final Gate B verification, 2026-10-23:** all 20 acceptance checks pass; **62 tests pass normally and under optimized Python**. Current staging conserves **18,590,360 = 9,469,257 + 9,121,103** records. Raw-field differences against staging and the frozen CSV are zero, and all typed Parquet fields compare equal with matching names/types. Independent SQL/CSV metrics agree for all, 2023, debt collection and California. Timing-era totals are 795,104 pre and 8,674,153 post; all 119,711 August 2023 complaints remain in overview totals while being longitudinal-ineligible. These are development and validation counts, instead of findings or final CV achievements.

An [initial wide-comparison attempt](../outputs/gate_b_interrupted_validation.json) was interrupted after substantial observed spill and IO. It carries no acceptance. The bounded implementation retains exact bidirectional `EXCEPT ALL` field checks, partitioned by received month. Both relations require canonical, parseable, in-scope raw received dates and complete partition coverage; outside-scope or malformed extra rows must fail instead of falling outside the comparison. No before/after runtime improvement is claimed without matched, completed measurements.

Provenance scope remains explicit: Gate B rehashes the complete scoped CSV and compares every raw field in typed output with that frozen artifact and current staging. It relies on the prior source report and user-mediated official origin for the full raw snapshot. It does not repeat full raw hashing, certify live official-export byte agreement, or establish publication completeness.

## Gate C population acceptance

[Analysis methods](analysis_method.md) document six SQL query responsibilities, the independent sparse-aggregate rational reference, context-specific reruns and numerical/runtime limits. [Gate C analysis](../outputs/gate_c_analysis.json) passes for the unchanged accepted typed Parquet, rule and canonical SQL. The full population is evaluated at minima 50/100/200; 2023, debt collection and California are recomputed at minimum 100. Exactly 5,849,172 monthly diagnostic rows are checked, including own/peer totals, complete months, August exclusion, prior calendar-month shares, rolling windows and exact dense ranks. Counts and medians reconcile in all four overview scopes.

The [additional product verifier](../scripts/verify_product_findings.py) freshly hashes and streams the complete scoped CSV and independently agrees on counts and Yes/No/unknown flags for all 14 raw products; [evidence](../outputs/product_reference_validation.json). This gate does not repeat full raw hashing or live official-export comparison; fresh official-export agreement remains unverified.

The [queue](../outputs/review_queue.csv) contains 112/36/5 qualifying segment-windows at minima 50/100/200, and exactly five base windows pass all minima. [Monthly histories](../outputs/review_segment_history.csv) preserve monthly explanations for qualifying segments. California's empty base-rule queue is supported by [279 eligible segment-windows](../outputs/review_monthly_summary.csv), rather than an absence of complaints. Three supported [findings and investigation proposals](findings.md) disclose overlapping windows, volume sensitivity and monthly-versus-pooled differences.

[Gate C acceptance](../outputs/gate_c_acceptance.json) rechecks current artifact inventories and executed scope/minimum coverage; all **72 tests pass normally and under optimized Python**. Tests add sparse-reference corruption checks, three-month peer totals/unknowns, sensitivity membership and ties, filtered rank recomputation, empty queues, count/median corruption rejection and CSV product flags. [Normal log](../outputs/gate_c_tests.txt), [optimized log](../outputs/gate_c_tests_optimized.txt).

Single-run complete SQL timings are 2.99–3.12 seconds per minimum. The lowest minimum has at most nine distinct exact-ranking tuples per month and 618 potential tuple pairs across months; isolated rank replay is 0.0033 seconds. Canonical ranking remains quadratic; no scalability improvement, UI performance or cloud result is claimed. At that Gate C checkpoint, no Power BI build, DAX reconciliation, refresh or rendered/interaction acceptance had been performed.

## Gate D live and rendered repair checks

[Current live acceptance](../outputs/native_queue_acceptance_results.json) passes 49 operations and 2,194 compared fields. Coverage includes six overview contexts; all/2023/Debt collection/California priorities and native-shaped queue fields at minima 50/100/200; and fourteen focused/arithmetic cases. Keyed identity sets, exact dense ranks and counts require exact equality. Displayed ratios are checked to absolute tolerance 1e-12; undefined values remain BLANK. Duplicate/missing rows, truncated outputs, missing fields and count drift cause reconciliation failure.

The native visual initially generated a broad measure-filter query, confirmed in [the captured DAX](../outputs/native_queue_query_52.dax). It evaluated every displayed diagnostic before qualification. The owner approved replacing this filter with [sparse queue projections](../scripts/queue_measures.py); diagnostic measures remain unchanged for rejected-window audits. All 53 measures read back as Ready and the model is exported. Current native-shaped full-scope queue queries take approximately 19–21 seconds in the recorded local run; no speed-up percentage or general benchmark is claimed.

[Schema validation](../outputs/report_repair_validation.json) has zero errors and warnings. [Fresh baseline captures](../outputs/render_repair_review.json) show populated overview/audit visuals, exact KPI denominators, the flat priority queue with identities, 1,873/36/13/5 base-rule cards, context and all minimum options. The owner also confirms queue rows are visible after reopening. The latest files match the generation manifest. Two older Desktop-saved states were backed up with explicit approval before restoring pending authored changes. Temporary captures were reviewed and removed; accepted baseline previews are retained separately.

Full row-focus/sensitivity, slicer clearing/navigation and filtered/empty rendered acceptance remain pending. Long product labels and horizontally scrolled queue fields remain documented presentation limits. A Full refresh invocation timed out with an unspecified remote outcome; later Ready-state readback is insufficient to certify refresh. Confirmed clean-folder refresh and packaging remain prerequisites for Gate D.

## Handoff

F1 is `In progress`; Gates A–C passed, with live SQL/DAX and baseline render repairs verified. The [documentation/current-window checkpoint](../outputs/interaction_acceptance_checkpoint.json) records fresh 110 normal/optimized Python and 21 WSL Node passes. Warm captures confirm visible baseline data; all 36 authored report-file hashes match. Desktop still reports unsaved changes after owner confirmation, so no automatic reload was performed and disk-to-window freshness remains unproven by this capture.

[Technical evidence](technical_evidence.md), [walkthroughs](../walkthrough.md) and [owner/refresh checks](../reports/owner_review.md) are delivered. The subsequent guided MOHELA focus/sensitivity and CA overview/empty-state captures pass current-window review. December-focused cards match existing SQL at 96/1/1/0; CA shows 906,980 complaints, 3,701 No and 279/0/0/0. Reset, minimum changes and CA navigation are accepted as user-reported checks, rather than separately observed intermediate clicks. All temporary capture children were removed after review.

Next: complete Debt collection, two-state/partial-date/multi-row and keyboard/zoom cases, confirmed clean-folder refresh, presentation polish and final package acceptance. H1 and R2 remain `Complete`. Live CFPB access remains a documented HTTP 403 limitation; native queue latency remains a development caveat. F1 has no Gate D sign-off, so final CV measurement is not permitted.

## Gate D final acceptance, 2026-10-28

[Sign-off](../outputs/gate_d_signoff_20261028.json) follows a successful Full refresh in a separate, cache-free project copy. Before refresh, all ten partitions were NoData. The live Source Folder parameter and ten partition expressions point to copied inputs whose hashes match the accepted exports. After successful MCP completion, all ten table counts and complaint frequencies reconcile; [45 operations / 2,194 field comparisons](../outputs/clean_refresh_reconciliation_20261028.json) pass. This is a distinct completed test, instead of evidence about the earlier timed-out operation.

[CA+NY SQL expectations](../outputs/owner_multistate_expectations_20261028.json) and [live DAX](../outputs/owner_multistate_live_results_20261028.json) agree at all minima. At minimum 100 the overview contains 1,468,258 complaints and 5,403 No, with 291 eligible and zero qualifying windows. The owner confirmed all five remaining navigation, multi-state, partial-date, two-row-focus and keyboard/scroll checks at Fit to page, then confirmed the latest layout was loaded manually. These are user-reported interactions, separate from numerical and screenshot checks.

Both original and copied reports validate with zero errors/warnings. [Final renders](../outputs/final_build_acceptance_20261028.json) show the navy product bars and complete baseline headline values; the copied and original report definitions match byte-for-byte. Long chart labels and supporting queue columns still require tooltip/scroll access. Temporary screenshots were removed after review, with two dated previews retained.

A repeatable cursor-lifecycle defect was found while composing two independent expectation generators: `fetchone()` left the one-row result unfinished in DuckDB 2.0.0. Consuming the complete aggregate result lets the next relation operation reuse the connection. [Before-fix regression](../outputs/overview_cursor_regression_before_20261028.txt) fails and the new multi-call test passes. The chart palette regression likewise fails before the single-series unselected `defaultColor` fix in [its log](../outputs/chart_color_regression_before_20261028.txt), then passes with the corrected render. Neither change alters the screening contract or population findings.

Final suites pass **117 normal/optimized Python tests and 22 Node checks**. An independent delegated review found no blocking issues in the changed code and retained evidence, and separately passed 10 Python live-plan, 6 staging and 11 Node report-builder checks. Gate D now permits final claim measurement against 138 frozen artifacts. No achieved improvement, scheduled refresh or cloud publication is claimed.

## Post-build measurement and claim audit, 2026-10-28

Fresh measurement starts after the signed build, checks all 138 frozen artifacts before and after and independently streams the scoped CSV. The measured population is 9,469,257 unique complaints across 36 received months and 14 raw product labels, conserving 9,431,474 Yes + 37,783 No + 0 unknown. The standalone CSV audit agrees on all aggregate flag counts and raw product count. The original complete raw snapshot is not freshly hashed; the scoped CSV and typed Parquet are.

The canonical SQL is freshly evaluated at minima 50/100/200. A separate Fraction reference checks 1,566,288 dense monthly diagnostics at each minimum and agrees on 112/36/5 qualifying windows, 30/13/3 segments and a five-window intersection. The [independent focal audit](../outputs/final_claim_audit_20261028.json) uses direct monthly SQL and rational arithmetic, independently confirming 590/972 versus 253/452 and a pooled gap of 129775/27459 percentage points, approximately 4.726pp. At minimum 200 the peer volume fails all three months; raw rate elevation is separate from eligible screening elevation.

The [measurement output](../outputs/final_claim_measurements_20261028.json), [audit output](../outputs/final_claim_audit_20261028.json) and [claim register](../evidence_register.md) preserve the source hashes, scope, denominators, query paths and caveats. The additional Gate E tools and tests are separate from the unchanged frozen analytical/report build.

[Final release review](../outputs/final_evidence_review_20261028.json) approves all three original claims. The independent reviewer rehashes all 138 signed artifacts with zero mismatches and separately reproduces the focal monthly SQL and exact gap. The completed suite passes **122 tests normally and optimized, plus 22 Node checks**; five targeted Gate E tests also pass in the independent review. Gate E is signed off, with no supporting project started.

# Compact Import projection handoff

This is SQL/Parquet projection validation only; no semantic-model, DAX, rendering, refresh or Gate D acceptance is granted.

## Reproduction

From workspace root using the existing audited DuckDB environment (no new dependencies):

```bash
projects/f1-complaint-response-reliability/.venv/bin/python projects/f1-complaint-response-reliability/scripts/export_import_projection.py
projects/f1-complaint-response-reliability/.venv/bin/python -m unittest discover -s projects/f1-complaint-response-reliability/tests -p test_import_projection.py -v
projects/f1-complaint-response-reliability/.venv/bin/python -O -m unittest discover -s projects/f1-complaint-response-reliability/tests -p test_import_projection.py -v
```

The runner verifies Gate B's accepted artifact hashes before reading the immutable typed source. It performs reverse raw-label/frequency reconciliation, key uniqueness and raw-identity checks, selection set equivalence, four scoped overview count/median checks, and exact Parquet round-trip checks. Failure writes explicit failed status. Generated Parquet remains covered by the existing `data/processed/` ignore rule. No raw/preparation artifact is changed.

The ten exported files are in `data/processed/model-input/`. Native folder:
`C:\Users\Aayush\my_files\da_projects\projects\f1-complaint-response-reliability\data\processed\model-input`.

[Validation JSON](import_projection_validation.json) is authoritative for filenames, complete field/type schemas, row counts, input hashes, output hashes and implementation hashes. Exported dates are DATE, counts/keys/routing days BIGINT, calendar ordinals INTEGER, flags BOOLEAN and labels VARCHAR; no HUGEINT export columns.

## Explicit mapped-column handoff

| File/table | Model table | Source → intended mapped column |
|---|---|---|
| complaint_cohorts.parquet | Complaint Cohorts | received_date → Received Date; company_key → Company Key; product_key → Product Key; issue_key → Issue Key; geography_key → Geography Key; routing_status → Routing Status; routing_days → Routing Days; complaint_rows → Complaint Rows; yes_rows → Yes Rows; no_rows → No Rows; unknown_rows → Unknown Rows |
| date.parquet | Date | date → Date; year → Year; month_start → Month Start; month_label → Month Label; month_order → Month Order; timing_era → Timing Era; boundary_month → Boundary Month |
| company.parquet | Company | company_key → Company Key; raw_value → Raw Value; is_missing → Is Missing; missingness → Missingness; display_label → Company |
| product.parquet | Product | product_key → Product Key; raw_value → Raw Value; is_missing → Is Missing; missingness → Missingness; display_label → Product |
| issue.parquet | Issue | issue_key → Issue Key; raw_value → Raw Value; is_missing → Is Missing; missingness → Missingness; display_label → Issue |
| geography.parquet | Geography | geography_key → Geography Key; raw_value → Raw Value; is_missing → Is Missing; missingness → Missingness; display_label → State |
| review_minimum.parquet | Review Minimum | minimum → Minimum |
| sensitivity_minimum.parquet | Sensitivity Minimum | minimum → Minimum |
| review_window.parquet | Review Window | window_end → Window End; window_label → Window Label; month_order → Month Order |
| review_selection.parquet | Review Selection | selection_key → Selection Key; segment_key → Segment Key; company_key/product_key/issue_key → Company Key/Product Key/Issue Key; window_end → Window End; company_raw/product_raw/issue_raw → Company Raw/Product Raw/Issue Raw; company/product/issue → Company/Product/Issue; company_missingness/product_missingness/issue_missingness → Company Missingness/Product Missingness/Issue Missingness |

These are handoff mappings, not claims that model objects exist. Relationship types must match the exported BIGINT keys; Date joins by DATE, not a generated date integer.

## Identities and observed-month losslessness

Raw NULL, empty strings, whitespace and literal labels (including `[Empty]`, `[SQL NULL]`, `missing:`) are separate identities. Null-safe raw joins and integer keys enforce this; `missingness` distinguishes `sql_null`, `empty`, `value`. `is_missing` includes NULL and empty. Display labels are **not keys** and may collide with real raw labels; preserve integer identities in all tuple logic and provide missingness/raw values for disambiguation. No concatenated sentinel tuple keys are used.

`segment_key` is a deterministic integer identity of company/product/issue over the frozen source, independent of month; `selection_key` identifies that segment's observed month. `window_end` is the first day of the ending calendar month, as in canonical SQL. Keys are reproducible for this frozen source, not a promise of stability across new snapshots.

Review Selection includes every observed company/product/issue/month, with no volume-based pruning and no geography expansion. Every eligible three-month window requires positive volume in its ending month (the allowed minima are 50/100/200). Population filters can remove source rows but cannot create an unobserved segment/month. Therefore every potentially eligible ending month exists in this utility under arbitrary population subfilters. Missing months and timing boundaries are still handled by subsequent rule evaluation; this utility does not claim eligibility or store priority ranks. Dedicated fixture tests exercise all/no/CA/NY selections and multiple positive minima.

## Execution evidence

Full export: 1,883,868 cohorts preserving 9,469,257 complaints (9,431,474 Yes, 37,783 No, zero Unknown). Dimensions: Date 1,096; Company 5,150; Product 14; Issue 94; Geography 63. Both minima utilities: three rows each. Review Window: 36 rows; Review Selection: 233,427 observed tuple/months. Reverse projection and selection set differences: zero. Full/2023/Debt collection/CA count and weighted-median checks passed; all four population medians are zero days. Even/odd/empty fixture medians separately prevent that uniform population result masking errors.

Projection logs: `import_projection_run.log`, `import_projection_tests.txt`, `import_projection_tests_optimized.txt`. Regression logs: `import_projection_regression_tests.txt`, `import_projection_regression_tests_optimized.txt`. Empty successful runner output is normal; detailed results are in the validation JSON.

Five dedicated tests pass normally and optimized. The full existing suite plus these tests passes: 83 tests normally and 83 optimized.

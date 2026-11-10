# F1 data manifest

Source preparation validated on **2026-10-23T05:13:52.225835+00:00**. This is data-readiness evidence, instead of an analytical finding or a completed F1 build gate.

## Source identity

- Publisher and intended source: [CFPB Consumer Complaint Database](https://www.consumerfinance.gov/data-research/consumer-complaints/).
- Supplied file: `complaints/complaints.csv` at the workspace root; preserved unchanged.
- Download URL and original download date: not recorded. On 2026-10-23 the user confirmed a direct official CFPB download. Agreement with a fresh official export remains unverified; local identity and publisher schema evidence are recorded separately.
- Supplied-file modification time: `2026-10-23T04:59:02.182287+00:00`; this is filesystem metadata, instead of a verified download time.
- Raw size: **5,635,795,886 bytes** (5.25 GiB).
- Raw/source SHA-256: `ef4494d4ea9787db5dc87e3de659e07ffaecb6e19ee3df97c7c15e14d54a74d9`. The project snapshot has the same hash.
- Public analytical reuse is supported by the explicitly reviewed official publisher search excerpt; direct PDF and current landing-page access returned HTTP 403. See [publisher evidence](../config/publisher_evidence.json) and the [official references and limits](validation.md#official-source-references-and-verification-limits). No named dataset-wide licence is asserted.

## Project-local data

| Path relative to this project | Purpose |
|---|---|
| `data/raw/complaints.csv` | Byte-identical full snapshot; all supplied dates and products |
| `data/processed/complaints_2023_2025.csv` | Date-scoped CSV for the future F1 build; all 15 source fields preserved |
| `data/processed/source_validation.duckdb` | Local SQL staging and validated/scoped views; not a Power BI semantic model |

Source and generated row-level data are Git-ignored. The original remains in its supplied location.

## Validation results

| Check | Full supplied file | Retained 2023–2025 cohort |
|---|---:|---:|
| Complaint records | 18,590,360 | 9,469,257 |
| Distinct complaint IDs | 18,590,360 | 9,469,257 |
| Duplicate extra records | 0 | 0 |
| Blank IDs | 0 | 0 |
| Non-numeric IDs | 0 | 0 |
| Invalid or missing received dates | 0 | 0 |
| Invalid or missing sent-to-company dates | 0 | 0 |
| Negative routing lags | 7,050 | 0 |
| Unknown timely-response flags | 0 | 0 |
| Future received dates at validation | 0 | 0 |
| Future sent dates at validation | 0 | 0 |

Observed received-date range: **2011-12-01 to 2026-10-22** in the full file; **2023-01-01 to 2025-12-31** in the retained cohort.

## Filtering decision

**Apply the planned received-date filter; preserve all products as the baseline.**

The condition is `Date received >= 2023-01-01 AND Date received < 2026-01-01`. No random sampling, automatic deduplication, category merging, field imputation, company selection or outcome-based row deletion was applied.

| Disposition | Records |
|---|---:|
| After 2025 | 5,908,002 |
| Before 2023 | 3,213,101 |
| Retained 2023–2025 | 9,469,257 |

Reconciliation: **18,590,360 = 9,469,257 retained + 9,121,103 excluded by date**. The date filter removes **49.06%** of supplied records. All 36 expected months are present; this does not independently establish publication completeness.

| Received year | Retained records |
|---|---:|
| 2023 | 1,292,048 |
| 2024 | 2,734,268 |
| 2025 | 5,442,941 |

Credit-reporting labels account for **8,222,746 records (86.84%)** of this baseline; **1,246,511** records belong to other products. This combined count is only a scope diagnostic, not a validated taxonomy crosswalk. Further product filtering is optional for a more focused or smaller report and requires an explicit business scope. No product was removed on volume alone.

Keep optional-field blanks, unknown timeliness and routing exceptions in the source. A negative routing lag is invalid for a routing-duration summary, instead of a reason to delete the complaint. The validation JSON records missingness for every field.

### Retained exceptions

- **6 blank issues** and **19 blank company-response categories** remain in the scoped data. Use an explicit unknown bucket for these fields; retain the complaints in total-volume and known-timeliness denominators.
- **279 response categories are `In progress`**. A recorded timely response does not establish final resolution.
- **17,967 states**, **193,762 sub-issues** and **9,131,385 tags** are blank. These fields do not determine core cohort eligibility; show unknown geography or subcategories separately when relevant.
- All scoped timely-response flags are known: **9,431,474 `Yes`** and **37,783 `No`**. The separate company-response category `Untimely response` has **11,644** records; it is not a substitute for the flag.
- The full historical file has **7,050 negative routing lags**; none remain within the planned date cohort. They were excluded solely because they are outside 2023–2025, instead of through a separate data-quality deletion rule.

## Export integrity and evidence

- Scoped CSV: **9,469,257 records**, **2,969,678,291 bytes** (2.77 GiB).
- Scoped SHA-256: `15680a5a1a8f8eaed17fe9b9f5ce0c1297e21e69fd2088a7cdb860a7037cb9f8`.
- Export/source field-value differences, checked in both directions: **0**. All machine-readable source/export checks pass.
- [Source quality, dispositions and checksums](../outputs/source_validation.json).
- [Independent Python reconciliation of eight SQL profile totals and 36-month coverage](../outputs/source_profile_reconciliation.json).
- [Independent full retained-CSV scan](../outputs/independent_csv_validation.json): Python's standard CSV and date parsers independently confirm all 9,469,257 records, date eligibility, monthly counts, timeliness counts and core-field blanks.
- [Retained monthly counts](../outputs/scoped_monthly_counts.csv), [product counts](../outputs/scoped_product_counts.csv), [timeliness values](../outputs/scoped_timely_flags.csv), [response categories](../outputs/scoped_response_categories.csv). Corresponding `full_` files describe the entire supplied source.
- [Ten passing behavioral tests](../outputs/source_validation_tests.txt); also [passed under optimized Python](../outputs/source_validation_tests_optimized.txt).
- [Methods, field rules, reproduction, source-access limitations and handoff](validation.md).

## Gate A provenance update

The [source-access verification](../outputs/source_access_verification.json) rehashes the raw snapshot, matches all 15 headers to the publisher's pinned current API source, retrieves the first-party field reference and records the user's official-download confirmation. Main-site/live-record/PDF requests remain HTTP 403; public-reuse and August-2023 effective-date claims use explicitly reviewed indexed official excerpts, instead of claimed PDF downloads. The [gate record](../completion.md) accepts this user-mediated source basis with those limits.

The [real SQL feasibility sample](../outputs/gate_a_sample_validation.json) has 2,304 records across 769 month/product/raw-flag strata, all 36 months and 14 raw products. Its selection intentionally overrepresents rare flags; sample rates are mechanics checks, instead of population findings. All 15 fields survive CSV import and Parquet round-trip. Typed analytical exports and Desktop import remain future work.

The analytical/report build remains pending. Do not use these preparation counts as final CV achievements or infer customer-service quality, incidence, resolution duration or causal effects from complaint counts.

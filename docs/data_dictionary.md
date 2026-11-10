# F1 data dictionary: Gates A–B

## Authority and storage contract
Definitions below paraphrase the official [CFPB field reference](https://cfpb.github.io/api/ccdb/fields.html), corroborated against the 15-field export mapping in [current repository source at pinned revision](https://raw.githubusercontent.com/cfpb/ccdb5-api/9bf8c3e8b013d846394dd285bb49470a23ead628/complaint_search/defaults.py).
The repository README warns that the GitHub Pages documentation is not updated; it is not sole evidence of the current schema. Here the definitions and current code's export headers agree with the supplied header.

Raw CSV fields remain text and unchanged. Proposed typed dates and derived categories are separate analytical columns; complaint IDs and ZIP codes remain text. Blank counts below describe the **9,469,257-row 2023–2025 baseline**, not the feasibility sample; evidence: [source validation JSON](../outputs/source_validation.json).

| Exact source field | Official meaning | Analytical use/type and handling | Scoped blanks |
|---|---|---|---:|
| Date received | Date CFPB received the complaint | Derived date; cohort and received-month basis; invalid/missing values block automatic eligibility | 0 |
| Product | Product type identified by consumer | Text; raw classification, no merges | 0 |
| Sub-product | Sub-product identified by consumer; not all products have one | Text; optional detail, explicit unknown display | 5 |
| Issue | Issue identified by consumer; options depend on product | Text; raw segment key within product; unknown bucket retains complaint | 6 |
| Sub-issue | Sub-issue identified by consumer; depends on product/issue and not always available | Text; optional detail, explicit unknown display | 193,762 |
| Company public response | Optional public-facing company response selected from preset options | Text; not consumer response or timeliness; unknown bucket | 3,859,425 |
| Company | Company the complaint concerns | Text; investigation grouping, not a verified legal-entity consolidation | 0 |
| State | State of consumer-provided mailing address | Text; not incident location; retain explicit unknown geography | 17,967 |
| ZIP code | Consumer-provided mailing ZIP, subject to publication privacy rules | Text; preserve leading zeros, shortened/masked values; no inferred precision | 0 |
| Tags | Information supporting search/sort, such as Older American or Servicemember | Text; optional metadata, absence does not prove demographic absence | 9,131,385 |
| Submitted via | How complaint was submitted to CFPB | Text; submission channel, not service delivery channel | 0 |
| Date sent to company | Date CFPB sent complaint to company | Derived date; routing endpoint only; invalid/missing remains flagged | 0 |
| Company response to consumer | How company responded, e.g. Closed with explanation | Text; response-category mix only, unknown bucket; independent of timely flag | 19 |
| Timely response? | Whether company gave a timely response | Text; exact Yes/No known, all other values explicitly Unknown | 0 |
| Complaint ID | Unique complaint identification number | Text key despite official numeric description; nonblank unique validated IDs | 0 |

## Classification and exception rules
- Product/issue/sub-issue options are dependent and release-dependent. [Official options effective 2023-08-24](https://files.consumerfinance.gov/f/documents/cfpb_consumer_complaint_form_product_issue_options_August_2023_FINAL.pdf) establish an in-cohort taxonomy boundary.
- Preserve all 14 observed raw product labels in the [product profile](../outputs/scoped_product_counts.csv); no approved label crosswalk exists. The [Gate B contract](metric_dictionary.md#taxonomy-and-complete-month-contract) uses the 2023-08-24 date boundary, with all August complaints retained in overview counts but excluded from comparable-change and persistence windows. Date eras are timing proxies, instead of certified individual form versions.
- Derive explicit missingness/category states without overwriting raw values; use a separate unknown indicator so an actual label cannot collide with a display bucket. Missing optional fields never delete complaints.
- [Scoped response categories](../outputs/scoped_response_categories.csv) include **279 In progress**, **19 blanks** and **11,644 Untimely response**; none replaces the timely flag.
- [Scoped timely flags](../outputs/scoped_timely_flags.csv): **9,431,474 Yes**, **37,783 No**, **0 unknown**. Maintain the Unknown path for future snapshots and tests.
- All scoped dates parse and all routing lags are nonnegative. **7,050 historical negative lags** are outside the date cohort; their exclusion is due to date scope, not a complaint-deletion rule for lag quality.
- Derived routing days = sent date minus received date; valid only when both dates parse and difference is nonnegative. Retain invalid-lag complaints in count/timeliness metrics.
- Received month is calendar month from received date, not sent date or response date. No response/resolution timestamp is supplied.
- Narrative text is absent from this 15-field export; no NLP, sentiment or narrative issue extraction is available.
- User attested official CFPB download; original URL/date are unrecorded. [Manifest](data_manifest.md) hashes identify the snapshot, not agreement with today's mutable official database.

## Typed preparation interface

[Preparation SQL](../sql/prepare_complaints.sql) builds complaint-grain `complaints` in the separate ignored `data/processed/prepared.duckdb`. The original staging database stays read-only. The analytical table retains all 15 raw columns and adds the fields below; a full typed Parquet export is a preparation artifact, instead of the final compact Power BI import model.

| Derived field | Type and contract |
|---|---|
| `complaint_id` | Text alias of the raw Complaint ID; one unique, nonblank key per row |
| `received_date`, `sent_date` | Parsed canonical `YYYY-MM-DD` calendar dates; received date controls scope, sent date controls routing only. Basic ISO/week-date forms and non-padded dates are invalid. |
| `received_month` | Date on the first day of the received calendar month |
| `timely_response_status` | Exact raw Yes or No; any other input has the explicit Unknown state |
| `routing_status` | `valid`, `missing_or_invalid` or `negative`; invalid-lag complaints remain in count/flag metrics |
| `routing_days` | Nonnegative integer sent-minus-received calendar days for valid lags; otherwise absent by definition |
| `taxonomy_era` | `pre_2023_08_24`, `post_2023_08_24` or `unknown`; a timing proxy, instead of a certified source schema version |
| `longitudinal_eligible` | False for August 2023; true for other parsed received dates. This field handles the taxonomy boundary only; complete selected months, known flags and volume rules are additional requirements. |
| Category `*_missing` | Separate missingness indicator; raw blank/null remains distinguishable from a literal display label or whitespace-only value |
| Category `*_bucket` | Tagged key: `missing:` for missing and `value:` followed by the untouched raw label otherwise. A real label such as `missing:` gets key `value:missing:` and cannot collide with the missing key. |

The contract evaluator accepts a caller-provided `contract_input` relation with text `complaint_id`, `company`, `product`, `issue`, `state`, `timely_flag` and date `received_date`. The caller must retain the preparation's unique complaint grain; the evaluator does not repeat the full key audit on every filter evaluation. Use raw labels, rather than rendered display text, in this adapter. SQL NULL is supported for synthetic/future missing-category tests; the frozen source preserves blank strings. Issue identity remains separate from display missingness.

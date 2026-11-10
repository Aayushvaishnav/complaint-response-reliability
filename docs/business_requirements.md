# F1 business requirements: Gates A–B

## Decision and authority
- **Authority:** the earlier user confirmation on 2026-10-23 approved activating F1. The later R2 request deferred this unchanged foundation; R2 is now released and F1 is unlocked for its next request. Gate A scope remains frozen; the user also approved the proposed investigation rule before rankings. Current acceptance and next work are recorded in [completion](../completion.md).
- **Stakeholder:** simulated financial-service operations manager with limited investigation capacity; not a real client engagement.
- **Decision:** identify company × raw-product × raw-issue segments warranting process investigation using complaint volume, recorded timeliness and persistence safeguards; do not rank overall company service quality.
- Follow the [source plan](../../../data_analyst_portfolio_plan_v2.md) source table/F1 and [implementation plan](../../../implementation_plan.md) Gate A/F1.

## Frozen population and grain
- One row per unique text complaint ID; baseline Date received >= 2023-01-01 AND Date received < 2026-01-01.
- Retain **9,469,257 complaints**, all **14 raw product labels**, all companies and states, including unknown geography. All 36 received months occur in the supplied snapshot.
- Preserve all 15 raw fields and values; no arbitrary product exclusions, label merges, crosswalks, imputation, automatic deduplication or outcome-based deletion.
- Product and issue categories are dependent and changed on **2023-08-24**. Raw labels are not automatically comparable over time. Use date-based pre/post eras without label merges; retain August in descriptive totals but exclude the whole month from longitudinal change and persistence windows. These are timing proxies, instead of verified complaint-level form versions.
- Unknown issue/geography/response categories remain explicit display buckets, not excluded complaints. Raw blanks remain unchanged beneath derived display categories.
- Source checks: [manifest](data_manifest.md), [validation JSON](../outputs/source_validation.json), [monthly profile](../outputs/scoped_monthly_counts.csv), [raw products](../outputs/scoped_product_counts.csv).

## Provenance and interpretation
- User attested **“Official CFPB download”**; original download URL/date were not recorded. This updates earlier source-only uncertainty about origin, not byte agreement with a fresh export.
- Local snapshot identity and scope are validated; publication completeness, allegations and final outcomes are not independently certified. Historical status wording in source-only validation is superseded by the approved activation above.
- Official source: [CFPB database](https://www.consumerfinance.gov/data-research/consumer-complaints/). Public analytical reuse is supported by the official materials cited in [validation](validation.md#official-source-references-and-verification-limits); no specific named licence is asserted.
- No customer/account/transaction exposure denominators exist; complaint volumes are not incidence, market-adjusted risk, verified wrongdoing or causal effects.
- Routing lag is not resolution duration; recorded Yes/No is not a measured 15-day resolution outcome. Response category is not a timeliness proxy.
- Narratives are absent; no NLP or narrative-derived root causes. Recommendations will be investigation hypotheses, not established causes.

## MVP and delivery boundary
- Two planned Power BI pages: **Response Overview** (volume, timeliness, unknown flags, routing lag and monthly cohorts) and **Review Priorities** (supported segment review queue, counts, denominators, reasons and sensitivity).
- Segment Detail is optional only for a distinct investigation decision; no additional default page.
- Filters: received period, company, raw product and state; preserve unknown buckets and disclose taxonomy comparability limits.
- User-approved base minimum segment volume **100 per month**, sensitivity **50/200**, with three consecutive complete selected calendar months in one era. Require a known flag denominator and the same minimum volume/known eligibility for the company's other-issue comparator in the same raw product/geography, in all three months.
- Persistent review eligibility requires an untimely share at least **1 percentage point above peers in 2 of 3 months**. Missing months, ineligible peers and August/cross-era windows fail eligibility. Equal rank tuples share rank; labels provide stable display order. The full denominator, ranking and sensitivity rules are frozen in the [metric contract](metric_dictionary.md), instead of chosen after inspecting rankings.
- Future scope: six analytical SQL queries, at least five explicit measures, SQL/DAX reconciliation under two meaningful filters, compact import model, refresh/render/interaction checks and decision memo. None are claimed complete.

## Gate A feasibility route and acceptance
- Verified local project environment: **DuckDB 2.0.0**, [environment evidence](../outputs/environment_validation.json); SQL performs sample selection/import/metrics, Python orchestrates reproducibility, not a separate analytical deliverable. Full typed analytical preparation remains Gate B work.
- Implemented feasibility extraction: [sample builder](../scripts/build_feasibility_sample.py), three lexicographically lowest complaint IDs per received-month × raw-product × raw-timely-flag stratum (or all if fewer than three).
- This deterministic sample is deliberately nonrepresentative; sample metrics verify mechanics, not population findings or priorities.
- [Sample validation](../outputs/gate_a_sample_validation.json) passes for 2,304 records, all 36 months/14 raw products, exact CSV/Parquet field preservation and four independently checked metric scopes. [28 passing tests](../outputs/gate_a_tests.txt) cover selection, unknowns, empty cohorts, zero denominators, response-field independence and lag validity/medians.
- Planned curated typed Parquet for future Power BI Import via the [official Parquet connector](https://learn.microsoft.com/power-query/connectors/parquet); no actual Power BI load, model or refresh evidence yet.
- Gate A exit requires reproducible real-sample import supporting the initial metric contract, documented access/terms and environment, with failures explicit. [Gate A acceptance](../completion.md) records the passed checks and live-access limits; it does not authorize analytical findings or CV claims.

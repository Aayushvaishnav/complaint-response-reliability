# F1 semantic model

## Build status

**Status:** ten-table, 53-measure model accepted at Gate D on 2026-10-28; [final build evidence](../outputs/final_build_acceptance_20261028.json).

The model is in `reports/powerbi/F1.SemanticModel/`, with entry point `reports/powerbi/F1.pbip` and two report pages. Sixteen foundation measures, twenty-nine dynamic diagnostic measures and eight queue-display projections make 53 measures. [Current live acceptance](../outputs/native_queue_acceptance_results.json) records 49 successful operations and 2,194 field comparisons across overview, priority, native-shaped queue and edge cases. [Baseline render review](../outputs/render_repair_review.json) confirms populated pages and preserved exact denominators. Owner-reported interaction acceptance and confirmed clean-folder refresh now pass in the [final build record](../outputs/final_build_acceptance_20261028.json); each evidence type remains separately identified.

- [Projection validation](../outputs/import_projection_validation.json): full input hashes, sufficient-statistic reconstruction and exported schemas.
- [Model build inventory](../outputs/model_foundation_validation.json): actual modeling operations and object inventory.
- [Readback and input checks](../outputs/model_foundation_readback.json): reopened metadata, identity checks and artifact hashes.
- [Blueprint](../scripts/model_definition.py): source-column mappings, M partitions, relationships and foundation measures.
- [Rank arithmetic](model-rank-arithmetic.md): bounded exact comparator; Python oracles and 104 live DAX comparisons pass.
- [Dynamic measure generator](../scripts/priority_measures.py), [grouped population](../scripts/priority_population.py) and [focused/arithmetic engine checks](../outputs/live_edge_results.json).

## Tables and filter paths

| Table | Source rows | Grain and role |
|---|---:|---|
| Complaint Cohorts | 1,883,868 | Received day × company × raw product × raw issue × raw state × routing status × routing days; additive complaint/Yes/No/unknown frequencies |
| Date | 1,096 | Contiguous days from 2023-01-01 through 2025-12-31; month labels sort by Month Order |
| Company | 5,150 | Raw company identity with integer key and explicit missingness |
| Product | 14 | Raw product identity with integer key and explicit missingness |
| Issue | 94 | Raw issue identity with integer key and explicit missingness |
| Geography | 63 | Raw state identity with integer key and explicit missingness |
| Review Minimum | 3 | Disconnected analyst choices 50/100/200 |
| Sensitivity Minimum | 3 | Independent disconnected choices 50/100/200 |
| Review Window | 36 | Disconnected potential ending calendar months |
| Review Selection | 233,427 | Disconnected observed company/product/issue/month identities; no stored ranks or qualification |

Date, Company, Product, Issue and Geography each filter Complaint Cohorts through a single-direction one-to-many relationship. Utilities have no physical relationships. The selected utility tuple must be applied explicitly by subsequent priority measures. Window End is the first day of the ending calendar month, matching the canonical SQL.

The cohort frequencies conserve **9,469,257 complaints = 9,431,474 Yes + 37,783 No + 0 unknown**. Full, received-2023, Debt collection and California count/median checks agree with complaint-grain SQL. Those are projection checks, instead of evaluated DAX results.

## Identity and missingness

SQL NULL, empty strings and literal display labels retain separate integer identities. Labels are presentation fields. A source audit found four company display-label groups that collide after SQL `lower`; this is an identity warning, rather than a simulation of every VertiPaq collation rule.

Every conformed dimension label groups by its integer key. Review Selection's Company, Product and Issue labels also group by their corresponding tuple keys; MCP readback confirms this metadata. Subsequent DAX and report queries must include those grouping keys and use keys for tuple filtering. Do not reconstruct identity from labels or use a label-only `SELECTEDVALUE` where its grouping key is absent. Live-engine and slicer tests must verify these cases. VertiPaq can normalize displayed case; unchanged SQL/Parquet raw values remain authoritative.

## Foundation measures

Sixteen measures are defined, with formats and descriptions:

- Complaint Count, Timely Yes Count, Untimely No Count, Known Flag Count, Unknown Flag Count.
- Timely Response Rate, Untimely Share, Unknown Flag Rate.
- Valid Routing Count, Invalid Routing Count, Median Routing Days.
- Monthly Issue Share.
- Peer Complaint Count, Peer Known Count, Peer No Count, Peer Untimely Share.

Counts sum frequencies and return zero when empty. Undefined rates and medians return BLANK. The routing median uses valid-lag frequencies, cumulative positions and both middle observations. Peers remove only the Issue dimension and subtract the focal issue selection; company, product, received dates and geography stay in context. Dynamic priority measures add explicit tuple/window context; focused evidence applies one selected utility key while headline counts retain the population.

## Dynamic priorities and repair evidence

The initial row-iterated population timed out after 20 seconds in Desktop. The replacement computes monthly focal counts and same-company/product/month all-issue totals in grouped storage-engine scans. Peer totals use `IGNORE` so they cannot introduce nonexistent focal groups. Three shifted keyed monthly tables join on the same ending month, preserving consecutive months without substituting a previous observed row. Complete selected days, August exclusion and known denominators are checked before joining.

Monthly counts below 50 cannot qualify at any supported minimum. Pruning those months is therefore lossless for eligible/qualifying/rank populations under minima 50/100/200. Focused diagnostics retain rejected windows so sensitivity can explain a failed rule. Their integer selection key is pushed into the utility source before constructing monthly diagnostics.

The first grouped live probe returns the SQL-matching 1,873 eligible base windows in 1,448 ms; this is a single development probe, instead of a repeatable performance benchmark. The full summary checks conserve 112/36/5 qualifying windows and 30/13/3 qualifying segments across minima 50/100/200. California has zero qualifying windows at every minimum. [Engine edge checks](../outputs/live_edge_results.json) verify 104 Fraction-oracle comparisons, the focal monthly counts, independent sensitivity, partial/noncontiguous selected days, boundary months, absent focus and ambiguous minimum selection.

Live readback also exposed two generated syntax defects: an unterminated Review Context text literal and an unclosed Priority Rank expression. Both generators are repaired and have delimiter regressions. All twenty-nine priority measures subsequently read back as Ready. Earlier offline serialization and schema-only tests did not establish DAX validity.

### Native queue query

The original visual-level rank filter produced `__ValueFilterDM0`, evaluating every displayed diagnostic before qualification and then evaluating them again for display. The [captured query](../outputs/native_queue_query_52.dax) and [trace](../outputs/native_queue_trace.json) record this path; one native query ran for 301 seconds before a slicer change cancelled it. Changing a matrix into a flat table alone did not resolve this query shape.

The user approved removing that visual measure filter. [Queue projections](../scripts/queue_measures.py) read the sparse qualifying-window table directly and return BLANK for every non-qualifying selector, allowing native blank-row suppression. Diagnostic measures remain available for rejected-window audits and independent sensitivity. All eight projections preserve the original tuple keys and numerical rules. Complete-month day counts are computed once per calendar month before grouping complaints.

[Native-shaped queue acceptance](../outputs/native_queue_acceptance_results.json) verifies the same SQL row identities, ranks, numerators, denominators, gaps and passing minima across all twelve scope/minimum combinations. The full-scope queries take approximately 19–21 seconds in this recorded local run; this is a latency caveat, instead of a repeatable benchmark. The final screenshot shows actual flat queue rows with company/product/issue identities. Supporting fields require horizontal scrolling.

Date is marked with Time category and unique date metadata; automatic date-table generation is disabled in the model annotation. Technical keys and count columns are hidden. All source-column names/types are explicitly mapped in the M partitions.

## Reproduction

Run the projection first using [the projection instructions](../outputs/import_projection_notes.md). It verifies the accepted typed source before writing generated inputs. The existing audited DuckDB environment and modeling MCP 1.0.0 are reused; no dependencies were added.

From the workspace root in Bash/WSL:

```bash
projects/f1-complaint-response-reliability/.venv/bin/python \
  projects/f1-complaint-response-reliability/scripts/model_definition.py \
  --source-folder 'C:/Users/Aayush/my_files/da_projects/projects/f1-complaint-response-reliability/data/processed/model-input' \
  --output projects/f1-complaint-response-reliability/outputs/model_definition.json
```

Use native Windows Node for the MCP build. From PowerShell, supply the `index.js` of the existing Windows modeling MCP installation:

```powershell
node projects/f1-complaint-response-reliability/scripts/build_model.cjs `
  --server-entry '<installed Windows @microsoft/powerbi-modeling-mcp/index.js>'
```

The supplied installation must include its matching `@microsoft/powerbi-modeling-mcp-win32-x64` package. The project-local wrapper lacks that Windows package; invoking it initially failed before model creation. The successful run used the already installed Windows npm-cache copy. The runner now requires an explicit server entry instead of assuming the project-local wrapper is usable. The [initial failure record](../outputs/model_foundation_initial_failure.json) is retained separately.

The builder creates a new offline database, calls modeling MCP for all authoring, checks operation failures, exports TMDL and records the inventory. It deliberately refuses to overwrite an existing export folder. For regeneration, preserve the existing definitions and use the exported `build()` function with a fresh `exportPath` and `evidencePath`, or extend the existing model through MCP. Do not delete or replace manual model edits to rerun the foundation builder.

The single Power Query **Source Folder** parameter owns the local input location. Changing it changes all ten partition paths. The [2026-10-28 cache-free copy](../outputs/final_build_acceptance_20261028.json) verifies the relocated parameter and all ten live partition expressions before a successful Full refresh and imported-count reconciliation. The original model and inputs are preserved.

## Refresh acceptance and operating limits

1. [Fresh clean-copy reconciliation](../outputs/clean_refresh_reconciliation_20261028.json) passes 2,194 field comparisons across 45 operations, including all twelve queue scope/minimum combinations. Keep the checks repeatable if the model changes.
2. The successful Full refresh from ten NoData partitions supersedes the earlier refresh attempt's unknown outcome. It certifies this local copy and frozen inputs, instead of scheduled or cloud refresh.
3. [Owner acceptance](../reports/owner_review.md) distinguishes user-reported clicks and keyboard checks from agent-observed renders and DAX checks. Supporting queue fields require horizontal scrolling at Fit to page.
4. Full-population native-shaped queue queries retain a roughly 19–21-second historical latency caveat; no production performance guarantee is made.

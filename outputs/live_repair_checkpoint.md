# F1 live repair checkpoint, 2026-10-23

## Latest accepted repair scope

The subsequent native-visual repair extends the model to **53 Ready measures**. [Current acceptance](native_queue_acceptance_results.json) passes **49 operations and 2,194 field comparisons**. The owner confirms that the final queue rows are visible; [fresh baseline render review](render_repair_review.json) independently confirms the flat queue, 1,873/36/13/5 base-rule cards, exact denominators, context text and all minimum choices. [Overview](../reports/previews/f1-response-overview-2026-10-23.png) and [priorities](../reports/previews/f1-review-priorities-2026-10-23.png) previews are retained; the temporary capture child is removed.

The native visual's `__ValueFilterDM0` evaluated every diagnostic before filtering and again for display. One traced query ran for 301 seconds before a slicer change cancelled it. With owner approval, eight sparse queue-only projections replace that visual filter without changing qualifying output. Rejected-window diagnostic measures remain separate. Native-shaped full-scope queue queries take roughly **19–21 seconds** in this recorded development run; this is a remaining latency caveat, instead of a general benchmark.

Latest suites: [110 normal Python](queue_query_tests.txt), [110 optimized Python](queue_query_tests_optimized.txt), [21 WSL Node](queue_query_node_tests.txt) and [21 Windows Node](queue_query_node_windows_tests.txt). Windows Node uses WSL Python for its source-contract check. No dependency or cloud service was added. Two Desktop-saved states were preserved in owner-approved backups before restoring authored PBIR.

Actual row-focus/sensitivity, slicer-clear/navigation and filtered/empty rendered acceptance, confirmed clean-folder refresh, presentation polish and packaging remain pending. **Gate D remains unsigned; final CV measurement is prohibited.** The earlier 45-measure phase below is retained as the diagnosis/progression record.

## Diagnosis and changes

- The original population measure iterated 233,427 selector rows and repeatedly transitioned context for monthly facts. A full-scope Eligible Window Count query timed out at 20 seconds. Grouped monthly frequency scans and keyed three-month shift joins replace that population iterator without changing the approved rule or physical model.
- Focused diagnostics initially scanned the full utility before selecting its key. The key now filters the utility at its source. The complete 112-row minimum-50 queue subsequently reconciles in a rank-first query in about 11 seconds in that development run; timings are diagnostics, instead of a benchmark or final CV claim.
- Review Context had an unterminated string and Priority Rank had an unclosed expression. Live readback exposed both defects. Generator regressions now cover string termination and balanced delimiters; all 45 model measures read back as Ready.
- Label-only DAX test filters failed because labels belong to composite grouping keys. Reconciliation queries now filter the complete small dimension table, preserving its identity key.
- Report fixes use concise labels, full KPI units, hidden automatic subtitles, more product-label space, a taller minimum control and flat text tables for sensitivity/context. These are authored fixes pending fresh rendered review.

## Earlier 45-measure live data checks

| Evidence | Scope |
|---|---|
| [Overview and priority summaries](live_acceptance_results.json) | Six overview contexts, including partial dates and empty scope; four priority populations at all three minima; 114 scalar comparisons |
| [Complete queue parity](live_queue_results.json) | All 12 scope/minimum cases; 203 qualifying result rows across repeated scopes and minima, 2,030 compared identity/count/rank/rate/passing-minimum fields; empty queues checked |
| [Focused and arithmetic cases](live_edge_results.json) | 104 Fraction-oracle comparisons, MOHELA counts/monthly history, independent sensitivity, focus-preserved headline counts, partial/noncontiguous dates, August boundaries, ambiguous minima and no-focus behavior |
| [Model readback/export](live_post_refresh_results.json) | Ten Ready Import partitions, 45 Ready measures, unchanged baseline complaint/No totals, and exported live definitions |
| [Python tests](live_repair_tests.txt) | 108 passed; source/SQL, projection, sparse-join oracle, generation and numerical regressions |
| [Node tests](live_repair_node_tests.txt) | 19 passed; report structure, source-only bindings, MCP result handling and reconciliation failures |

The global base queue contains 36 qualifying windows across 13 segments; five qualify at every minimum. The focal MOHELA window retains 590/972 No/known versus 253/452 for peers, rank 1, three elevated months and passing minima 50/100. These are frozen-population analytical results, instead of overall service-quality rankings or intervention benefits.

## Validation limits and next step

The Full refresh tool invocation timed out with its remote outcome unspecified. A later connection finds all ten partitions Ready and baseline totals unchanged, but this does not independently certify that requested refresh. Do not treat it as a passed refresh checkpoint. Clean-folder refresh remains pending.

The latest report passes schema validation, owner-confirmed loading and fresh baseline screenshot review. Actual slicer, navigation and queue-focus interaction checks remain separate from DAX filtering tests. Packaging and Gate D sign-off remain pending; final CV measurement is prohibited. R2 and H1 remain Complete with their released artifacts unchanged. No cloud publication or dependency installation occurred.

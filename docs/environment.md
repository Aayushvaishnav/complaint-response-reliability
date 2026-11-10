# F1 environment and reproduction

## Verified local environment

- Python 3.14.7; shell execution uses Linux/WSL despite the Windows workspace path.
- Project-local environment: `.venv/`; DuckDB **2.0.0** and pip **26.0.1**. `pip check` passes. R2's environment and data are unchanged.
- [requirements.txt](../requirements.txt) records the installed DuckDB version. SQL handles source selection, import, profiling and sample calculations. Python is a file/checksum/test/verification runner and independent reference calculation, instead of a separate portfolio analysis tool.
- Dependency provenance reviewed before installation: [PyPI release metadata](https://pypi.org/pypi/duckdb/2.0.0/json) identifies the DuckDB Foundation, MIT licence, the official [source repository](https://github.com/duckdb/duckdb-python) and [Python documentation](https://duckdb.org/docs/stable/clients/python/overview). This is an established database engine; no optional extras or numerical/ML packages were installed.
- Publisher-reference retrieval uses the Python standard library. Where publisher PDFs are accessible, the verification utility uses the existing `pdftotext` executable to check publication text. No PDF parser dependency was installed.
- `.venv/`, native `.venv-windows/`, caches, raw snapshots, sample records, databases, Parquet and SQL spill files remain Git-ignored. Compact aggregate evidence stays in `outputs/`.

## Setup and tests

From the workspace root in Bash/WSL:

```bash
python -m venv projects/f1-complaint-response-reliability/.venv
projects/f1-complaint-response-reliability/.venv/bin/python -m pip install --index-url https://pypi.org/simple -r projects/f1-complaint-response-reliability/requirements.txt
projects/f1-complaint-response-reliability/.venv/bin/python -m pip check
projects/f1-complaint-response-reliability/.venv/bin/python -m unittest discover -s projects/f1-complaint-response-reliability/tests -v
```

These commands have been executed in this shell. A WSL environment cannot serve as a native Windows Python environment. If later needed, create a separate `.venv-windows/`, install the same requirements with that interpreter and run the same entry-point files. Native Windows Python execution and native PDF-text tooling are not verified here.

## Source and sample entry points

```bash
projects/f1-complaint-response-reliability/.venv/bin/python projects/f1-complaint-response-reliability/scripts/verify_source_access.py
projects/f1-complaint-response-reliability/.venv/bin/python projects/f1-complaint-response-reliability/scripts/build_feasibility_sample.py
```

The publisher-reference check is separate from the sample builder. It records retrieval outcomes and verification limits in `outputs/source_access_verification.json`; publisher references are saved under ignored `data/raw/verification/`. For the blocked public-reuse and effective-date PDFs, it checks the explicitly reviewed official-domain search excerpts in [publisher evidence](../config/publisher_evidence.json) and records that evidence method separately. These are analyst-reviewed citations, not downloaded/read PDFs or newly fetched policy text. A required source-evidence failure is explicit rather than treated as live verification success.

The sample builder opens `data/processed/source_validation.duckdb` read-only, checks the prior validated source identity plus staging counts, and selects up to three lowest text complaint IDs per received-month × raw-product × raw-timely-flag stratum. It exports a real-source CSV, imports it into a separate sample database, verifies every selected field value, and tests a Parquet round-trip. Independent Python calculations check counts, known/unknown flags, rates and valid routing medians under all/2023/debt-collection/California filters. This sample is intentionally nonrepresentative; its outcome proportions cannot estimate the full population. The sample builder does not independently rehash or certify all staging-table contents; the prior full validation establishes that upstream preparation, while the separate source-access utility rehashes the raw snapshot.

Outputs: `data/processed/gate_a_sample.csv`, `gate_a_sample.duckdb`, `gate_a_sample.parquet` and [sample evidence](../outputs/gate_a_sample_validation.json). Sample Parquet fields preserve the source strings; this is a format-feasibility check, instead of the future typed analytical export.

If the validated staging database is absent, rebuild source staging first:

```bash
projects/f1-complaint-response-reliability/.venv/bin/python projects/f1-complaint-response-reliability/scripts/validate_source.py
```

That command revalidates the full supplied file and regenerates the 2023–2025 CSV; it is larger work than rebuilding the small sample. Its earlier full pass is recorded in [source validation](../outputs/source_validation.json) and the [manifest](data_manifest.md).

## Gate B preparation and contract checks

From the workspace root in Bash/WSL:

```bash
projects/f1-complaint-response-reliability/.venv/bin/python projects/f1-complaint-response-reliability/scripts/prepare_complaints.py
projects/f1-complaint-response-reliability/.venv/bin/python projects/f1-complaint-response-reliability/scripts/validate_gate_b.py
```

Preparation hashes and independently streams the complete scoped CSV, reads existing source staging without writing it, builds a separate complaint-grain typed database, and exports/reconciles typed Parquet. The database and Parquet stay ignored. `outputs/typed_preparation_validation.json` records the generated evidence; a failed run records its error instead of retaining a success state. This run does not repeat official-source retrieval or rehash the full raw snapshot.

The acceptance command checks current preparation artifact hashes and runs all project tests with normal and optimized Python, including the separate exact-arithmetic synthetic oracle. It records results in `outputs/gate_b_acceptance.json` and test logs. Gate acceptance and test execution remain distinct from Power BI rendering/refresh or Gate D sign-off.

The isolated review evaluator takes a canonical `contract_input` SQL relation, with the [field interface](data_dictionary.md#typed-preparation-interface) and [frozen metric rules](metric_dictionary.md). Filter arguments use explicit `Selection.ALL` or a list of raw labels; an empty list selects no rows, while `[None]` selects a SQL NULL category. Company/product/state/date selections apply before aggregation; issue selection affects displayed rows only. Complete-month and taxonomy checks are calculated in SQL. Contract verification is synthetic mechanics; population ranking and the three volume-sensitivity findings belong to Gate C.

No additional packages are required beyond the existing audited DuckDB dependency. The independent reference uses Python's standard-library CSV reader, dates, counters and exact fractions.

## Gate C population analysis

```bash
projects/f1-complaint-response-reliability/.venv/bin/python projects/f1-complaint-response-reliability/scripts/population_analysis.py
projects/f1-complaint-response-reliability/.venv/bin/python projects/f1-complaint-response-reliability/scripts/verify_product_findings.py
projects/f1-complaint-response-reliability/.venv/bin/python projects/f1-complaint-response-reliability/scripts/validate_gate_c.py
```

The population runner uses the hash-verified typed Parquet, unchanged canonical review SQL and existing DuckDB dependency. It evaluates the complete population at minima 50/100/200 and recalculates received-2023, debt-collection and California contexts at minimum 100. The independent aggregate reference streams all dense monthly diagnostics without expanding source complaints in Python. See [analysis methods](analysis_method.md) for output grains, numerical checks, runtime limits and reproduction prerequisites.

Acceptance rechecks the analysis inventories and runs the behavior suite normally and under optimized Python into separate Gate C logs. It preserves historical Gate B logs and does not grant Power BI or Gate D sign-off.

## Planned Power BI import route

Use local **Import** from compact typed Parquet fact/dimension exports after Gate B preparation. SQL remains the authoritative transformation/calculation layer; raw 5.25 GiB CSV text and unused high-cardinality fields will stay outside the default report import. Reconcile any projected exports before use; retain all original fields in raw staging.

Microsoft's [Parquet connector documentation](https://learn.microsoft.com/power-query/connectors/parquet), reviewed on 2026-10-23, supports Power BI Import from local files and documents local filesystem/Azure-source limits. CSV Import is a documented alternative, rather than requiring a second SQL server or unofficial ODBC driver.

This is the intended route, not a Desktop load or refresh test. No semantic model, DAX, report, publication or paid service was created or used in Gate A. Power BI integration, rendered review and clean-folder refresh remain later acceptance work.

## Gate D Import/model foundation environment

Verified on 2026-10-23:

- Existing Python 3.14.7 / DuckDB 2.0.0 environment exports the ten compact Parquet inputs without new dependencies. [Projection instructions](../outputs/import_projection_notes.md) contain the exact commands.
- Native Windows Node **v24.19.0** runs the existing Microsoft modeling MCP **1.0.0** and serializes the offline model. The project-local report CLI **0.5.0** responds; no report validation or preview was attempted in this checkpoint.
- Standard x64 Desktop executable presence is verified at `C:/Program Files/Microsoft Power BI Desktop/bin/PBIDesktop.exe`. Modeling MCP finds no running local model. Executable presence alone does not certify F1 import/preview availability.
- The project-local modeling wrapper lacks the Windows platform package. Its initial invocation failed before model creation; the successful build uses the existing Windows npm-cache installation, including `@microsoft/powerbi-modeling-mcp-win32-x64`. No package installation or manifest change was made.
- [Model structure/reproduction](model.md) documents the explicit `--server-entry`, source-folder parameter and non-overwriting export behavior. All authoring uses modeling MCP, rather than handwritten TMDL. A separate MCP connection reopens the export.
- Final checkpoint suites: 89 Python tests normally and optimized; six builder tests in both native Windows Node and WSL Node. These cover projection and offline-definition behavior. DAX-engine evaluation, refresh, report rendering and actual UI interactions remain unperformed.

The model is a local, unprocessed foundation with sixteen measures, not a completed PBIP/report. No cloud authentication, deployment or paid service was used. Gates D–E remain unsigned.

## Gate D live repair environment

The subsequent repair checkpoint uses the same Python **3.14.7** / DuckDB **2.0.0**, WSL Node **24.18.0**, Windows Node **24.19.0**, modeling MCP **1.0.0** and report CLI **0.5.0**. No dependency or service was added. Modeling MCP authored and exported the 53-measure model; the intended local F1 Desktop instance was identified by its window title and discovered port.

[110 Python checks](../outputs/queue_query_tests.txt) and the [optimized run](../outputs/queue_query_tests_optimized.txt) pass. [21 Node checks](../outputs/queue_query_node_tests.txt) also pass under [Windows Node](../outputs/queue_query_node_windows_tests.txt). The Windows Python application alias is unavailable; the source-contract test uses the existing `wsl.exe` with `python3`, configured through `F1_PYTHON` and JSON-array `F1_PYTHON_ARGS`. This is Windows Node plus WSL Python verification, instead of a claim that a native Windows Python environment was installed.

The final report passes schema validation and baseline screenshot review. Pending Desktop edits were preserved with owner-approved backups before restoring authored PBIR. The generator retains its manual-edit guard; the explicit restoration helper requires approval and a fresh backup directory. Power BI `.pbi/` caches/local settings are ignored. The [render review](../outputs/render_repair_review.json) records retained previews and cleanup of the workflow-owned temporary capture child.

Confirmed clean-folder refresh, full UI interactions and packaging remain pending. A Full refresh call timed out with an unspecified remote outcome; Ready partition readback alone is insufficient to certify that refresh. Gates D–E remain unsigned, with no cloud publication or final CV measurement.

## Final local refresh and verification, 2026-10-28

The existing WSL Python/DuckDB environment and native Windows Node/report CLI were reused with no dependency installation. The CLI launched a separate cache-free PBIP copy through the standard Desktop installation. Modeling MCP changed only that copy's Source Folder parameter, read back all ten partition expressions and successfully completed Full refresh. [Final acceptance](../outputs/final_build_acceptance_20261028.json) records table counts, SQL/DAX parity, owner-reported checks and reviewed screenshots. No cloud authentication or publication was used.

To stage another isolated refresh copy from the workspace root:

```bash
projects/f1-complaint-response-reliability/.venv/bin/python \
  projects/f1-complaint-response-reliability/scripts/stage_refresh_copy.py \
  --destination projects/f1-complaint-response-reliability/data/processed/refresh-new \
  --output projects/f1-complaint-response-reliability/outputs/refresh-new-staging.json
```

Choose new destination/evidence paths. Update Source Folder in the copy to its `model-input` directory through Power Query parameters or modeling MCP, then follow the [owner refresh checklist](../reports/owner_review.md#5-clean-folder-refresh-separate-checkpoint). Staging alone does not refresh the model.

The final regression suites pass 117 Python tests normally and optimized, plus 22 WSL Node checks. The owner accepted keyboard and scrolling readability at Fit to page. The later Gate E measurement tools are separate from the frozen analytical/report build.

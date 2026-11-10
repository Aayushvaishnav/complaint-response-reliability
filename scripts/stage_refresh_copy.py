"""Stage a cache-free F1 refresh copy without altering the working project."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil

PROJECT = Path(__file__).resolve().parents[1]
INPUT_NAMES = {
    "company", "complaint_cohorts", "date", "geography", "issue", "product",
    "review_minimum", "review_selection", "review_window", "sensitivity_minimum",
}


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def inventory(folder):
    files = {}
    for path in sorted(folder.rglob("*")):
        if ".pbi" in path.relative_to(folder).parts:
            continue
        if path.is_symlink():
            raise ValueError(f"Symbolic link is outside the copy contract: {path}")
        if path.is_file():
            files[path.relative_to(folder).as_posix()] = sha256(path)
    return files


def stage(project, destination):
    project = Path(project).resolve()
    destination = Path(destination).resolve()
    report_root = project / "reports/powerbi"
    input_root = project / "data/processed/model-input"
    if destination.exists():
        raise FileExistsError(f"Use a new destination: {destination}")
    if destination.is_relative_to(report_root) or report_root.is_relative_to(destination):
        raise ValueError("Destination must be separate from the working report")
    if destination.is_relative_to(input_root) or input_root.is_relative_to(destination):
        raise ValueError("Destination must be separate from the working inputs")
    validation = json.loads((project / "outputs/import_projection_validation.json").read_text())
    if validation.get("status") != "passed" or set(validation["exports"]) != INPUT_NAMES:
        raise ValueError("A passed ten-input projection is required")
    inputs = {}
    for name in sorted(INPUT_NAMES):
        record = validation["exports"][name]
        expected_path = f"data/processed/model-input/{name}.parquet"
        if record["path"] != expected_path:
            raise ValueError(f"Unexpected projection path: {name}")
        path = project / expected_path
        if path.is_symlink() or sha256(path) != record["sha256"]:
            raise ValueError(f"Input differs from accepted projection: {name}")
        inputs[path.name] = record["sha256"]
    required = ["F1.pbip", "F1.Report/definition.pbir", "F1.SemanticModel/definition.pbism",
                "F1.SemanticModel/definition/model.tmdl"]
    for name in required:
        if not (report_root / name).is_file():
            raise ValueError(f"Missing project artifact: {name}")
    before = inventory(report_root)
    destination.mkdir(parents=True)
    shutil.copy2(report_root / "F1.pbip", destination / "F1.pbip")
    for name in ("F1.Report", "F1.SemanticModel"):
        shutil.copytree(report_root / name, destination / name, ignore=shutil.ignore_patterns(".pbi"))
    copied_inputs = destination / "model-input"
    copied_inputs.mkdir()
    for name in inputs:
        shutil.copy2(input_root / name, copied_inputs / name)
    copied = inventory(destination)
    for name, digest in before.items():
        if name == "F1.pbip" or name.startswith(("F1.Report/", "F1.SemanticModel/")):
            if copied.get(name) != digest:
                raise ValueError(f"Copied definition differs: {name}")
    if {path.name: sha256(path) for path in copied_inputs.iterdir()} != inputs:
        raise ValueError("Copied inputs differ")
    if inventory(report_root) != before:
        raise ValueError("Working definitions changed during staging")
    if {name: sha256(input_root / name) for name in inputs} != inputs:
        raise ValueError("Working inputs changed during staging")
    return {
        "status": "staged",
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "copy_directory": str(destination),
        "definition_sha256_before": before,
        "input_sha256": inputs,
        "copied_file_sha256": copied,
        "original_definitions_and_inputs_unchanged": True,
        "cache_directories_copied": False,
        "source_folder_parameter": "requires_update_in_copy",
        "refresh_status": "not_performed",
        "gate_d_signoff": "not_granted",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Use a new evidence path")
    result = stage(PROJECT, args.destination)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"Staged {result['copy_directory']}; parameter update and refresh remain required")

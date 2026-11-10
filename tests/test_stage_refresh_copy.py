import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from stage_refresh_copy import INPUT_NAMES, sha256, stage


class RefreshCopyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.project = self.root / "project"
        self.report = self.project / "reports/powerbi"
        for name in ("F1.pbip", "F1.Report/definition.pbir",
                     "F1.Report/definition/pages/page.json", "F1.Report/.pbi/localSettings.json",
                     "F1.SemanticModel/definition.pbism", "F1.SemanticModel/definition/model.tmdl",
                     "F1.SemanticModel/.pbi/cache.abf"):
            path = self.report / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(name)
        self.exports = {}
        for name in INPUT_NAMES:
            relative = f"data/processed/model-input/{name}.parquet"
            path = self.project / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(name.encode())
            self.exports[name] = {"path": relative, "sha256": sha256(path)}
        self.validation = self.project / "outputs/import_projection_validation.json"
        self.validation.parent.mkdir()
        self.write_validation()
        self.destination = self.root / "copy"

    def write_validation(self, status="passed"):
        self.validation.write_text(json.dumps({"status": status, "exports": self.exports}))

    def test_copy_conserves_inputs_and_definitions_without_caches(self):
        result = stage(self.project, self.destination)
        self.assertEqual(result["status"], "staged")
        self.assertEqual(result["refresh_status"], "not_performed")
        self.assertEqual(result["source_folder_parameter"], "requires_update_in_copy")
        self.assertTrue(result["original_definitions_and_inputs_unchanged"])
        self.assertEqual(len(list((self.destination / "model-input").glob("*.parquet"))), 10)
        self.assertEqual(list(self.destination.rglob(".pbi")), [])
        self.assertTrue((self.report / "F1.SemanticModel/.pbi/cache.abf").is_file())
        self.assertEqual((self.destination / "F1.pbip").read_text(), "F1.pbip")

    def test_existing_copy_is_preserved(self):
        self.destination.mkdir()
        sentinel = self.destination / "manual.txt"
        sentinel.write_text("preserve")
        with self.assertRaises(FileExistsError):
            stage(self.project, self.destination)
        self.assertEqual(sentinel.read_text(), "preserve")

    def test_changed_input_prevents_staging(self):
        (self.project / self.exports["date"]["path"]).write_text("changed")
        with self.assertRaisesRegex(ValueError, "Input differs"):
            stage(self.project, self.destination)
        self.assertFalse(self.destination.exists())

    def test_unaccepted_or_incomplete_inventory_prevents_staging(self):
        self.write_validation("failed")
        with self.assertRaisesRegex(ValueError, "passed ten-input"):
            stage(self.project, self.destination)
        del self.exports["date"]
        self.write_validation()
        with self.assertRaisesRegex(ValueError, "passed ten-input"):
            stage(self.project, self.destination)

    def test_projection_path_cannot_escape_project(self):
        self.exports["date"]["path"] = "../outside.parquet"
        self.write_validation()
        with self.assertRaisesRegex(ValueError, "Unexpected projection path"):
            stage(self.project, self.destination)

    def test_nested_destinations_and_missing_artifacts_are_rejected(self):
        for destination in (self.report / "copy", self.project / "data/processed/model-input/copy"):
            with self.subTest(destination=destination), self.assertRaises(ValueError):
                stage(self.project, destination)
        (self.report / "F1.pbip").unlink()
        with self.assertRaisesRegex(ValueError, "Missing project artifact"):
            stage(self.project, self.destination)


if __name__ == "__main__":
    unittest.main()

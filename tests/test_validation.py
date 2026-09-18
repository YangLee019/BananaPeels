"""Checks that protect submission counts and the permitted training split."""

from __future__ import annotations

import copy
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from banana_peels.cli import main
from banana_peels.validation import (
    TEMPLATE_PATH,
    ValidationError,
    load_json,
    make_train_list,
    official_tasks,
    validate_results,
)


class ResultsValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.template = load_json(TEMPLATE_PATH)
        self.formal = copy.deepcopy(self.template)
        self.formal["team_id"] = "banana-peels-team"
        for setting in self.formal["results"].values():
            for result in setting.values():
                result.update(attempts=100, successes=43)

    def test_valid_formal_and_template_have_distinct_modes(self) -> None:
        self.assertEqual(validate_results(self.formal), [])
        self.assertEqual(validate_results(self.template, template=True), [])
        self.assertTrue(validate_results(self.template))
        self.assertTrue(validate_results(self.formal, template=True))

    def test_wrong_task_set_and_missing_setting_are_rejected(self) -> None:
        task = official_tasks()[0]
        for template_mode in (False, True):
            with self.subTest(template=template_mode):
                data = copy.deepcopy(self.template if template_mode else self.formal)
                data["results"]["clean"]["made_up_task"] = data["results"]["clean"].pop(task)
                errors = validate_results(data, template=template_mode)
                self.assertTrue(any("missing keys" in error for error in errors))
                self.assertTrue(any("unexpected keys" in error for error in errors))
        del self.formal["results"]["randomized"]
        self.assertTrue(validate_results(self.formal))

    def test_boolean_and_out_of_range_counts_are_rejected(self) -> None:
        task = official_tasks()[0]
        for field, value in (
            ("attempts", True),
            ("successes", False),
            ("successes", -1),
            ("successes", 101),
            ("successes", 1.0),
            ("attempts", 99),
        ):
            with self.subTest(field=field, value=value):
                data = copy.deepcopy(self.formal)
                data["results"]["clean"][task][field] = value
                self.assertTrue(validate_results(data))
        self.formal["schema_version"] = True
        self.assertTrue(validate_results(self.formal))

    def test_placeholders_and_empty_team_are_rejected(self) -> None:
        for team_id in ("replace_with_your_team_id", " ", None, "TODO"):
            with self.subTest(team=team_id):
                self.formal["team_id"] = team_id
                self.assertTrue(validate_results(self.formal))

    def test_duplicate_json_keys_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="banana_test_") as directory:
            path = Path(directory) / "duplicate.json"
            path.write_text('{"schema_version": 1, "schema_version": 1}', encoding="utf-8")
            with self.assertRaises(ValidationError):
                load_json(path)

    def test_template_cli_requires_explicit_flag(self) -> None:
        with redirect_stderr(io.StringIO()), redirect_stdout(io.StringIO()):
            self.assertEqual(main(["validate-results", str(TEMPLATE_PATH)]), 1)
            self.assertEqual(main(["validate-results", str(TEMPLATE_PATH), "--template"]), 0)


class TrainListTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="banana_test_")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "data"
        self.output = Path(self.temporary.name) / "train.txt"

    def make_metadata(self, task: str, episodes: object = 50) -> Path:
        metadata = self.root / f"{task}-aloha-agilex_clean_50-50" / "meta" / "info.json"
        metadata.parent.mkdir(parents=True, exist_ok=True)
        metadata.write_text(json.dumps({"total_episodes": episodes}), encoding="utf-8")
        return metadata

    def test_missing_data_does_not_create_or_replace_output(self) -> None:
        with self.assertRaises(ValidationError):
            make_train_list(self.root, self.output)
        self.assertFalse(self.output.exists())
        self.output.write_text("existing list\n", encoding="utf-8")
        with self.assertRaises(ValidationError):
            make_train_list(self.root, self.output)
        self.assertEqual(self.output.read_text(encoding="utf-8"), "existing list\n")

    def test_planning_list_is_clean_aloha_only_and_warns(self) -> None:
        stderr = io.StringIO()
        with redirect_stderr(stderr), redirect_stdout(io.StringIO()):
            result = main(
                [
                    "make-train-list",
                    "--data-root",
                    str(self.root),
                    "--output",
                    str(self.output),
                    "--allow-missing",
                ]
            )
        self.assertEqual(result, 0)
        self.assertIn("unverified", stderr.getvalue())
        lines = self.output.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 50)
        self.assertEqual(len(set(lines)), 50)
        for task, line in zip(official_tasks(), lines, strict=True):
            self.assertEqual(len(line.split()), 2)
            self.assertEqual(line.split()[0], "robotwin")
            self.assertTrue(line.endswith(f"/{task}-aloha-agilex_clean_50-50"))
            self.assertNotIn("randomized", line)
            self.assertNotIn("piper", line)

    def test_all_fifty_metadata_files_must_report_fifty_episodes(self) -> None:
        for task in official_tasks():
            self.make_metadata(task)
        lines, unverified = make_train_list(self.root, self.output)
        self.assertEqual(len(lines), 50)
        self.assertEqual(unverified, [])

    def test_allow_missing_never_accepts_bad_existing_metadata(self) -> None:
        for episodes in (49, 51, True, "50", None):
            with self.subTest(episodes=episodes):
                self.make_metadata(official_tasks()[0], episodes)
                with self.assertRaises(ValidationError):
                    make_train_list(self.root, self.output, allow_missing=True)
                self.assertFalse(self.output.exists())
        info = self.make_metadata(official_tasks()[0])
        info.write_text("not JSON", encoding="utf-8")
        with self.assertRaises(ValidationError):
            make_train_list(self.root, self.output, allow_missing=True)

    def test_allow_missing_rejects_a_file_in_place_of_a_dataset(self) -> None:
        self.root.mkdir()
        dataset = self.root / f"{official_tasks()[0]}-aloha-agilex_clean_50-50"
        dataset.write_text("not a directory", encoding="utf-8")
        with self.assertRaises(ValidationError):
            make_train_list(self.root, self.output, allow_missing=True)
        self.assertFalse(self.output.exists())

    def test_paths_with_whitespace_are_not_written(self) -> None:
        for suffix in ("with space", "with\nnewline", "with\ttab"):
            with self.subTest(suffix=suffix):
                with self.assertRaises(ValidationError):
                    make_train_list(str(self.root / suffix), self.output, allow_missing=True)
                self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()

"""Competition checks that do not need a GPU or third-party packages."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

TEMPLATE_PATH = Path(__file__).resolve().parents[2] / "templates" / "results.template.json"
SETTINGS = ("clean", "randomized")
TEAM_PLACEHOLDER = "replace_with_your_team_id"


class ValidationError(ValueError):
    """An input cannot be used for this competition."""


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValidationError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValidationError(f"Invalid JSON numeric constant: {value}")


def load_json(path: str | Path) -> Any:
    """Read UTF-8 JSON, accepting a BOM but rejecting duplicate keys and NaN."""
    with Path(path).open(encoding="utf-8-sig") as stream:
        return json.load(stream, object_pairs_hook=_unique_object, parse_constant=_reject_constant)


def official_tasks() -> tuple[str, ...]:
    """Use the checked-in official template as the single task-name source."""
    document = load_json(TEMPLATE_PATH)
    try:
        clean = document["results"]["clean"]
        randomized = document["results"]["randomized"]
    except (TypeError, KeyError) as exc:
        raise ValidationError("The bundled official results template is malformed.") from exc
    if (
        not isinstance(clean, dict)
        or not isinstance(randomized, dict)
        or len(clean) != 50
        or set(clean) != set(randomized)
        or any(not task or not all(c.isalnum() or c == "_" for c in task) for task in clean)
    ):
        raise ValidationError(
            "The bundled template must contain the same 50 official tasks in both settings."
        )
    return tuple(clean)


def _key_errors(value: dict[str, Any], expected: set[str], label: str) -> list[str]:
    errors = []
    missing = expected - value.keys()
    extra = value.keys() - expected
    if missing:
        errors.append(f"{label}: missing keys: {', '.join(sorted(missing))}")
    if extra:
        errors.append(f"{label}: unexpected keys: {', '.join(sorted(extra))}")
    return errors


def validate_results(document: Any, *, template: bool = False) -> list[str]:
    """Return structural/count errors; this cannot prove a reported run occurred.

    Template mode validates an unfilled, zero-attempt template. It must never be
    used to decide whether a result file is ready for formal submission.
    """
    tasks = set(official_tasks())
    if not isinstance(document, dict):
        return ["results file must be a JSON object"]
    errors = _key_errors(document, {"schema_version", "team_id", "results"}, "root")
    version = document.get("schema_version")
    if type(version) is not int or version != 1:
        errors.append("schema_version must be the integer 1 (not a boolean)")
    team_id = document.get("team_id")
    if not isinstance(team_id, str) or not team_id.strip():
        errors.append("team_id must be a non-empty string")
    elif not template and team_id.strip().casefold() in {
        TEAM_PLACEHOLDER,
        "your_team_id",
        "team_id",
        "todo",
        "tbd",
        "placeholder",
        "团队名称",
        "团队id",
        "待填写",
        "请填写",
    }:
        errors.append(
            "team_id must identify your team; placeholder values are not valid for submission"
        )
    results = document.get("results")
    if not isinstance(results, dict):
        errors.append("results must be an object containing clean and randomized")
        return errors
    errors.extend(_key_errors(results, set(SETTINGS), "results"))
    expected_attempts = 0 if template else 100
    for setting in SETTINGS:
        entries = results.get(setting)
        if not isinstance(entries, dict):
            errors.append(f"results.{setting} must be an object of 50 official tasks")
            continue
        errors.extend(_key_errors(entries, tasks, f"results.{setting}"))
        for task in sorted(tasks & entries.keys()):
            label = f"results.{setting}.{task}"
            entry = entries[task]
            if not isinstance(entry, dict):
                errors.append(f"{label} must be an object")
                continue
            errors.extend(_key_errors(entry, {"attempts", "successes"}, label))
            attempts = entry.get("attempts")
            successes = entry.get("successes")
            if type(attempts) is not int or attempts != expected_attempts:
                errors.append(
                    f"{label}.attempts must be the integer {expected_attempts} (not a boolean)"
                )
            if type(successes) is not int:
                errors.append(f"{label}.successes must be an integer (not a boolean)")
            elif successes < 0 or (type(attempts) is int and successes > attempts):
                errors.append(f"{label}.successes must be between 0 and attempts")
    return errors


def make_train_list(
    data_root: str | Path,
    output: str | Path,
    *,
    allow_missing: bool = False,
) -> tuple[list[str], list[str]]:
    """Write 50 clean Aloha entries after checking each LeRobot episode count.

    Returns the lines and the datasets whose metadata could not be checked.
    ``allow_missing`` only permits absent directories/metadata, never malformed
    metadata or a wrong episode count. Existing output is preserved on failure.
    """
    if any(character.isspace() for character in str(data_root)):
        raise ValidationError(
            "data root contains whitespace; the upstream training list requires exactly two columns"
        )
    root = Path(data_root).expanduser().resolve()
    if any(character.isspace() for character in str(root)):
        raise ValidationError(
            "resolved data root contains whitespace; choose a path without spaces or newlines"
        )
    lines: list[str] = []
    unverified: list[str] = []
    errors: list[str] = []
    for task in official_tasks():
        dataset = root / f"{task}-aloha-agilex_clean_50-50"
        lines.append(f"robotwin {dataset.as_posix()}")
        info_path = dataset / "meta" / "info.json"
        if dataset.exists() and not dataset.is_dir():
            errors.append(f"Expected a dataset directory: {dataset}")
            continue
        if not dataset.exists() or not info_path.exists():
            unverified.append(str(dataset))
            if not allow_missing:
                errors.append(f"Missing LeRobot metadata: {info_path}")
            continue
        if not info_path.is_file():
            errors.append(f"Expected a dataset directory and a metadata file: {info_path}")
            continue
        try:
            metadata = load_json(info_path)
        except (OSError, ValueError) as exc:
            errors.append(f"Cannot read LeRobot metadata {info_path}: {exc}")
            continue
        episodes = metadata.get("total_episodes") if isinstance(metadata, dict) else None
        if type(episodes) is not int or episodes != 50:
            errors.append(
                f"{info_path}: total_episodes must be the integer 50 (not a boolean); "
                f"got {episodes!r}"
            )
    if errors:
        raise ValidationError("Training list was not written:\n" + "\n".join(errors))
    destination = Path(output).expanduser()
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=destination.parent,
            prefix=f".{destination.name}.",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary_path = Path(stream.name)
            stream.write("\n".join(lines) + "\n")
        os.replace(temporary_path, destination)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
    return lines, unverified

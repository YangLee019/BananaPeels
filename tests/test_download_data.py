"""Exercise download provenance and failure behavior without network or archives."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "download_data.py"
SHA = "a" * 40
FIRST = "dataset/adjust_bottle/aloha-agilex_clean_50.zip"
SECOND = "dataset/beat_block_hammer/aloha-agilex_clean_50.zip"


@pytest.fixture
def download_module():
    spec = importlib.util.spec_from_file_location("banana_download_under_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def hub(download_module, monkeypatch):
    api = MagicMock(name="HfApi_instance")
    api.dataset_info.return_value = SimpleNamespace(
        sha=SHA,
        siblings=[
            SimpleNamespace(rfilename=FIRST, size=111),
            SimpleNamespace(rfilename=SECOND, size=222),
            # These extra files must never enter allow_patterns or the manifest.
            SimpleNamespace(
                rfilename="dataset/adjust_bottle/aloha-agilex_randomized_500.zip", size=333
            ),
            SimpleNamespace(rfilename="dataset/adjust_bottle/piper_clean_50.zip", size=444),
        ],
    )
    constructor = MagicMock(name="HfApi", return_value=api)
    snapshot = MagicMock(name="snapshot_download")
    disk = MagicMock(name="disk_usage", return_value=SimpleNamespace(free=20 * 1024**3))
    monkeypatch.setattr(download_module, "HfApi", constructor)
    monkeypatch.setattr(download_module, "snapshot_download", snapshot)
    monkeypatch.setattr(download_module.shutil, "disk_usage", disk)
    return SimpleNamespace(api=api, constructor=constructor, snapshot=snapshot, disk=disk)


def run_script(module, monkeypatch, output: Path, *arguments: str):
    monkeypatch.setattr(sys, "argv", [str(SCRIPT), "--output", str(output), *arguments])
    return module.main()


def write_manifest(output: Path, repo: str, **changes):
    output.mkdir(parents=True, exist_ok=True)
    manifest = {
        "repo": repo,
        "revision": SHA,
        "files": [FIRST],
        "bytes": 111,
        "setting": "clean",
        "episodes_per_task": 50,
        "complete": True,
    }
    manifest.update(changes)
    path = output / "download_manifest.json"
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return path


def test_default_plan_has_no_network_or_filesystem_mutation(
    download_module, hub, monkeypatch, tmp_path, capsys
):
    output = tmp_path / "not-created" / "data"
    assert run_script(download_module, monkeypatch, output) == 0
    hub.constructor.assert_not_called()
    hub.api.dataset_info.assert_not_called()
    hub.snapshot.assert_not_called()
    hub.disk.assert_not_called()
    assert not output.parent.exists()
    printed = capsys.readouterr().out
    plan, _ = json.JSONDecoder().raw_decode(printed.lstrip())
    official = json.loads(
        (download_module.ROOT / "templates" / "results.template.json").read_text(
            encoding="utf-8-sig"
        )
    )
    expected = {
        f"dataset/{task}/aloha-agilex_clean_50.zip" for task in official["results"]["clean"]
    }
    assert len(plan["files"]) == 50
    assert set(plan["files"]) == expected
    assert plan["download"] is False


def test_unknown_task_is_rejected_before_metadata(download_module, hub, monkeypatch, tmp_path):
    output = tmp_path / "data"
    with pytest.raises(SystemExit) as error:
        run_script(
            download_module, monkeypatch, output, "--download", "--task", "not_an_official_task"
        )
    assert error.value.code != 0
    hub.constructor.assert_not_called()
    hub.snapshot.assert_not_called()
    assert not output.exists()


def test_download_freezes_resolved_sha_and_selects_only_requested_clean_archive(
    download_module, hub, monkeypatch, tmp_path
):
    output = tmp_path / "data"

    def inspect_download(**kwargs):
        assert hub.api.dataset_info.called
        pending = json.loads((output / "download_manifest.json").read_text(encoding="utf-8"))
        assert pending["complete"] is False
        assert pending["revision"] == SHA
        assert kwargs["revision"] == SHA
        assert kwargs["repo_id"] == download_module.REPO
        assert kwargs["repo_type"] == "dataset"
        assert kwargs["allow_patterns"] == [FIRST]

    hub.snapshot.side_effect = inspect_download
    assert (
        run_script(download_module, monkeypatch, output, "--download", "--task", "adjust_bottle")
        == 0
    )
    hub.api.dataset_info.assert_called_once()
    metadata_call = hub.api.dataset_info.call_args
    assert metadata_call.kwargs["files_metadata"] is True
    assert metadata_call.kwargs["revision"] == "main"
    hub.snapshot.assert_called_once()
    completed = json.loads((output / "download_manifest.json").read_text(encoding="utf-8"))
    assert completed["repo"] == download_module.REPO
    assert completed["revision"] == SHA
    assert completed["files"] == [FIRST]
    assert completed["bytes"] == 111
    assert completed["complete"] is True


def test_matching_manifest_merges_old_and_new_tasks(download_module, hub, monkeypatch, tmp_path):
    output = tmp_path / "data"
    manifest_path = write_manifest(output, download_module.REPO)
    previous_archive = output / FIRST
    previous_archive.parent.mkdir(parents=True)
    previous_archive.write_bytes(b"previous download is preserved")
    assert (
        run_script(
            download_module, monkeypatch, output, "--download", "--task", "beat_block_hammer"
        )
        == 0
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert set(manifest["files"]) == {FIRST, SECOND}
    assert len(manifest["files"]) == 2
    assert manifest["repo"] == download_module.REPO
    assert manifest["revision"] == SHA
    assert manifest["complete"] is True
    assert previous_archive.read_bytes() == b"previous download is preserved"
    assert SECOND in hub.snapshot.call_args.kwargs["allow_patterns"]
    assert set(hub.snapshot.call_args.kwargs["allow_patterns"]) <= {FIRST, SECOND}


@pytest.mark.parametrize(
    "changes",
    [
        {"repo": "unrelated/repository"},
        {"revision": "b" * 40},
        {"files": ["dataset/adjust_bottle/aloha-agilex_randomized_500.zip"]},
        {"files": ["dataset/not_an_official_task/aloha-agilex_clean_50.zip"]},
        {"files": ["dataset/adjust_bottle/piper_clean_50.zip"]},
    ],
)
def test_incompatible_manifest_preserves_existing_files(
    download_module, hub, monkeypatch, tmp_path, changes
):
    output = tmp_path / "data"
    manifest_changes = dict(changes)
    repo = manifest_changes.pop("repo", download_module.REPO)
    manifest_path = write_manifest(output, repo, **manifest_changes)
    before = manifest_path.read_bytes()
    sentinel = output / "existing-file.bin"
    sentinel.write_bytes(b"keep this file")
    with pytest.raises(SystemExit) as error:
        run_script(download_module, monkeypatch, output, "--download", "--task", "adjust_bottle")
    assert error.value.code != 0
    hub.snapshot.assert_not_called()
    assert manifest_path.read_bytes() == before
    assert sentinel.read_bytes() == b"keep this file"


def test_nonempty_directory_without_manifest_is_not_adopted(
    download_module, hub, monkeypatch, tmp_path
):
    output = tmp_path / "data"
    output.mkdir()
    unknown_file = output / "unknown-origin.zip"
    unknown_file.write_bytes(b"existing data")
    with pytest.raises(SystemExit) as error:
        run_script(download_module, monkeypatch, output, "--download", "--task", "adjust_bottle")
    assert error.value.code != 0
    hub.snapshot.assert_not_called()
    assert unknown_file.read_bytes() == b"existing data"
    assert not (output / "download_manifest.json").exists()


def test_insufficient_disk_space_prevents_download_and_manifest_write(
    download_module, hub, monkeypatch, tmp_path
):
    output = tmp_path / "data"
    hub.disk.return_value = SimpleNamespace(free=0)
    with pytest.raises(SystemExit) as error:
        run_script(download_module, monkeypatch, output, "--download", "--task", "adjust_bottle")
    assert error.value.code != 0
    hub.api.dataset_info.assert_called_once()
    hub.snapshot.assert_not_called()
    assert not output.exists()


def test_download_failure_keeps_manifest_incomplete(download_module, hub, monkeypatch, tmp_path):
    output = tmp_path / "data"
    hub.snapshot.side_effect = RuntimeError("simulated interrupted transfer")
    # The script may propagate a transfer error or turn it into a CLI error;
    # both must leave a resumable, explicitly incomplete manifest.
    try:
        result = run_script(
            download_module, monkeypatch, output, "--download", "--task", "adjust_bottle"
        )
    except (RuntimeError, SystemExit) as error:
        if isinstance(error, SystemExit):
            assert error.code not in (None, 0)
    else:
        assert result != 0
    hub.snapshot.assert_called_once()
    manifest = json.loads((output / "download_manifest.json").read_text(encoding="utf-8"))
    assert manifest["complete"] is False
    assert manifest["revision"] == SHA
    assert manifest["files"] == [FIRST]

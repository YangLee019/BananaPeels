"""Plan or download only the competition's original Aloha-AgileX clean-50 archives."""

import argparse
import json
import shutil
from pathlib import Path

from huggingface_hub import HfApi, snapshot_download

ROOT = Path(__file__).resolve().parents[1]
REPO = "TianxingChen/RoboTwin2.0"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--revision", default="main", help="A HF revision; resolved to a commit SHA."
    )
    parser.add_argument(
        "--download", action="store_true", help="Actually download; default is a plan."
    )
    parser.add_argument(
        "--task", action="append", help="Restrict to named task(s) for a small check."
    )
    args = parser.parse_args()
    template = json.loads(
        (ROOT / "templates/results.template.json").read_text(encoding="utf-8-sig")
    )
    tasks = list(template["results"]["clean"])
    if args.task:
        unknown = set(args.task) - set(tasks)
        if unknown:
            parser.error(f"Unknown competition tasks: {sorted(unknown)}")
        tasks = [task for task in tasks if task in args.task]
    files = [f"dataset/{task}/aloha-agilex_clean_50.zip" for task in tasks]
    print(
        json.dumps(
            {
                "repo": REPO,
                "revision": args.revision,
                "files": files,
                "output": str(args.output.resolve()),
                "download": args.download,
            },
            indent=2,
        )
    )
    if not args.download:
        print("Plan only. Add --download to fetch these archives; no network requests were made.")
        return 0
    # Query only metadata first, freeze the revision, and avoid partial downloads on a small disk.
    info = HfApi().dataset_info(REPO, revision=args.revision, files_metadata=True)
    target = args.output.resolve()
    manifest_path = target / "download_manifest.json"
    allowed = {f"dataset/{task}/aloha-agilex_clean_50.zip" for task in template["results"]["clean"]}
    if manifest_path.exists():
        previous = json.loads(manifest_path.read_text(encoding="utf-8"))
        if previous.get("repo") != REPO or previous.get("revision") != info.sha:
            parser.error(
                "This directory belongs to another dataset/revision. "
                "Use a new output directory or --revision with the existing manifest SHA."
            )
        previous_files = previous.get("files")
        if not isinstance(previous_files, list) or any(
            not isinstance(name, str) or name not in allowed for name in previous_files
        ):
            parser.error("The existing manifest contains invalid/non-clean dataset paths.")
        files = sorted(set(files) | set(previous_files))
    elif target.exists() and (not target.is_dir() or any(target.iterdir())):
        parser.error(
            "Output must be empty or contain this tool's download_manifest.json. "
            "Choose a dedicated raw-data directory."
        )
    metadata = {item.rfilename: item for item in info.siblings}
    missing = [name for name in files if name not in metadata]
    if missing:
        parser.error(f"Required clean-50 archives missing at {info.sha}: {missing}")
    sizes = [metadata[name].size for name in files]
    if any(type(size) is not int or size < 0 for size in sizes):
        parser.error("The server did not return all file sizes; disk-space check cannot proceed.")
    total = sum(sizes)
    disk_target = target
    while not disk_target.exists():
        disk_target = disk_target.parent
    # Conservative: reserves the full archive size again even when a partial download exists.
    needed = total + 2 * 1024**3
    if shutil.disk_usage(disk_target).free < needed:
        parser.error(
            f"Need at least {needed / 1024**3:.2f} GiB free for archives + reserve. "
            "Extraction and conversion require additional space."
        )
    target.mkdir(parents=True, exist_ok=True)
    manifest = {
        "repo": REPO,
        "revision": info.sha,
        "files": files,
        "bytes": total,
        "setting": "clean",
        "episodes_per_task": 50,
        "complete": False,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    snapshot_download(
        repo_id=REPO,
        repo_type="dataset",
        revision=info.sha,
        allow_patterns=files,
        local_dir=target,
        max_workers=4,
    )
    manifest["complete"] = True
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Downloaded {len(files)} archives. Manifest: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

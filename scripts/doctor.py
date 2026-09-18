"""Inspect the preparation environment; no training framework or model is loaded."""

import argparse
import importlib.metadata
import json
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    packages = {}
    errors = []
    for name in ("banana-peels", "huggingface-hub", "PyYAML"):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            errors.append(f"Missing package: {name}")
    if sys.version_info[:2] != (3, 12):
        errors.append("The preparation environment requires Python 3.12.")
    gpu = None
    smi = shutil.which("nvidia-smi")
    if smi:
        try:
            result = subprocess.run(
                [smi, "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            gpu = result.stdout.strip() or result.stderr.strip()
        except (OSError, subprocess.TimeoutExpired) as exc:
            gpu = f"GPU probe unavailable: {exc}"
    disk = shutil.disk_usage(ROOT)
    warnings = []
    if disk.free < 20 * 1024**3:
        warnings.append("Less than 20 GiB free: put datasets and weights on another disk/server.")
    if platform.system() != "Linux":
        warnings.append("This is the preparation environment. GPU training/simulation is separate.")
    report = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "project_root": str(ROOT),
        "python": sys.version,
        "executable": sys.executable,
        "platform": platform.platform(),
        "packages": packages,
        "gpu": gpu,
        "free_disk_gib": round(disk.free / 1024**3, 2),
        "preparation_ready": not errors,
        "training_verified": False,
        "simulation_verified": False,
        "warnings": warnings,
        "errors": errors,
    }
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Fetch pinned source snapshots, without executing upstream installation scripts."""

import argparse
import json
import shutil
import time
import urllib.request
import uuid
import zipfile
from contextlib import contextmanager
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]


@contextmanager
def staging_directory(parent):
    parent = parent.resolve()
    work = parent / f".fetch-{uuid.uuid4().hex}"
    # mkdir inherits the project's ACL. TemporaryDirectory uses a restrictive
    # Windows ACL that would survive a rename into the final vendor directory.
    work.mkdir()
    try:
        yield work
    finally:
        resolved = work.resolve()
        if resolved.parent != parent or not resolved.name.startswith(".fetch-"):
            raise RuntimeError(f"Refusing to clean unexpected staging path: {resolved}")
        shutil.rmtree(resolved)


def fetch(name, spec):
    vendor = ROOT / "vendor"
    vendor.mkdir(exist_ok=True)
    target = vendor / name
    marker = target / ".banana-source.json"
    if target.exists():
        if marker.exists() and json.loads(marker.read_text())["revision"] == spec["revision"]:
            print(f"Already present: {name} @ {spec['revision']}")
            return
        raise RuntimeError(f"Existing directory has an unknown/different revision: {target}")
    repo = spec["repository"].removeprefix("https://github.com/")
    url = f"https://codeload.github.com/{repo}/zip/{spec['revision']}"
    if shutil.disk_usage(vendor).free < 1024**3:
        raise RuntimeError("At least 1 GiB free is required before fetching source snapshots.")
    with staging_directory(vendor) as work:
        archive = work / "source.zip"
        request = urllib.request.Request(url, headers={"User-Agent": "BananaPeels-bootstrap"})
        with urllib.request.urlopen(request, timeout=60) as response, archive.open("wb") as output:
            total = 0
            while chunk := response.read(1024 * 1024):
                total += len(chunk)
                if total > 128 * 1024**2:
                    raise RuntimeError("Source archive unexpectedly exceeds 128 MiB.")
                output.write(chunk)
        with zipfile.ZipFile(archive) as bundle:
            members = bundle.infolist()
            expanded_size = sum(item.file_size for item in members)
            if expanded_size > shutil.disk_usage(work).free - 512 * 1024**2:
                raise RuntimeError("Not enough space to extract this source snapshot.")
            roots = set()
            for member in members:
                path = PurePosixPath(member.filename)
                if path.is_absolute() or ".." in path.parts or "\\" in member.filename:
                    raise RuntimeError(f"Unsafe archive path: {member.filename}")
                if not path.parts or ":" in member.filename:
                    raise RuntimeError(f"Invalid archive path: {member.filename}")
                if (member.external_attr >> 16) & 0o170000 == 0o120000:
                    raise RuntimeError(f"Symlinks are not accepted: {member.filename}")
                roots.add(path.parts[0])
            if len(roots) != 1:
                raise RuntimeError("Expected one top-level source directory.")
            bundle.extractall(work / "extracted")
        source = work / "extracted" / roots.pop()
        (source / ".banana-source.json").write_text(
            json.dumps(spec, indent=2) + "\n", encoding="utf-8"
        )
        # Windows antivirus/indexers can briefly hold newly extracted directories open.
        for attempt in range(7):
            try:
                source.rename(target)
                break
            except PermissionError:
                if attempt == 6:
                    raise
                time.sleep(0.25 * 2**attempt)
    print(f"Fetched {name} @ {spec['revision']} to {target}")


def main():
    lock = json.loads((ROOT / "configs/sources.lock.json").read_text(encoding="utf-8"))
    names = [name for name in lock if name != "checked_on"]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", choices=names)
    args = parser.parse_args()
    for name in [args.only] if args.only else names:
        fetch(name, lock[name])


if __name__ == "__main__":
    main()

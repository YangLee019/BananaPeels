#!/usr/bin/env bash
set -euo pipefail
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
command -v uv >/dev/null || { echo 'Install uv first: https://docs.astral.sh/uv/getting-started/installation/' >&2; exit 1; }
export UV_CACHE_DIR="${PROJECT_ROOT}/.cache/uv"
export UV_PYTHON_INSTALL_DIR="${PROJECT_ROOT}/.runtime/python"
cd "${PROJECT_ROOT}"
uv sync --locked --python 3.12.13 --managed-python
.venv/bin/python scripts/doctor.py --output outputs/environment.json

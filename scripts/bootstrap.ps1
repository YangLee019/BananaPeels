param()
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw 'uv is required. Install it with: winget install --id astral-sh.uv -e'
}
$env:UV_CACHE_DIR = Join-Path $projectRoot '.cache\uv'
$env:UV_PYTHON_INSTALL_DIR = Join-Path $projectRoot '.runtime\python'
$env:PYTHONUTF8 = '1'
Push-Location $projectRoot
try {
    & uv sync --locked --python 3.12.13 --managed-python
    if ($LASTEXITCODE -ne 0) { throw 'uv sync failed.' }
    & .\.venv\Scripts\python.exe scripts\doctor.py --output outputs\environment.json
    if ($LASTEXITCODE -ne 0) { throw 'Environment validation failed.' }
} finally {
    Pop-Location
}

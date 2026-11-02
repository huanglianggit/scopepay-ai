$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    $taskPython = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
    if (-not (Test-Path -LiteralPath $taskPython)) {
        $taskPython = Join-Path (Split-Path -Parent $PSScriptRoot) '.venv/Scripts/python.exe'
    }
    if (-not (Test-Path -LiteralPath $taskPython)) {
        throw 'Install the Python environment first; see README.md.'
    }
    if (-not (Test-Path -LiteralPath (Join-Path $PSScriptRoot 'dist/index.html'))) {
        & npm run build
        if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
    }
    Write-Host 'ScopePay: http://127.0.0.1:8791  (Ctrl+C to stop)'
    & $taskPython -m uvicorn api.main:app --host 127.0.0.1 --port 8791
} finally {
    Pop-Location
}

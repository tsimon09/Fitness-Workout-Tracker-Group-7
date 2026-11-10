$ErrorActionPreference = 'Stop'
$FitNutProject = Split-Path -Parent $PSScriptRoot
$FitNutPython = Join-Path $FitNutProject '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $FitNutPython)) {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3 -m venv (Join-Path $FitNutProject '.venv')
    } elseif (Get-Command python -ErrorAction SilentlyContinue) {
        & python -m venv (Join-Path $FitNutProject '.venv')
    } else { throw 'Install Python 3.12 or newer, then run this script again.' }
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the Python environment.' }
}
& $FitNutPython -m pip install -r (Join-Path $FitNutProject 'requirements.txt')
if ($LASTEXITCODE -ne 0) { throw 'Could not install the Python packages.' }
Write-Output 'Python setup complete. Run scripts/run.ps1 to start FitNut.'

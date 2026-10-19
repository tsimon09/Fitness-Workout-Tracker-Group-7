$ErrorActionPreference = 'Stop'
$FitNutProject = Split-Path -Parent $PSScriptRoot
$FitNutPython = Join-Path $FitNutProject '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $FitNutPython)) { & (Join-Path $PSScriptRoot 'setup-python.ps1') }
& (Join-Path $PSScriptRoot 'start-mysql.ps1')
Write-Output 'Open http://127.0.0.1:5000 in your browser. Press Ctrl+C to stop FitNut.'
Push-Location $FitNutProject
try { & $FitNutPython app.py } finally { Pop-Location }

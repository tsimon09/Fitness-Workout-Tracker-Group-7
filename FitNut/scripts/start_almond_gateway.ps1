param([Parameter(Mandatory=$true)][string]$PythonPath, [string]$AppPath='C:\ProgramData\FitNut\app', [string]$EnvironmentPath='C:\ProgramData\FitNut\service\app.env')
$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $PythonPath)) { throw 'Configured Python executable not found.' }
if (-not (Test-Path -LiteralPath $EnvironmentPath)) { throw 'Server environment file not found.' }
foreach ($line in Get-Content -LiteralPath $EnvironmentPath) {
    if ($line -match '^([A-Za-z_][A-Za-z0-9_]*)=(.*)$') {
        [Environment]::SetEnvironmentVariable($Matches[1], $Matches[2].Trim().Trim('"').Trim("'"), 'Process')
    }
}
Set-Location -LiteralPath $AppPath
# This process binds only 127.0.0.1:8001. Existing HTTPS gateway consumers are unaffected.
& $PythonPath (Join-Path $AppPath 'almond_gateway_service.py')
exit $LASTEXITCODE

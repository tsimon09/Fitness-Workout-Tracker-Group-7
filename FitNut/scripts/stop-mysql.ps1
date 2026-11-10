. (Join-Path $PSScriptRoot 'mysql-common.ps1')
$result = Invoke-FitNutSql -Sql 'SHUTDOWN;'
if ($result.ExitCode -ne 0) { throw $result.Output }
Write-Output 'FitNut MySQL was stopped.'

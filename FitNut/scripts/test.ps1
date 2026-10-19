# All test data lives in a newly created, temporary database.
. (Join-Path $PSScriptRoot 'mysql-common.ps1')
Start-FitNutMySql
$FitNutTestDatabase = 'fitnut_test_' + [Guid]::NewGuid().ToString('N')
$FitNutPreviousEnvironment = @{}
foreach ($name in @('MYSQL_HOST','MYSQL_PORT','MYSQL_DATABASE','MYSQL_USER','MYSQL_PASSWORD')) {
    $FitNutPreviousEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
}
$result = Invoke-FitNutSql -Sql "CREATE DATABASE $FitNutTestDatabase;"
if ($result.ExitCode -ne 0) { throw 'Could not create the isolated test database.' }
try {
    $credential = Import-Clixml -LiteralPath (Join-Path $FitNutRuntime 'root.credential.xml')
    $env:MYSQL_HOST = '127.0.0.1'
    $env:MYSQL_PORT = '3307'
    $env:MYSQL_DATABASE = $FitNutTestDatabase
    $env:MYSQL_USER = $credential.UserName
    $env:MYSQL_PASSWORD = $credential.GetNetworkCredential().Password
    Push-Location $FitNutRoot
    try {
        & (Join-Path $FitNutRoot '.venv\Scripts\python.exe') -m unittest discover -s tests -v
        if ($LASTEXITCODE -ne 0) { throw 'FitNut integration tests failed.' }
    } finally { Pop-Location }
} finally {
    foreach ($name in $FitNutPreviousEnvironment.Keys) {
        [Environment]::SetEnvironmentVariable($name, $FitNutPreviousEnvironment[$name], 'Process')
    }
    if ($FitNutTestDatabase -notmatch '^fitnut_test_[a-f0-9]{32}$') { throw 'Unsafe test database name.' }
    $result = Invoke-FitNutSql -Sql "DROP DATABASE $FitNutTestDatabase;"
    if ($result.ExitCode -ne 0) { Write-Warning 'Test database cleanup failed.' }
}

# Run with PowerShell. No IDE or administrator rights are required.
. (Join-Path $PSScriptRoot 'mysql-common.ps1')
if (-not (Test-Path -LiteralPath $FitNutMySqlServer)) {
    throw "MySQL was not found at $FitNutMySqlBin. Adjust mysql-common.ps1 for your installation."
}
if (-not (Test-Path -LiteralPath $FitNutRuntime)) {
    New-Item -ItemType Directory -Path $FitNutRuntime | Out-Null
    Protect-FitNutPath $FitNutRuntime
}
$dataDirectory = Join-Path $FitNutRuntime 'data'
$configFile = Join-Path $FitNutRuntime 'my.ini'
$credentialFile = Join-Path $FitNutRuntime 'root.credential.xml'
if (-not (Test-Path -LiteralPath (Join-Path $dataDirectory 'mysql'))) {
    if (Test-Path -LiteralPath $dataDirectory) {
        throw 'A data directory already exists without a completed MySQL initialization. Inspect it before retrying.'
    }
    $baseForIni = (Split-Path -Parent $FitNutMySqlBin).Replace('\', '/')
    $dataForIni = $dataDirectory.Replace('\', '/')
    @"
[mysqld]
basedir="$baseForIni"
datadir="$dataForIni"
port=3307
bind-address=127.0.0.1
mysqlx=OFF
default-time-zone=+00:00
max-connections=50
innodb-buffer-pool-size=128M
"@ | Set-Content -LiteralPath $configFile -Encoding ascii
    $initializationLog = Join-Path $FitNutRuntime 'initialize.log'
    & $FitNutMySqlServer "--defaults-file=$configFile" --initialize "--log-error=$initializationLog"
    if ($LASTEXITCODE -ne 0) { throw 'MySQL initialization failed. Inspect .mysql/initialize.log.' }
    $rootPassword = New-FitNutPassword
    $appPassword = New-FitNutPassword
    $rootCredential = [PSCredential]::new('root', (ConvertTo-SecureString $rootPassword -AsPlainText -Force))
    $rootCredential | Export-Clixml -LiteralPath $credentialFile
    @"
ALTER USER 'root'@'localhost' IDENTIFIED BY '$rootPassword';
CREATE DATABASE IF NOT EXISTS fitnut;
CREATE USER 'fitnut_app'@'localhost' IDENTIFIED BY '$appPassword';
GRANT SELECT, INSERT, UPDATE, DELETE ON fitnut.* TO 'fitnut_app'@'localhost';
"@ | Set-Content -LiteralPath (Join-Path $FitNutRuntime 'bootstrap.sql') -Encoding ascii
    $envFile = Join-Path $FitNutRoot '.env.local'
    @"
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3307
MYSQL_DATABASE=fitnut
MYSQL_USER=fitnut_app
MYSQL_PASSWORD=$appPassword
MYSQL_TIMEZONE=UTC
"@ | Set-Content -LiteralPath $envFile -Encoding ascii
    Protect-FitNutPath $envFile
}
if (-not (Test-Path -LiteralPath $credentialFile)) {
    throw 'The FitNut administrator credential file is missing. Existing data was not changed.'
}
Start-FitNutMySql
$FitNutPython = Join-Path $FitNutRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $FitNutPython)) { & (Join-Path $PSScriptRoot 'setup-python.ps1') }
$FitNutOldUser = $env:MYSQL_USER
$FitNutOldPassword = $env:MYSQL_PASSWORD
try {
    $FitNutCredential = Import-Clixml -LiteralPath $credentialFile
    $env:MYSQL_USER = $FitNutCredential.UserName
    $env:MYSQL_PASSWORD = $FitNutCredential.GetNetworkCredential().Password
    & $FitNutPython (Join-Path $PSScriptRoot 'init_database.py')
    if ($LASTEXITCODE -ne 0) { throw 'FitNut database setup failed.' }
} finally {
    $env:MYSQL_USER = $FitNutOldUser
    $env:MYSQL_PASSWORD = $FitNutOldPassword
}
$result = Invoke-FitNutSql -Sql 'SELECT VERSION(); SHOW TABLES FROM fitnut;'
if ($result.ExitCode -ne 0) { throw $result.Output }
Write-Output 'FitNut MySQL is ready at 127.0.0.1:3307.'
Write-Output $result.Output

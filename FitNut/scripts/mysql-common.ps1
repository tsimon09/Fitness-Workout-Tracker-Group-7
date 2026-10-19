$ErrorActionPreference = 'Stop'
$FitNutRoot = Split-Path -Parent $PSScriptRoot
$FitNutRuntime = Join-Path $FitNutRoot '.mysql'
$FitNutMySqlBin = 'C:\Program Files\MySQL\MySQL Server 9.6\bin'
$FitNutMySqlClient = Join-Path $FitNutMySqlBin 'mysql.exe'
$FitNutMySqlServer = Join-Path $FitNutMySqlBin 'mysqld.exe'

function Protect-FitNutPath([string] $Path) {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent().Name
    $acl = Get-Acl -LiteralPath $Path
    $acl.SetAccessRuleProtection($true, $false)
    foreach ($rule in @($acl.Access)) { [void]$acl.RemoveAccessRuleAll($rule) }
    $isDirectory = (Get-Item -LiteralPath $Path).PSIsContainer
    $inheritance = if ($isDirectory) {
        [Security.AccessControl.InheritanceFlags]'ContainerInherit, ObjectInherit'
    } else { [Security.AccessControl.InheritanceFlags]::None }
    $rule = [Security.AccessControl.FileSystemAccessRule]::new(
        $identity, 'FullControl', $inheritance,
        [Security.AccessControl.PropagationFlags]::None, 'Allow')
    $acl.AddAccessRule($rule)
    Set-Acl -LiteralPath $Path -AclObject $acl
}

function New-FitNutPassword {
    $bytes = [byte[]]::new(32)
    $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
    return ([Convert]::ToBase64String($bytes) + '!aA1')
}

function Invoke-FitNutSql {
    param([string] $Sql, [PSCredential] $Credential)
    if (-not $Credential) {
        $Credential = Import-Clixml -LiteralPath (Join-Path $FitNutRuntime 'root.credential.xml')
    }
    $previousPassword = $env:MYSQL_PWD
    $previousErrorPreference = $ErrorActionPreference
    try {
        $env:MYSQL_PWD = $Credential.GetNetworkCredential().Password
        $query = "SET SESSION time_zone = '+00:00';`n" + $Sql
        # Windows PowerShell represents native stderr as error records. Capture
        # those alongside the exit code, including expected connection failures.
        $ErrorActionPreference = 'Continue'
        $output = $query | & $FitNutMySqlClient --no-defaults --no-login-paths `
            --protocol=TCP --host=127.0.0.1 --port=3307 "--user=$($Credential.UserName)" `
            --connect-timeout=5 --default-character-set=utf8mb4 --batch --raw --skip-column-names 2>&1
        return [pscustomobject]@{ ExitCode = $LASTEXITCODE; Output = ($output -join "`n") }
    } finally {
        $env:MYSQL_PWD = $previousPassword
        $ErrorActionPreference = $previousErrorPreference
    }
}

function Start-FitNutMySql {
    $result = Invoke-FitNutSql -Sql 'SELECT 1;'
    if ($result.ExitCode -eq 0) { return }
    $listener = Get-NetTCPConnection -State Listen -LocalPort 3307 -ErrorAction SilentlyContinue
    if ($listener) { throw 'Port 3307 is occupied, but the FitNut administrator login failed.' }
    $config = Join-Path $FitNutRuntime 'my.ini'
    if (-not (Test-Path -LiteralPath $config)) { throw 'Run setup-mysql.ps1 first.' }
    $arguments = @("--defaults-file=`"$config`"", '--no-monitor', '--console')
    $bootstrap = Join-Path $FitNutRuntime 'bootstrap.sql'
    if (Test-Path -LiteralPath $bootstrap) {
        $arguments += "--init-file=`"$bootstrap`""
    }
    $process = Start-Process -FilePath $FitNutMySqlServer -ArgumentList $arguments `
        -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $FitNutRuntime 'server.stdout.log') `
        -RedirectStandardError (Join-Path $FitNutRuntime 'server.stderr.log')
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        Start-Sleep -Milliseconds 500
        $result = Invoke-FitNutSql -Sql 'SELECT 1;'
        if ($result.ExitCode -eq 0) {
            if (Test-Path -LiteralPath $bootstrap) {
                Remove-Item -LiteralPath $bootstrap
            }
            return
        }
        if ($process.HasExited) {
            throw 'FitNut MySQL stopped during startup. Inspect .mysql/server.stderr.log.'
        }
    }
    throw 'FitNut MySQL did not become ready. Inspect .mysql/server.stderr.log.'
}

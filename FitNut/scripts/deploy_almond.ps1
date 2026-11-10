param(
 [Parameter(Mandatory=$true)][string]$PythonPath,
 [Parameter(Mandatory=$true)][string]$MySqlDumpPath,
 [Parameter(Mandatory=$true)][PSCredential]$MigrationCredential,
 [string]$Root='C:\ProgramData\FitNut',
 [string]$EnvironmentPath='C:\ProgramData\FitNut\service\app.env'
)
$ErrorActionPreference='Stop'
$source = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$target = [IO.Path]::GetFullPath((Join-Path $Root 'app'))
if ($source -eq $target) { throw 'Extract the release separately, then deploy it into the existing app.' }
foreach ($required in @($target,$EnvironmentPath,$PythonPath,$MySqlDumpPath)) {
 if (-not (Test-Path -LiteralPath $required)) { throw "Missing deployment prerequisite: $required" }
}
$task=Get-ScheduledTask -TaskName 'FitNut Web'
$backup=Join-Path $Root ('backups\almond-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Path $backup -Force | Out-Null
$acl=Get-Acl -LiteralPath $backup
$acl.SetAccessRuleProtection($true,$false)
foreach ($rule in @($acl.Access)) { [void]$acl.RemoveAccessRuleAll($rule) }
foreach ($identity in @([Security.Principal.WindowsIdentity]::GetCurrent().User, [Security.Principal.SecurityIdentifier]::new('S-1-5-18'), [Security.Principal.SecurityIdentifier]::new('S-1-5-32-544'))) {
 $rule=[Security.AccessControl.FileSystemAccessRule]::new($identity,'FullControl',[Security.AccessControl.InheritanceFlags]'ContainerInherit,ObjectInherit',[Security.AccessControl.PropagationFlags]::None,[Security.AccessControl.AccessControlType]::Allow)
 $acl.AddAccessRule($rule)
}
Set-Acl -LiteralPath $backup -AclObject $acl
Copy-Item -LiteralPath $EnvironmentPath -Destination (Join-Path $backup 'app.env')
Copy-Item -LiteralPath $target -Destination (Join-Path $backup 'app') -Recurse
$saved=@{}
try {
 foreach ($line in Get-Content -LiteralPath $EnvironmentPath) {
  if ($line -match '^([A-Za-z_][A-Za-z0-9_]*)=(.*)$') {
   $name=$Matches[1]; $saved[$name]=[Environment]::GetEnvironmentVariable($name,'Process')
   [Environment]::SetEnvironmentVariable($name,$Matches[2].Trim().Trim('"').Trim("'"),'Process')
  }
 }
 $saved['MYSQL_PWD']=[Environment]::GetEnvironmentVariable('MYSQL_PWD','Process')
 $env:MYSQL_PWD=$MigrationCredential.GetNetworkCredential().Password
 & $MySqlDumpPath --no-defaults --no-tablespaces --set-gtid-purged=OFF --single-transaction --protocol=TCP "--host=$env:MYSQL_HOST" "--port=$env:MYSQL_PORT" "--user=$($MigrationCredential.UserName)" "--result-file=$(Join-Path $backup 'fitnut.sql')" $env:MYSQL_DATABASE
 if ($LASTEXITCODE -ne 0) { throw 'Database backup failed; application has not been changed.' }
 Stop-ScheduledTask -TaskName 'FitNut Web'
 foreach ($item in Get-ChildItem -LiteralPath $source -Force) {
  if ($item.Name -in @('.env.local','.venv','.mysql','.test-results','work','__pycache__')) { continue }
  Copy-Item -LiteralPath $item.FullName -Destination $target -Recurse -Force
 }
 & $PythonPath -m pip install -r (Join-Path $target 'requirements.txt')
 if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
 Push-Location -LiteralPath $target
 try {
  $env:MYSQL_USER=$MigrationCredential.UserName; $env:MYSQL_PASSWORD=$MigrationCredential.GetNetworkCredential().Password
  & $PythonPath -m scripts.init_database; if ($LASTEXITCODE -ne 0) { throw 'Schema migration failed.' }
 }
 finally { Pop-Location }
 # Generation starts disabled. Existing server credentials are not printed or copied into this release.
 $lines=@(Get-Content -LiteralPath $EnvironmentPath | Where-Object { $_ -notmatch '^ALMOND_ENABLED=' })
 $lines += 'ALMOND_ENABLED=false'
 if (-not ($lines -match '^ALMOND_GATEWAY_URL=')) { $lines += 'ALMOND_GATEWAY_URL=http://127.0.0.1:8001' }
 if (-not ($lines -match '^ALMOND_GATEWAY_TOKEN=')) {
  $bytes=[byte[]]::new(48); $rng=[Security.Cryptography.RandomNumberGenerator]::Create()
  try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
  $lines += 'ALMOND_GATEWAY_TOKEN=' + [Convert]::ToBase64String($bytes)
 }
 if (-not ($lines -match '^ALMOND_VENDOR_ENV=')) { $lines += 'ALMOND_VENDOR_ENV=C:/broll-api/geography/.env' }
 [IO.File]::WriteAllLines($EnvironmentPath,$lines,[Text.UTF8Encoding]::new($false))
 $startScript=Join-Path $target 'scripts\start_almond_gateway.ps1'
 $arguments='-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "' + $startScript + '" -PythonPath "' + $PythonPath + '" -AppPath "' + $target + '" -EnvironmentPath "' + $EnvironmentPath + '"'
 $action=New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $arguments
 $settings=New-ScheduledTaskSettingsSet -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero)
 # Reuse the existing task principal; no password/private key is requested or embedded.
 Register-ScheduledTask -TaskName 'FitNut Almond Gateway' -Action $action -Trigger (New-ScheduledTaskTrigger -AtStartup) -Principal $task.Principal -Settings $settings -Force | Out-Null
 Start-ScheduledTask -TaskName 'FitNut Almond Gateway'
 Start-ScheduledTask -TaskName 'FitNut Web'
 Write-Output "Deployment files installed. Backup: $backup. Generation remains disabled pending evidence review and evaluation."
} catch {
 # Additive tables/columns may remain, but restore the original application and environment.
 if (Test-Path -LiteralPath (Join-Path $backup 'app')) {
  foreach ($item in Get-ChildItem -LiteralPath (Join-Path $backup 'app') -Force) {
   Copy-Item -LiteralPath $item.FullName -Destination $target -Recurse -Force
  }
 }
 Copy-Item -LiteralPath (Join-Path $backup 'app.env') -Destination $EnvironmentPath -Force
 Start-ScheduledTask -TaskName 'FitNut Web' -ErrorAction SilentlyContinue
 Write-Warning "Deployment requires review. Original files and database backup are at $backup."
 throw
} finally {
 foreach ($name in $saved.Keys) { [Environment]::SetEnvironmentVariable($name,$saved[$name],'Process') }
}

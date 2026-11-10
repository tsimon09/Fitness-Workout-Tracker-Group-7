# FitNut production deployment

Branch to deploy: `feature/ask-almond` at commit `d68ed64`.

Run these commands on the Windows machine that hosts FitNut. That machine should already contain the existing production application at `C:\ProgramData\FitNut\app`, the `FitNut Web` scheduled task, its MySQL credential, and Caddy configuration.

```powershell
git clone --branch feature/ask-almond https://github.com/tsimon09/Fitness-Workout-Tracker-Group-7.git C:\deploy\FitNut-ask-almond
cd C:\deploy\FitNut-ask-almond\FitNut

# Inspect these paths before deployment.
$python = 'C:\ProgramData\FitNut\venv\Scripts\python.exe'
$dump = 'C:\ProgramData\FitNut\mysql\bin\mysqldump.exe'
$credential = Import-Clixml 'C:\ProgramData\FitNut\mysql\root.credential.xml'

.\scripts\deploy_almond.ps1 -PythonPath $python -MySqlDumpPath $dump -MigrationCredential $credential
```

The deployment script backs up the application and MySQL database, copies the release into the production application folder, installs dependencies, runs additive schema migrations, restarts `FitNut Web`, and creates the loopback-only Almond gateway task. It writes `ALMOND_ENABLED=false` so production generation remains disabled after the install.

After the script completes, verify the production service and site.

```powershell
Get-ScheduledTask -TaskName 'FitNut Web','FitNut Almond Gateway'
Invoke-WebRequest https://192.236.176.111 -UseBasicParsing
```

Before enabling generation, configure the server-held provider credentials, run the approved evaluation, save the qualified evaluation record, then set `ALMOND_ENABLED=true` in `C:\ProgramData\FitNut\service\app.env` and restart both scheduled tasks.

The deployment was not run from the development machine because it has no `C:\ProgramData\FitNut` installation or `FitNut Web` task. Its local preview is unrelated to the production service.

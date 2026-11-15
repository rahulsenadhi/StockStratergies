# Registers (or replaces) the Windows task that runs the daily holdings check with alerts.
# Weekdays 16:15; runs late if the laptop was asleep or off; allowed on battery.
# Runs as the current user while logged on (no password is stored).
#   powershell -ExecutionPolicy Bypass -File scripts\register_holdings_task.ps1

$ErrorActionPreference = "Stop"
$TaskName = "NSE Strategy Hub Holdings Check"
$Project = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Python = Join-Path $Project ".venv\Scripts\python.exe"

if (-not (Test-Path $Python)) { throw "Project Python not found at $Python" }
if (-not (Test-Path (Join-Path $Project ".env"))) {
    Write-Warning ".env not found. The task will run but cannot send messages until .env is set up (see docs\holdings-alerts-setup.md)."
}

$Command = "`"$Python`" holdings_check.py >> holdings_check.log 2>&1"
$Action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c $Command" -WorkingDirectory $Project
$Trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday, Tuesday, Wednesday, Thursday, Friday -At "16:15"
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1) -MultipleInstances IgnoreNew
$Principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings `
    -Principal $Principal -Description "Daily holdings check and Telegram/email alerts (holdings_check.py)." -Force | Out-Null

$Info = Get-ScheduledTaskInfo -TaskName $TaskName
Write-Host "Registered '$TaskName'. Next run: $($Info.NextRunTime)"
Write-Host "Run it now with: Start-ScheduledTask -TaskName '$TaskName'"

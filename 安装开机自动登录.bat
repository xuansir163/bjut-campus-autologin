@echo off
REM Install BJUT campus network auto-login scheduled task (requires admin)
REM Uses python from PATH. Edit if your python is elsewhere.
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Requesting administrator privileges...
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found in PATH. Install Python 3 first.
    pause
    exit /b 1
)

powershell -NoProfile -Command "$py = (Get-Command python).Source; $pyw = Join-Path (Split-Path $py) 'pythonw.exe'; if (-not (Test-Path $pyw)) { $pyw = $py }; $t1 = New-ScheduledTaskTrigger -AtLogOn; $t2 = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 5) -RepetitionDuration (New-TimeSpan -Days 3650); Register-ScheduledTask -TaskName 'BJUT-CampusAutoLogin' -Trigger $t1,$t2 -Action (New-ScheduledTaskAction -Execute $pyw -Argument 'campus_login.py' -WorkingDirectory '%~dp0') -Settings (New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 4) -MultipleInstances IgnoreNew -Hidden) -Force | Out-Null; if ($?) { Write-Host '=== INSTALL OK ===' } else { Write-Host '=== INSTALL FAILED ===' }"

echo.
echo Done. You can close this window.
pause

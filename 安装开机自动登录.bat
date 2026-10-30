@echo off
chcp 65001 >nul 2>&1
setlocal
cd /d "%~dp0"

net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Requesting administrator privileges...
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"

if not exist "campus_login.py" (
  echo [ERROR] campus_login.py NOT found. Extract the zip first, then run this file.
  pause
  exit /b 1
)

set "PY="
set "PYARGS="
call :pick python
if not defined PY call :pick py -3
if not defined PY call :pick python3

if not defined PY (
  echo [ERROR] No working Python 3 found. Install it from python.org first
  echo         and tick "Add python.exe to PATH".
  pause
  exit /b 1
)

echo [..] Using: %PY% %PYARGS%
echo.
%PY% %PYARGS% campus_login.py --install-task

echo.
echo Done. You can close this window.
pause
exit /b 0

:pick
where %~1 >nul 2>&1
if errorlevel 1 exit /b 0
for /f "delims=" %%P in ('where %~1 2^>nul') do (
  if not defined PY (
    echo %%P | findstr /i "WindowsApps" >nul
    if errorlevel 1 (
      "%%P" %~2 -c "import encodings" >nul 2>&1
      if not errorlevel 1 (
        set "PY=%%P"
        set "PYARGS=%~2"
      )
    )
  )
)
if not defined PY (
  %~1 %~2 -c "import encodings" >nul 2>&1
  if not errorlevel 1 (
    set "PY=%~1"
    set "PYARGS=%~2"
  )
)
exit /b 0

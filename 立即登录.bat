@echo off
chcp 65001 >nul 2>&1
setlocal
title BJUT Campus Auto Login
cd /d "%~dp0"
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"

echo ==================================================
echo   BJUT Campus Auto Login
echo   Folder: %CD%
echo ==================================================
echo.

if not exist "campus_login.py" (
  echo [ERROR] campus_login.py NOT found in this folder.
  echo         You are probably running this .bat from INSIDE the zip viewer.
  echo         Right-click the zip -^> Extract All, then run it again
  echo         in the extracted folder.
  echo.
  pause
  exit /b 1
)

rem ---- pick a WORKING python, skip Microsoft Store stubs ----
set "PY="
set "PYARGS="
call :pick python
if not defined PY call :pick py -3
if not defined PY call :pick python3

if not defined PY (
  echo [ERROR] No working Python 3 found.
  echo.
  echo   Candidates found in PATH:
  where python 2^>nul
  where py 2^>nul
  echo.
  echo   Fix it like this:
  echo   1^) Install Python 3 from https://www.python.org/downloads/
  echo      and CHECK "Add python.exe to PATH" during setup.
  echo   2^) If typing "python" opens Microsoft Store, disable the fake one:
  echo      Settings -^> Apps -^> Advanced app settings
  echo      -^> App execution aliases -^> turn OFF python.exe / python3.exe
  echo   3^) Run diagnose.bat and send diagnose.txt for help.
  echo.
  pause
  exit /b 1
)

echo [..] Using: %PY% %PYARGS%
%PY% %PYARGS% -c "import sys;print('    Python',sys.version.split()[0],sys.executable)"
echo.

%PY% %PYARGS% campus_login.py
set "RC=%ERRORLEVEL%"
echo.
echo [exit code] %RC%
if not "%RC%"=="0" (
  echo.
  echo If it says config error: fill in config.json first.
  echo If it says login failed: make sure you are ON the campus network,
  echo   then run diagnose.bat to collect a full report.
)
echo.
pause
exit /b 0

:pick
rem %1 = command, %2 = extra args. Sets PY / PYARGS if a working one is found.
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

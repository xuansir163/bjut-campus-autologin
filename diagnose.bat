@echo off
chcp 65001 >nul 2>&1
setlocal
cd /d "%~dp0"
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"
set "OUT=%~dp0diagnose.txt"

call :run > "%OUT%" 2>&1
type "%OUT%"
echo.
echo --------------------------------------------------
echo Report saved to: %OUT%
echo Send this file to the author if you need help.
echo --------------------------------------------------
pause
exit /b 0

:run
echo ==== 1. System ====
ver
echo.
echo ==== 2. Python candidates in PATH ====
where python 2>nul
where python3 2>nul
where py 2>nul
echo.
echo ==== 3. Chosen Python ====
set "PY="
set "PYARGS="
call :pick python
if not defined PY call :pick py -3
if not defined PY call :pick python3
if defined PY (
  echo USING: %PY% %PYARGS%
  %PY% %PYARGS% -c "import sys;print('version',sys.version.split()[0]);print('exe',sys.executable)"
) else (
  echo NO WORKING PYTHON FOUND
)
echo.
echo ==== 4. Files in current folder ====
dir /b
echo.
echo ==== 5. config.json status ====
if exist "config.json" (
  echo config.json EXISTS
  %PY% %PYARGS% -c "import json,io;d=json.load(io.open('config.json',encoding='utf-8'));print('account:',d.get('account'));print('password length:',len(str(d.get('password',''))));print('service:',d.get('service'))" 2>nul
) else (
  echo config.json MISSING
)
echo.
echo ==== 6. Auth server 10.21.221.98:801 (TCP) ====
if defined PY (
  %PY% %PYARGS% -c "import socket;s=socket.socket();s.settimeout(3);s.connect(('10.21.221.98',801));print('TCP 801 OK');s.close()" 2>&1
) else (
  ping -n 2 -w 1000 10.21.221.98
)
echo.
echo ==== 7. Local IPv4 ====
ipconfig | findstr /i "IPv4"
echo.
echo ==== 8. Internet probe ====
%PY% %PYARGS% -c "import urllib.request;print(urllib.request.urlopen('http://www.msftconnecttest.com/connecttest.txt',timeout=5).read().decode('utf-8','replace').strip())" 2>nul
if errorlevel 1 echo probe failed
echo.
echo ==== 9. Script status ====
%PY% %PYARGS% campus_login.py --status 2>&1
if errorlevel 1 echo status failed with exit code %ERRORLEVEL%
echo.
echo ==== 10. Scheduled task ====
schtasks /query /tn BJUT-CampusAutoLogin /fo list 2>nul
if errorlevel 1 echo no scheduled task installed
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

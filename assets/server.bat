@echo off
setlocal
rem ==== Edit these lines per project ======================
set "APP_TITLE=3D Presentation"
set "PORT_START=8780"
set "PORT_END=8899"
set "ENTRY=main.html"
rem ==========================================================
title %APP_TITLE% - Control Panel
cd /d "%~dp0"
rem State file remembers "<port> <pid>" of the server THIS folder started,
rem so we only ever stop our own server, never another program's port.
set "STATE=%~dp0.server.state"

rem Usage: double-click to start; or run with "stop" to only stop our server
if /i "%~1"=="stop" goto stop_only

set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY where python >nul 2>nul && set "PY=python"
if not defined PY goto nopython

rem Stop a server left over from a previous run of this folder (if any)
call :stop_previous

rem Report which ports in our range are already taken, and by which program
call :port_report

call :find_free_port
if errorlevel 1 (
  echo [ERROR] No free port between %PORT_START% and %PORT_END%.
  pause
  exit /b 1
)
if not "%PORT%"=="%PORT_START%" echo Port %PORT_START% is busy, using free port %PORT% instead.
set "URL=http://127.0.0.1:%PORT%/%ENTRY%"

echo Starting local server on port %PORT% ...
rem Serve with "Cache-Control: no-store" so the browser never shows a cached
rem page/model from another project that used the same port earlier
start "" /b %PY% -c "import http.server as s,sys;H=type('H',(s.SimpleHTTPRequestHandler,),{'end_headers':lambda self:(self.send_header('Cache-Control','no-store'),s.SimpleHTTPRequestHandler.end_headers(self))});s.ThreadingHTTPServer(('127.0.0.1',int(sys.argv[1])),H).serve_forever()" %PORT% >nul 2>&1
set /a TRIES=0
:wait_up
ping -n 2 127.0.0.1 >nul
call :pid_on_port
if defined SRV_PID goto started
set /a TRIES+=1
if %TRIES% LSS 6 goto wait_up
echo [ERROR] Server failed to start on port %PORT%.
pause
exit /b 1

:started
> "%STATE%" echo %PORT% %SRV_PID%
start "" "%URL%"

:menu
echo.
echo ==================================================
echo   Presentation : %URL%
echo   [1] Open presentation in browser again
echo   [2] Server status + port usage report
echo   [3] Stop server (release port %PORT%) and exit
echo   Please use [3] before closing this window.
echo   (If closed by mistake: run this file again, it cleans up the old server.)
echo ==================================================
choice /c 123 /n /m "Select 1, 2 or 3: "
if errorlevel 3 goto stop
if errorlevel 2 goto status
start "" "%URL%"
goto menu

:status
call :pid_on_port
if defined SRV_PID (echo Server is running on port %PORT% [PID %SRV_PID%].) else (echo Server is NOT running.)
call :port_report
goto menu

:stop
call :stop_previous
echo Server stopped. Port %PORT% released.
ping -n 2 127.0.0.1 >nul
exit /b 0

:stop_only
call :stop_previous
echo Server for this folder stopped.
exit /b 0

:nopython
echo Python 3 was not found. Please install Python 3 from https://www.python.org/ and try again.
pause
exit /b 1

rem ---- helpers ----------------------------------------------

:find_free_port
rem First port in [PORT_START, PORT_END] that nothing is LISTENING on (any address)
set /a P=PORT_START
:ffp_loop
if %P% GTR %PORT_END% exit /b 1
netstat -ano | findstr /r /c:":%P% .*LISTENING" >nul
if not errorlevel 1 (
  set /a P+=1
  goto ffp_loop
)
set "PORT=%P%"
exit /b 0

:port_report
rem List LISTENING TCP/IPv4 ports in [PORT_START, PORT_END] with PID and program name
echo.
echo Ports in use between %PORT_START% and %PORT_END%:
set "RP_COUNT=0"
for /f "delims==" %%v in ('set RP_SEEN_ 2^>nul') do set "%%v="
for /f "tokens=2,5" %%a in ('netstat -ano -p tcp ^| findstr /c:"LISTENING"') do call :port_report_line %%a %%b
if "%RP_COUNT%"=="0" echo   (none - every port in the range is free)
exit /b 0

:port_report_line
rem %1 = local address like 127.0.0.1:8780, %2 = PID
set "RL_ADDR=%~1"
set "RL_PID=%~2"
set "RL_PORT="
for %%t in (%RL_ADDR::= %) do set "RL_PORT=%%t"
if not defined RL_PORT exit /b 0
if %RL_PORT% LSS %PORT_START% exit /b 0
if %RL_PORT% GTR %PORT_END% exit /b 0
if defined RP_SEEN_%RL_PORT%_%RL_PID% exit /b 0
set "RP_SEEN_%RL_PORT%_%RL_PID%=1"
set "RL_NAME=unknown"
for /f "tokens=1 delims=," %%n in ('tasklist /fi "PID eq %RL_PID%" /fo csv /nh 2^>nul') do set "RL_NAME=%%~n"
set "RL_MARK="
if "%RL_PID%"=="%SRV_PID%" if "%RL_PORT%"=="%PORT%" set "RL_MARK=  [this presentation]"
set /a RP_COUNT+=1
echo   Port %RL_PORT%   PID %RL_PID%   %RL_NAME%%RL_MARK%
exit /b 0

:pid_on_port
set "SRV_PID="
for /f "tokens=5" %%p in ('netstat -ano ^| findstr /r /c:"127.0.0.1:%PORT% .*LISTENING"') do set "SRV_PID=%%p"
exit /b 0

:stop_previous
if not exist "%STATE%" exit /b 0
set "OLD_PORT="
set "OLD_PID="
for /f "usebackq tokens=1,2" %%a in ("%STATE%") do (
  set "OLD_PORT=%%a"
  set "OLD_PID=%%b"
)
rem Kill only if that exact PID is still the one listening on the recorded port
if defined OLD_PID (
  for /f "tokens=5" %%p in ('netstat -ano ^| findstr /r /c:"127.0.0.1:%OLD_PORT% .*LISTENING"') do (
    if "%%p"=="%OLD_PID%" taskkill /PID %%p /F >nul 2>&1
  )
)
del "%STATE%" >nul 2>&1
exit /b 0

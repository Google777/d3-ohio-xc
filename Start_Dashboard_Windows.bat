@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
echo ============================================
echo    D3 Ohio XC - Coach Dashboard
echo ============================================
echo Starting up... (the FIRST launch takes a minute; later launches are fast)
echo.

set "PYEXE="
set "PYARG="

rem 1) the py launcher (installed by python.org by default) - most reliable
py -3 --version >nul 2>nul
if !errorlevel! == 0 (
  set "PYEXE=py"
  set "PYARG=-3"
)

rem 2) real python.org install locations (works even if NOT added to PATH,
rem    and avoids a flaky Microsoft Store alias)
if not defined PYEXE (
  for /d %%D in ("%LocalAppData%\Programs\Python\Python3*") do if exist "%%D\python.exe" set "PYEXE=%%D\python.exe"
)
if not defined PYEXE (
  for /d %%D in ("%ProgramFiles%\Python3*") do if exist "%%D\python.exe" set "PYEXE=%%D\python.exe"
)
if not defined PYEXE (
  for /d %%D in ("%ProgramFiles(x86)%\Python3*") do if exist "%%D\python.exe" set "PYEXE=%%D\python.exe"
)
if not defined PYEXE (
  for /d %%D in ("C:\Python3*") do if exist "%%D\python.exe" set "PYEXE=%%D\python.exe"
)

rem 3) last resort: python / python3 on PATH (may be a Microsoft Store alias)
if not defined PYEXE (
  python --version >nul 2>nul
  if !errorlevel! == 0 set "PYEXE=python"
)
if not defined PYEXE (
  python3 --version >nul 2>nul
  if !errorlevel! == 0 set "PYEXE=python3"
)

if not defined PYEXE (
  echo Python 3 was not found on this computer.
  echo.
  echo   * If you JUST installed Python: CLOSE this window and double-click again
  echo     ^(or restart the PC^) so Windows can see it.
  echo   * If you have not installed it: get it from https://www.python.org/downloads/
  echo     and on the FIRST screen CHECK the box "Add python.exe to PATH".
  echo.
  pause
  exit /b 1
)

echo Using Python: !PYEXE! !PYARG!
if not exist .venv (
  echo Creating a private environment for the app...
  "!PYEXE!" !PYARG! -m venv .venv
)
call .venv\Scripts\activate.bat
python -m pip install --disable-pip-version-check --quiet --upgrade pip
python -m pip install --disable-pip-version-check --quiet -r requirements.txt

echo.
echo Launching the dashboard in your web browser...
echo (To STOP the app later, just close this black window.)
echo.
python -m streamlit run src\d3xc\dashboard\app.py
pause

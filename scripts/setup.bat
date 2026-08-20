@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "REPO_ROOT=%%~fI"
set "VENV_DIR=%REPO_ROOT%\.venv"
set "VENV_PYTHON=%VENV_DIR%\Scripts\python.exe"

where node >nul 2>&1
if errorlevel 1 (
  echo Node.js was not found.
  echo Install Node.js 20.19+, 22.13+, or 24+, then run this script again.
  exit /b 1
)

where npm >nul 2>&1
if errorlevel 1 (
  echo npm was not found.
  echo Reinstall Node.js with npm and run this script again.
  exit /b 1
)

node -e "const [major, minor] = process.versions.node.split('.').map(Number); process.exit((major === 20 && minor >= 19) || (major === 22 && minor >= 13) || major >= 24 ? 0 : 1)" >nul 2>&1
if errorlevel 1 (
  echo Node.js 20.19+, 22.13+, or 24+ is required.
  node --version
  exit /b 1
)

set "PYTHON_COMMAND="
for %%V in (3.13 3.12 3.11 3.10) do (
  if not defined PYTHON_COMMAND (
    py -%%V -c "import sys; raise SystemExit(sys.version_info[:2] not in {(3, 10), (3, 11), (3, 12), (3, 13)})" >nul 2>&1
    if not errorlevel 1 set "PYTHON_COMMAND=py -%%V"
  )
)

if not defined PYTHON_COMMAND (
  python -c "import sys; raise SystemExit(sys.version_info[:2] not in {(3, 10), (3, 11), (3, 12), (3, 13)})" >nul 2>&1
  if not errorlevel 1 set "PYTHON_COMMAND=python"
)

if not defined PYTHON_COMMAND (
  echo Python 3.10-3.13 was not found.
  echo Install a supported Python version and run this script again.
  exit /b 1
)

cd /d "%REPO_ROOT%"

if not exist "%VENV_PYTHON%" (
  echo Creating Python virtual environment...
  %PYTHON_COMMAND% -m venv "%VENV_DIR%"
  if errorlevel 1 exit /b 1
)

"%VENV_PYTHON%" -c "import sys; raise SystemExit(sys.version_info[:2] not in {(3, 10), (3, 11), (3, 12), (3, 13)})" >nul 2>&1
if errorlevel 1 (
  echo The existing .venv does not use Python 3.10-3.13.
  echo Remove only "%VENV_DIR%", then run this script again.
  exit /b 1
)

echo Installing Python dependencies...
"%VENV_PYTHON%" -m pip install -e .
if errorlevel 1 exit /b 1

echo Installing frontend dependencies and building the web interface...
pushd "%REPO_ROOT%\frontend"
call npm ci
if errorlevel 1 (
  popd
  exit /b 1
)
call npm run build
if errorlevel 1 (
  popd
  exit /b 1
)
popd

if not exist "%REPO_ROOT%\data\chats\sessions" mkdir "%REPO_ROOT%\data\chats\sessions"
if not exist "%REPO_ROOT%\data\knowledge" mkdir "%REPO_ROOT%\data\knowledge"
if not exist "%REPO_ROOT%\data\credentials" mkdir "%REPO_ROOT%\data\credentials"

echo.
echo Setup complete.
echo Start the application with: scripts\run.bat
exit /b 0

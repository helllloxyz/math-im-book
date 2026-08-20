@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "REPO_ROOT=%%~fI"
set "VENV_PYTHON=%REPO_ROOT%\.venv\Scripts\python.exe"
set "FRONTEND_INDEX=%REPO_ROOT%\frontend\dist\index.html"

set "APP_HOST=%~1"
if not defined APP_HOST set "APP_HOST=127.0.0.1"
set "APP_PORT=%~2"
if not defined APP_PORT set "APP_PORT=8000"

if not exist "%VENV_PYTHON%" (
  echo Python environment not found: %REPO_ROOT%\.venv
  echo Run scripts\setup.bat first.
  exit /b 1
)

if not exist "%FRONTEND_INDEX%" (
  echo Frontend build not found: %FRONTEND_INDEX%
  echo Run scripts\setup.bat first.
  exit /b 1
)

cd /d "%REPO_ROOT%"

echo Math IM Book is starting at http://%APP_HOST%:%APP_PORT%
echo Press Ctrl+C to stop.
"%VENV_PYTHON%" -m uvicorn math_im_book.api.app:create_app --factory --host "%APP_HOST%" --port "%APP_PORT%" --log-level warning --no-access-log

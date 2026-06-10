@echo off
setlocal

set "ROOT_DIR=%~dp0"
set "WATCHER_DIR=%ROOT_DIR%memory_watcher"
set "VENV_DIR=%WATCHER_DIR%\.venv"

where python >nul 2>&1
if %errorlevel% neq 0 (
    echo Python 3.11+ is required. Please install Python and add it to PATH.
    exit /b 1
)

where docker >nul 2>&1
if %errorlevel% neq 0 (
    echo Docker is required for local Qdrant. Install Docker Desktop, then rerun install.bat.
    exit /b 1
)

echo Creating Python environment...
python -m venv "%VENV_DIR%"
if %errorlevel% neq 0 (
    echo Failed to create virtual environment. Ensure python is correctly installed.
    exit /b %errorlevel%
)

"%VENV_DIR%\Scripts\python.exe" -m pip install --upgrade pip
"%VENV_DIR%\Scripts\pip.exe" install -r "%WATCHER_DIR%\requirements.txt"
"%VENV_DIR%\Scripts\pip.exe" install -e "%ROOT_DIR%uams_sdk"

echo.
echo UAMS installed.
echo Run: uams.bat start
echo API docs: http://localhost:8000/docs

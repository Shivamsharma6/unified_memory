@echo off
setlocal

set "ROOT_DIR=%~dp0"
set "WATCHER_DIR=%ROOT_DIR%memory_watcher"
set "VENV_PYTHON=%WATCHER_DIR%\.venv\Scripts\python.exe"

if not exist "%VENV_PYTHON%" (
    echo UAMS is not installed. Please run install.bat first.
    exit /b 1
)

if "%1"=="start" (
    echo Starting Qdrant via Docker...
    docker compose -f "%ROOT_DIR%docker-compose.yml" up -d
    
    echo Starting UAMS API on port 8000...
    start "UAMS API" /b "%VENV_PYTHON%" -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --app-dir "%WATCHER_DIR%" > "%WATCHER_DIR%\api.log" 2>&1
    
    echo Starting Memory Watcher Daemon...
    start "UAMS Watcher" /b "%VENV_PYTHON%" "%WATCHER_DIR%\daemon.py" > "%WATCHER_DIR%\watcher.log" 2>&1
    
    echo UAMS is running in the background.
    echo Logs are located in memory_watcher\api.log and memory_watcher\watcher.log
    exit /b 0
)

if "%1"=="stop" (
    echo Stopping UAMS...
    :: Taskkill based on the window titles we set or by process matching
    :: Note: On Windows, finding the exact python script is tricky without WMIC.
    :: We'll attempt to kill uvicorn and daemon.py
    for /f "tokens=2" %%i in ('tasklist /v ^| findstr /i "uvicorn api.main:app"') do taskkill /F /PID %%i >nul 2>&1
    for /f "tokens=2" %%i in ('tasklist /v ^| findstr /i "daemon.py"') do taskkill /F /PID %%i >nul 2>&1
    
    :: Fallback: kill window titles if they spawned distinct consoles
    taskkill /F /FI "WINDOWTITLE eq UAMS API*" >nul 2>&1
    taskkill /F /FI "WINDOWTITLE eq UAMS Watcher*" >nul 2>&1
    
    docker compose -f "%ROOT_DIR%docker-compose.yml" stop
    echo Stopped.
    exit /b 0
)

if "%1"=="logs" (
    echo Tail is not native to Windows cmd. 
    echo Please open %WATCHER_DIR%\api.log and %WATCHER_DIR%\watcher.log in a text editor.
    exit /b 0
)

if "%1"=="mcp" (
    "%VENV_PYTHON%" "%ROOT_DIR%uams_sdk\uams_sdk\mcp_server.py"
    exit /b 0
)

echo Usage: uams.bat start ^| stop ^| logs ^| mcp
exit /b 1

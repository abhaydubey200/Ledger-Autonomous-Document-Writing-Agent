@echo off
setlocal enabledelayedexpansion
title TrustGraph — Autonomous Document Agent
cd /d "%~dp0"

:: ANSI escape setup (requires Windows 10+ / VirtualTerminalLevel)
for /f %%A in ('echo prompt $E ^| cmd') do set "ESC=%%A"
set "GREEN=%ESC%[92m"
set "YELLOW=%ESC%[93m"
set "RED=%ESC%[91m"
set "CYAN=%ESC%[96m"
set "BOLD=%ESC%[1m"
set "RESET=%ESC%[0m"

echo.
echo  %CYAN%╔══════════════════════════════════════════════════════════╗%RESET%
echo  %CYAN%║%RESET%  %BOLD%TrustGraph — Autonomous Document Agent%RESET%            %CYAN%║%RESET%
echo  %CYAN%║%RESET%     Enterprise Document Intelligence Platform        %CYAN%║%RESET%
echo  %CYAN%╚══════════════════════════════════════════════════════════╝%RESET%
echo.

:: ── Ensure critical directories exist ──────────────────────────────
if not exist "outputs\" mkdir outputs
if not exist "uploads\" mkdir uploads

:: ── Python check ───────────────────────────────────────────────────
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo %RED%[ERROR]%RESET% Python not found. Install Python 3.10+ from https://python.org
    pause
    exit /b 1
)

:: ── Python version gate ────────────────────────────────────────────
python -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1
if %errorlevel% neq 0 (
    echo %RED%[ERROR]%RESET% Python 3.10+ is required.
    python --version
    pause
    exit /b 1
)

:: ── Dependency check ───────────────────────────────────────────────
echo %CYAN%[INFO]%RESET% Checking dependencies...
python -c "import fastapi, uvicorn, docx, pydantic" >nul 2>&1
if %errorlevel% neq 0 (
    echo %YELLOW%[INFO]%RESET% Installing required packages...
    pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo %RED%[ERROR]%RESET% Failed to install dependencies.
        echo         Try: pip install -r requirements.txt
        pause
        exit /b 1
    )
    echo %GREEN%[OK]%RESET% Dependencies installed.
)

:: ── .env configuration check ───────────────────────────────────────
if not exist ".env" (
    if exist ".env.example" (
        echo %YELLOW%[HINT]%RESET% No .env file found. Copying from .env.example...
        copy .env.example .env >nul
        echo %YELLOW%[HINT]%RESET% Edit .env to set your GROQ_API_KEY for AI document generation.
        echo %YELLOW%[HINT]%RESET% Without it, the agent runs in offline fallback mode.
        echo.
    ) else (
        echo %YELLOW%[HINT]%RESET% No .env file found. Create one with:
        echo         GROQ_API_KEY=gsk_your_key_here
        echo         LLM_PROVIDER=groq
        echo.
    )
)

:: ── Check if Docker is a viable alternative ─────────────────────────
where docker >nul 2>&1
if %errorlevel% equ 0 (
    if exist "docker-compose.yml" (
        echo %CYAN%[TIP]%RESET% Docker is installed. Run with containers instead:
        echo         docker compose up --build
        echo.
    )
)

:: ── Kill any existing server on port 8000 ───────────────────────────
echo %CYAN%[INFO]%RESET% Checking for existing server on port 8000...

for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000 " ^| findstr "LISTENING"') do (
    echo %YELLOW%[INFO]%RESET% Stopping process PID %%a on port 8000
    taskkill /F /PID %%a >nul 2>&1
    if !errorlevel! equ 0 (
        echo %GREEN%[OK]%RESET% Process %%a stopped.
    ) else (
        echo %RED%[WARN]%RESET% Could not stop PID %%a ^(try running as Admin^)
    )
    timeout /t 1 /nobreak >nul
)

:: Also check for 127.0.0.1:8000 variant
for /f "tokens=5" %%a in ('netstat -ano ^| findstr "127.0.0.1:8000"') do (
    echo %YELLOW%[INFO]%RESET% Stopping process PID %%a on 127.0.0.1:8000
    taskkill /F /PID %%a >nul 2>&1
    if !errorlevel! equ 0 (
        echo %GREEN%[OK]%RESET% Process %%a stopped.
    ) else (
        echo %RED%[WARN]%RESET% Could not stop PID %%a ^(try running as Admin^)
    )
    timeout /t 1 /nobreak >nul
)

:: Also check for [::1]:8000 variant (IPv6 localhost)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr "\[::1\]:8000"') do (
    echo %YELLOW%[INFO]%RESET% Stopping process PID %%a on [::1]:8000
    taskkill /F /PID %%a >nul 2>&1
    if !errorlevel! equ 0 (
        echo %GREEN%[OK]%RESET% Process %%a stopped.
    ) else (
        echo %RED%[WARN]%RESET% Could not stop PID %%a ^(try running as Admin^)
    )
    timeout /t 1 /nobreak >nul
)

echo.
echo  %GREEN%──────────────────────────────────────────────────────────%RESET%
echo  %GREEN%  Server starting...%RESET%
echo  %GREEN%──────────────────────────────────────────────────────────%RESET%
echo.
echo  %CYAN%  Frontend :%RESET% http://127.0.0.1:8000/
echo  %CYAN%  API docs :%RESET% http://127.0.0.1:8000/docs
echo  %CYAN%  Health   :%RESET% http://127.0.0.1:8000/health
echo.
echo  %YELLOW%  Press Ctrl+C to stop the server.%RESET%
echo  %GREEN%──────────────────────────────────────────────────────────%RESET%
echo.

python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload

if %errorlevel% neq 0 (
    echo.
    echo %RED%[ERROR]%RESET% Server exited with code %errorlevel%.
    pause
)

endlocal

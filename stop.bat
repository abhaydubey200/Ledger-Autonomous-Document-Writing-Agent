@echo off
setlocal enabledelayedexpansion
title TrustGraph — Stop Server
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
echo  %CYAN%║%RESET%        %BOLD%TrustGraph%RESET% — Stopping Server                   %CYAN%║%RESET%
echo  %CYAN%╚══════════════════════════════════════════════════════════╝%RESET%
echo.

set "FOUND=0"

:: ── Kill by port 8000 (netstat) ────────────────────────────────────
echo %CYAN%[INFO]%RESET% Scanning for processes on port 8000...

for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000 " ^| findstr "LISTENING"') do (
    echo %YELLOW%[INFO]%RESET% Found server PID %%a on port 8000
    taskkill /F /PID %%a >nul 2>&1
    if !errorlevel! equ 0 (
        echo %GREEN%[OK]%RESET% Server PID %%a stopped.
    ) else (
        echo %RED%[WARN]%RESET% Could not stop PID %%a ^(try running as Admin^)
    )
    set "FOUND=1"
    timeout /t 1 /nobreak >nul
)

:: Check for 127.0.0.1:8000 variant
for /f "tokens=5" %%a in ('netstat -ano ^| findstr "127.0.0.1:8000"') do (
    echo %YELLOW%[INFO]%RESET% Found server PID %%a on 127.0.0.1:8000
    taskkill /F /PID %%a >nul 2>&1
    if !errorlevel! equ 0 (
        echo %GREEN%[OK]%RESET% Server PID %%a stopped.
        set "FOUND=1"
    ) else (
        echo %RED%[WARN]%RESET% Could not stop PID %%a ^(try running as Admin^)
    )
    timeout /t 1 /nobreak >nul
)

:: Check for [::1]:8000 variant (IPv6)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr "\[::1\]:8000"') do (
    echo %YELLOW%[INFO]%RESET% Found server PID %%a on [::1]:8000
    taskkill /F /PID %%a >nul 2>&1
    if !errorlevel! equ 0 (
        echo %GREEN%[OK]%RESET% Server PID %%a stopped.
        set "FOUND=1"
    ) else (
        echo %RED%[WARN]%RESET% Could not stop PID %%a ^(try running as Admin^)
    )
    timeout /t 1 /nobreak >nul
)

:: ── Final status ───────────────────────────────────────────────────
echo.
echo  ══════════════════════════════════════════════════════════════
if "%FOUND%"=="0" (
    echo  %GREEN%  No server found running on port 8000.%RESET%
) else (
    echo  %GREEN%  All server processes stopped.%RESET%
)
echo  ══════════════════════════════════════════════════════════════
echo.
echo  %YELLOW%  You may close this window.%RESET%
echo.

timeout /t 3 /nobreak >nul
endlocal

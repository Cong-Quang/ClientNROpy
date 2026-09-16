@echo off
chcp 65001 >nul
title ClientNROpy - C/C++ Native Auto-Compiler
echo ======================================================================
echo    ClientNROpy - Trình Biên Dịch Tự Động Sang C/C++ Native (Anti-Decompile)
echo ======================================================================
echo.

where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [!] ERROR: Khong tim thay Python trong PATH!
    pause
    exit /b 1
)

python "%~dp0build.py" %*

if %errorlevel% neq 0 (
    echo.
    echo [!] Build that bai voi ma loi %errorlevel%.
    pause
    exit /b %errorlevel%
)

echo.
echo [OK] Hoan tat thanh cong!
pause

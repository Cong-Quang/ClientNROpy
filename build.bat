@echo off
chcp 65001 >nul
title ClientNROpy - Dong Goi 1 File Executable Duy Nhat Cho Windows va VPS
echo ======================================================================
echo    ClientNROpy - Trinh Dong Goi 1 File ClientNRO.exe Duy Nhat
echo    Tuong thich: Windows 10, 11 va Windows Server 2012 R2, 2016, 2019, 2022
echo    Ho tro Tieng Viet UTF-8 va khong bao gio bi tat man hinh dot ngot
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
    echo [!] Qua trinh dong goi that bai voi ma loi %errorlevel%.
    pause
    exit /b %errorlevel%
)

echo.
pause

@echo off
title Forum Studio Pro — Apple Edition
cd /d "%~dp0"
echo ========================================================
echo  Launching Forum Studio Pro (Apple Edition)...
echo ========================================================
python main.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [Notice] Python exited with an error. Check logs above.
    pause
)

@echo off
cd /d "%~dp0"
py -m pip install -r requirements.txt -q 2>nul

py -c "import psutil, pyautogui, pygetwindow, requests, keyboard, cv2, PIL" 2>_err.tmp
if errorlevel 1 (
    echo Import error:
    type _err.tmp
    del _err.tmp
    echo.
    pause
    exit /b 1
)
del _err.tmp 2>nul

start "CidMacro" pyw gui.py

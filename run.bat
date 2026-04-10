@echo off
cd /d "%~dp0"

echo Checking dependencies...
py -c "import psutil, pyautogui, pygetwindow, requests, keyboard, cv2, PIL" 2>nul
if errorlevel 1 (
    echo Some dependencies are missing. Installing now, please wait...
    echo.
    py -m pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo ERROR: Failed to install dependencies.
        echo Make sure you have an internet connection and Python is installed correctly.
        echo.
        pause
        exit /b 1
    )
    echo.
    echo Verifying installation...
    py -c "import psutil, pyautogui, pygetwindow, requests, keyboard, cv2, PIL" 2>_err.tmp
    if errorlevel 1 (
        echo ERROR: One or more dependencies could not be installed:
        echo.
        type _err.tmp
        echo.
        echo This is usually caused by an outdated version of Python.
        echo Please update Python at https://www.python.org/downloads/ and try again.
        echo.
        del _err.tmp 2>nul
        pause
        exit /b 1
    )
    del _err.tmp 2>nul
    echo All dependencies installed successfully!
    echo.
)

echo Launching macro...
start "CidMacro" pyw gui.py

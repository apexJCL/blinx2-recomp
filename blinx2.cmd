@echo off
rem blinx2: the project CLI (blinx2.py). Python 3.9 or newer.
where py >nul 2>nul
if %errorlevel%==0 (
    py -3 "%~dp0blinx2.py" %*
) else (
    python "%~dp0blinx2.py" %*
)
exit /b %errorlevel%

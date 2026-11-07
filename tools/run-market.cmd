@echo off
setlocal DisableDelayedExpansion
echo.
echo Empire Specialized Haulers - Market Setup
echo Run this with the Market service stopped.
echo.

py -3 -c "import tomllib" >nul 2>&1
if not errorlevel 1 goto UsePy
python -c "import tomllib" >nul 2>&1
if not errorlevel 1 goto UsePython
echo ERROR: Python 3.11 or newer was not found.
echo Install Python, enable "Add python.exe to PATH", then run this file again.
set "HAULER_MARKET_RESULT=1"
goto Finish

:UsePy
py -3 "%~dp0seed-market.py" %*
set "HAULER_MARKET_RESULT=%errorlevel%"
goto Finish

:UsePython
python "%~dp0seed-market.py" %*
set "HAULER_MARKET_RESULT=%errorlevel%"

:Finish
echo.
if "%HAULER_MARKET_RESULT%"=="0" (
  echo Finished successfully. Start the Market service again.
) else (
  echo Setup failed. Read the error above and MARKET-SETUP-RU.txt.
)
echo Press any key to close this window.
pause >nul
exit /b %HAULER_MARKET_RESULT%

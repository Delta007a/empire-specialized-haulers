@echo off
setlocal DisableDelayedExpansion
call "%~dp0tools\run-market.cmd" --mode normal --apply %*
exit /b %errorlevel%

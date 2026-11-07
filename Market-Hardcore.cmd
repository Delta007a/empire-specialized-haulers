@echo off
setlocal DisableDelayedExpansion
call "%~dp0tools\run-market.cmd" --mode hardcore --apply %*
exit /b %errorlevel%

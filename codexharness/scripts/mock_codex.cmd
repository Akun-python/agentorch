@echo off
setlocal
py -3.13 "%~dp0mock_codex_cli.py" %*
exit /b %ERRORLEVEL%

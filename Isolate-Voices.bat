@echo off
cd /d "%~dp0"
"%~dp0venv\Scripts\python.exe" "%~dp0src\isolate_voices.py" %1
pause

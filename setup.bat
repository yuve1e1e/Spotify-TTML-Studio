@echo off
setlocal
cd /d "%~dp0"

echo [1/4] Checking Python and FFmpeg...
python --version >nul 2>&1 || (echo Python not found. Install Python 3.10-3.13 and add to PATH. & pause & exit /b 1)
ffmpeg -version >nul 2>&1 || (echo FFmpeg not found. Run: winget install Gyan.FFmpeg & pause & exit /b 1)

echo [2/4] Creating virtual environment and installing CUDA PyTorch...
python -m venv venv
call venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu128
pip install -r requirements.txt
pip install --upgrade --pre yt-dlp

echo [3/4] Registering silent Spicetify local bridge on Windows startup...
set "STARTUP_VBS=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\TTMLBridge.vbs"
(
echo CreateObject^("WScript.Shell"^).Run """%~dp0venv\Scripts\pythonw.exe"" ""%~dp0src\ttml_bridge.py""", 0, False
) > "%STARTUP_VBS%"
start "" wscript.exe "%STARTUP_VBS%"

echo [4/4] Installing Spicetify extension (if Spicetify is installed)...
where spicetify >nul 2>&1
if %errorlevel%==0 (
    for /f "delims=" %%i in ('spicetify path userdata') do set "SPICE_USER=%%i"
    if not exist "%SPICE_USER%\Extensions" mkdir "%SPICE_USER%\Extensions"
    copy /Y "%~dp0spicetify\generate_ttml.js" "%SPICE_USER%\Extensions\generate_ttml.js" >nul
    spicetify config extensions generate_ttml.js
    spicetify apply
) else (
    echo Spicetify not found on PATH. Copy spicetify\generate_ttml.js manually if needed.
)

echo.
echo Setup complete!
pause

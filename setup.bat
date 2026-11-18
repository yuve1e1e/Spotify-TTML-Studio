@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"

echo [1/4] Checking prerequisites (Python, FFmpeg, Deno)...
set "NEED_INSTALL=0"
python --version >nul 2>&1 || set "NEED_INSTALL=1"
ffmpeg -version >nul 2>&1 || set "NEED_INSTALL=1"
deno --version >nul 2>&1 || set "NEED_INSTALL=1"

if "!NEED_INSTALL!"=="1" (
    echo.
    echo One or more prerequisites are missing:
    python --version >nul 2>&1 || echo   - Python 3.12
    ffmpeg -version >nul 2>&1 || echo   - FFmpeg ^(audio processing^)
    deno --version >nul 2>&1 || echo   - Deno ^(required by yt-dlp for YouTube extraction^)
    echo.
    set /p "INSTALL_CHOICE=Download and install missing prerequisites automatically via winget? (Y/N): "
    if /I "!INSTALL_CHOICE!"=="Y" (
        where winget >nul 2>&1 || (
            echo winget is not available on this Windows version. Please install Python 3.12, FFmpeg, and Deno manually.
            pause
            exit /b 1
        )
        python --version >nul 2>&1 || winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
        ffmpeg -version >nul 2>&1 || winget install -e --id Gyan.FFmpeg --accept-package-agreements --accept-source-agreements
        deno --version >nul 2>&1 || winget install -e --id DenoLand.Deno --accept-package-agreements --accept-source-agreements

        echo Refreshing environment PATH...
        for /f "tokens=2*" %%A in ('reg query "HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment" /v Path 2^>nul') do set "SYS_PATH=%%B"
        for /f "tokens=2*" %%A in ('reg query "HKCU\Environment" /v Path 2^>nul') do set "USR_PATH=%%B"
        set "PATH=!SYS_PATH!;!USR_PATH!;%LocalAppData%\Programs\Python\Python312;%LocalAppData%\Programs\Python\Python312\Scripts;%USERPROFILE%\.deno\bin"
    ) else (
        echo Setup cancelled. Install the missing prerequisites and run setup.bat again.
        pause
        exit /b 1
    )
)

python --version >nul 2>&1 || (echo Python still not detected. Restart your PC/terminal and re-run setup.bat. & pause & exit /b 1)
ffmpeg -version >nul 2>&1 || (echo FFmpeg still not detected. Restart your PC/terminal and re-run setup.bat. & pause & exit /b 1)

echo.
echo [2/4] Creating isolated virtual environment and installing CUDA PyTorch...
python -m venv venv
call venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu128
pip install -r requirements.txt
pip install --upgrade --pre yt-dlp

echo.
echo [3/4] Registering silent Spicetify local bridge on Windows startup...
set "STARTUP_VBS=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\TTMLBridge.vbs"
(
echo CreateObject^("WScript.Shell"^).Run """%~dp0venv\Scripts\pythonw.exe"" ""%~dp0src\ttml_bridge.py""", 0, False
) > "%STARTUP_VBS%"
start "" wscript.exe "%STARTUP_VBS%"

echo.
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

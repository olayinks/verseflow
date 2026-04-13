@echo off
setlocal enabledelayedexpansion

echo.
echo  ==================================================
echo   VerseFlow Setup
echo  ==================================================
echo.

:: ── Check Node.js ────────────────────────────────────────────────────────────
echo [1/6] Checking Node.js...
where node >nul 2>&1
if errorlevel 1 (
    echo.
    echo  ERROR: Node.js was not found.
    echo  Please install it from https://nodejs.org and re-run this script.
    echo.
    pause
    exit /b 1
)
for /f "tokens=*" %%v in ('node --version') do set NODE_VER=%%v
echo       Found Node.js !NODE_VER!

:: ── Check Python ─────────────────────────────────────────────────────────────
echo [2/6] Checking Python...
where python >nul 2>&1
if errorlevel 1 (
    where py >nul 2>&1
    if errorlevel 1 (
        echo.
        echo  ERROR: Python was not found.
        echo  Please install it from https://python.org
        echo  Make sure to tick "Add Python to PATH" during installation.
        echo.
        pause
        exit /b 1
    )
    set PYTHON=py -3
) else (
    set PYTHON=python
)
for /f "tokens=*" %%v in ('!PYTHON! --version') do set PY_VER=%%v
echo       Found !PY_VER!

:: ── Install Node packages ─────────────────────────────────────────────────────
echo.
echo [3/6] Installing Node.js packages (this may take a minute)...
call npm install --legacy-peer-deps
if errorlevel 1 ( echo  ERROR: npm install failed. & pause & exit /b 1 )

:: ── Install Python packages ───────────────────────────────────────────────────
echo.
echo [4/6] Installing Python packages (this may take several minutes)...
!PYTHON! -m pip install -r sidecar/requirements.txt
if errorlevel 1 ( echo  ERROR: pip install failed. & pause & exit /b 1 )

:: ── Build Bible search index ──────────────────────────────────────────────────
echo.
echo [5/6] Building Bible search index (downloads KJV ^& builds AI index)...
echo       This downloads ~10 MB and may take 5-10 minutes on first run.
!PYTHON! scripts/build_bible_index.py
if errorlevel 1 ( echo  ERROR: Bible index build failed. & pause & exit /b 1 )

:: ── Build lyrics search index ─────────────────────────────────────────────────
echo.
echo [5/6] Building worship lyrics index...
!PYTHON! scripts/build_lyrics_index.py
if errorlevel 1 ( echo  ERROR: Lyrics index build failed. & pause & exit /b 1 )

:: ── Download AI models ────────────────────────────────────────────────────────
echo.
echo [6/6] Downloading AI speech recognition model (~150 MB)...
echo       This only happens once. Please wait...
!PYTHON! scripts/download_models.py
if errorlevel 1 ( echo  ERROR: Model download failed. & pause & exit /b 1 )

:: ── Done ──────────────────────────────────────────────────────────────────────
echo.
echo  ==================================================
echo   Setup complete!
echo  ==================================================
echo.
echo  To start VerseFlow, open TWO terminals and run:
echo.
echo    Terminal 1:  npm run sidecar:dev
echo    Terminal 2:  npm run dev
echo.
echo  Or in VS Code: Terminal menu -^> Run Task -^> Start VerseFlow
echo.
pause

@echo off
setlocal enabledelayedexpansion

:: ─────────────────────────────────────────────────────────────────────────────
:: scripts\create-github-repo.bat
::
:: Creates a new GitHub repository and pushes the VerseFlow codebase to it.
::
:: Requirements:
::   - git     (https://git-scm.com)
::   - gh CLI  (https://cli.github.com) — run `gh auth login` first
::
:: Usage:
::   scripts\create-github-repo.bat
::
:: Optional: pass a repo name as an argument (default: verseflow)
::   scripts\create-github-repo.bat my-verseflow
:: ─────────────────────────────────────────────────────────────────────────────

set "REPO_NAME=%~1"
if "%REPO_NAME%"=="" set "REPO_NAME=verseflow"
set "REPO_DESC=Real-time Bible verse and worship lyric detection for church services"
set "BRANCH=main"

echo.
echo  ==================================================
echo   VerseFlow ^-^> GitHub
echo  ==================================================
echo.

:: ── Pre-flight checks ─────────────────────────────────────────────────────────

where git >nul 2>&1
if errorlevel 1 (
    echo  ERROR: git is not installed.
    echo  Download it from https://git-scm.com and re-run this script.
    echo.
    pause
    exit /b 1
)

where gh >nul 2>&1
if errorlevel 1 (
    echo  ERROR: GitHub CLI ^(gh^) is not installed.
    echo  Download it from https://cli.github.com
    echo  Then run:  gh auth login
    echo.
    pause
    exit /b 1
)

gh auth status >nul 2>&1
if errorlevel 1 (
    echo  You are not logged in to GitHub. Starting login...
    gh auth login
    if errorlevel 1 (
        echo  ERROR: GitHub login failed.
        pause
        exit /b 1
    )
)

:: ── Initialise git if needed ──────────────────────────────────────────────────

if not exist ".git" (
    echo [1/4] Initialising git repository...
    git init -b %BRANCH%
    if errorlevel 1 (
        :: Older git versions don't support -b flag
        git init
        git checkout -b %BRANCH% 2>nul || git checkout %BRANCH% 2>nul
    )
) else (
    echo [1/4] Git repository already initialised.
    git checkout -B %BRANCH% >nul 2>&1 || echo       ^(already on %BRANCH%^)
)

:: ── Stage and commit ──────────────────────────────────────────────────────────

echo [2/4] Staging all files...
git add .

:: Check if there is anything to commit
git diff --cached --quiet >nul 2>&1
if errorlevel 1 (
    :: There are staged changes — get version from package.json
    for /f "tokens=2 delims=:, " %%v in ('findstr /i "\"version\"" package.json') do (
        set "PKG_VERSION=%%~v"
        goto :got_version
    )
    :got_version
    if "%PKG_VERSION%"=="" set "PKG_VERSION=1.0.0"

    echo [2/4] Creating initial commit...
    git commit -m "Initial commit: VerseFlow v%PKG_VERSION%"
    if errorlevel 1 (
        echo  ERROR: git commit failed.
        pause
        exit /b 1
    )
) else (
    echo       Nothing new to commit — working tree is clean.
)

:: ── Create GitHub repository ──────────────────────────────────────────────────

echo [3/4] Creating GitHub repository '%REPO_NAME%'...

gh repo create "%REPO_NAME%" --public --description "%REPO_DESC%" --source=. --remote=origin --push >nul 2>&1
if errorlevel 1 (
    echo       Repository may already exist. Pushing to existing remote...
    for /f "tokens=*" %%u in ('gh api user --jq .login') do set "GITHUB_USER=%%u"
    git remote remove origin >nul 2>&1
    git remote add origin "https://github.com/%GITHUB_USER%/%REPO_NAME%.git"
    git push -u origin %BRANCH%
    if errorlevel 1 (
        echo  ERROR: git push failed.
        pause
        exit /b 1
    )
) else (
    echo       Repository created and code pushed successfully.
)

:: ── Done ──────────────────────────────────────────────────────────────────────

for /f "tokens=*" %%u in ('gh api user --jq .login') do set "GITHUB_USER=%%u"

echo.
echo  ==================================================
echo   Done!
echo  ==================================================
echo.
echo   Your repository is live at:
echo   https://github.com/%GITHUB_USER%/%REPO_NAME%
echo.
echo   To push future changes:
echo     git add .
echo     git commit -m "Your message"
echo     git push
echo.
pause

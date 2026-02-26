@echo off
set TAG=%1

if "%TAG%"=="" (
    echo [ERROR] You must provide a version tag!
    echo Usage: release.bat v2.0.0
    exit /b 1
)

echo [1/4] Staging all files...
git add .

echo [2/4] Committing code...
git commit -m "chore: release %TAG%"

echo [3/4] Pushing code to main...
git push origin main

echo [4/4] Tagging and pushing release %TAG% to trigger Docker build...
git tag -a %TAG% -m "Release %TAG%"
git push origin %TAG%

echo.
echo [SUCCESS] Code pushed and %TAG% triggered! Check GitHub Actions.
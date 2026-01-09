@echo off
REM Build script for SSM Ports executable
echo Installing PyInstaller...
pip install https://github.com/pyinstaller/pyinstaller/archive/develop.zip

echo Determining version...
set VERSION=
for /f %%i in ('git describe --tags --exact-match 2^>nul') do set VERSION=%%i
if "%VERSION%"=="" (
    for /f %%i in ('git rev-parse --short HEAD') do set VERSION=%%i
)
echo VERSION = "%VERSION%" > src\version.py

echo Building executable...
pyinstaller ssmports.spec
echo Build complete! Executable is in dist/ssmports.exe

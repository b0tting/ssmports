@echo off
REM Build script for SSM Ports executable
echo Installing PyInstaller...
pip install https://github.com/pyinstaller/pyinstaller/archive/develop.zip
echo Building executable...
pyinstaller ssmports.spec
echo Build complete! Executable is in dist/ssmports.exe


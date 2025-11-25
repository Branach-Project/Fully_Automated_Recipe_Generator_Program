@echo off
setlocal

REM Launch the Recipe Generator GUI from the project folder
set SCRIPT_DIR=%~dp0
pushd "%SCRIPT_DIR%"

REM Use python from PATH; change to full path (e.g., C:\Python311\python.exe) if needed
set PYTHON_EXE=python

%PYTHON_EXE% main.py

popd
endlocal

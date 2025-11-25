
@echo off
setlocal

REM Launch the Recipe Generator GUI using the virtual environment's Python
set SCRIPT_DIR=%~dp0
pushd "%SCRIPT_DIR%"

REM Use the Python executable from the .venv folder
.venv\Scripts\python.exe main.py

popd
endlocal

REM Pause so the window stays open if there is an error
pause


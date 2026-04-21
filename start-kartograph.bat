@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "ROOT_VENV_PYW=%SCRIPT_DIR%..\.venv\Scripts\pythonw.exe"
set "LOCAL_VENV_PYW=%SCRIPT_DIR%.venv\Scripts\pythonw.exe"
set "ENTRY=%SCRIPT_DIR%kartograph.py"

if not exist "%ENTRY%" (
	echo Startdatei nicht gefunden: %ENTRY%
	pause
	exit /b 1
)

if exist "%ROOT_VENV_PYW%" (
	start "" "%ROOT_VENV_PYW%" "%ENTRY%"
) else if exist "%LOCAL_VENV_PYW%" (
	start "" "%LOCAL_VENV_PYW%" "%ENTRY%"
) else (
	start "" pyw -3 "%ENTRY%"
)

endlocal

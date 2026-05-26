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

for /f "usebackq delims=" %%P in (`powershell -NoProfile -Command "$entry=[IO.Path]::GetFullPath('%ENTRY%'); Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'pythonw.exe' -and $_.CommandLine -like ('*' + $entry + '*') } | Select-Object -ExpandProperty ProcessId"`) do (
	taskkill /PID %%P /F >nul 2>nul
)

if exist "%LOCAL_VENV_PYW%" (
	start "" "%LOCAL_VENV_PYW%" "%ENTRY%"
) else if exist "%ROOT_VENV_PYW%" (
	start "" "%ROOT_VENV_PYW%" "%ENTRY%"
) else (
	start "" pyw -3 "%ENTRY%"
)

endlocal

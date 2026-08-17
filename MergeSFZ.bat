@echo off
rem MergeSFZ.bat - drag and drop one or more .sfz files onto this file to
rem combine them into a single "Merged.sfz" using mergeSFZ.py.
setlocal enabledelayedexpansion

if "%~1"=="" (
	echo Drag and drop one or more .sfz files onto this batch file to merge them.
	pause
	exit /b 1
)

rem Find a Python interpreter.
set "PY="
where python >nul 2>nul && set "PY=python"
if not defined PY (
	where py >nul 2>nul && set "PY=py"
)
if not defined PY (
	echo ERROR: Could not find "python" or "py" on the PATH.
	pause
	exit /b 1
)

set "SCRIPT_DIR=%~dp0"
set "OUT_DIR=%~dp1"
set "OUT_FILE=%OUT_DIR%Merged.sfz"

set "BANKNAME="
set /p BANKNAME=Bank name for the merged file (leave empty to keep each file's own bank name): 

set "FILES="
:collect
if "%~1"=="" goto merge
set "FILES=%FILES% "%~1""
shift
goto collect

:merge
echo.
if defined BANKNAME (
	"%PY%" "%SCRIPT_DIR%mergeSFZ.py" %FILES% -o "%OUT_FILE%" --name "%BANKNAME%"
) else (
	"%PY%" "%SCRIPT_DIR%mergeSFZ.py" %FILES% -o "%OUT_FILE%"
)

echo.
if errorlevel 1 (
	echo Merge failed, see errors above.
) else (
	echo Done: %OUT_FILE%
)
pause

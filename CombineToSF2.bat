@echo off
rem CombineToSF2.bat - combine several .sfz files (from possibly different
rem folders) into a single .sf2 soundfont using convertSoundBank.py.
rem
rem Usage: run this file (double-click it), type a bank name, then drag and
rem drop .sfz files onto this console window -- one at a time or several at
rem once -- pressing Enter after each drop. Press Enter with nothing typed
rem when you're done to combine everything.
setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"

echo ===================================================
echo   Combine SFZ files into one SF2 soundfont
echo ===================================================
echo.

set "BANKNAME="
set /p BANKNAME=Bank name: 
if not defined BANKNAME set "BANKNAME=Sound Bank"

rem Sanitize the bank name for use as a file name (just the characters
rem someone might plausibly type; a stray * ? < > | " is left alone).
set "SAFENAME=%BANKNAME%"
set "SAFENAME=%SAFENAME:\=_%"
set "SAFENAME=%SAFENAME:/=_%"
set "SAFENAME=%SAFENAME::=_%"

set "OUTFILE="
set /p OUTFILE=Output .sf2 file (leave empty for %SCRIPT_DIR%%SAFENAME%.sf2): 
if not defined OUTFILE set "OUTFILE=%SCRIPT_DIR%%SAFENAME%.sf2"

echo.
echo Now drag and drop .sfz files onto this window, one at a time or several
echo at once, pressing Enter after each drop. Press Enter with nothing typed
echo when you're done.
echo.

set "FILES="
set /a COUNT=0

:collect
set "LINE="
set /p LINE=Files (or Enter to finish): 
if not defined LINE goto merge
rem When several files are dropped at once, Explorer sometimes pastes
rem their quoted paths back-to-back with no space in between
rem (""), which would otherwise be seen as a single token below.
set "LINE=%LINE:""=" "%"
set "FILES=%FILES% %LINE%"
for %%F in (%LINE%) do set /a COUNT+=1
echo   added, total so far: %COUNT%
goto collect

:merge
if %COUNT%==0 (
	echo No files were added, nothing to do.
	pause
	exit /b 1
)

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

echo.
echo Combining %COUNT% file(s) into: %OUTFILE%
echo.
"%PY%" "%SCRIPT_DIR%convertSoundBank.py" %FILES% "%OUTFILE%" --name "%BANKNAME%"

echo.
if errorlevel 1 (
	echo Combine failed, see errors above.
) else (
	echo Done: %OUTFILE%
)
pause

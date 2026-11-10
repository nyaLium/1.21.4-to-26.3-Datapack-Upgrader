@echo off
rem Upgrade a Minecraft Java data pack from 1.21.4 (pack format 61) to 26.3 (121.0).
rem
rem   run_upgrade.cmd <source-pack-dir> [output-dir]
rem
rem You can also drag a pack folder onto this file.
rem See README.md / README-CN.md for details.
setlocal

set "PY=python"
where py >nul 2>nul && set "PY=py -3"

if "%~1"=="" (
  echo Usage: run_upgrade.cmd ^<source-pack-dir^> [output-dir]
  echo Example: run_upgrade.cmd "D:\packs\MyPack"
  echo.
  echo Or drag a pack folder onto this file.
  pause
  exit /b 2
)

set "PYTHONPATH=%~dp0;%PYTHONPATH%"

if "%~2"=="" (
  %PY% -m upgrader2 "%~1" --force
) else (
  %PY% -m upgrader2 "%~1" -o "%~2" --force
)
set "RC=%ERRORLEVEL%"

echo.
if not "%RC%"=="0" (
  echo Upgrade finished with errors - see _upgrade\report.md
) else (
  echo Upgrade finished - see _upgrade\report.md
)
pause
endlocal & exit /b %RC%

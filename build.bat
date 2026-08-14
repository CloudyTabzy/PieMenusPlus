@echo off
setlocal

if not defined BLENDER_EXE (
    where blender >nul 2>&1
    if errorlevel 1 (
        echo Blender was not found on PATH.
        echo Set BLENDER_EXE to your Blender executable and run this script again.
        exit /b 1
    )
    set "BLENDER_EXE=blender"
)

if not exist "%~dp0dist\" mkdir "%~dp0dist"

"%BLENDER_EXE%" --background --command extension build --source-dir "%~dp0addon" --output-dir "%~dp0dist"
if errorlevel 1 exit /b %errorlevel%

explorer "%~dp0dist"

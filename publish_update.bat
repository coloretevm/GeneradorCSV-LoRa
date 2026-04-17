@echo off
setlocal EnableExtensions EnableDelayedExpansion

rem Uso:
rem publish_update.bat 1.43 "C:\ruta\GeneradorCSV_LoRa_v43.exe"

if "%~1"=="" goto :usage
if "%~2"=="" goto :usage

set "VERSION=%~1"
set "EXE_SOURCE=%~2"
set "REPO_DIR=%~dp0"
set "DOWNLOADS_DIR=%REPO_DIR%downloads"
set "TARGET_EXE=%DOWNLOADS_DIR%\%~nx2"
set "MANIFEST=%REPO_DIR%update_manifest.json"

if not exist "%EXE_SOURCE%" (
    echo [ERROR] No existe el exe: %EXE_SOURCE%
    exit /b 1
)

if not exist "%DOWNLOADS_DIR%" mkdir "%DOWNLOADS_DIR%"

copy /Y "%EXE_SOURCE%" "%TARGET_EXE%" > nul
if errorlevel 1 (
    echo [ERROR] No se pudo copiar el exe.
    exit /b 1
)

(
echo {
echo   "version": "%VERSION%",
echo   "url": "https://raw.githubusercontent.com/coloretevm/GeneradorCSV-LoRa/main/downloads/%~nx2",
echo   "notes": "Versione pubblicata automaticamente."
echo }
) > "%MANIFEST%"

pushd "%REPO_DIR%"
git add update_manifest.json downloads/%~nx2
git commit -m "Publish v%VERSION%"
if errorlevel 1 (
    echo [INFO] Ningun cambio nuevo para publicar o commit no realizado.
    popd
    exit /b 1
)

git push origin main
if errorlevel 1 (
    echo [ERROR] Fallo el push a GitHub.
    popd
    exit /b 1
)

popd
echo [OK] Version %VERSION% publicada correctamente.
echo [OK] Manifest: https://raw.githubusercontent.com/coloretevm/GeneradorCSV-LoRa/main/update_manifest.json
exit /b 0

:usage
echo.
echo Uso:
echo   publish_update.bat 1.43 "C:\ruta\GeneradorCSV_LoRa_v43.exe"
echo.
exit /b 1

@echo off
chcp 65001 >nul
cd /d "%~dp0"
docker compose stop
echo.
echo Dibujos Magicos se detuvo. Sus dibujos y videos siguen guardados en la carpeta "datos".
pause

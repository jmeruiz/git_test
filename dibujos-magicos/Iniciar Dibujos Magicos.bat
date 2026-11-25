@echo off
chcp 65001 >nul
title Dibujos Magicos
cd /d "%~dp0"
echo.
echo    *  Dibujos Magicos  *
echo.

docker info >nul 2>&1
if errorlevel 1 goto sin_docker

rem Puerto: 8000, salvo que el archivo .env diga otro (por ejemplo PUERTO=8010)
set PUERTO=8000
if exist .env for /f "usebackq tokens=1,2 delims==" %%a in (".env") do if /i "%%a"=="PUERTO" set PUERTO=%%b

for /f "usebackq delims=" %%i in (`powershell -NoProfile -Command "$ip = Get-NetIPConfiguration | Where-Object { $_.IPv4DefaultGateway -ne $null -and $_.NetAdapter.Status -eq 'Up' } | Select-Object -First 1; if ($ip) { $ip.IPv4Address.IPAddress }"`) do set DIRECCION_LAN=%%i

echo La primera vez tarda bastante, entre 20 y 60 minutos, porque descarga e instala todo.
echo Las siguientes veces arranca en segundos.
echo.
docker compose up -d --build
if errorlevel 1 goto fallo

echo.
echo Esperando a que la pagina este lista...
:esperar
timeout /t 2 /nobreak >nul
powershell -NoProfile -Command "try { Invoke-WebRequest -UseBasicParsing http://localhost:%PUERTO%/api/salud -TimeoutSec 2 | Out-Null; exit 0 } catch { exit 1 }"
if errorlevel 1 goto esperar

start "" http://localhost:%PUERTO%
echo.
echo ===========================================================
echo  Listo. Se abrio http://localhost:%PUERTO% en el navegador.
if defined DIRECCION_LAN echo  En el celular, conectado al mismo WiFi: http://%DIRECCION_LAN%:%PUERTO%
echo  Para apagarlo use "Detener Dibujos Magicos.bat".
echo ===========================================================
echo.
pause
exit /b 0

:sin_docker
echo Docker Desktop no esta abierto.
echo Abralo, espere a que abajo a la izquierda diga "Engine running" y vuelva a abrir este archivo.
if exist "C:\Program Files\Docker\Docker\Docker Desktop.exe" start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
echo.
pause
exit /b 1

:fallo
echo.
echo Algo salio mal al preparar los contenedores. Copie el texto de arriba para revisarlo.
echo Si dice "port is already allocated", el puerto %PUERTO% ya lo usa otro programa:
echo cree un archivo .env en esta carpeta con la linea PUERTO=8010 y vuelva a intentar.
pause
exit /b 1

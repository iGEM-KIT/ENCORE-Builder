@echo off
rem Double-click start for Windows: starts the ENCORE-Builder from the ready-made images
rem (docker-compose.pull.yml) and opens it in the browser. Every start first fetches the newest
rem images from Docker Hub, so starting again is also the update.
cd /d "%~dp0"

docker info >nul 2>&1
if errorlevel 1 (
  echo Docker is not running.
  echo Start Docker Desktop, wait until it says Engine running, then open this file again.
  pause
  exit /b 1
)

if not exist docker-compose.pull.yml (
  echo Downloading docker-compose.pull.yml ...
  curl.exe -fL -o docker-compose.pull.yml https://raw.githubusercontent.com/iGEM-KIT/ENCORE-Builder/main/docker-compose.pull.yml
  if errorlevel 1 (
    pause
    exit /b 1
  )
)

echo Checking for a newer version ...
docker compose -f docker-compose.pull.yml pull
if errorlevel 1 echo Could not check for updates, using the version on this computer.

echo Starting the ENCORE-Builder. The first start takes several minutes.
docker compose -f docker-compose.pull.yml up -d
if errorlevel 1 (
  pause
  exit /b 1
)

echo Waiting for the Builder ...
:wait
curl.exe -fs -o nul http://localhost:3000
if errorlevel 1 (
  timeout /t 3 /nobreak >nul
  goto wait
)

echo Ready: http://localhost:3000
echo The screening shows a green dot in the top right when its databases are loaded.
echo To stop the program, use the Containers tab in Docker Desktop.
start http://localhost:3000
pause

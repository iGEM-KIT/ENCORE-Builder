#!/bin/bash
# Double-click start for Mac and Linux: starts the ENCORE-Builder from the ready-made images
# (docker-compose.pull.yml) and opens it in the browser. Every start first fetches the newest
# images from Docker Hub, so starting again is also the update.
cd "$(dirname "$0")" || exit 1

pause_and_exit() {
  read -n 1 -s -r -p "Press any key to close this window."
  echo
  exit "$1"
}

if ! docker info >/dev/null 2>&1; then
  echo "Docker is not running."
  echo "Start Docker Desktop, wait until it says Engine running, then open this file again."
  pause_and_exit 1
fi

if [ ! -f docker-compose.pull.yml ]; then
  echo "Downloading docker-compose.pull.yml ..."
  curl -fL -o docker-compose.pull.yml \
    https://raw.githubusercontent.com/iGEM-KIT/ENCORE-Builder/main/docker-compose.pull.yml || pause_and_exit 1
fi

echo "Checking for a newer version ..."
docker compose -f docker-compose.pull.yml pull || echo "Could not check for updates, using the version on this computer."

echo "Starting the ENCORE-Builder. The first start takes several minutes."
docker compose -f docker-compose.pull.yml up -d || pause_and_exit 1

echo "Waiting for the Builder ..."
until curl -fs -o /dev/null http://localhost:3000; do sleep 3; done

echo "Ready: http://localhost:3000"
echo "The screening shows a green dot in the top right when its databases are loaded."
echo "To stop the program, use the Containers tab in Docker Desktop."
open http://localhost:3000 2>/dev/null || xdg-open http://localhost:3000 2>/dev/null
pause_and_exit 0

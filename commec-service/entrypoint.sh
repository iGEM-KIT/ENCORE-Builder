#!/bin/sh
# Starts the HTTP wrapper right away and downloads the commec databases in the background if they are not there yet.
# While the download runs, /health reports ok:false (the app then shows "Biosecurity screening: off"). The marker file
# SETUP_RUNNING (see app.py) says that a download is in progress; a failed download leaves no marker, the next start tries again.
DB_DIR="${COMMEC_DB_DIR:-/databases}"
mkdir -p "$DB_DIR"

if [ ! -f "$DB_DIR/.setup-complete" ]; then
    (
        touch "$DB_DIR/.setup-running"
        echo "[commec-service] first start: downloading the databases into $DB_DIR (about 6 GB download, about 40 GB on disk) ..."
        if commec setup -d "$DB_DIR" </dev/null; then
            touch "$DB_DIR/.setup-complete"
            echo "[commec-service] databases ready."
        else
            echo "[commec-service] commec setup failed; restart the container to try again."
        fi
        rm -f "$DB_DIR/.setup-running"
    ) &
fi

exec python3 /app/app.py

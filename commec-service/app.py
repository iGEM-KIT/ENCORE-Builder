#!/usr/bin/env python3
"""Thin HTTP wrapper around the commec CLI (Common Mechanism, IBBIS) for the
ENCORE-Builder. commec itself has no REST API, only a FASTA-in/JSON-out
CLI (see https://github.com/ibbis-bio/common-mechanism/wiki); this
wrapper takes a sequence over HTTP, writes it to a temporary
FASTA file, calls `commec screen` and returns the parsed result.

Only the Python standard library on purpose (no Flask/FastAPI): this avoids
version conflicts with the packages installed by `conda create -n commec-env commec`
(strict channel priority, see the install guide).

Endpoints:
  GET  /health           -> {"ok": bool, "detail": str}
  POST /screen            body: {"sequences": [{"label": str, "sequence": str}]}
                           -> {"results": [{"available": bool, "status"?: {...}, "reason"?: str}]}

`status` is the object delivered by commec itself, passed
through unchanged, verified against a real run (commec 1.0.4, only the
biorisk + low-concern database, see Dockerfile), e.g.:
  {"screen_status": "Warning", "biorisk": "Pass", "protein_taxonomy": "Skip",
   "nucleotide_taxonomy": "Skip", "low_concern": "Pass",
   "rationale": "No matches found during any stage of analysis. ..."}
Without protein/nucleotide taxonomy databases (see Dockerfile),
protein_taxonomy/nucleotide_taxonomy are always "Skip", and a sequence without
any hit gets "Warning" (not "Pass") with the rationale above;
that is commec's own expected reaction to an incomplete
database set, not an error in this wrapper. screen_status values according to the docs:
Pass, Warning, Flag, Mixed, Error, Skip.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DB_DIR = os.environ.get("COMMEC_DB_DIR", "/databases")
THREADS = os.environ.get("COMMEC_THREADS", "4")
PORT = int(os.environ.get("PORT", "8787"))
# The first start only downloads the mandatory set (curated biorisk + low_concern,
# ~1.2 GB) via `commec setup`, not the ~530GB protein-NR / ~580GB
# nucleotide-NT taxonomy databases (see Dockerfile for why); so the
# protein/nucleotide taxonomy search steps must be skipped, or commec errors
# looking for databases that were never downloaded. Kept as an env var, not
# hardcoded, so a deployment that DID download nr/nt can flip this off
# without editing code.
SKIP_TAXONOMY = os.environ.get("COMMEC_SKIP_TAXONOMY", "true").strip().lower() not in ("false", "0", "no")
# A full run (biorisk + protein/nucleotide taxonomy) can take several minutes
# according to IBBIS; the timeout is generous accordingly, but not
# unlimited, so that a hanging sequence does not block the whole service.
RUN_TIMEOUT_SECONDS = int(os.environ.get("COMMEC_RUN_TIMEOUT_SECONDS", "900"))
MAX_SEQ_LEN = int(os.environ.get("COMMEC_MAX_SEQ_LEN", "20000"))


def _find_status(node):
    """commec's .output.json structure is not officially documented with a schema
        (only examples in the wiki); instead of committing to an assumed shape,
        the tree is searched for the first object that looks like the
        documented `status` object (has a `screen_status` field)."""
    if isinstance(node, dict):
        status = node.get("status")
        if isinstance(status, dict) and "screen_status" in status:
            return status
        if "screen_status" in node:
            return node
        for value in node.values():
            found = _find_status(value)
            if found is not None:
                return found
    elif isinstance(node, list):
        for item in node:
            found = _find_status(item)
            if found is not None:
                return found
    return None


def _screen_one(label: str, sequence: str) -> dict:
    seq = re.sub(r"[^ACGT]", "", sequence.upper())
    if not seq:
        return {"available": False, "reason": "Sequence is empty after removing non-ACGT characters."}
    if len(seq) > MAX_SEQ_LEN:
        return {"available": False, "reason": f"Sequence longer than {MAX_SEQ_LEN} bp: skipped for this service's configured limit."}

    run_id = uuid.uuid4().hex[:12]
    # No user text in the file name/FASTA header, only a generated ID. The
    # label is used exclusively in the HTTP response, never passed on to a
    # shell command or file name.
    with tempfile.TemporaryDirectory(prefix=f"commec-{run_id}-") as tmp:
        fasta_path = os.path.join(tmp, "query.fasta")
        out_prefix = os.path.join(tmp, "out")
        with open(fasta_path, "w") as fh:
            fh.write(f">query_{run_id}\n{seq}\n")

        cmd = ["commec", "screen", "-d", DB_DIR, fasta_path, "-o", out_prefix, "-t", str(THREADS), "-F"]
        if SKIP_TAXONOMY:
            cmd += ["--skip-tx", "--skip-nt"]
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=RUN_TIMEOUT_SECONDS,
            )
        except FileNotFoundError:
            return {"available": False, "reason": "The `commec` executable was not found in this container."}
        except subprocess.TimeoutExpired:
            return {"available": False, "reason": f"commec did not finish within {RUN_TIMEOUT_SECONDS}s."}

        output_json = f"{out_prefix}.output.json"
        if not os.path.exists(output_json):
            detail = (proc.stderr or proc.stdout or "no output produced").strip()
            return {"available": False, "reason": f"commec produced no {os.path.basename(output_json)}: {detail[:500]}"}

        try:
            with open(output_json) as fh:
                data = json.load(fh)
        except (OSError, json.JSONDecodeError) as error:
            return {"available": False, "reason": f"Could not parse commec output: {error}"}

        status = _find_status(data)
        if status is None:
            return {"available": False, "reason": "commec output did not contain a recognizable status object."}
        return {"available": True, "status": status}


class Handler(BaseHTTPRequestHandler):
    def _send_json(self, code: int, payload: dict):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            # Ready = the database directory has content and no download is running (entrypoint.sh marks a running
            # download with .setup-running). A manual `commec setup` (e.g. under pm2) works the same way.
            has_content = os.path.isdir(DB_DIR) and any(not name.startswith(".") for name in os.listdir(DB_DIR))
            running = os.path.exists(os.path.join(DB_DIR, ".setup-running"))
            db_ok = has_content and not running
            if running:
                detail = f"{DB_DIR}: the databases are being downloaded (first start, about 1.2 GB); screening is available afterwards."
            else:
                detail = DB_DIR if db_ok else f"{DB_DIR} missing or empty: run `commec setup -d {DB_DIR}` (see Dockerfile)."
            self._send_json(200, {"ok": db_ok, "detail": detail})
            return
        self._send_json(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/screen":
            self._send_json(404, {"error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, json.JSONDecodeError):
            self._send_json(400, {"error": "invalid JSON body"})
            return

        sequences = body.get("sequences")
        if not isinstance(sequences, list):
            self._send_json(400, {"error": "expected {\"sequences\": [{\"label\", \"sequence\"}, ...]}"})
            return

        results = []
        for item in sequences:
            label = str(item.get("label", "Sequence")) if isinstance(item, dict) else "Sequence"
            sequence = str(item.get("sequence", "")) if isinstance(item, dict) else ""
            results.append(_screen_one(label, sequence))
        self._send_json(200, {"results": results})

    def log_message(self, fmt, *args):
        print(f"[commec-service] {self.address_string()}: {fmt % args}")


if __name__ == "__main__":
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"[commec-service] listening on :{PORT} (db={DB_DIR}, threads={THREADS}, timeout={RUN_TIMEOUT_SECONDS}s)")
    server.serve_forever()

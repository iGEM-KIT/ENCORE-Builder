#!/usr/bin/env python3
"""Zero-dependency local UI preview. The Nuxt/Python computation backend is not started."""
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import os

ROOT=Path(__file__).resolve().parent.parent

class Preview(SimpleHTTPRequestHandler):
    def translate_path(self, path):
        path=path.split('?',1)[0].split('#',1)[0]
        if path in ('/','/index.html'):
            return str(ROOT/'frontend'/'index.html')
        if path.startswith('/selector/'):
            return str(ROOT/'encapsulin_selector'/path[len('/selector/'):].lstrip('/'))
        candidate=(ROOT/'frontend'/path.lstrip('/')).resolve()
        if candidate.is_file() and ROOT/'frontend' in candidate.parents:       # scripts, styles, language files and fonts of the pages
            return str(candidate)
        return str(ROOT/'frontend'/'__not_found__')
    def do_GET(self):
        if self.path.startswith('/api/'):
            self.send_response(503)
            self.send_header('Content-Type','application/json')
            self.end_headers()
            self.wfile.write(b'{"error":"This is a UI preview only. Run pnpm dev for the full ENCORE backend."}')
            return
        super().do_GET()

if __name__=='__main__':
    port=int(os.environ.get('ENCORE_PREVIEW_PORT','8080'))
    print(f'ENCORE preview: http://127.0.0.1:{port}/selector/builder-filter.html',flush=True)
    print('Full Builder backend requires pnpm dev. Press Ctrl+C to stop.',flush=True)
    ThreadingHTTPServer(('127.0.0.1',port),Preview).serve_forever()

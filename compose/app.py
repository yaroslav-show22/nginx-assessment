#!/usr/bin/env python3
import json, sys, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8080

class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body):
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/api/health":
            self._send(200, {"status": "ok", "port": PORT})
        elif self.path == "/api/headers":
            self._send(200, dict(self.headers))
        elif self.path == "/api/slow":
            time.sleep(90)
            self._send(200, {"status": "finally"})
        else:
            self._send(404, {"error": "not found", "path": self.path})

    def do_POST(self):
        if self.path == "/api/upload":
            size = int(self.headers.get("Content-Length", 0))
            self.rfile.read(size)
            self._send(200, {"received_bytes": size})
        else:
            self._send(404, {"error": "not found"})

ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()

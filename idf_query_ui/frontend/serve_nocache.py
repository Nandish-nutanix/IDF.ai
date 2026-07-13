"""Static file server that disables browser caching.

Plain `python -m http.server` lets browsers cache index.html/JS, which causes
stale code (e.g. old hardcoded values) to keep running after updates. This
server sends no-store headers so every reload fetches the latest file.
"""
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer


class NoCacheHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    server = ThreadingHTTPServer(("0.0.0.0", port), NoCacheHandler)
    print(f"No-cache static server running on http://localhost:{port}")
    server.serve_forever()

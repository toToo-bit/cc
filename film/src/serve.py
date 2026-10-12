#!/usr/bin/env python3
"""Serveur local du rendu.

Deux roles :
  - servir la page du film et ses dependances (three.js, polices) ;
  - recevoir les images brutes postees par la page (POST /frame) et les
    ecrire, dans l'ordre, sur l'entree standard de ffmpeg.

La page poste elle-meme ses pixels : on evite ainsi un aller-retour par image
a travers le pilote Playwright, qui serialiserait 8 Mo a chaque fois.
"""
import argparse
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

MIME = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".ttf": "font/ttf",
    ".otf": "font/otf",
    ".png": "image/png",
}


class Sink:
    """Reordonne les images et les pousse dans ffmpeg."""

    def __init__(self, proc, first):
        self.proc = proc
        self.next = first
        self.pending = {}
        self.lock = threading.Lock()
        self.written = 0

    def put(self, index, data):
        with self.lock:
            self.pending[index] = data
            while self.next in self.pending:
                buf = self.pending.pop(self.next)
                if self.proc:
                    self.proc.stdin.write(buf)
                self.next += 1
                self.written += 1


def make_handler(sink, quiet=True):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            if not quiet:
                sys.stderr.write("%s\n" % (a,))

        def _send(self, code, body=b"", ctype="text/plain"):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            if body:
                self.wfile.write(body)

        def do_POST(self):
            if not self.path.startswith("/frame/"):
                return self._send(404)
            index = int(self.path.rsplit("/", 1)[1])
            n = int(self.headers.get("Content-Length", 0))
            data = self.rfile.read(n)
            sink.put(index, data)
            self._send(200, b"ok")

        def do_GET(self):
            path = self.path.split("?")[0]
            if path == "/status":
                return self._send(200, str(sink.written).encode())
            rel = path.lstrip("/") or "src/film.html"
            target = (ROOT / rel).resolve()
            if not str(target).startswith(str(ROOT)) or not target.is_file():
                return self._send(404, b"not found")
            body = target.read_bytes()
            self._send(200, body, MIME.get(target.suffix, "application/octet-stream"))

    return H


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8711)
    ap.add_argument("--out")
    ap.add_argument("--width", type=int, default=1080)
    ap.add_argument("--height", type=int, default=1920)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--first", type=int, default=0)
    args = ap.parse_args()

    proc = None
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        proc = subprocess.Popen(
            ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
             "-f", "rawvideo", "-pix_fmt", "rgba",
             "-s", f"{args.width}x{args.height}", "-r", str(args.fps),
             "-i", "-",
             "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "17",
             "-pix_fmt", "yuv420p", args.out],
            stdin=subprocess.PIPE)

    sink = Sink(proc, args.first)
    srv = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(sink))
    print(f"serveur sur http://127.0.0.1:{args.port}", flush=True)

    # Un processus lance en arriere-plan par un script ignore SIGINT : on
    # s'arrete sur SIGTERM, depuis un fil a part (shutdown() bloque sinon).
    import signal
    def stop(*_):
        threading.Thread(target=srv.shutdown, daemon=True).start()
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    try:
        srv.serve_forever()
    finally:
        srv.server_close()
        if proc:
            proc.stdin.close()
            proc.wait()
        print(f"arret propre, {sink.written} images", flush=True)


if __name__ == "__main__":
    main()

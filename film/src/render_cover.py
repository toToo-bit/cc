#!/usr/bin/env python3
"""Rend la couverture (cover.html) en PNG 1080x1920 via Chromium headless."""
import base64, subprocess, sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
out = Path(sys.argv[1] if len(sys.argv) > 1 else "cover.png")
srv = subprocess.Popen([sys.executable, "-m", "http.server", "8771", "-d", str(ROOT)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    time.sleep(0.8)
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1080, "height": 1920})
        pg.goto("http://127.0.0.1:8771/src/cover.html")
        url = pg.evaluate("window.READY")
        out.write_bytes(base64.b64decode(url.split(",", 1)[1]))
        b.close()
finally:
    srv.terminate()
print(out)

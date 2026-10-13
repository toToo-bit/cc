#!/usr/bin/env python3
"""Pilote de rendu : ouvre la page du film dans Chromium et en sort des images.

Deux usages :
  --still 2.9 --out planche.png     une image a un instant donne
  --range 0 128                     une plage d'images, poussee vers ffmpeg
                                    via le serveur local (voir serve.py)

Le moteur GL se choisit avec --gl :
  llvmpipe    Mesa, environ 4x plus rapide, mais a donne des aplats noirs
              sur le cerveau lors de la session precedente (a verifier)
  swiftshader rendu de reference, lent (~3 s/image en 1080x1920)
"""
import argparse
import os
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent

GL_FLAGS = {
    "swiftshader": [
        "--use-angle=swiftshader",
        "--enable-unsafe-swiftshader",
    ],
    "llvmpipe": [
        "--use-gl=angle",
        "--use-angle=gl-egl",
        "--enable-unsafe-swiftshader",
    ],
}

COMMON_FLAGS = [
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--disable-gpu-sandbox",
    "--ignore-gpu-blocklist",
    "--enable-webgl",
    "--disable-frame-rate-limit",
    "--force-device-scale-factor=1",
]


def build_url(args):
    q = f"w={args.width}&h={args.height}&detail={args.detail}&fps={args.fps}&v={args.variant}"
    return f"http://127.0.0.1:{args.port}/src/{args.page}.html?{q}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8711)
    ap.add_argument("--width", type=int, default=1080)
    ap.add_argument("--height", type=int, default=1920)
    ap.add_argument("--detail", type=int, default=112)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--page", default="motion", help="film (3D) ou motion (2D)")
    ap.add_argument("--variant", default="ig", help="ig ou tt")
    ap.add_argument("--gl", choices=list(GL_FLAGS), default="llvmpipe")
    ap.add_argument("--still", type=float, action="append",
                    help="instant (s) a sortir en PNG ; repetable")
    ap.add_argument("--out", default="out/still")
    ap.add_argument("--range", nargs=2, type=int, metavar=("DE", "A"))
    ap.add_argument("--probe", action="store_true",
                    help="afficher le moteur GL reellement utilise")
    args = ap.parse_args()

    env = dict(os.environ)
    if args.gl == "llvmpipe":
        env["EGL_PLATFORM"] = "surfaceless"
        env["LIBGL_ALWAYS_SOFTWARE"] = "1"
        env["GALLIUM_DRIVER"] = "llvmpipe"

    flags = COMMON_FLAGS + GL_FLAGS[args.gl]

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
            args=flags, env=env, headless=True)
        page = browser.new_page(viewport={"width": args.width, "height": args.height})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("console", lambda m: errors.append(f"[{m.type}] {m.text}")
                if m.type == "error" else None)

        t0 = time.time()
        page.goto(build_url(args), wait_until="load", timeout=120_000)
        page.wait_for_function("window.FILM !== undefined", timeout=180_000)
        page.evaluate("window.FILM.ready")
        build = time.time() - t0
        print(f"page prete en {build:.1f}s", flush=True)

        if args.probe:
            info = page.evaluate("""() => {
              const c = document.createElement('canvas');
              const gl = c.getContext('webgl2') || c.getContext('webgl');
              const d = gl.getExtension('WEBGL_debug_renderer_info');
              return {
                renderer: d ? gl.getParameter(d.UNMASKED_RENDERER_WEBGL) : '?',
                vendor: d ? gl.getParameter(d.UNMASKED_VENDOR_WEBGL) : '?',
              };
            }""")
            print("GL :", info, flush=True)

        if args.still:
            Path(args.out).parent.mkdir(parents=True, exist_ok=True)
            for t in args.still:
                s = time.time()
                data = page.evaluate("""t => { window.FILM.renderAt(t);
                    const c = document.getElementById('stage');
                    return c.toDataURL('image/png').split(',')[1]; }""", t)
                target = f"{args.out}_{t:06.2f}.png".replace(" ", "0")
                import base64
                Path(target).write_bytes(base64.b64decode(data))
                print(f"  {target}  ({time.time()-s:.1f}s)", flush=True)

        if args.range:
            a, b = args.range
            s = time.time()
            page.evaluate("([a,b]) => window.FILM.runRange(a,b)", [a, b],
                          )
            n = b - a + 1
            dt = time.time() - s
            print(f"{n} images en {dt:.1f}s ({dt/max(1,n):.2f}s/image)", flush=True)

        if errors:
            print("--- erreurs page ---", file=sys.stderr)
            for e in errors[:20]:
                print("  ", e, file=sys.stderr)

        browser.close()


if __name__ == "__main__":
    main()

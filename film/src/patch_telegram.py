#!/usr/bin/env python3
"""Remplace des lignes de texte dans une video deja montee (sans les sources).

Pour chaque ligne : on recouvre sa zone avec le meme morceau de fond pris a un
instant ou la zone est encore vide, puis on ecrit le nouveau texte a la meme
place, dans la meme police, avec le meme fondu d'apparition.

  python3 -I patch_telegram.py ENTREE SORTIE spec.json
spec = {"clean_t": 22.0, "lines": [{"box": [x0,y0,x1,y1], "old": "...", "new": "...",
         "font": "serif|sans", "t0": 22.6, "fade": 0.5}]}
"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

A = Path(__file__).resolve().parent.parent / "assets"
FONTS = {"serif": A / "InstrumentSerif-Regular.ttf", "sans": A / "Inter-Variable.ttf"}


def grab(video, t):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(t), "-i", video, "-frames:v", "1",
                          "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
    w, h = map(int, subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries",
                                    "stream=width,height", "-of", "csv=p=0", video],
                                   capture_output=True, text=True).stdout.strip().split(","))
    return Image.frombytes("RGB", (w, h), raw)


def fit_font(kind, text, width, weight=None):
    """taille telle que le texte d'origine occupe la largeur mesuree."""
    lo, hi = 8, 200
    while hi - lo > 1:
        s = (lo + hi) // 2
        f = ImageFont.truetype(str(FONTS[kind]), s)
        if weight and kind == "sans":
            try:
                f.set_variation_by_axes([14, weight])
            except Exception:
                pass
        if f.getbbox(text)[2] - f.getbbox(text)[0] > width:
            hi = s
        else:
            lo = s
    f = ImageFont.truetype(str(FONTS[kind]), lo)
    if weight and kind == "sans":
        try:
            f.set_variation_by_axes([14, weight])
        except Exception:
            pass
    return f


def main(src, dst, spec_path):
    spec = json.loads(Path(spec_path).read_text(encoding="utf-8"))
    clean = grab(src, spec["clean_t"])
    full = grab(src, spec["ink_t"])
    work = Path(dst).with_suffix("")
    work.mkdir(exist_ok=True)
    inputs, filters, last = [], [], "0:v"
    for i, L in enumerate(spec["lines"]):
        x0, y0, x1, y1 = L["box"]
        pad = L.get("pad", 14)
        X0, Y0, X1, Y1 = x0 - pad, y0 - pad, x1 + pad + L.get("extra_w", 0), y1 + pad
        # couleur de l'encre : pixels les plus sombres de la ligne d'origine
        reg = np.asarray(full.crop((x0, y0, x1, y1))).reshape(-1, 3).astype(float)
        lum = reg.mean(1)
        ink = tuple(int(c) for c in reg[lum <= np.percentile(lum, 3)].mean(0))
        patch = clean.crop((X0, Y0, X1, Y1)).convert("RGBA")
        d = ImageDraw.Draw(patch)
        f = fit_font(L["font"], L["old"], x1 - x0, L.get("weight"))
        bb = f.getbbox(L["old"])
        # meme position que l'ancien texte : on aligne le haut de la boite
        d.text((x0 - X0 - bb[0], y0 - Y0 - bb[1]), L["new"], font=f, fill=ink + (255,))
        p = work / f"patch{i}.png"
        patch.save(p)
        inputs += ["-loop", "1", "-i", str(p)]
        n = len(inputs) // 4
        filters.append(f"[{n}:v]format=rgba,fade=in:st={L['t0']}:d={L.get('fade', 0.4)}:alpha=1[p{i}]")
        filters.append(f"[{last}][p{i}]overlay={X0}:{Y0}:shortest=1:enable='gte(t,{L['t0']})'[v{i}]")
        last = f"v{i}"
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", src] + inputs + [
        "-filter_complex", ";".join(filters), "-map", f"[{last}]", "-map", "0:a?",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
        "-c:a", "copy", "-movflags", "+faststart", dst]
    subprocess.run(cmd, check=True)
    print("ok", dst)


if __name__ == "__main__":
    main(*sys.argv[1:4])

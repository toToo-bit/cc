#!/usr/bin/env python3
"""Repere chaque apparition du mot « Telegram » dans des videos (OCR tesseract).

  python3 -I scan_telegram.py video1.mp4 video2.mp4 ... > hits.json

Pour chaque video : une image toutes les PAS secondes, lecture du texte avec
ses boites, et releve des lignes qui contiennent « elegram » (tolere une
premiere lettre mal lue).
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

PAS = 0.5


def duration(f):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", f],
                                capture_output=True, text=True).stdout)


def ocr_lines(png):
    tsv = subprocess.run(["tesseract", png, "-", "--psm", "11", "-l", "eng", "tsv"], capture_output=True, text=True).stdout
    rows = [r.split("\t") for r in tsv.splitlines()[1:]]
    lines = {}
    for r in rows:
        if len(r) < 12 or not r[11].strip():
            continue
        key = (r[2], r[3], r[4])  # bloc, paragraphe, ligne
        x, y, w, h = map(int, r[6:10])
        L = lines.setdefault(key, {"words": [], "box": [x, y, x + w, y + h]})
        L["words"].append(r[11])
        b = L["box"]
        L["box"] = [min(b[0], x), min(b[1], y), max(b[2], x + w), max(b[3], y + h)]
    return [{"text": " ".join(v["words"]), "box": v["box"]} for v in lines.values()]


def scan(f):
    d = duration(f)
    hits = []
    with tempfile.TemporaryDirectory() as td:
        subprocess.run(["ffmpeg", "-v", "error", "-i", f, "-vf", f"fps={1/PAS}", f"{td}/f%04d.png"], check=True)
        for i, png in enumerate(sorted(Path(td).glob("f*.png"))):
            t = round(i * PAS, 2)
            for L in ocr_lines(str(png)):
                if "elegram" in L["text"].lower():
                    hits.append({"t": t, **L})
    return {"file": f, "duration": d, "hits": hits}


if __name__ == "__main__":
    out = [scan(f) for f in sys.argv[1:]]
    print(json.dumps(out, ensure_ascii=False, indent=1))

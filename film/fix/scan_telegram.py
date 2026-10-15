#!/usr/bin/env python3
"""Repere les instants ou « Telegram » est ecrit a l'ecran (OCR tesseract)."""
import json, subprocess, sys, re, tempfile, os
from concurrent.futures import ThreadPoolExecutor

def scan(path, step=0.5):
    du = float(subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",path],capture_output=True,text=True).stdout)
    d = tempfile.mkdtemp()
    subprocess.run(["ffmpeg","-v","error","-i",path,"-vf",f"fps={1/step},format=gray","-q:v","3",f"{d}/f_%05d.png"])
    hits = []
    frames = sorted(os.listdir(d))
    def ocr(fn):
        out = subprocess.run(["tesseract",f"{d}/{fn}","-","--psm","6"],capture_output=True,text=True).stdout
        return fn, out
    with ThreadPoolExecutor(2) as ex:
        for fn, out in ex.map(ocr, frames):
            t = (int(fn[2:7]) - 1) * step
            for line in out.splitlines():
                if re.search(r"t[e3]l[e3]gr[a4]m", line, re.I):
                    hits.append((round(t, 1), line.strip()))
    subprocess.run(["rm","-rf",d])
    return du, hits

if __name__ == "__main__":
    res = {}
    for p in sys.argv[1:]:
        du, hits = scan(p)
        res[p] = {"duration": du, "hits": hits}
        first = hits[0][0] if hits else None
        print(f"{os.path.basename(p)[:44]:44s} {du:5.1f}s  {len(hits):3d} detections, premiere a {first}", flush=True)
    json.dump(res, open("/home/claude/cc/film/fix/scan.json","w"), ensure_ascii=False, indent=1)

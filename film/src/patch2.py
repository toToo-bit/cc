#!/usr/bin/env python3
"""Remplace (ou efface) des lignes de texte dans une video deja montee, image par image.

  python3 -I patch2.py ENTREE SORTIE spec.json

spec = {"lines": [{"t": [t0, t1],            # fenetre ou la ligne est visible (approx., OCR)
                   "box": [x0, y0, x1, y1],  # zone approximative (OCR)
                   "old": "texte d'origine exact", "new": "nouveau texte",
                   "font": "serif|serif_i|sans", "weight": 500,
                   "keep": "POUR RECEVOIR LE LIEN"}]}  # (au lieu de new) : ne garder que ce debut

Pour chaque ligne :
  1. on mesure, image par image, la presence de l'encre dans la zone : cela donne
     la courbe d'apparition/disparition (fondus compris) ;
  2. on prend le fond propre juste avant l'apparition ;
  3. sur toute la duree, on recouvre la zone par ce fond, et on y dessine le
     nouveau texte avec la MEME courbe d'opacite, la meme police (taille ajustee
     sur la largeur reelle de l'ancien texte), la meme ligne de base, la meme encre.
"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

A = Path(__file__).resolve().parent.parent / "assets"
FONTS = {"serif": A / "InstrumentSerif-Regular.ttf", "serif_i": A / "InstrumentSerif-Italic.ttf",
         "sans": A / "Inter-Variable.ttf"}


def probe(src):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries",
                          "stream=width,height,r_frame_rate", "-of", "csv=p=0", src],
                         capture_output=True, text=True).stdout.strip().split(",")
    w, h = int(out[0]), int(out[1])
    num, den = map(int, out[2].split("/"))
    return w, h, num / den


def frames(src, w, h):
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-i", src, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                         stdout=subprocess.PIPE)
    n = w * h * 3
    while True:
        b = p.stdout.read(n)
        if len(b) < n:
            break
        yield np.frombuffer(b, dtype=np.uint8).reshape(h, w, 3)
    p.wait()


def font(kind, size, weight=None):
    f = ImageFont.truetype(str(FONTS[kind]), size)
    if kind == "sans" and weight:
        try:
            axes = f.get_variation_axes()
            vals = [a.get("default", 0) for a in axes]
            for i, a in enumerate(axes):
                nm = a.get("name", b"")
                nm = nm.decode() if isinstance(nm, bytes) else str(nm)
                if "eight" in nm:
                    vals[i] = weight
                if "ptical" in nm:
                    vals[i] = min(max(a["minimum"], size), a["maximum"])
            f.set_variation_by_axes(vals)
        except Exception:
            pass
    return f


def fit(kind, text, width, weight):
    lo, hi = 6, 240
    while hi - lo > 1:
        s = (lo + hi) // 2
        bb = font(kind, s, weight).getbbox(text)
        if bb[2] - bb[0] > width:
            hi = s
        else:
            lo = s
    # affine entre lo et lo+1 : on garde celui dont la largeur est la plus proche
    best = min((lo, lo + 1), key=lambda s: abs((lambda b: b[2] - b[0])(font(kind, s, weight).getbbox(text)) - width))
    return font(kind, best, weight)


def main(src, dst, spec_path):
    spec = json.loads(Path(spec_path).read_text(encoding="utf-8"))
    W, H, fps = probe(src)
    lines = spec["lines"]
    for L in lines:
        x0, y0, x1, y1 = L["box"]
        ml, mt, mr, mb = L.get("m", [30, 8, 60, 8])          # marges : jamais sur la ligne voisine
        L["reg"] = (max(0, x0 - ml), max(0, y0 - mt), min(W, x1 + mr), min(H, y1 + mb))
        L["f0"] = max(0, int((L["t"][0] - 1.6) * fps))
        L["f1"] = int((L["t"][1] + 1.6) * fps)
        L["crops"] = {}

    # ---- passe 1 : mesures
    for i, fr in enumerate(frames(src, W, H)):
        for L in lines:
            if L["f0"] <= i <= L["f1"]:
                X0, Y0, X1, Y1 = L["reg"]
                L["crops"][i] = fr[Y0:Y1, X0:X1].copy()

    for L in lines:
        idx = sorted(L["crops"])
        stack = np.stack([L["crops"][i] for i in idx]).astype(np.float32)
        gray = stack.mean(3)
        bg = np.median(gray[:5].reshape(-1))                       # fond, avant apparition
        dark = (gray < bg - 45).reshape(len(idx), -1).mean(1)
        plateau = np.percentile(dark, 90)
        alpha = np.clip(dark / max(plateau, 1e-6), 0, 1)
        # apparition qui contient le maximum : on s'etend tant que l'encre est la
        # le maximum est cherche dans la fenetre ou l'OCR a lu la ligne (evite les transitions)
        win = [k for k, i in enumerate(idx) if L["t"][0] - 0.3 <= i / fps <= L["t"][1] + 0.3]
        kp0 = win[int(np.argmax(dark[win]))] if win else int(np.argmax(dark))
        ka = kp0
        while ka > 0 and alpha[ka - 1] > 0.03:
            ka -= 1
        kb = kp0
        while kb < len(idx) - 1 and alpha[kb + 1] > 0.03:
            kb += 1
        # hors de cette apparition, opacite nulle (une autre ligne peut passer avant)
        alpha = np.where((np.arange(len(idx)) >= ka) & (np.arange(len(idx)) <= kb), alpha, 0.0)
        L["alpha"] = {idx[k]: float(alpha[k]) for k in range(len(idx))}
        L["fa"], L["fb"] = idx[max(0, ka - 1)], idx[min(len(idx) - 1, kb + 2)]
        # fond propre : premiere image vide en remontant depuis l'apparition
        # seuil strict (tout pixel un peu plus sombre que le papier) : un texte gris
        # en tout debut de fondu ne doit pas passer pour du fond
        faint = (gray < bg - 12).reshape(len(idx), -1).mean(1)
        before = [k for k in range(0, ka) if dark[k] < 0.002]
        # parmi les images sans texte franc, la plus « vide » ; a egalite, la plus proche
        clean_k = min(before, key=lambda k: (round(float(faint[k]), 4), -k)) if before else None
        if clean_k is None:
            raise SystemExit(f"pas de fond propre avant : {L['old']}")
        L["clean"] = L["crops"][idx[clean_k]]
        # etendue reelle de l'ancien texte, sur l'image la plus nette
        kp = kp0
        m = gray[kp] < bg - 45
        ys, xs = np.where(m)
        X0, Y0 = L["reg"][0], L["reg"][1]
        L["ext"] = (X0 + xs.min(), Y0 + ys.min(), X0 + xs.max() + 1, Y0 + ys.max() + 1)
        # encre : pixels les plus sombres sur les images ou la ligne est pleinement visible
        full = [k for k in range(ka, kb + 1) if alpha[k] > 0.97] or [kp]
        pool = np.concatenate([stack[k].reshape(-1, 3)[(gray[k] < bg - 45).reshape(-1)] for k in full])
        lum = pool.mean(1)
        L["ink"] = tuple(int(c) for c in pool[lum <= np.percentile(lum, 2)].mean(0))
        L["colmask"] = m.any(0)

        # calque du nouveau texte (RGBA, taille de la zone)
        ex0, ey0, ex1, ey1 = L["ext"]
        layer = Image.new("RGBA", (L["reg"][2] - X0, L["reg"][3] - Y0), (0, 0, 0, 0))
        if "keep" in L:
            # police a chasse fixe : on coupe au milieu de l'espace qui suit le texte garde
            n_tot, n_keep = len(L["old"]), len(L["keep"])
            keep_to = int((ex0 - X0) + (ex1 - ex0) * (n_keep + 0.5) / n_tot)
            orig = Image.fromarray(stack[kp].astype(np.uint8))
            # le calque reprend les N premiers mots tels quels, avec leur opacite
            src_rgba = orig.convert("RGBA")
            a = Image.new("L", orig.size, 0)
            ImageDraw.Draw(a).rectangle([0, 0, keep_to + 4, orig.size[1]], fill=255)
            src_rgba.putalpha(a)
            L["layer"] = src_rgba
            L["mode"] = "keep"
        else:
            f = fit(L["font"], L["old"], ex1 - ex0, L.get("weight"))
            bb = f.getbbox(L["old"])
            d = ImageDraw.Draw(layer)
            d.text((ex0 - X0 - bb[0], ey0 - Y0 - bb[1]), L["new"], font=f, fill=L["ink"] + (255,))
            L["layer"] = layer
            L["mode"] = "new"
        L["clean_img"] = Image.fromarray(L["clean"]).convert("RGBA")
        print(f"  {L['old'][:46]:46s} images {L['fa']}-{L['fb']}  encre {L['ink']}  largeur {ex1-ex0}px", file=sys.stderr)
        del L["crops"]

    # ---- passe 2 : application
    enc = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                            "-r", str(fps), "-i", "-", "-i", src, "-map", "0:v", "-map", "1:a?",
                            "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
                            "-c:a", "copy", "-movflags", "+faststart", dst], stdin=subprocess.PIPE)
    for i, fr in enumerate(frames(src, W, H)):
        hit = [L for L in lines if L["fa"] <= i <= L["fb"]]
        if hit:
            img = Image.fromarray(fr).convert("RGBA")
            for L in hit:
                X0, Y0, X1, Y1 = L["reg"]
                if L["mode"] == "keep":
                    # zone d'origine remplacee par : fond propre + debut de ligne d'origine
                    cur = img.crop((X0, Y0, X1, Y1))
                    base = L["clean_img"].copy()
                    keep = Image.new("L", cur.size, 0)
                    kt = L["layer"].getchannel("A")
                    base.paste(cur, (0, 0), kt)          # on garde le debut tel qu'il est a cette image
                    img.paste(base, (X0, Y0))
                else:
                    a = L["alpha"].get(i, 0.0)
                    base = L["clean_img"].copy()
                    lay = L["layer"].copy()
                    lay.putalpha(lay.getchannel("A").point(lambda v: int(v * a)))
                    base.alpha_composite(lay)
                    img.paste(base, (X0, Y0))
            fr = np.asarray(img.convert("RGB"))
        enc.stdin.write(fr.tobytes())
    enc.stdin.close()
    enc.wait()
    print("ok", dst, file=sys.stderr)


if __name__ == "__main__":
    main(*sys.argv[1:4])

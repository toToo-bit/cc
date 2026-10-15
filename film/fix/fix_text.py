#!/usr/bin/env python3
"""Remplace une ligne de texte incrustee dans une video deja rendue.

Pour chaque ligne a remplacer :
  1. on la trouve par OCR (tesseract) sur une image ou elle est pleinement visible ;
  2. on mesure son encre (boite exacte, couleur) et on retrouve la taille et la
     graisse de la police en rendant le texte d'origine jusqu'a ce qu'il colle ;
  3. sur chaque image, on efface la ligne en reconstruisant le papier (grain du
     papier voisin + eclairage local) et on ecrit le nouveau texte avec la meme
     opacite que l'original sur cette image (gere apparitions et fondus).

  python3 fix_text.py JOBS.json      (une entree par video, voir jobs.json)
"""
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.ndimage import gaussian_filter, maximum_filter

W, H = 1080, 1920
A = Path(__file__).resolve().parent.parent / "assets"
FONTS = {
    "serif": A / "InstrumentSerif-Regular.ttf",
    "serif_it": A / "InstrumentSerif-Italic.ttf",
    "sans": A / "Inter-Variable.ttf",
    "mono": A / "IBMPlexMono-Regular.ttf",
}


def font(kind, size, weight=400):
    f = ImageFont.truetype(str(FONTS[kind]), size=max(4, int(round(size))))
    if kind == "sans":
        f.set_variation_by_axes([min(32, max(14, size)), weight])
    return f


def grab(path, t):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", path, "-frames:v", "1",
                          "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(H, W, 3)


def ocr_lines(img):
    with tempfile.NamedTemporaryFile(suffix=".png") as f:
        # resolution doublee : les petites mentions en chasse fixe sont mieux lues
        Image.fromarray(img).convert("L").resize((W * 2, H * 2), Image.LANCZOS).save(f.name)
        tsv = subprocess.run(["tesseract", f.name, "-", "--psm", "11", "tsv"], capture_output=True, text=True).stdout
    words = []
    for row in tsv.splitlines()[1:]:
        c = row.split("\t")
        if len(c) == 12 and c[11].strip() and float(c[10]) > 0:
            words.append(dict(text=c[11], x=int(c[6]) // 2, y=int(c[7]) // 2, w=int(c[8]) // 2, h=int(c[9]) // 2))
    return words


def find_line(img, pattern, line_pattern=r"gram|egr"):
    """boites (x0, y0, x1, y1) des lignes qui contiennent le motif ET dont le
    texte complet contient line_pattern (par defaut : « Telegram », meme mal lu)."""
    words = ocr_lines(img)
    anchors = [w for w in words if re.search(pattern, w["text"], re.I)]
    out = []
    for a in anchors:
        cy = a["y"] + a["h"] / 2
        line = sorted([w for w in words if abs((w["y"] + w["h"] / 2) - cy) < a["h"] * 0.6], key=lambda w: w["x"])
        if line_pattern and not re.search(line_pattern, " ".join(w["text"] for w in line), re.I):
            continue
        box = (min(w["x"] for w in line), min(w["y"] for w in line),
               max(w["x"] + w["w"] for w in line), max(w["y"] + w["h"] for w in line))
        if box not in out:
            out.append(box)
    return out or None


def line_above(img, box, max_up=220):
    """boite de la ligne d'encre situee juste au-dessus de box."""
    x0, y0, x1, y1 = box
    g = img[:, :, :].mean(axis=2).astype(np.float32)
    band = g[max(0, y0 - max_up):y0 - 2, 60:1020]
    bg = gaussian_filter(maximum_filter(band, size=25), 6)
    rows = ((bg - band) > 45).sum(axis=1) > 0
    idx = np.where(rows)[0]
    if not len(idx):
        return None
    bottom = idx[-1]
    top = bottom
    while top - 1 >= 0 and rows[top - 1]:
        top -= 1
    a = max(0, y0 - max_up)
    return (60, a + top, 1020, a + bottom + 1)


def ink_box(img, box, pad=14):
    """boite exacte de l'encre autour de la boite OCR."""
    x0, y0, x1, y1 = box
    x0, y0, x1, y1 = max(0, x0 - pad), max(0, y0 - pad), min(W, x1 + pad), min(H, y1 + pad)
    g = img[y0:y1, x0:x1].mean(axis=2)
    bg = gaussian_filter(maximum_filter(g, size=25), 6)
    ink = (bg - g) > 45
    ys, xs = np.where(ink)
    return (x0 + xs.min(), y0 + ys.min(), x0 + xs.max() + 1, y0 + ys.max() + 1)


def render(text, f, color=None, with_offset=False):
    """masque d'encre (float 0..1) du texte, recadre sur son encre ;
    avec_offset : + position de l'encre par rapport a l'origine du texte."""
    l, t, r, b = f.getbbox(text)
    im = Image.new("L", (r - l + 4, b - t + 4), 0)
    ox, oy = 2 - l, 2 - t
    ImageDraw.Draw(im).text((ox, oy), text, font=f, fill=255)
    m = np.asarray(im, np.float32) / 255.0
    ys, xs = np.where(m > 0.04)
    crop = m[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    return (crop, xs.min() - ox, ys.min() - oy) if with_offset else crop


def fit_font(img, ib, kind, original):
    """taille (et graisse) qui reproduisent l'encre mesuree du texte d'origine."""
    x0, y0, x1, y1 = ib
    target_w = x1 - x0
    g = img[y0:y1, x0:x1].mean(axis=2)
    bg = np.percentile(img[max(0, y0 - 30):y0 - 4, x0:x1].mean(axis=2), 50) if y0 > 40 else 235
    density = np.clip((bg - g) / max(1, bg - g.min()), 0, 1).mean()
    best = None
    for weight in ([350, 400, 450, 500, 550] if kind == "sans" else [400]):
        size = 40.0
        for _ in range(6):
            m = render(original, font(kind, size, weight), None)
            size *= target_w / m.shape[1]
        m = render(original, font(kind, size, weight), None)
        err = abs(m.mean() - density)
        if best is None or err < best[0]:
            best = (err, size, weight, m.shape)
    return best[1], best[2]


def plan_paper(frame, box, margin=6):
    """une fois par ligne : bande de papier vide voisine + eclairage local de la zone
    (texte retire par un filtre de rang), ramene au niveau moyen du papier."""
    from scipy.ndimage import percentile_filter
    x0, y0, x1, y1 = box
    h = y1 - y0
    best = None
    for dy in list(range(-h - margin, -3 * h - margin, -4)) + list(range(h + margin, 3 * h + margin, 4)):
        a, b = y0 + dy, y1 + dy
        if a < 0 or b > H:
            continue
        score = frame[a:b, x0:x1].mean(axis=2).std()
        if best is None or score < best[0]:
            best = (score, dy)
    dy = best[1]
    clean = frame[y0 + dy:y1 + dy, x0:x1].astype(np.float32)
    region = frame[y0:y1, x0:x1].astype(np.float32)
    light = np.empty_like(region)
    for c in range(3):
        k = (min(h, 41), 41)
        lc = gaussian_filter(percentile_filter(region[..., c], 75, size=k), 8)
        ref = gaussian_filter(percentile_filter(clean[..., c], 75, size=k), 8)
        light[..., c] = lc + float(clean[..., c].mean() - ref.mean())
    return dict(dy=dy, light=light)


def paper_patch(frame, box, pp):
    """papier de la boite pour cette image : eclairage fixe + grain courant voisin."""
    x0, y0, x1, y1 = box
    clean = frame[y0 + pp["dy"]:y1 + pp["dy"], x0:x1].astype(np.float32)
    grain = clean - gaussian_filter(clean, (6, 6, 0))
    return np.clip(pp["light"] + grain, 0, 255)


def opacity(frame, ib, ref_ink):
    x0, y0, x1, y1 = ib
    g = frame[y0:y1, x0:x1].mean(axis=2).astype(np.float32)
    bg = gaussian_filter(maximum_filter(g, size=25), 6)
    return float(np.clip(np.clip(bg - g, 0, None).mean() / ref_ink, 0, 1))


def plan_job(path, items):
    """mesure chaque ligne a remplacer sur une image de reference."""
    plans = []
    for it in items:
        ref = grab(path, it["ref_t"])
        if it.get("above"):
            anchor = find_line(ref, it["above"], line_pattern=None)
            boxes = [line_above(ref, ink_box(ref, anchor[0]))] if anchor else None
        else:
            boxes = find_line(ref, it["pattern"], it.get("line", r"gram|egr"))
        if not boxes:
            sys.exit(f"{path} : ligne introuvable « {it['pattern']} » a {it['ref_t']}s")
        for k, box in enumerate(boxes):
            if "index" in it and k != it["index"]:
                continue
            ib = ink_box(ref, box)
            if it.get("mode") == "truncate":
                # chasse fixe : la largeur est proportionnelle au nombre de signes
                x0, y0, x1, y1 = ib
                cut = x0 + (x1 - x0) * (len(it["new"]) + 0.5) / len(it["original"])
                gg = ref[y0:y1, x0:x1].mean(axis=2).astype(np.float32)
                ref_ink = np.clip(gaussian_filter(maximum_filter(gg, size=25), 6) - gg, 0, None).mean()
                er = (int(cut), max(0, y0 - 6), min(W, x1 + 8), min(H, y1 + 6))
                plans.append(dict(item=it, ib=ib, erase=er, paper=plan_paper(ref, er),
                                  mask=None, ref_ink=ref_ink, t0=it["t0"], t1=it["t1"]))
                print(f"   « {it['new']} » : fin de ligne effacee a partir de x={int(cut)}", flush=True)
                continue
            size, weight = fit_font(ref, ib, it["font"], it["original"])
            x0, y0, x1, y1 = ib
            g = ref[y0:y1, x0:x1].astype(np.float32)
            gg = g.mean(axis=2)
            color = np.median(g[gg <= np.percentile(gg, 4)], axis=0)
            bgm = gaussian_filter(maximum_filter(gg, size=25), 6)
            ref_ink = np.clip(bgm - gg, 0, None).mean()
            f = font(it["font"], size, weight)
            new, nx, ny = render(it["new"], f, with_offset=True)
            _, ox, oy = render(it["original"], f, with_offset=True)
            # meme origine (donc meme ligne de base et meme marge gauche) que l'original
            gx, gy = x0 - ox, y0 - oy
            pos = (int(round(gx + nx)), int(round(gy + ny)))
            erase = (max(0, x0 - 8), max(0, min(y0, pos[1]) - 8),
                     min(W, max(x1, pos[0] + new.shape[1]) + 10), min(H, max(y1, pos[1] + new.shape[0]) + 10))
            plans.append(dict(item=it, ib=ib, erase=erase, paper=plan_paper(ref, erase), size=size, weight=weight, color=color,
                              ref_ink=ref_ink, mask=new, pos=pos, t0=it["t0"], t1=it["t1"]))
            print(f"   « {it['new']} » : boite {ib}, police {it['font']} {size:.1f}px "
                  f"graisse {weight}, couleur {color.astype(int).tolist()}", flush=True)
    return plans


def process(src, dst, plans, fps=30):
    dec = subprocess.Popen(["ffmpeg", "-v", "error", "-i", src, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                           stdout=subprocess.PIPE)
    enc = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                            "-r", str(fps), "-i", "-", "-i", src, "-map", "0:v", "-map", "1:a?", "-c:a", "copy",
                            "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
                            "-movflags", "+faststart", dst], stdin=subprocess.PIPE)
    n = 0
    fs = W * H * 3
    while True:
        buf = dec.stdout.read(fs)
        if len(buf) < fs:
            break
        t = n / fps
        frame = None
        for p in plans:
            if not (p["t0"] <= t <= p["t1"]):
                continue
            if frame is None:
                frame = np.frombuffer(buf, np.uint8).reshape(H, W, 3).copy()
            a = opacity(frame, p["ib"], p["ref_ink"])
            if a < 0.02:
                continue
            ex0, ey0, ex1, ey1 = p["erase"]
            frame[ey0:ey1, ex0:ex1] = paper_patch(frame, p["erase"], p["paper"]).astype(np.uint8)
            if p["mask"] is None:
                continue
            m = p["mask"] * a
            x, y = p["pos"]
            h, w = m.shape
            reg = frame[y:y + h, x:x + w].astype(np.float32)
            reg = reg * (1 - m[..., None]) + p["color"][None, None, :] * m[..., None]
            frame[y:y + h, x:x + w] = np.clip(reg, 0, 255).astype(np.uint8)
        enc.stdin.write(frame.tobytes() if frame is not None else buf)
        n += 1
    enc.stdin.close()
    enc.wait()
    dec.wait()
    return n


if __name__ == "__main__":
    jobs = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    only = sys.argv[2:] or None
    for job in jobs:
        if only and not any(o in job["src"] for o in only):
            continue
        print(Path(job["src"]).name, flush=True)
        plans = plan_job(job["src"], job["items"])
        n = process(job["src"], job["dst"], plans)
        print(f"   -> {Path(job['dst']).name} ({n} images)", flush=True)

#!/usr/bin/env python3
"""« strategie » -> « algorithme » : insere les 6 phrases reenregistrees.

Entree : voix_main.mp3 + words_scribe.json (prise d'origine)
         algo_take1.mp3 + ses timings Scribe (ci-dessous)
Sortie : voix_main_algo.wav + words_scribe_algo.json, que assemble_voix.py
         utilise a la place de la prise d'origine quand ils existent.
"""
import json
import subprocess
import unicodedata
import wave
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
A = HERE.parent / "assets"
SR = 48000

# Scribe v1, generation kmUH0R3F8iA1HgJ49oXg (prise 1, 18,29 s)
NEW = [
    [["Un", .04, .14], ["algorithme", .22, .64], ["automatique", .66, 1.14], ["sur", 1.2, 1.34], ["l'euro-dollar,", 1.38, 2.0],
     ["le", 2.32, 2.36], ["marche", 2.44, 2.72], ["le", 2.76, 2.8], ["plus", 2.92, 3.12], ["echange", 3.2, 3.6], ["au", 3.62, 3.66], ["monde.", 3.74, 4.0]],
    [["Il", 4.48, 4.58], ["lit", 4.62, 4.7], ["les", 4.74, 4.86], ["chiffres,", 4.94, 5.28], ["pas", 5.52, 5.6], ["les", 5.62, 5.7], ["rumeurs.", 5.74, 6.14]],
    [["Il", 6.58, 6.62], ["applique", 6.68, 6.92], ["ses", 6.96, 7.06], ["regles", 7.1, 7.38], ["sans", 7.44, 7.6], ["emotion,", 7.66, 8.1],
     ["du", 8.38, 8.46], ["lundi", 8.52, 8.94], ["au", 8.98, 9.02], ["vendredi.", 9.08, 9.52]],
    [["Et", 9.98, 10.08], ["chaque", 10.16, 10.36], ["position", 10.4, 10.8], ["de", 10.82, 10.88], ["l'algorithme", 10.92, 11.4], ["se", 11.52, 11.62],
     ["copie", 11.66, 11.88], ["automatiquement", 12.04, 12.7], ["chez", 12.72, 12.86], ["toi.", 12.9, 13.08]],
    [["Pendant", 13.62, 13.8], ["que", 13.84, 13.92], ["tu", 13.96, 14.04], ["vivais", 14.08, 14.28], ["ta", 14.32, 14.42], ["journee,", 14.46, 14.76],
     ["ton", 15.06, 15.18], ["algorithme", 15.24, 15.64], ["a", 15.66, 15.74], ["suivi", 15.78, 16.0], ["ses", 16.059, 16.18], ["regles.", 16.219, 16.5]],
    [["Il", 16.9, 16.98], ["garde", 17.1, 17.38], ["la", 17.42, 17.5], ["discipline.", 17.52, 18.02]],
]
# phrases d'origine a remplacer : (premier mot, son occurrence, dernier mot)
OLD = [("Une", 0, "monde."), ("Elle", 0, "rumeurs."), ("Elle", 1, "vendredi."),
       ("et", 1, "toi."), ("Pendant", 1, "regles."), ("elle", 0, "discipline.")]


def decode(p):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(p), "-f", "s16le", "-ac", "1", "-ar", str(SR), "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype="<i2").astype(np.float64) / 32768


def rms(x):
    return np.sqrt(np.mean(x ** 2) + 1e-12)


def fade(x, ms=10):
    n = int(SR * ms / 1000)
    x = x.copy()
    x[:n] *= np.linspace(0, 1, n)
    x[-n:] *= np.linspace(1, 0, n)
    return x


def main():
    meta = json.loads((HERE / "words_scribe.json").read_text(encoding="utf-8"))
    words = [list(w) for w in meta["words"]]
    src, take = decode(A / "voix_main.mp3"), decode(A / "algo_take1.mp3")

    def find(w, occ, after=0):
        hits = [i for i, x in enumerate(words) if x[0] == w and i >= after]
        return hits[occ]

    spans = []
    for (w0, occ, w1), new in zip(OLD, NEW):
        i0 = find(w0, occ)
        i1 = find(w1, 0, i0)
        spans.append((i0, i1, new))
    spans.sort(key=lambda s: words[s[0]][1])

    out, out_words, t_src, shift = [], [], 0.0, 0.0
    for i0, i1, new in spans:
        a, b = words[i0][1] - 0.05, words[i1][2] + 0.08          # trou dans la prise d'origine
        na, nb = max(0.0, new[0][1] - 0.05), new[-1][2] + 0.10   # phrase neuve, avec sa fin de souffle
        old_seg, new_seg = src[int(a * SR):int(b * SR)], take[int(na * SR):int(nb * SR)]
        new_seg = fade(new_seg * rms(old_seg) / rms(new_seg))     # meme niveau que la phrase remplacee

        # mots avant ce remplacement, decales
        for w in words:
            if t_src <= w[1] < a:
                out_words.append([w[0], round(w[1] + shift, 3), round(w[2] + shift, 3)])
        out.append(fade(src[int(t_src * SR):int(a * SR)]) if t_src > 0 else src[:int(a * SR)])
        start = sum(len(x) for x in out) / SR
        out.append(new_seg)
        for w, s, e in new:
            out_words.append([w, round(start + s - na, 3), round(start + e - na, 3)])
        shift = start + len(new_seg) / SR - b
        t_src = b

    for w in words:
        if w[1] >= t_src:
            out_words.append([w[0], round(w[1] + shift, 3), round(w[2] + shift, 3)])
    out.append(src[int(t_src * SR):])
    y = np.concatenate(out)

    with wave.open(str(A / "voix_main_algo.wav"), "wb") as f:
        f.setnchannels(1); f.setsampwidth(2); f.setframerate(SR)
        f.writeframes((np.clip(y, -1, 1) * 32767).astype("<i2").tobytes())
    meta2 = dict(meta, words=out_words, duration=len(y) / SR,
                 note=meta["note"] + " | « strategie » -> « algorithme » : 6 phrases remplacees (prise algo_take1).")
    (HERE / "words_scribe_algo.json").write_text(json.dumps(meta2, ensure_ascii=False), encoding="utf-8")
    print(f"voix_main_algo.wav : {len(y)/SR:.2f}s (avant {len(src)/SR:.2f}s), {len(out_words)} mots (avant {len(words)})")


if __name__ == "__main__":
    main()

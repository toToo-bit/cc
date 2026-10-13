#!/usr/bin/env python3
"""Partition orchestrale « cinema », jouee avec de vrais instruments echantillonnes.

Banque : FluidR3Mono_GM.sf3 (licence MIT, distribuee avec MuseScore).
Rendu hors ligne avec tinysoundfont, puis reverberation de grande salle.
La partition suit la voix : memes reperes que motion.js et sfx.py
(S(i) = debut de la phrase i, T(i, mot) = instant du mot).

  python3 -I src/score.py [ig] [tt]      -> assets/score_<v>.wav
"""
import json
import sys
import unicodedata
import wave
from pathlib import Path

import numpy as np
import tinysoundfont
from scipy.signal import fftconvolve, butter, sosfilt

HERE = Path(__file__).resolve().parent
SR = 48000
SF = Path(sys.argv[0]).resolve().parent.parent / "assets" / "FluidR3Mono_GM.sf3"

# canaux -> programme General MIDI
CH = {
    "low": (0, 48), "high": (1, 49), "choir": (2, 52), "horn": (3, 60), "piano": (4, 0),
    "ost": (5, 45), "timp": (6, 47), "trem": (7, 44), "brass": (8, 61), "cello": (10, 42),
    "harp": (11, 46), "celesta": (12, 8), "flute": (13, 73), "vibes": (14, 11), "taiko": (15, 116),
}

CHORDS = {
    "Dm": (38, [50, 57, 62, 65]), "Bb": (34, [46, 53, 58, 62]), "Gm": (43, [50, 55, 58, 62]),
    "A": (45, [49, 52, 57, 61]), "F": (41, [53, 57, 60, 65]), "C": (36, [48, 55, 60, 64]),
    "Am": (45, [48, 52, 57, 60]), "Dsus": (38, [50, 57, 62, 64]),
}


def load_beats(variant):
    data = json.loads((HERE / f"beats_{variant}.json").read_text(encoding="utf-8"))
    B = data["beats"]

    def nrm(w):
        w = unicodedata.normalize("NFD", w.lower())
        w = "".join(c for c in w if unicodedata.category(c) != "Mn")
        return "".join(c for c in w if c.isalnum() or c in "'’-")

    S = lambda i: B[i]["start"]
    E = lambda i: B[i]["end"]

    def T(i, w):
        n = nrm(w)
        for x in B[i]["words"]:
            if nrm(x["w"]).startswith(n):
                return x["s"]
        return S(i)

    return data["duration"], B, S, E, T


def compose(variant):
    """Chaque chapitre a sa couleur d'orchestre, son rythme, et ses silences."""
    dur, B, S, E, T = load_beats(variant)
    end = dur + 3.5
    ev = []

    def note(t, ch, key, vel, d):
        c = CH[ch][0]
        ev.append((max(0, t), 1, c, key, int(np.clip(vel, 1, 127))))
        ev.append((max(0, t) + d, 0, c, key, 0))

    def chord(t, ch, keys, vel, d):
        for k in keys:
            note(t, ch, k, vel, d)

    def swell(ch, t0, t1, v0, v1):
        c = CH[ch][0]
        n = max(2, int((t1 - t0) / 0.05))
        for i in range(n + 1):
            u = i / n
            ev.append((t0 + (t1 - t0) * u, 2, c, 11, int(v0 + (v1 - v0) * u)))

    plan = [
        (0.0, "Dm"), (S(2), "Bb"), (S(6), "Gm"), (S(8), "Dm"), (S(11), "Bb"), (S(13), "A"),
        (S(15), "Dm"), (S(17), "Gm"), (S(19), "Bb"), (S(22), "F"), (S(24), "C"),
        (S(27), "A"), (S(28), "F"), (S(31), "C"), (S(34), "F"), (S(38), "Bb"),
        (S(41), "F"), (S(45), "Am"), (S(46), "F"), (S(49), "C"), (S(51), "Bb"),
        (S(54), "F"), (S(58), "C"), (S(60), "F"), (S(61) - 0.2, "F"),
    ]
    harm = lambda t: [n for (t0, n) in plan if t0 <= t][-1]

    # intensite : plus de relief, avec de vrais creux
    def inten(t):
        pts = [(0, .6), (3.4, .7), (4.3, .3), (10, .38), (12.2, .55), (14.4, .35), (20, .55), (27, .85),
               (28.7, .2), (29.4, .9), (30.5, .3), (38.4, .15), (39.5, .3), (41, .3), (47, .5), (51.5, .2),
               (52.6, .45), (60, .55), (62.8, .9), (66, .55), (73, .45), (79, .6), (85.5, .3), (100, .35),
               (103, .45), (111, .4), (113.5, .6), (118, .4), (128.6, .2), (136, .45), (138.5, .75),
               (142, .45), (S(61) - 0.2, .8), (end, .6)]
        xs, ys = zip(*pts)
        return float(np.interp(t, xs, ys))

    def bed(t0, t1, layers, vel=1.0):
        """nappe d'accords sur [t0, t1] avec les couches demandees."""
        cuts = [t0] + [x for (x, _) in plan if t0 < x < t1] + [t1]
        for a, b in zip(cuts, cuts[1:]):
            root, voic = CHORDS[harm(a + 0.01)]
            I = inten(a + 0.3) * vel
            d = b - a + 0.4
            if "low" in layers:
                note(a, "low", root, 45 + 50 * I, d); note(a, "low", root + 12, 35 + 45 * I, d)
            if "cello" in layers:
                note(a, "cello", root + 12, 40 + 45 * I, d)
            if "high" in layers:
                chord(a + 0.05, "high", voic[1:], 30 + 55 * I, d)
            if "choir" in layers:
                chord(a, "choir", [v + 12 for v in voic[1:3]], 35 + 45 * I, d)

    # ---------------------------------------------------------------- 1 · accroche
    bed(0, S(2) - 0.1, {"low"})
    note(0.0, "timp", 38, 100, 2.0)
    for k, key in enumerate([74, 77, 81, 77]):
        note(0.3 + k * 0.55, "celesta", key, 70, 1.2)
    for k in range(10):
        note(T(1, "expres") - 1.0 + k * 0.1, "timp", 38, 40 + k * 7, 0.2)
    note(T(1, "expres") - 0.05, "timp", 38, 127, 2.5)
    chord(T(1, "expres") - 0.05, "brass", [38, 50, 57], 105, 1.8)

    # ---------------------------------------------------------------- 2 · savane : harpe, flute, choeur
    bed(S(2), S(7) - 0.2, {"choir"}, 0.9)
    t, k = S(2) + 0.2, 0
    while t < S(7) - 0.4:                        # harpe en arpeges lents
        voic = CHORDS[harm(t)][1]
        note(t, "harp", voic[k % 4] + 12, 55, 1.4)
        t += 0.42; k += 1
    for k, (key, d, o) in enumerate([(74, 0.9, 0), (81, 0.9, 0.9), (79, 0.5, 1.8), (77, 1.4, 2.3), (74, 1.8, 3.7)]):
        note(S(2) + 0.6 + o, "flute", key, 78, d)
    note(S(4), "taiko", 45, 70, 0.6); note(S(4) + 0.35, "taiko", 45, 60, 0.6)   # le groupe en marche
    note(S(5), "timp", 43, 95, 0.8)
    chord(S(7) - 0.15, "trem", [50, 56, 62], 95, 1.7)                          # tout bascule
    note(T(7, "catastrophique") - 0.05, "timp", 38, 115, 1.8)
    bed(S(7) - 0.15, S(8), {"low"}, 1.0)

    # ---------------------------------------------------------------- 3 · pieges : ostinato qui evolue
    t, k = S(8) + 0.1, 0
    pats = {0: [0, 0, 12, 0, 7, 0, 12, 7], 1: [0, 12, 7, 12, 0, 12, 7, 15], 2: [0, 3, 7, 12, 7, 3, 0, -2]}
    while t < S(14) - 0.6:
        sec = 0 if t < S(11) else 1 if t < S(13) else 2
        root = CHORDS[harm(t)][0] + 12
        step = 60 / (96 if sec < 2 else 112) / 2      # accelere pour la vengeance
        note(t, "ost", root + pats[sec][k % 8], (50 + 50 * inten(t)) * (1.25 if k % 8 == 0 else 1), 0.22)
        if sec >= 1 and k % 4 == 0:
            note(t, "cello", root - 12, 60 + 30 * inten(t), step * 3.5)
        t += step; k += 1
    bed(S(9), S(11), {"high"}, 0.9)
    swell("high", S(9), T(10, "haut"), 60, 120)
    chord(T(10, "haut") - 0.05, "brass", [45, 52, 57], 95, 1.0)
    note(T(10, "haut") - 0.05, "timp", 45, 110, 1.2)
    chord(S(11), "trem", [46, 53, 58], 70, E(11) - S(11) + 0.4)
    chord(S(12) + 0.2, "vibes", [69, 73, 76], 60, 1.8)                         # le gain qui file, scintillant
    for k in range(8):
        note(T(13, "mises") + k * 0.14, "taiko", 45, 50 + k * 9, 0.3)
    # silence brutal juste avant « tu perds plus »… puis le coup
    note(T(14, "perds") - 0.05, "timp", 38, 127, 2.4)
    note(T(14, "perds") - 0.05, "taiko", 41, 120, 1.2)
    chord(T(14, "perds") - 0.05, "brass", [38, 45, 50, 53], 115, 1.8)
    bed(T(14, "perds"), S(15) - 0.1, {"low", "cello"}, 0.8)

    # ---------------------------------------------------------------- 4 · journee : horloge, celesta, violoncelle seul
    t = S(15)
    while t < S(18) - 0.2:
        note(t, "piano", 81 if int(round((t - S(15)) / 0.5)) % 2 else 76, 46, 0.35)
        t += 0.5
    for k, key in enumerate([62, 60, 58, 57, 55, 57]):                        # violoncelle qui s'epuise
        note(S(16) + k * 0.9, "cello", key - 12, 70 - k * 6, 1.2)
    for k in range(4):
        note(S(17) + k * 0.22, "celesta", 84 - k * 5, 55, 0.6)
    note(S(18) - 0.1, "low", 26, 65, 3.0)
    chord(S(18), "high", [74, 77], 35, 2.6)

    # ---------------------------------------------------------------- 5 · la methode : flute + cordes legeres, silence « a froid »
    bed(S(19), S(22) - 0.1, {"high", "cello"}, 0.8)
    for k, key in enumerate([62, 65, 69, 67, 65, 64, 62]):
        note(S(19) + 0.2 + k * 0.45, "piano", key + 12, 60, 1.2)
    t, k = S(20), 0
    while t < S(22) - 0.3:                       # cordes pincees discretes, en 3 temps
        root = CHORDS[harm(t)][0] + 24
        note(t, "ost", root + [0, 7, 12][k % 3], 45, 0.2)
        t += 0.38; k += 1
    swell("high", S(21), T(22, "avant"), 60, 120)
    chord(T(22, "avant") - 0.05, "brass", [41, 53, 57, 60], 95, 1.8)
    note(T(22, "avant") - 0.05, "timp", 41, 105, 1.5)
    # « a froid » : tout s'arrete, ne reste que le celesta glace
    for k, key in enumerate([88, 91, 96, 91]):
        note(S(23) + k * 0.18, "celesta", key, 60, 1.4)
    bed(S(24), S(27) - 0.1, {"low", "high"}, 0.9)
    for w in ["tout", "reuni"]:
        note(T(24, w), "vibes", 84, 62, 0.9)
    note(T(24, "agit") - 0.2, "vibes", 84, 62, 0.9)
    chord(T(24, "agit"), "harp", [65, 69, 72, 77], 70, 1.5)
    note(S(25), "cello", 34, 80, 1.6)                                          # on attend
    note(T(26, "posee"), "timp", 41, 85, 1.0)

    # ---------------------------------------------------------------- 6 · Compound Capital
    rise0, hit = T(28, "compound") - 3.0, T(28, "compound") - 0.12
    chord(S(27), "trem", [45, 49, 52], 55, hit - S(27))
    for k in range(int((hit - rise0) / 0.1)):
        note(rise0 + k * 0.1, "timp", 41, 35 + int(85 * k / ((hit - rise0) / 0.1)), 0.15)
    swell("trem", S(27), hit, 50, 127)
    note(hit, "timp", 29, 127, 3.0)
    note(hit, "taiko", 41, 110, 1.5)
    chord(hit, "brass", [41, 53, 57, 60, 65], 115, 3.2)
    chord(hit, "choir", [65, 69, 72], 85, 4.0)
    bed(hit, S(29), {"low", "high"}, 1.0)
    for k, (key, d) in enumerate([(65, 0.8), (72, 0.8), (70, 0.5), (69, 1.2), (65, 1.6)]):
        note(hit + 0.4 + [0, .8, 1.6, 2.1, 3.3][k], "horn", key - 12, 92, d)
    # l'euro-dollar et les chiffres : pulsation de taiko + spiccato
    t, k = S(29), 0
    while t < E(31):
        root = CHORDS[harm(t)][0] + 12
        note(t, "ost", root + [0, 7, 12, 7][k % 4], 50 + 30 * inten(t), 0.2)
        if k % 4 == 0:
            note(t, "taiko", 45, 55 + 30 * inten(t), 0.4)
        t += 60 / 104 / 2; k += 1
    bed(S(29), E(31), {"low"}, 0.7)
    for k in range(5):                             # L M M J V : vibraphone en escalier
        note(T(32, "lundi") + k * 0.2, "vibes", [72, 74, 76, 77, 81][k], 70, 0.6)
    bed(S(32), S(33), {"high", "cello"}, 0.8)
    # « rien a faire » : l'orchestre se pose, harpe seule
    for k in range(10):
        voic = CHORDS[harm(S(33) + k * 0.5)][1]
        note(S(33) + k * 0.5, "harp", voic[k % 4] + 12, 50, 1.2)

    # ---------------------------------------------------------------- 7 · concretement : marimba et vibraphone
    t, k = S(34), 0
    while t < E(40):
        voic = CHORDS[harm(t)][1]
        inst = "vibes" if t < S(38) else "piano"
        note(t, inst, voic[[0, 2, 1, 3][k % 4]] + 12, 42 + 20 * inten(t), 0.8)
        t += 60 / 88 / 2; k += 1
    bed(S(36), S(38), {"cello"}, 0.7)
    bed(S(38), E(40), {"high", "low"}, 0.75)
    chord(T(37, "l'acces"), "harp", [72, 77, 81], 70, 1.0)
    chord(S(39) + 0.2, "brass", [41, 48, 53], 70, 1.2)                          # le cadenas : solide

    # ---------------------------------------------------------------- 8 · paye sur les gains : pizz qui montent
    for k in range(8):
        note(S(41) + k * 0.28, "ost", [53, 55, 57, 60, 62, 65, 67, 69][k], 60, 0.25)
    bed(S(42), E(44), {"high", "cello"}, 0.8)
    for k in range(4):
        note(T(42, "gains") + k * 0.24, "celesta", [84, 88, 91, 96][k], 55, 0.8)
    chord(T(44, "progresse") - 0.1, "horn", [53, 57, 60], 80, 2.0)

    # ---------------------------------------------------------------- 9 · la preuve : suspense, puis lumiere
    chord(S(45), "trem", [57, 60, 64], 60, E(45) - S(45))
    for k in range(6):
        note(S(45) + k * 0.4, "timp", 33, 45 + k * 6, 0.3)                       # pouls sourd
    note(T(45, "capture") + 0.1, "timp", 45, 100, 1.0)
    bed(S(46), E(48), {"low", "high", "choir"}, 0.85)
    for k, key in enumerate([72, 76, 79, 84]):
        note(T(46, "verifiable") + k * 0.2, "harp", key, 65, 1.4)
    t, k = S(49), 0
    while t < E(50):
        note(t, "ost", [48, 55, 60, 55][k % 4], 48, 0.2)
        t += 0.32; k += 1
    note(T(50, "presses"), "timp", 36, 80, 0.8)

    # ---------------------------------------------------------------- 10 · imagine : piano seul, puis tout revient
    for k, key in enumerate([65, 69, 72, 70, 69, 67, 65, 64, 65]):
        note(S(51) + 0.2 + k * 0.55, "piano", key + 12, 54, 1.8)
    bed(S(53), S(55), {"cello"}, 0.6)
    bed(S(54), E(57), {"high"}, 0.75)
    for bi, w in [(55, "stress"), (56, "ecran"), (57, "toi")]:
        note(T(bi, w), "harp", 77, 70, 1.2)
    bed(S(58), S(60), {"low", "high", "choir", "cello"}, 1.0)
    swell("high", S(58), E(59), 80, 125)
    chord(S(58), "horn", [53, 60, 65], 85, E(59) - S(58) + 0.5)

    # ---------------------------------------------------------------- 11 · appel a l'action et final
    for k in range(int((S(61) - S(60)) / 0.42)):
        voic = CHORDS["F"][1]
        note(S(60) + k * 0.42, "harp", voic[k % 4] + 12, 50, 1.2)
    chord(S(60), "high", [65, 69, 72], 45, S(61) - S(60))
    rise0, hit = S(61) - 2.2, S(61) - 0.2
    for k in range(int((hit - rise0) / 0.1)):
        note(rise0 + k * 0.1, "timp", 41, 35 + int(80 * k / ((hit - rise0) / 0.1)), 0.15)
    note(hit, "timp", 29, 127, 4.0)
    note(hit, "taiko", 41, 115, 1.5)
    chord(hit, "brass", [29, 41, 53, 57, 60, 65], 115, 4.0)
    chord(hit, "choir", [65, 69, 72, 77], 90, 4.5)
    chord(hit, "high", [77, 81, 84], 80, 4.5)
    chord(hit, "low", [29, 41], 95, 4.5)
    note(hit + 4.2, "piano", 89, 50, 3.0)                                     # derniere note, seule

    return ev, end, inten


def render(ev, end):
    syn = tinysoundfont.Synth(samplerate=SR, gain=-3)
    sfid = syn.sfload(str(SF))
    for ch, (c, prog) in CH.items():
        syn.program_select(c, sfid, 0, prog)
        syn.control_change(c, 11, 100)
        syn.control_change(c, 7, 110)
    ev = sorted(ev, key=lambda e: (e[0], e[1]))
    out, cur = [], 0
    for t, typ, c, a, b in ev:
        n = int(t * SR) - cur
        if n > 0:
            out.append(np.frombuffer(syn.generate(n), dtype=np.float32).reshape(-1, 2))
            cur += n
        if typ == 1:
            syn.noteon(c, a, b)
        elif typ == 0:
            syn.noteoff(c, a)
        else:
            syn.control_change(c, a, b)
    n = int(end * SR) - cur
    if n > 0:
        out.append(np.frombuffer(syn.generate(n), dtype=np.float32).reshape(-1, 2))
    return np.concatenate(out).astype(np.float64)


def hall(x, seconds=2.8, wet=0.32):
    """reverberation de grande salle : reponse impulsionnelle synthetique."""
    rng = np.random.default_rng(9)
    n = int(seconds * SR)
    t = np.arange(n) / SR
    ir = rng.standard_normal((n, 2)) * np.exp(-t / (seconds / 6.9))[:, None]
    ir = sosfilt(butter(2, 6000, fs=SR, output="sos"), ir, axis=0)   # les aigus s'eteignent plus vite
    ir[: int(0.02 * SR)] *= np.linspace(0, 1, int(0.02 * SR))[:, None]  # pre-delai doux
    ir /= np.sqrt((ir ** 2).sum(axis=0))
    wetsig = np.stack([fftconvolve(x[:, i], ir[:, i])[: len(x)] for i in range(2)], axis=1)
    return (1 - wet) * x + wet * wetsig * 3.0


def main(variant):
    ev, end, inten = compose(variant)
    x = render(ev, end)
    x = hall(x)
    # dynamique de cinema : ~12 dB entre les passages calmes et les sommets
    t = np.arange(len(x)) / SR
    I = np.interp(t, np.arange(0, end, 0.05), [inten(u) for u in np.arange(0, end, 0.05)])
    x *= (10 ** ((-14 + 14 * np.clip((I - 0.25) / 0.75, 0, 1) ** 1.3) / 20))[:, None]
    # fondus d'entree et de sortie
    t = np.arange(len(x)) / SR
    x *= np.clip(t / 0.3, 0, 1)[:, None] * np.clip((end - t) / 2.5, 0, 1)[:, None]
    x /= np.abs(x).max() + 1e-9
    x *= 0.8
    out = HERE.parent / "assets" / f"score_{variant}.wav"
    with wave.open(str(out), "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((x * 32767).astype("<i2").tobytes())
    print(f"{out.name} : {len(x)/SR:.1f}s, {sum(1 for e in ev if e[1] == 1)} notes")


if __name__ == "__main__":
    for v in sys.argv[1:] or ["ig", "tt"]:
        main(v)

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
    "low": (0, 48),     # cordes (ensemble) graves
    "high": (1, 49),    # cordes lentes, aigues
    "choir": (2, 52),   # choeur « aah »
    "horn": (3, 60),    # cor
    "piano": (4, 0),    # piano
    "ost": (5, 45),     # cordes pincees (ostinato)
    "timp": (6, 47),    # timbales
    "trem": (7, 44),    # cordes en tremolo
    "brass": (8, 61),   # section de cuivres
    "cello": (10, 42),  # violoncelle
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
    dur, B, S, E, T = load_beats(variant)
    end = dur + 3.5
    ev = []  # (temps, type, canal, a, b)  type: on/off/cc

    def note(t, ch, key, vel, d):
        c = CH[ch][0]
        ev.append((max(0, t), 1, c, key, int(np.clip(vel, 1, 127))))
        ev.append((max(0, t) + d, 0, c, key, 0))

    def chord(t, ch, keys, vel, d):
        for k in keys:
            note(t, ch, k, vel, d)

    def swell(ch, t0, t1, v0, v1):
        """crescendo/decrescendo par l'expression (CC11)."""
        c = CH[ch][0]
        n = max(2, int((t1 - t0) / 0.05))
        for i in range(n + 1):
            u = i / n
            ev.append((t0 + (t1 - t0) * u, 2, c, 11, int(v0 + (v1 - v0) * u)))

    # ---- grille harmonique (memes reperes que music.py)
    plan = [
        (0.0, "Dm"), (S(2), "Bb"), (S(6), "Gm"), (S(8), "Dm"), (S(11), "Bb"), (S(13), "A"),
        (S(15), "Dm"), (S(17), "Gm"), (S(19), "Bb"), (S(22), "F"), (S(24), "C"),
        (S(27), "A"), (S(28), "F"), (S(31), "C"), (S(34), "F"), (S(38), "Bb"),
        (S(41), "F"), (S(45), "Am"), (S(46), "F"), (S(49), "C"), (S(51), "Bb"),
        (S(54), "F"), (S(58), "C"), (S(60), "F"), (S(61) - 0.2, "F"),
    ]

    # intensite generale (0..1) par chapitre : guide les velocites
    def inten(t):
        pts = [(0, .55), (4, .45), (11, .4), (14.5, .55), (26, .8), (30, .6), (31, .35), (38.6, .25),
               (41, .4), (48, .55), (60, .6), (62.5, .95), (66, .65), (85.5, .45), (103, .5), (111, .6),
               (122, .55), (128.6, .45), (138, .75), (142, .6), (S(61) - 0.2, 1.0), (end, .8)]
        xs, ys = zip(*pts)
        return float(np.interp(t, xs, ys))

    # ---- nappes de cordes : basse + accord, a chaque changement d'harmonie
    for i, (t0, name) in enumerate(plan):
        t1 = plan[i + 1][0] if i + 1 < len(plan) else end
        root, voic = CHORDS[name]
        d = t1 - t0 + 0.6               # leger tuilage
        I = inten(t0 + 0.5)
        note(t0, "low", root, 50 + 50 * I, d)
        note(t0, "low", root + 12, 40 + 45 * I, d)
        note(t0, "cello", root + 12, 45 + 40 * I, d)
        if I > 0.38:
            chord(t0 + 0.05, "high", voic[1:], 35 + 55 * I, d)

    # expression : respiration lente de l'orchestre, un peu plus haute aux temps forts
    for ch in ["low", "high", "cello"]:
        swell(ch, 0, 2.0, 70, 105)

    # ---- 1 · accroche : timbales et cuivres sur « expres »
    note(0.0, "timp", 38, 100, 2.0)
    for k in range(10):                         # roulement qui monte vers « expres »
        note(T(1, "expres") - 1.0 + k * 0.1, "timp", 38, 40 + k * 7, 0.2)
    note(T(1, "expres") - 0.05, "timp", 38, 127, 2.5)
    chord(T(1, "expres") - 0.05, "brass", [38, 50, 57], 110, 2.2)
    for k, key in enumerate([74, 77, 81, 77]):  # motif de piano, haut et froid
        note(0.3 + k * 0.55, "piano", key, 55, 1.5)

    # ---- 2 · savane : cor solo sur un choeur
    chord(S(2), "choir", [62, 65, 69], 55, S(7) - S(2))
    for k, (key, d) in enumerate([(62, 1.0), (69, 1.0), (67, 0.6), (65, 1.6), (62, 2.0)]):
        note(S(2) + 0.3 + sum(x[1] for x in [(62, 1.0), (69, 1.0), (67, 0.6), (65, 1.6), (62, 2.0)][:k]), "horn", key - 12, 80, d)
    note(S(5), "timp", 43, 95, 0.8)            # « agir vite »
    chord(T(7, "catastrophique") - 0.05, "trem", [50, 56, 62], 100, 1.6)   # dissonance (triton)
    note(T(7, "catastrophique") - 0.05, "timp", 38, 115, 1.8)

    # ---- 3 · pieges : ostinato pince qui pousse, tremolos sur les pertes
    beat = 60 / 96 / 2                        # croches a 96 bpm
    t = S(8) + 0.1
    pat = [0, 0, 12, 0, 7, 0, 12, 7]
    k = 0
    while t < E(14) + 0.3:
        name = [n for (tt0, n) in plan if tt0 <= t][-1]
        root = CHORDS[name][0] + 12
        acc = 1 + 0.3 * (k % 8 == 0)
        note(t, "ost", root + pat[k % 8], (55 + 50 * inten(t)) * acc, 0.25)
        t += beat
        k += 1
    swell("high", S(9), T(10, "haut"), 70, 120)
    note(T(10, "haut") - 0.05, "timp", 45, 110, 1.2)
    chord(S(11), "trem", [46, 53, 58], 75, E(11) - S(11) + 0.5)
    chord(S(12) + 0.2, "trem", [57, 61, 64], 70, E(12) - S(12))
    for k in range(8):                         # la pile qui grimpe : timbales en crescendo
        note(T(13, "mises") + k * 0.15, "timp", 45, 50 + k * 9, 0.2)
    note(T(14, "perds") - 0.05, "timp", 38, 127, 2.4)
    chord(T(14, "perds") - 0.05, "brass", [38, 45, 50, 53], 115, 1.8)

    # ---- 4 · journee : le piano egrene les heures
    t = S(15)
    while t < S(18) - 0.2:
        note(t, "piano", 81 if int((t - S(15)) / 0.5) % 2 else 76, 48, 0.4)
        t += 0.5
    note(S(18) - 0.1, "low", 26, 70, 3.0)      # la nuit : une note tres grave
    chord(S(18), "high", [74, 77], 40, 2.6)

    # ---- 5 · la methode : le theme au piano, puis les cordes s'ouvrent
    motif = [62, 65, 69, 67, 65, 64, 62]
    for k, key in enumerate(motif):
        note(S(19) + k * 0.45, "piano", key + 12, 62, 1.2)
    swell("high", S(21), T(22, "avant"), 70, 120)
    chord(T(22, "avant") - 0.05, "brass", [41, 53, 57, 60], 100, 2.0)
    note(T(22, "avant") - 0.05, "timp", 41, 110, 1.5)
    chord(S(23), "high", [84, 88, 91], 45, 2.2)          # « a froid » : aigu cristallin
    for w in ["tout", "reuni"]:
        note(T(24, w), "piano", 84, 60, 0.8)
    note(T(26, "posee"), "timp", 41, 85, 1.0)

    # ---- 6 · Compound Capital : montee, puis l'orchestre s'ouvre en fa majeur
    rise0, hit = T(28, "compound") - 3.0, T(28, "compound") - 0.12
    for k in range(int((hit - rise0) / 0.1)):
        note(rise0 + k * 0.1, "timp", 41, 35 + int(85 * k / ((hit - rise0) / 0.1)), 0.15)
    swell("high", rise0, hit, 55, 127)
    chord(rise0, "trem", [53, 57, 60], 70, hit - rise0)
    note(hit, "timp", 29, 127, 3.0)
    chord(hit, "brass", [41, 53, 57, 60, 65], 120, 3.2)
    chord(hit, "choir", [65, 69, 72], 90, 4.0)
    for k, (key, d) in enumerate([(65, 0.8), (72, 0.8), (70, 0.5), (69, 1.2), (65, 1.6)]):   # theme au cor, majeur
        note(hit + 0.4 + [0, .8, 1.6, 2.1, 3.3][k], "horn", key - 12, 95, d)
    # puis une pulsation optimiste jusqu'a « rien a faire »
    t, k = S(29), 0
    while t < E(33):
        name = [n for (tt0, n) in plan if tt0 <= t][-1]
        root = CHORDS[name][0] + 12
        note(t, "ost", root + [0, 7, 12, 7][k % 4], 52 + 30 * inten(t), 0.22)
        t += 60 / 104 / 2
        k += 1
    for k in range(5):                         # L M M J V
        note(T(32, "lundi") + k * 0.2, "timp", 41 if k < 4 else 45, 70 + k * 8, 0.3)

    # ---- 7-8 · concretement : arpeges de piano, legers
    t, k = S(34), 0
    while t < E(44):
        name = [n for (tt0, n) in plan if tt0 <= t][-1]
        voic = CHORDS[name][1]
        note(t, "piano", voic[k % 4] + 12, 42 + 20 * inten(t), 0.9)
        t += 60 / 84 / 2
        k += 1
    chord(T(44, "progresse") - 0.1, "horn", [53, 57, 60], 80, 2.0)

    # ---- 9 · la preuve : tension contenue, puis detente
    chord(S(45), "trem", [57, 60, 64], 60, E(45) - S(45))
    note(T(45, "capture") + 0.1, "timp", 45, 100, 1.0)
    swell("high", S(46), E(48), 70, 110)
    chord(S(49), "cello", [48, 55], 70, E(50) - S(49) + 0.5)
    note(T(50, "presses"), "timp", 36, 80, 0.8)

    # ---- 10 · imagine : le theme, ample et chaleureux, vers le final
    for k, key in enumerate([65, 69, 72, 70, 69, 67, 65]):
        note(S(51) + 0.2 + k * 0.6, "piano", key + 12, 58, 1.6)
    chord(S(54), "choir", [65, 69, 72], 60, E(59) - S(54) + 0.6)
    swell("high", S(54), E(59), 70, 125)
    for bi, w in [(55, "stress"), (56, "ecran"), (57, "toi")]:
        note(T(bi, w), "timp", 41, 75, 0.6)
    chord(S(58), "horn", [53, 60, 65], 85, E(59) - S(58) + 0.5)

    # ---- 11 · appel a l'action et final
    chord(S(60), "high", [65, 69, 72, 77], 60, S(61) - S(60))
    rise0, hit = S(61) - 2.2, S(61) - 0.2
    for k in range(int((hit - rise0) / 0.1)):
        note(rise0 + k * 0.1, "timp", 41, 35 + int(80 * k / ((hit - rise0) / 0.1)), 0.15)
    note(hit, "timp", 29, 127, 4.0)
    chord(hit, "brass", [29, 41, 53, 57, 60, 65], 120, 4.5)
    chord(hit, "choir", [65, 69, 72, 77], 95, 5.0)
    chord(hit, "high", [77, 81, 84], 85, 5.0)
    chord(hit, "low", [29, 41], 100, 5.0)

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

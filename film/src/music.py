#!/usr/bin/env python3
"""Bande-son synthetisee (aucun credit) : nappe d'accords + souffles de transition.

La nappe est sombre (re mineur) pendant les chapitres « probleme », puis
s'eclaire (fa majeur) a la revelation de Compound Capital. Un souffle de bruit
filtre marque chaque changement de scene. Sortie : music_<variante>.wav.
"""
import json
import sys
import wave
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SR = 48000

SCENE_BEATS = [2, 8, 15, 19, 27, 34, 41, 45, 51, 60]   # debuts de scene (indices de phrases)


def note(n):  # n en demi-tons depuis le la 440
    return 440.0 * 2 ** (n / 12)


# accords en demi-tons relatifs au la 440 (voix graves)
DM = [-19, -16, -12, -7]       # re fa la re
BB = [-23, -19, -16, -11]      # sib re fa sib
GM = [-14, -19, -11, -7]       # sol sib re
A7 = [-12, -17, -8, -5]        # la do# mi sol
F = [-16, -12, -9, -4]         # fa la do fa
C = [-21, -17, -14, -9]        # do mi sol do
AM = [-12, -21, -9, -5]        # la do mi
BB2 = [-23, -14, -11, -7]


def pad(chords, dur, t0):
    """chords : liste de (instant, accord). Fondus lents entre accords."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    out = np.zeros(n)
    for i, (start, ch) in enumerate(chords):
        end = chords[i + 1][0] if i + 1 < len(chords) else dur
        a, b = int(max(0, start - 1.2) * SR), int(min(dur, end + 1.2) * SR)
        if b <= a:
            continue
        tt = t[a:b]
        env = np.clip((tt - (start - 1.2)) / 1.6, 0, 1) * np.clip(((end + 1.2) - tt) / 1.6, 0, 1)
        env = env * env * (3 - 2 * env)
        seg = np.zeros(b - a)
        for k, semi in enumerate(ch):
            f = note(semi)
            for det in (-0.12, 0.12):        # leger desaccord : chaleur
                ph = 2 * np.pi * (f * (1 + det / 100)) * tt
                seg += (np.sin(ph) + 0.28 * np.sin(2 * ph) + 0.10 * np.sin(3 * ph)) * (0.9 if k else 1.2)
        out[a:b] += seg * env
    # filtre passe-bas doux (moyenne glissante) pour arrondir
    k = np.ones(24) / 24
    out = np.convolve(out, k, mode="same")
    return out / (np.abs(out).max() + 1e-9)


def swoosh(n_total, at, rng):
    out = np.zeros(n_total)
    for t0 in at:
        d = 0.55
        a = int(max(0, t0 - d * 0.75) * SR)
        m = int(d * SR)
        if a + m > n_total:
            continue
        x = rng.standard_normal(m)
        # bruit filtre de plus en plus clair puis coupe : effet de souffle
        y = np.zeros(m)
        alpha = np.linspace(0.02, 0.35, m)
        for i in range(1, m):
            y[i] = y[i - 1] + alpha[i] * (x[i] - y[i - 1])
        env = np.sin(np.linspace(0, np.pi, m)) ** 2
        out[a:a + m] += y * env
    return out / (np.abs(out).max() + 1e-9)


def main(variant):
    beats = json.loads((HERE / f"beats_{variant}.json").read_text(encoding="utf-8"))
    B, dur = beats["beats"], beats["duration"] + 1.0
    S = lambda i: B[i]["start"]

    chords = [
        (0.0, DM), (S(2), BB), (S(6), GM), (S(8), DM), (S(11), BB), (S(13), A7),
        (S(15), DM), (S(17), GM), (S(19), BB), (S(22), F), (S(24), C),
        (S(27), A7), (S(28), F), (S(31), C), (S(34), F), (S(38), BB2),
        (S(41), F), (S(45), AM), (S(46), F), (S(49), C), (S(51), BB2),
        (S(54), F), (S(58), C), (S(60), F),
    ]
    p = pad(chords, dur, 0)
    rng = np.random.default_rng(3)
    sw = swoosh(len(p), [S(i) - 0.22 for i in SCENE_BEATS], rng)

    # sous-basse tres douce sur la fondamentale, qui pulse lentement
    t = np.arange(len(p)) / SR
    mix = 0.55 * p + 0.22 * sw
    mix *= np.clip(t / 1.5, 0, 1) * np.clip((dur - t) / 2.0, 0, 1)
    stereo = np.stack([mix, np.roll(mix, int(0.011 * SR))], axis=1)
    stereo /= np.abs(stereo).max() + 1e-9
    stereo *= 0.5

    out = HERE.parent / "assets" / f"music_{variant}.wav"
    with wave.open(str(out), "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((stereo * 32767).astype("<i2").tobytes())
    print(out.name, f"{len(p)/SR:.1f}s")


if __name__ == "__main__":
    for v in sys.argv[1:] or ["ig", "tt"]:
        main(v)

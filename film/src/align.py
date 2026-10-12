#!/usr/bin/env python3
"""Aligne le texte de la voix off sur les segments de parole detectes dans le mp3.

Principe : ffmpeg silencedetect donne les bornes exactes des groupes de souffle.
On aligne ensuite les phrases du script sur ces segments par programmation
dynamique (cout = ecart entre duree attendue et duree reelle), en autorisant
qu'un segment porte plusieurs phrases ou qu'une phrase s'etale sur plusieurs
segments. Les mots sont ensuite repartis dans leur phrase au prorata des
caracteres. Precision suffisante pour des sous-titres mot a mot.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSETS = HERE.parent / "assets"


def detect_segments(mp3: Path, noise="-35dB", dur=0.25):
    out = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", str(mp3),
         "-af", f"silencedetect=noise={noise}:d={dur}", "-f", "null", "-"],
        capture_output=True, text=True).stderr
    total = float(subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(mp3)], capture_output=True, text=True).stdout.strip())

    pauses = []
    cur = None
    for line in out.splitlines():
        m = re.search(r"silence_start: ([-\d.]+)", line)
        if m:
            cur = float(m.group(1))
        m = re.search(r"silence_end: ([-\d.]+)", line)
        if m and cur is not None:
            pauses.append((cur, float(m.group(1))))
            cur = None

    segs, t = [], 0.0
    for s, e in pauses:
        if s > t + 0.05:
            segs.append((t, s))
        t = e
    if total > t + 0.05:
        segs.append((t, total))
    return segs, total


def weight(text: str) -> float:
    """Duree attendue, en unites arbitraires : les caracteres parlent."""
    return max(1.0, len(re.sub(r"[^\w'À-ÿ]", "", text)))


def align(phrases, segs):
    """DP : phrases[i:] sur segs[j:]. Retourne la liste des (i0,i1,j0,j1) groupes."""
    n, m = len(phrases), len(segs)
    W = [weight(p) for p in phrases]
    D = [e - s for s, e in segs]
    total_w, total_d = sum(W), sum(D)
    rate = total_d / total_w  # secondes par caractere

    INF = float("inf")
    # cost[i][j] = cout minimal pour aligner phrases[i:] sur segs[j:]
    cost = [[INF] * (m + 1) for _ in range(n + 1)]
    back = [[None] * (m + 1) for _ in range(n + 1)]
    cost[n][m] = 0.0

    # on autorise un groupe de 1..3 phrases sur 1..3 segments
    for i in range(n, -1, -1):
        for j in range(m, -1, -1):
            if i == n and j == m:
                continue
            best, bk = INF, None
            for di in range(1, 4):
                for dj in range(1, 4):
                    if i + di > n or j + dj > m:
                        continue
                    w = sum(W[i:i + di])
                    d = sum(D[j:j + dj])
                    c = abs(w * rate - d) + 0.12 * (di - 1) + 0.12 * (dj - 1)
                    nxt = cost[i + di][j + dj]
                    if nxt < INF and c + nxt < best:
                        best, bk = c + nxt, (di, dj)
            cost[i][j], back[i][j] = best, bk

    groups, i, j = [], 0, 0
    while i < n or j < m:
        bk = back[i][j]
        if bk is None:
            break
        di, dj = bk
        groups.append((i, i + di, j, j + dj))
        i, j = i + di, j + dj
    return groups


def main():
    mp3 = ASSETS / "voix_main.mp3"
    phrases = [l.strip() for l in (HERE / "voix_texte.txt").read_text(encoding="utf-8").splitlines() if l.strip()]
    segs, total = detect_segments(mp3)
    print(f"{len(phrases)} phrases, {len(segs)} segments de parole, {total:.2f}s", file=sys.stderr)

    groups = align(phrases, segs)

    items = []
    for i0, i1, j0, j1 in groups:
        t0, t1 = segs[j0][0], segs[j1 - 1][1]
        span = t1 - t0
        wsum = sum(weight(p) for p in phrases[i0:i1])
        acc = t0
        for p in phrases[i0:i1]:
            d = span * weight(p) / wsum
            items.append({"text": p, "start": round(acc, 3), "end": round(acc + d, 3)})
            acc += d

    # mots, au prorata des caracteres dans leur phrase
    words = []
    for it in items:
        toks = it["text"].split()
        wsum = sum(weight(t) for t in toks)
        acc = it["start"]
        span = it["end"] - it["start"]
        for t in toks:
            d = span * weight(t) / wsum
            words.append({"w": t, "start": round(acc, 3), "end": round(acc + d, 3)})
            acc += d

    out = {"duration": total, "phrases": items, "words": words}
    (HERE / "voix_timing.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    for it in items:
        print(f"{it['start']:7.2f} {it['end']:7.2f}  {it['text'][:70]}")


if __name__ == "__main__":
    main()

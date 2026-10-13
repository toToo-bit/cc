#!/usr/bin/env python3
"""Phrases calees sur la voix montee : beats_<v>.json (lu par motion.js, sfx.py, score.py)."""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
NB = " "
SKIP = {"Rien ne presse.", "L'historique, la FAQ et les conditions t'attendent sur notre Telegram.", "Lien en bio."}


def toks(p):
    out = []
    for t in p.split():
        if re.search(r"\w", t):
            out.append(t)
        elif out:
            out[-1] += NB + t        # « : », « ? » colles au mot precedent
    return out


def build(v):
    H = json.loads((HERE / f"horloge_{v}.json").read_text(encoding="utf-8"))
    words = H["words"]
    phr = [l.strip() for l in (HERE / "voix_texte.txt").read_text(encoding="utf-8").splitlines()
           if l.strip() and l.strip() not in SKIP]
    i, beats = 0, []
    for p in phr:
        tk = toks(p)
        ws = words[i:i + len(tk)]
        i += len(tk)
        beats.append({"text": p, "start": ws[0]["start"], "end": ws[-1]["end"],
                      "words": [{"w": t, "s": w["start"], "e": w["end"]} for t, w in zip(tk, ws)]})
    if i != len(words):
        sys.exit(f"{v} : {i} mots dans le script, {len(words)} dans la voix")
    beats.insert(len(beats) - 2, {"text": "CTA", "start": H["cta"]["start"], "end": H["cta"]["end"], "words": []})
    (HERE / f"beats_{v}.json").write_text(json.dumps({"duration": H["duration"], "beats": beats}, ensure_ascii=False),
                                          encoding="utf-8")
    print(f"beats_{v}.json : {len(beats)} phrases, {i} mots")


if __name__ == "__main__":
    for v in sys.argv[1:] or ["ig", "tt"]:
        build(v)

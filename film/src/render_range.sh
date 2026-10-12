#!/usr/bin/env bash
# Rend une plage d'images en video muette.
#   src/render_range.sh SORTIE.mp4 PREMIERE DERNIERE [options render.py...]
# Le serveur est lance, alimente puis arrete via son PID : jamais de pkill -f,
# qui tue aussi le shell appelant quand le motif apparait dans sa ligne.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$1"; FIRST="$2"; LAST="$3"; shift 3
PORT="${PORT:-8711}"

cd "$ROOT"
python3 -I src/serve.py --port "$PORT" --out "$OUT" --first "$FIRST" \
  --width "${W:-1080}" --height "${H:-1920}" --fps 30 &
SRV=$!
trap 'kill -TERM $SRV 2>/dev/null || true' EXIT

for _ in $(seq 50); do
  curl -sf "http://127.0.0.1:$PORT/status" >/dev/null && break
  sleep 0.2
done

python3 -I src/render.py --port "$PORT" --width "${W:-1080}" --height "${H:-1920}" \
  --range "$FIRST" "$LAST" "$@" 2>&1 | grep -vE "favicon|status of 404|erreurs page" || true

WRITTEN="$(curl -s "http://127.0.0.1:$PORT/status")"
EXPECTED=$((LAST - FIRST + 1))
kill -TERM "$SRV"; wait "$SRV" 2>/dev/null || true
trap - EXIT

echo "images ecrites : $WRITTEN / $EXPECTED"
[ "$WRITTEN" = "$EXPECTED" ] || { echo "ECHEC : images manquantes" >&2; exit 1; }

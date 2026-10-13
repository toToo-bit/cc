#!/usr/bin/env bash
# Remixe le son d'un master sans reencoder l'image.
#   src/mix_sfx.sh MASTER_VIDEO VARIANTE SORTIE
# voix (devant) + musique (compressee par la voix) + effets (legerement compresses)
set -euo pipefail
cd "$(dirname "$0")/.."
V="$1"; VAR="$2"; OUT="$3"
ffmpeg -y -v error -i "$V" -i "assets/voix_$VAR.wav" -i "assets/music_$VAR.wav" -i "assets/sfx_$VAR.wav" \
  -filter_complex "[1:a]aformat=sample_rates=48000:channel_layouts=stereo,asplit=3[v1][v2][v3];\
[2:a]volume=0.30[m];[m][v1]sidechaincompress=threshold=0.015:ratio=10:attack=15:release=450[md];\
[3:a]volume=0.42[s];[s][v2]sidechaincompress=threshold=0.03:ratio=3:attack=10:release=250[sd];\
[v3][md][sd]amix=inputs=3:normalize=0:duration=first,loudnorm=I=-13:TP=-1.5:LRA=11,aresample=48000,alimiter=limit=0.84:level=false[a]" \
  -map 0:v -map "[a]" -c:v copy -c:a aac -b:a 192k -movflags +faststart -shortest "$OUT"
ffmpeg -hide_banner -i "$OUT" -af ebur128=peak=true -f null - 2>&1 | grep -E "^\s+(I|Peak):" | head -2

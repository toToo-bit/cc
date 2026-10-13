#!/usr/bin/env bash
# Mixe et encode la version finale.  src/mix.sh VIDEO_MUETTE VARIANTE SORTIE
# Voix au premier plan, musique compressee par la voix (ducking), -14 LUFS,
# H.264 plafonne a ~4,5 Mb/s pour rester sous 100 Mo (hebergement GitHub).
set -euo pipefail
cd "$(dirname "$0")/.."
V="$1"; VAR="$2"; OUT="$3"
ffmpeg -y -v error -i "$V" -i "assets/voix_$VAR.wav" -i "assets/music_$VAR.wav" \
  -filter_complex "[1:a]aformat=sample_rates=48000:channel_layouts=stereo,asplit=2[v1][v2];\
[2:a]volume=0.30[m];[m][v1]sidechaincompress=threshold=0.015:ratio=10:attack=15:release=450[md];\
[v2][md]amix=inputs=2:normalize=0:duration=first,loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000[a]" \
  -map 0:v -map "[a]" -c:v libx264 -preset medium -crf 21 -maxrate 4500k -bufsize 9000k \
  -pix_fmt yuv420p -movflags +faststart -c:a aac -b:a 192k -shortest "$OUT"
ffprobe -v error -show_entries format=duration,size,bit_rate -of compact "$OUT"

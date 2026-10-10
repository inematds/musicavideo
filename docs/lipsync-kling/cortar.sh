#!/usr/bin/env bash
# cortar.sh <clipe.mp4> <vocals.wav> <dir_saida> <ini:fim> [<ini:fim> ...]
# Corta cada trecho do clipe MONTADO (vídeo sem áudio) e a voz isolada do mesmo intervalo.
# Gera <dir>/vNN.mp4, <dir>/aNN.mp3 e <dir>/segs.txt ("NN ini fim"), na ordem dos argumentos.
set -euo pipefail
clipe=$1; voz=$2; dir=$3; shift 3
mkdir -p "$dir"; : > "$dir/segs.txt"
i=0
for seg in "$@"; do
  i=$((i+1)); n=$(printf %02d $i); a=${seg%:*}; b=${seg#*:}
  echo "$n $a $b" >> "$dir/segs.txt"
  ffmpeg -v error -y -ss "$a" -to "$b" -i "$clipe" -an -c:v libx264 -crf 16 -preset fast "$dir/v$n.mp4"
  ffmpeg -v error -y -ss "$a" -to "$b" -i "$voz" -c:a libmp3lame -b:a 192k "$dir/a$n.mp3"
done
echo "ok: $i trechos em $dir"

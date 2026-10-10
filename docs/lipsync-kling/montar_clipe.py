#!/usr/bin/env python3
"""Encaixa cada ls2/ks<NN>.mp4 (Lip Sync) no clipe.mp4 no tempo de segs.txt; mantém o áudio original.
Uso: montar_clipe.py <clipe.mp4> <ls2_dir> <saida.mp4>"""
import os, subprocess, sys

clipe, d, saida = sys.argv[1:4]
segs = [l.split() for l in open(os.path.join(d, 'segs.txt')) if l.strip()]
ins, fil, last = ['-i', clipe], [], '0:v'
k = 0
for nn, a, b in segs:
    ks = os.path.join(d, f'ks{nn}.mp4')
    if not os.path.exists(ks):
        continue
    k += 1
    a, b = float(a), float(b)
    ins += ['-i', ks]
    fil.append(f'[{k}:v]fps=24,setpts=PTS-STARTPTS,tpad=stop_mode=clone:stop_duration=1,'
               f'trim=0:{b - a},setpts=PTS-STARTPTS+{a}/TB[s{k}]')
    fil.append(f"[{last}][s{k}]overlay=enable='between(t,{a},{b - 0.001})':eof_action=pass[o{k}]")
    last = f'o{k}'
print('trechos encaixados:', k)
cmd = ['ffmpeg', '-v', 'error', '-y', *ins, '-filter_complex', ';'.join(fil), '-map', f'[{last}]', '-map', '0:a',
       '-c:v', 'libx264', '-crf', '20', '-preset', 'fast', '-c:a', 'copy', '-movflags', '+faststart', saida]
subprocess.run(cmd, check=True)

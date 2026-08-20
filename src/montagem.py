"""Fase 2.5: casar o vídeo dos shots com a faixa — é isso que faz um CLIPE.

Sem esta etapa saem três arquivos soltos: o vídeo carrega só o áudio ambiente
que o gerador inventou por shot, e a música fica de fora.
"""
import subprocess
from pathlib import Path


class MontagemError(RuntimeError):
    pass


def _ffprobe_duracao(arq: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                        "-of", "csv=p=0", str(arq)], capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        raise MontagemError(f"ffprobe não leu a duração de {arq.name}: {r.stderr[-200:]}")


def montar(video: Path, faixa: Path, alvo: Path, fade_s: float = 2.0,
           cobrir_musica: bool = False) -> dict:
    """Troca o áudio do vídeo pela faixa.

    - vídeo mais curto que a música: por padrão corta a música no tamanho do
      vídeo com fade-out; com `cobrir_musica`, repete o vídeo em loop até a
      música acabar (o vídeo vira pano de fundo do trecho inteiro).
    - vídeo mais longo: a música toca até acabar e o resto do vídeo fica mudo.
    """
    dur_v, dur_a = _ffprobe_duracao(video), _ffprobe_duracao(faixa)
    loop = cobrir_musica and dur_v < dur_a
    dur_final = dur_a if loop else dur_v      # sem loop, quem manda é o vídeo
    inicio_fade = max(0.0, min(dur_final, dur_a) - fade_s)

    cmd = ["ffmpeg", "-y"]
    if loop:
        cmd += ["-stream_loop", "-1"]
    # apad: se o vídeo for mais longo que a música, o resto fica em silêncio em
    # vez de o `-shortest` cortar o vídeo no fim da faixa.
    cmd += ["-i", str(video), "-i", str(faixa),
            "-filter_complex",
            f"[1:a]afade=t=out:st={inicio_fade:.2f}:d={fade_s},apad[a]",
            "-map", "0:v:0", "-map", "[a]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            "-t", f"{dur_final:.2f}", str(alvo)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not alvo.exists():
        raise MontagemError(f"ffmpeg falhou na montagem: {r.stderr[-300:]}")
    return {"duracao_video_s": round(dur_v, 2), "duracao_faixa_s": round(dur_a, 2),
            "duracao_final_s": round(_ffprobe_duracao(alvo), 2),
            "video_em_loop": loop}

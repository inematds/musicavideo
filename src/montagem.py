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


def faixas_existentes(w: Path) -> list[Path]:
    """As faixas baixadas, na ordem. O Suno entrega duas — às vezes só uma
    (status FIRST_SUCCESS), e slug antigo tem a `faixa.mp3` sozinha."""
    numeradas = sorted(w.glob("faixa-*.mp3"),
                       key=lambda p: int(p.stem.split("-")[-1]) if p.stem.split("-")[-1].isdigit() else 99)
    if numeradas:
        return numeradas
    return [w / "faixa.mp3"] if (w / "faixa.mp3").exists() else []


def apontar_clipe(w: Path, versao: Path) -> Path:
    """`clipe.mp4` é o ponteiro pra versão aprovada — hardlink, não cópia:
    trocar de faixa depois do clipe pronto não pode custar disco nem render."""
    import os
    import shutil
    alvo = w / "clipe.mp4"
    if versao.resolve() == alvo.resolve():
        return alvo
    alvo.unlink(missing_ok=True)
    try:
        os.link(versao, alvo)
    except OSError:
        shutil.copy2(versao, alvo)
    return alvo


def montar_todas(w: Path, bruto: Path, cobrir_musica: bool = False,
                 aprovada: str | None = None) -> dict:
    """Casa o MESMO vídeo com cada faixa: `clipe-1.mp4`, `clipe-2.mp4`…

    Cada faixa tem sua duração, então cada uma é uma passada de ffmpeg própria
    (fade e loop mudam). `clipe.mp4` fica sendo a versão da faixa aprovada.
    """
    faixas = faixas_existentes(w)
    if not faixas:
        raise MontagemError(f"nenhuma faixa em {w}")
    if len(faixas) == 1 and faixas[0].name == "faixa.mp3":   # slug antigo
        meta = montar(bruto, faixas[0], w / "clipe.mp4", cobrir_musica=cobrir_musica)
        return {"versoes": {"faixa.mp3": "clipe.mp4"}, "principal": "clipe.mp4", **meta}

    versoes, metas = {}, {}
    for f in faixas:
        n = f.stem.split("-")[-1]
        saida = w / f"clipe-{n}.mp4"
        metas[f.name] = montar(bruto, f, saida, cobrir_musica=cobrir_musica)
        versoes[f.name] = saida.name
    escolhida = aprovada if aprovada in versoes else faixas[0].name
    principal = apontar_clipe(w, w / versoes[escolhida])
    return {"versoes": versoes, "principal": principal.name,
            "faixa_principal": escolhida, "metas": metas, **metas[escolhida]}

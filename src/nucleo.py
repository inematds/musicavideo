"""O NÚCLEO da faixa: o trecho de ~12s que carrega a música sozinho.

Ideia vinda da base de "potencial musical" do dono (teste dos 12 segundos):
existe um pedaço que ganha vida FORA da música inteira — é o que vira Short e é
onde vale gastar o melhor plano do clipe.

A diferença aqui é que ele não é OPINADO: nada de LLM dando nota a um trecho
que ninguém ouviu. O núcleo sai da própria onda — energia (RMS) por segundo,
medida com ffmpeg. Objetivo, local, US$ 0, e reprodutível.

Limite honesto: energia é uma APROXIMAÇÃO de "o trecho mais forte". Acerta o
refrão e o drop, que é o caso comum; erra em música que constrói por letra ou
por silêncio. Por isso é sugestão no prompt, nunca ordem.
"""
import array
import subprocess
from pathlib import Path

TAXA = 8000          # Hz: energia não precisa de fidelidade, e 8k lê rápido
JANELA_S = 12        # o "teste dos 12 segundos"
CONTRASTE = 0.35     # peso do salto de energia contra o silêncio que veio antes


class NucleoError(RuntimeError):
    pass


def rms_por_segundo(faixa: Path) -> list[float]:
    """Um valor de energia por segundo da faixa."""
    r = subprocess.run(
        ["ffmpeg", "-v", "quiet", "-i", str(faixa), "-ac", "1", "-ar", str(TAXA),
         "-f", "s16le", "-"], capture_output=True)
    if r.returncode != 0 or not r.stdout:
        raise NucleoError(f"ffmpeg não decodificou {Path(faixa).name}")
    amostras = array.array("h")
    amostras.frombytes(r.stdout[:len(r.stdout) // 2 * 2])
    saida = []
    for i in range(0, len(amostras) - TAXA + 1, TAXA):
        bloco = amostras[i:i + TAXA]
        saida.append((sum(float(x) * x for x in bloco) / len(bloco)) ** 0.5)
    return saida


def nucleo_de(faixa: Path, janela_s: int = JANELA_S) -> dict:
    """A janela de `janela_s` que melhor representa a faixa.

    Pontuação = energia média da janela + um bônus por CONTRASTE (quanto ela
    sobe em relação aos segundos anteriores). O contraste é o que separa "o
    trecho mais alto" de "o momento em que a música vira" — sem ele, uma faixa
    comprimida devolve sempre o primeiro refrão.
    """
    curva = rms_por_segundo(Path(faixa))
    if len(curva) < janela_s:
        raise NucleoError(f"faixa curta demais para um núcleo de {janela_s}s")
    pico = max(curva) or 1.0
    melhor, ponto = None, -1.0
    for i in range(0, len(curva) - janela_s + 1):
        janela = curva[i:i + janela_s]
        media = sum(janela) / janela_s
        antes = curva[max(0, i - janela_s):i]
        salto = (media - (sum(antes) / len(antes))) if antes else 0.0
        p = (media + CONTRASTE * max(0.0, salto)) / pico
        if p > ponto:
            melhor, ponto = i, p
    return {"inicio_s": melhor, "fim_s": melhor + janela_s,
            "forca": round(ponto, 3),
            "energia_relativa": round((sum(curva[melhor:melhor + janela_s]) / janela_s) / pico, 3)}


def recortar_vertical(clipe: Path, alvo: Path, inicio_s: float, dur_s: float = JANELA_S) -> Path:
    """O Short sai do clipe que JÁ existe: corte + 9:16, sem gerar nada.

    Recorte central em 1080x1920. Não é render novo, é a mesma imagem — por isso
    custa segundos e US$ 0.
    """
    cmd = ["ffmpeg", "-y", "-ss", f"{inicio_s:.2f}", "-i", str(clipe), "-t", f"{dur_s:.2f}",
           "-vf", "crop=ih*9/16:ih,scale=1080:1920:flags=lanczos",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
           "-c:a", "aac", "-b:a", "192k", str(alvo)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not alvo.exists():
        raise NucleoError(f"ffmpeg falhou no recorte vertical: {r.stderr[-300:]}")
    return alvo

"""O que você olha antes de aprovar: folha de contato dos shots e listagem.

Revisar 37 shots um a um é inviável. A folha de contato põe todos numa grade
numerada — você lê em 30 segundos e reprova pelos números.
"""
import subprocess
from pathlib import Path

MINIATURA_L = 320          # largura de cada miniatura na folha
COLUNAS = 6


class RevisaoError(RuntimeError):
    pass


def shots_de(workdir: Path) -> list[Path]:
    return sorted((Path(workdir) / "raw").glob("shot-*.mp4"))


def _frame_do_meio(video: Path, alvo: Path) -> Path:
    """Um frame representativo — o do meio, não o primeiro (que costuma ser fade)."""
    dur = subprocess.run(["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                          "-of", "csv=p=0", str(video)], capture_output=True, text=True).stdout.strip()
    try:
        meio = float(dur) / 2
    except ValueError:
        meio = 1.0
    r = subprocess.run(["ffmpeg", "-y", "-ss", f"{meio:.2f}", "-i", str(video),
                        "-frames:v", "1", "-vf", f"scale={MINIATURA_L}:-1", str(alvo)],
                       capture_output=True, text=True)
    if r.returncode != 0 or not alvo.exists():
        raise RevisaoError(f"não consegui extrair frame de {video.name}: {r.stderr[-200:]}")
    return alvo


def folha_de_contato(workdir: Path, alvo: Path | None = None) -> Path:
    """Grade numerada com um frame de cada shot."""
    workdir = Path(workdir)
    shots = shots_de(workdir)
    if not shots:
        raise RevisaoError(f"nenhum shot em {workdir / 'raw'}")
    alvo = alvo or workdir / "revisao" / "contato-clipe.jpg"
    alvo.parent.mkdir(parents=True, exist_ok=True)
    tmp = alvo.parent / "_frames"
    tmp.mkdir(exist_ok=True)
    entradas, filtros, dims = [], [], None
    for i, shot in enumerate(shots):
        n = shot.stem.split("-")[-1]
        f = _frame_do_meio(shot, tmp / f"{n}.jpg")
        if dims is None:
            dims = subprocess.run(["ffprobe", "-v", "quiet", "-show_entries",
                                   "stream=width,height", "-of", "csv=p=0:s=x", str(f)],
                                  capture_output=True, text=True).stdout.strip()
        entradas += ["-i", str(f)]
        # o número do shot desenhado por cima: é por ele que você reprova
        filtros.append(f"[{i}:v]drawtext=text='{int(n)}':x=8:y=8:fontsize=42:"
                       f"fontcolor=white:box=1:boxcolor=black@0.6:boxborderw=6[v{i}]")
    linhas = (len(shots) + COLUNAS - 1) // COLUNAS
    # xstack exige a grade cheia: o resto vira quadro preto do mesmo tamanho
    faltam = COLUNAS * linhas - len(shots)
    for j in range(faltam):
        entradas += ["-f", "lavfi", "-i", f"color=c=black:s={dims or '320x180'}:d=1"]
        filtros.append(f"[{len(shots) + j}:v]null[v{len(shots) + j}]")
    total = len(shots) + faltam
    filtro = ";".join(filtros) + ";" + "".join(f"[v{i}]" for i in range(total))
    filtro += f"xstack=inputs={total}:grid={COLUNAS}x{linhas}[out]"
    r = subprocess.run(["ffmpeg", "-y", *entradas, "-filter_complex", filtro,
                        "-map", "[out]", "-frames:v", "1", "-update", "1",
                        "-q:v", "3", str(alvo)],
                       capture_output=True, text=True)
    if r.returncode != 0 or not alvo.exists():
        raise RevisaoError(f"ffmpeg falhou na folha de contato: {r.stderr[-300:]}")
    for f in tmp.glob("*.jpg"):
        f.unlink()
    tmp.rmdir()
    return alvo


def descartar_shots(workdir: Path, numeros: list[int]) -> list[int]:
    """Apaga os shots reprovados — o `faz` seguinte regenera só eles."""
    apagados = []
    for n in numeros:
        arq = Path(workdir) / "raw" / f"shot-{n:02d}.mp4"
        if arq.exists():
            arq.unlink()
            apagados.append(n)
    return apagados


def parse_numeros(texto: str) -> list[int]:
    """Aceita "4,17,23" e "4-7,12"."""
    saida = []
    for pedaco in str(texto).replace(" ", "").split(","):
        if not pedaco:
            continue
        if "-" in pedaco:
            a, _, b = pedaco.partition("-")
            saida.extend(range(int(a), int(b) + 1))
        else:
            saida.append(int(pedaco))
    return sorted(set(saida))


def o_que_revisar(workdir: Path, estado: dict) -> list[dict]:
    """As partes paradas no portão, com o arquivo pra olhar."""
    itens = []
    for parte in ("musica", "capa", "clipe"):
        d = estado["partes"][parte]
        if d["estado"] != "revisao":
            continue
        item = {"parte": parte, "artefato": d.get("artefato"),
                "custo": d.get("custo_real_usd", 0.0), "opcoes": [], "extra": []}
        if parte == "musica":
            item["opcoes"] = [p.name for p in sorted(Path(workdir).glob("faixa-*.mp3"))]
        if parte == "clipe":
            folha = Path(workdir) / "revisao" / "contato-clipe.jpg"
            if folha.exists():
                item["extra"].append(str(folha))
            item["extra"].append(f"{len(shots_de(workdir))} shots em {Path(workdir) / 'raw'}")
        itens.append(item)
    return itens

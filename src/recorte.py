"""RECORTE: dar ritmo a um clipe que JÁ foi gerado, sem gerar nada de novo.

O caro no clipe é a geração dos shots (fila de 5/min, horas de parede). O corte
não custa nada — é ffmpeg em cima de arquivo que já está no disco. Então um
clipe parelho de 37 planos de 5s pode virar um clipe com ritmo sem pagar a
segunda geração: encurta o plano no refrão, estica no verso, mantém a soma.

Duas operações, e as duas são honestas com o material:
- ENCURTAR é corte: fica o miolo do plano, onde o movimento já engrenou.
- ESTICAR é slowmo (setpts), que é justamente o recurso que o acervo mostra
  sendo usado nesses clipes (`uso_de_slowmo_speedramp` em todos os medidos).
  Tem limite: além de ~1,6x o olho vê travando, então o teto é esse.

A soma é preservada por construção — o clipe continua cobrindo a música.
"""
import re
import subprocess
import unicodedata
from pathlib import Path

PISO_S = 1.5          # abaixo disso o plano não se lê
TETO_S = 18.0         # teto duro da Agnes, mantido aqui por coerência
LENTO_MAX = 1.6       # slowmo além disso trava aos olhos
RODADAS = 6           # redistribuição depois de travar os shots no limite

# Peso = quanto tempo aquele plano PEDE. <1 encurta, >1 estica.
PESOS = {"refrao": 0.55, "verso": 1.25, "ponte": 1.35, "intro": 1.15,
         "outro": 1.30, "solo": 1.35, "final": 0.6}
PESO_PADRAO = 1.0
# `variado` mantém a média (mesmo nº de planos, mesmas horas); `dinamico`
# aperta tudo — só faz sentido quando SOBRAM planos para cobrir a música.
INTENSIDADE = {"variado": 1.0, "dinamico": 1.35, "calmo": 0.6}
# Média de plano que cada ritmo persegue. `variado` mantém os planos que
# existem (mesma média, distribuição outra); `dinamico` precisa de MAIS planos
# do que foram gerados — e eles são fabricados do próprio material.
MEDIA_ALVO_S = {"variado": None, "dinamico": 3.0, "calmo": None}


def intensidade_nome(valor: float) -> str:
    for nome, v in INTENSIDADE.items():
        if abs(v - valor) < 1e-6:
            return nome
    return "variado"


class RecorteError(RuntimeError):
    pass


def _norm(s: str) -> str:
    return unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()


def peso_da_secao(secao: str, intensidade: float = 1.0) -> float:
    """Quanto o plano daquela seção afasta da média. Seção desconhecida = 1."""
    n = _norm(secao)
    peso = PESO_PADRAO
    for chave, valor in PESOS.items():
        if re.search(rf"\b{chave}", n):
            peso = valor
            break
    return 1.0 + (peso - 1.0) * intensidade      # intensidade 0 = tudo parelho


def duracoes_alvo(secoes: list[str], originais: list[float],
                  intensidade: float = 1.0, total: float | None = None) -> list[float]:
    """As durações novas: proporcionais ao peso, somando o total pedido.

    `total` existe porque quem manda na soma é a MÚSICA, não o material. Com
    planos novos entrando (37 gerados a 5s + 25 a 3s = 263s de material para
    186s de faixa), somar o material esticaria o clipe para além da canção.

    Quem bate no piso, no teto ou no limite de slowmo trava, e o que sobra é
    redistribuído entre os livres — senão a soma escorrega e o clipe encurta.
    """
    if not originais:
        return []
    total = float(total if total else sum(originais))
    tetos = [min(TETO_S, o * LENTO_MAX) for o in originais]
    pesos = [peso_da_secao(s, intensidade) for s in secoes]
    travados: dict[int, float] = {}
    for _ in range(RODADAS):
        resto = total - sum(travados.values())
        livres = [i for i in range(len(originais)) if i not in travados]
        soma_pesos = sum(pesos[i] for i in livres) or 1.0
        novos = {i: resto * pesos[i] / soma_pesos for i in livres}
        estourou = False
        for i, v in novos.items():
            if v < PISO_S:
                travados[i], estourou = PISO_S, True
            elif v > tetos[i]:
                travados[i], estourou = tetos[i], True
        if not estourou:
            saida = [travados.get(i, novos.get(i, originais[i])) for i in range(len(originais))]
            return [round(x, 2) for x in saida]
    return [round(travados.get(i, originais[i]), 2) for i in range(len(originais))]


def expandir_sequencia(shots: list[Path], secoes: list[str], n_alvo: int) -> list[tuple]:
    """Ritmo picado pede MAIS planos do que foram gerados — e eles saem daqui.

    Um plano de 5s vira dois de 2,5s: a primeira metade e a segunda, o que é
    material novo de verdade, não repetição. Quando ainda falta, entra o
    espelhado (mesma ideia do `agnes.variacao_de`), sempre longe do original.

    Devolve [(arquivo, fatia, espelhar, secao)], onde `fatia` é (0,2) = primeira
    de duas metades. Gerar nada disso custa: é corte em arquivo que já existe.
    """
    base = [(s, (0, 1), False, sec) for s, sec in zip(shots, secoes)]
    if n_alvo <= len(base):
        return base
    # prioriza fatiar os planos das seções que PEDEM picote (peso baixo)
    ordem = sorted(range(len(base)), key=lambda i: (peso_da_secao(secoes[i]), i))
    saida = list(base)
    faltam, i = n_alvo - len(base), 0
    while faltam > 0 and i < len(ordem) * 2:
        alvo = ordem[i % len(ordem)]
        arq, fatia, espelho, sec = saida[_indice_de(saida, base[alvo])]
        if fatia == (0, 1):                       # ainda inteiro: parte em dois
            pos = _indice_de(saida, (arq, fatia, espelho, sec))
            saida[pos] = (arq, (0, 2), False, sec)
            saida.insert(pos + 1, (arq, (1, 2), False, sec))
        else:                                     # já fatiado: espelha
            saida.insert(min(len(saida), _indice_de(saida, (arq, fatia, espelho, sec)) + 2),
                         (arq, fatia, True, sec))
        faltam -= 1
        i += 1
    return saida


def _indice_de(seq: list, item) -> int:
    for i, x in enumerate(seq):
        if x[0] == item[0] and x[1] == item[1] and x[2] == item[2]:
            return i
    return 0


def _refazer_shot(origem: Path, alvo: Path, dur_orig: float, dur_nova: float,
                  fatia: tuple = (0, 1), espelhar: bool = False) -> Path:
    """Encurta cortando o miolo; estica em slowmo. Sem áudio: a música entra depois."""
    k, n = fatia
    janela = dur_orig / n
    base = k * janela                            # de onde esta fatia começa
    if dur_nova <= janela:
        # o miolo, não o começo: plano de IA costuma levar um tempo até o
        # movimento engrenar, e o fim é onde ele desanda.
        inicio = base + (janela - dur_nova) * 0.35
        vf = "null"
        corte = ["-ss", f"{inicio:.3f}", "-t", f"{dur_nova:.3f}"]
    else:
        vf = f"setpts={dur_nova / janela:.4f}*PTS"
        corte = ["-ss", f"{base:.3f}", "-t", f"{dur_nova:.3f}"]
    if espelhar:
        vf = f"hflip,{vf}" if vf != "null" else "hflip"
    cmd = ["ffmpeg", "-y", "-i", str(origem), *corte, "-an",
           "-vf", f"{vf},fps=24,format=yuv420p",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", str(alvo)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not alvo.exists():
        raise RecorteError(f"ffmpeg falhou em {origem.name}: {r.stderr[-300:]}")
    return alvo


def duracao(arq: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                        "-of", "csv=p=0", str(arq)], capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        raise RecorteError(f"ffprobe não leu {arq.name}")


def recortar(shots: list[Path], secoes: list[str], destino: Path,
             intensidade: float = 1.0, total_s: float | None = None) -> dict:
    """Remonta os shots existentes com ritmo. Devolve o relatório do que mudou."""
    if not shots:
        raise RecorteError("nenhum shot para recortar")
    duracoes = {s: duracao(s) for s in shots}
    total = float(total_s) if total_s else sum(duracoes.values())
    media_alvo = MEDIA_ALVO_S.get(intensidade_nome(intensidade))
    n_alvo = max(len(shots), round(total / media_alvo)) if media_alvo else len(shots)
    seq = expandir_sequencia(shots, secoes, n_alvo)
    originais = [duracoes[a] / f[1] for a, f, _, _ in seq]     # a fatia é o material real
    alvos = duracoes_alvo([s for *_, s in seq], originais, intensidade, total)
    tmp = destino.parent / "recorte"
    tmp.mkdir(parents=True, exist_ok=True)
    partes = []
    for i, ((arq, fatia, espelho, _), o, a) in enumerate(zip(seq, originais, alvos), 1):
        partes.append(_refazer_shot(arq, tmp / f"r-{i:03d}.mp4", duracoes[arq], a,
                                    fatia, espelho))
    lista = tmp / "concat.txt"
    lista.write_text("".join(f"file '{p}'\n" for p in partes), encoding="utf-8")
    r = subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lista),
                        "-c", "copy", str(destino)], capture_output=True, text=True)
    if r.returncode != 0 or not destino.exists():
        raise RecorteError(f"ffmpeg concat falhou: {r.stderr[-300:]}")
    import shutil
    shutil.rmtree(tmp, ignore_errors=True)     # os pedaços já estão no concat
    curtos = sum(1 for o, a in zip(originais, alvos) if a < o - 0.2)
    lentos = sum(1 for o, a in zip(originais, alvos) if a > o + 0.2)
    return {"shots": len(seq), "gerados_do_material": len(seq) - len(shots),
            "encurtados": curtos, "em_slowmo": lentos,
            "duracao_antes_s": round(sum(originais), 2),
            "duracao_depois_s": round(duracao(destino), 2),
            "menor_s": min(alvos), "maior_s": max(alvos),
            "cortes_por_minuto": round(len(seq) / (sum(alvos) / 60), 1)}

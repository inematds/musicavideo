"""A aprovação de subida: o gesto que decide o que vira vitrine.

Subir para a nuvem não é consequência de ficar pronto. Produção pronta é
material de trabalho; vitrine é escolha, e quem escolhe é quem está olhando —
no painel local, com o clipe tocando ao lado. Por isso a marca mora aqui e não
no fluxo de geração: nada sobe sozinho.

A marca é POR FAIXA (v2.1). O Suno entrega duas músicas por pedido — mesma
letra, mesmo material de vídeo, outra interpretação — e aprovar a produção
inteira obrigava a levar as duas ou nenhuma. O que se escolhe é a música.

O que este módulo guarda é só a MARCA. Quem sobe de fato é o `publica-hf`.
"""
from datetime import datetime, timezone, timedelta
from pathlib import Path

from src.estado import carregar_estado, salvar_estado

TZ = timezone(timedelta(hours=-3))


def _agora() -> str:
    return datetime.now(TZ).isoformat(timespec="seconds")


def ler(w: Path) -> dict:
    """`{aprovado, aprovado_em, publicado_em, remover, faixas}` — vazio quando
    nunca tocado. O bloco de topo continua existindo: é o resumo da produção,
    e é por ele que todo código antigo (e o `subida.proxima`) enxerga o estado.
    """
    try:
        return dict(carregar_estado(w).get("nuvem") or {})
    except (OSError, ValueError, KeyError):
        return {}


def numeros(w: Path) -> list[str]:
    """As faixas que existem no disco: `faixa-1.mp3` -> `1`.

    Sem nenhuma numerada (produção de uma faixa só, ou antiga), a produção
    inteira responde como a faixa `1` — assim o modelo por faixa não abre um
    caso especial para cada pasta velha do acervo.
    """
    ns = []
    for f in sorted(Path(w).glob("faixa-*.mp3")):
        n = f.stem.rpartition("-")[2]
        if n.isdigit():
            ns.append(n)
    return ns or ["1"]


def _marcas(w: Path, n: dict | None = None) -> dict:
    """As marcas por faixa, já com o estado ANTIGO traduzido.

    Acervo aprovado antes desta versão não tem o bloco `faixas`: lá a marca era
    da produção, e o que ela queria dizer era "todas". Traduzir na leitura (e
    não numa migração de arquivos) é o que faz o acervo de 33 produções
    continuar na vitrine sem ninguém rodar nada.
    """
    n = ler(w) if n is None else n
    fx = dict(n.get("faixas") or {})
    if fx:
        return fx
    if n.get("aprovado") or n.get("publicado_em") or n.get("remover"):
        base = {"aprovado": bool(n.get("aprovado")),
                "aprovado_em": n.get("aprovado_em"),
                "publicado_em": n.get("publicado_em"),
                "remover": bool(n.get("remover"))}
        return {num: dict(base) for num in numeros(w)}
    return {}


def _palavra(m: dict) -> str:
    if m.get("remover"):
        return "remover"
    if m.get("publicado_em"):
        return "publicado"
    return "aprovado" if m.get("aprovado") else "local"


def situacao_faixa(w: Path, n: str | int) -> str:
    """Uma palavra para ESTA faixa: `local`, `aprovado`, `publicado`, `remover`."""
    return _palavra(_marcas(w).get(str(n), {}))


def situacao(w: Path) -> str:
    """Uma palavra para a PRODUÇÃO — o resumo que o card e a grade mostram.

    Com faixas em pés diferentes vale a mais "adiantada": uma faixa na fila faz
    a produção dizer `aprovado` mesmo que a outra já esteja publicada, porque o
    que interessa ali é que ainda há coisa para subir.
    """
    ms = _marcas(w)
    if not ms:
        return "local"
    palavras = {_palavra(m) for m in ms.values()}
    for p in ("remover", "aprovado", "publicado"):
        if p in palavras:
            return p
    return "local"


def _resumo(ms: dict) -> dict:
    """O bloco de topo, derivado das faixas.

    Ele não é fonte da verdade — é a tradução para quem só sabe perguntar pela
    produção (`subida.proxima`, o `publica-hf` antigo, o índice). Manter os dois
    em sincronia aqui evita que alguém leia `aprovado: true` de uma produção que
    já não tem faixa nenhuma marcada.
    """
    aprovados = [m for m in ms.values() if m.get("aprovado")]
    publicados = [m for m in ms.values() if m.get("publicado_em")]
    return {"aprovado": bool(aprovados),
            "aprovado_em": max((m.get("aprovado_em") or "" for m in aprovados),
                               default="") or None,
            "publicado_em": max((m.get("publicado_em") or "" for m in publicados),
                                default="") or None,
            "remover": any(m.get("remover") for m in ms.values())}


def _grava(w: Path, ms: dict) -> None:
    est = carregar_estado(w)
    n = dict(est.get("nuvem") or {})
    n.update(_resumo(ms))
    n["faixas"] = ms
    est["nuvem"] = n
    salvar_estado(w, est)


def aprovar(w: Path, sim: bool = True, faixa: str | int | None = None) -> str:
    """Marca (ou desmarca) para a nuvem. Sem `faixa`, vale para todas.

    Desmarcar NÃO apaga o que já está publicado — deixa uma pendência de
    remoção. Apagar de um lado e esquecer do outro é como um acervo público
    passa a mostrar o que já foi retirado do ar.
    """
    ms = _marcas(w)
    alvos = [str(faixa)] if faixa is not None else (list(ms) or numeros(w))
    for num in alvos:
        m = dict(ms.get(num) or {})
        if sim:
            m.update({"aprovado": True, "aprovado_em": _agora(), "remover": False})
        else:
            m["aprovado"] = False
            m["remover"] = bool(m.get("publicado_em"))
        ms[num] = m
    _grava(w, ms)
    return situacao_faixa(w, faixa) if faixa is not None else situacao(w)


def marcar_publicado(w: Path, quando: str | None = None,
                     faixa: str | int | None = None) -> None:
    """Chamado pelo `publica-hf` depois que os arquivos chegaram ao HF."""
    ms = _marcas(w)
    alvos = [str(faixa)] if faixa is not None else (list(ms) or numeros(w))
    for num in alvos:
        m = dict(ms.get(num) or {})
        m.update({"publicado_em": quando or _agora(), "remover": False})
        ms[num] = m
    _grava(w, ms)


def marcar_removido(w: Path, faixa: str | int | None = None) -> None:
    ms = _marcas(w)
    alvos = [str(faixa)] if faixa is not None else (list(ms) or numeros(w))
    for num in alvos:
        m = dict(ms.get(num) or {})
        m.update({"publicado_em": None, "remover": False, "aprovado": False})
        ms[num] = m
    _grava(w, ms)


def faixas_aprovadas(w: Path) -> list[str]:
    return [n for n, m in sorted(_marcas(w).items()) if m.get("aprovado")]


def faixas_publicadas(w: Path) -> list[str]:
    return [n for n, m in sorted(_marcas(w).items()) if m.get("publicado_em")]


def faixas_a_remover(w: Path) -> list[str]:
    return [n for n, m in sorted(_marcas(w).items()) if m.get("remover")]


def pendentes(outdir: Path) -> list[str]:
    """Slugs com ALGUMA faixa aprovada — publicada ou não. Isto é uma marcação,
    não uma fila.

    Quem decide o que de fato precisa subir é o `publicahf.a_subir`, que tira
    daqui quem já subiu e não mudou. Esta função dizia "que ainda não subiram",
    e não era verdade: o `publica-hf` reenviava o acervo inteiro toda vez.
    """
    return [w.name for w in sorted(p for p in outdir.iterdir() if p.is_dir())
            if faixas_aprovadas(w)]


def a_remover(outdir: Path) -> list[str]:
    """Produções que saem INTEIRAS do acervo público.

    Tirar uma faixa de duas não apaga a pasta — os arquivos da outra continuam
    lá e a vitrine continua mostrando ela. A pasta só sai quando não sobra
    faixa nenhuma para o lado de fora.
    """
    fora = []
    for w in sorted(p for p in outdir.iterdir() if p.is_dir()):
        ms = _marcas(w)
        if any(m.get("remover") for m in ms.values()) and not any(
                m.get("aprovado") for m in ms.values()):
            fora.append(w.name)
    return fora

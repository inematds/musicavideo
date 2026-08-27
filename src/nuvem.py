"""A aprovação de subida: o gesto que decide o que vira vitrine.

Subir para a nuvem não é consequência de ficar pronto. Produção pronta é
material de trabalho; vitrine é escolha, e quem escolhe é quem está olhando —
no painel local, com o clipe tocando ao lado. Por isso a marca mora aqui e não
no fluxo de geração: nada sobe sozinho.

O que este módulo guarda é só a MARCA. Quem sobe de fato é o `publica-hf`.
"""
from datetime import datetime, timezone, timedelta
from pathlib import Path

from src.estado import carregar_estado, salvar_estado

TZ = timezone(timedelta(hours=-3))


def _agora() -> str:
    return datetime.now(TZ).isoformat(timespec="seconds")


def ler(w: Path) -> dict:
    """`{aprovado, aprovado_em, publicado_em, remover}` — vazio quando nunca tocado."""
    try:
        return dict(carregar_estado(w).get("nuvem") or {})
    except (OSError, ValueError, KeyError):
        return {}


def situacao(w: Path) -> str:
    """Uma palavra para o painel: `local`, `aprovado`, `publicado` ou `remover`."""
    n = ler(w)
    if n.get("remover"):
        return "remover"
    if n.get("publicado_em"):
        return "publicado"
    return "aprovado" if n.get("aprovado") else "local"


def aprovar(w: Path, sim: bool = True) -> str:
    """Marca (ou desmarca) a produção para a nuvem.

    Desmarcar NÃO apaga o que já está publicado — deixa uma pendência de
    remoção. Apagar de um lado e esquecer do outro é como um acervo público
    passa a mostrar o que já foi retirado do ar.
    """
    est = carregar_estado(w)
    n = dict(est.get("nuvem") or {})
    if sim:
        n.update({"aprovado": True, "aprovado_em": _agora(), "remover": False})
    else:
        n["aprovado"] = False
        n["remover"] = bool(n.get("publicado_em"))
    est["nuvem"] = n
    salvar_estado(w, est)
    return situacao(w)


def marcar_publicado(w: Path, quando: str | None = None) -> None:
    """Chamado pelo `publica-hf` depois que os arquivos chegaram ao HF."""
    est = carregar_estado(w)
    n = dict(est.get("nuvem") or {})
    n.update({"publicado_em": quando or _agora(), "remover": False})
    est["nuvem"] = n
    salvar_estado(w, est)


def marcar_removido(w: Path) -> None:
    est = carregar_estado(w)
    n = dict(est.get("nuvem") or {})
    n.update({"publicado_em": None, "remover": False, "aprovado": False})
    est["nuvem"] = n
    salvar_estado(w, est)


def pendentes(outdir: Path) -> list[str]:
    """Slugs aprovados que ainda não subiram (ou que mudaram e precisam subir)."""
    return [w.name for w in sorted(p for p in outdir.iterdir() if p.is_dir())
            if ler(w).get("aprovado")]


def a_remover(outdir: Path) -> list[str]:
    return [w.name for w in sorted(p for p in outdir.iterdir() if p.is_dir())
            if ler(w).get("remover")]

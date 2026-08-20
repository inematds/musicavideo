"""estado.json: fonte de verdade. Máquina: planejado→(ok)→aprovado→(faz)→gerando→pronto|erro;
erro→(faz retry)|(ajusta→planejado); pronto→(refaz→planejado)."""
import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

TZ = timezone(timedelta(hours=-3))
PARTES = ("musica", "capa", "clipe")


class TransicaoInvalida(ValueError):
    pass


def _agora() -> str:
    return datetime.now(TZ).isoformat(timespec="seconds")


def novo_estado(slug: str) -> dict:
    return {"schema_version": "1", "slug": slug, "atualizado_em": _agora(),
            "fase": "plano", "telegram": False, "teto_usd": None,
            "partes": {p: {"estado": "planejado", "aprovado_em": None, "ajustes": 0,
                           "tentativas": 0, "custo_estimado_usd": 0.0, "custo_real_usd": 0.0,
                           "artefato": None, "erro": None, "meta": {}} for p in PARTES},
            "custo_total_usd": {"estimado": 0.0, "gasto": 0.0},
            "historico": [{"quando": _agora(), "evento": "plano", "detalhe": "criado"}]}


_TRANSICOES = {  # (estado_atual, evento) -> novo_estado
    ("planejado", "ok"): "aprovado",
    ("planejado", "ajusta"): "planejado",
    ("aprovado", "ajusta"): "planejado",
    ("aprovado", "faz"): "gerando",
    ("gerando", "pronto"): "pronto",
    ("gerando", "erro"): "erro",
    ("erro", "faz"): "gerando",
    ("erro", "ajusta"): "planejado",
    ("pronto", "refaz"): "planejado",
}


def transicao(estado: dict, parte: str, evento: str, **kw) -> None:
    p = estado["partes"][parte]
    novo = _TRANSICOES.get((p["estado"], evento))
    if novo is None:
        raise TransicaoInvalida(
            f"{parte}: '{evento}' não vale no estado '{p['estado']}' "
            f"(transições: {sorted(set(e for s, e in _TRANSICOES if s == p['estado']))})")
    p["estado"] = novo
    if evento == "ok":
        p["aprovado_em"] = _agora()
    elif evento == "ajusta":
        p["ajustes"] += 1
        p["aprovado_em"] = None
        p["erro"] = None
    elif evento == "faz":
        p["tentativas"] += 1
        p["erro"] = None
    elif evento == "pronto":
        p["artefato"] = kw["artefato"]
        p["erro"] = None
        p["custo_real_usd"] += float(kw.get("custo_real", 0.0))
        estado["custo_total_usd"]["gasto"] = round(
            sum(x["custo_real_usd"] for x in estado["partes"].values()), 4)
        if "meta" in kw:
            p["meta"] = kw["meta"]
    elif evento == "erro":
        p["erro"] = {"quando": _agora(), "motor": kw.get("motor", ""), "msg": kw.get("msg", "")}
    elif evento == "refaz":
        p["aprovado_em"] = None
        p["artefato"] = None
    registrar(estado, evento, parte=parte)


def registrar(estado: dict, evento: str, **detalhe) -> None:
    estado["historico"].append({"quando": _agora(), "evento": evento, **detalhe})


def salvar_estado(workdir: Path, estado: dict) -> None:
    estado["atualizado_em"] = _agora()
    alvo = workdir / "estado.json"
    tmp = workdir / "estado.json.tmp"
    tmp.write_text(json.dumps(estado, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, alvo)


def _lock(workdir: Path, parte: str) -> Path:
    return workdir / f".gerando-{parte}.pid"


def marcar_gerando(workdir: Path, parte: str) -> None:
    """Marca que ESTE processo está gerando a parte — distingue uma corrida viva
    de um `gerando` órfão deixado por crash/ctrl-c."""
    _lock(workdir, parte).write_text(str(os.getpid()), encoding="utf-8")


def desmarcar_gerando(workdir: Path, parte: str) -> None:
    _lock(workdir, parte).unlink(missing_ok=True)


def _vivo(workdir: Path, parte: str) -> bool:
    arq = _lock(workdir, parte)
    if not arq.exists():
        return False
    try:
        os.kill(int(arq.read_text().strip()), 0)   # sinal 0: só testa existência
        return True
    except (ValueError, ProcessLookupError):
        return False
    except PermissionError:
        return True


def carregar_estado(workdir: Path) -> dict:
    estado = json.loads((workdir / "estado.json").read_text(encoding="utf-8"))
    for parte, p in estado["partes"].items():
        if p["estado"] == "gerando" and _vivo(workdir, parte):
            continue                   # corrida viva: não mexer
        if p["estado"] == "gerando":   # crash/ctrl-c anterior
            p["estado"] = "erro"
            p["erro"] = {"quando": _agora(), "motor": "", "msg": "interrompido"}
            registrar(estado, "erro", parte=parte, detalhe="gerando interrompido")
    return estado

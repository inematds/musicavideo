"""Mescla providers/*.models.json num registry único; indisponível-com-motivo."""
import importlib
import json
from pathlib import Path

PROVIDERS_DIR = Path(__file__).resolve().parents[1] / "providers"


def carregar_registry() -> dict:
    reg = {}
    for mj in sorted(PROVIDERS_DIR.glob("*.models.json")):
        decl = json.loads(mj.read_text(encoding="utf-8"))
        mod = importlib.import_module(f"providers.{decl['provider']}")
        prov = mod.criar(decl)   # cada providers/<nome>.py expõe criar(decl) -> Provider
        for m in decl["modelos"]:
            reg[f"{decl['provider']}:{m['id']}"] = {"provider": prov, "modelo": m}
    return reg


def resolver_motor(reg: dict, motor: str):
    if motor not in reg:
        prov = motor.split(":")[0]
        raise KeyError(f"motor '{motor}' não existe no registry (provider '{prov}'; "
                       f"disponíveis: {sorted(reg)})")
    e = reg[motor]
    return e["provider"], e["modelo"]


def disponibilidade(reg: dict) -> dict:
    vistos = {}
    for e in reg.values():
        p = e["provider"]
        if p.nome not in vistos:
            vistos[p.nome] = p.disponivel()
    return vistos


def validar_params(modelo: dict, params: dict) -> list[str]:
    declarados = set(modelo.get("params", {}))
    return [f"param desconhecido '{k}' pro modelo {modelo['id']}"
            for k in params if k not in declarados]

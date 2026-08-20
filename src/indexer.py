"""index.jsonl: 1 linha por slug, reescrita por todo comando que muda estado."""
import json
import os
from pathlib import Path


def linha_de(plano: dict, estado: dict) -> dict:
    return {"slug": plano["slug"], "titulo": plano["titulo"],
            "criado_em": plano["criado_em"], "solicitacao": plano["solicitacao"],
            "estilo_ref": plano["estilo_ref"],
            "genero": plano["musica"]["estilo"]["genero"],
            "bpm": plano["musica"]["estilo"]["bpm"],
            "tom": plano["musica"]["estilo"]["tom"],
            "motores": {p: plano[p]["motor"] for p in ("musica", "capa", "clipe")},
            "estados": {p: estado["partes"][p]["estado"] for p in ("musica", "capa", "clipe")},
            "custo_gasto_usd": estado["custo_total_usd"]["gasto"],
            "tags": plano["musica"]["estilo"]["mood"]}


def _ler(outdir: Path) -> list[dict]:
    arq = outdir / "index.jsonl"
    if not arq.exists():
        return []
    return [json.loads(l) for l in arq.read_text(encoding="utf-8").splitlines() if l.strip()]


def _escrever(outdir: Path, linhas: list[dict]) -> None:
    tmp = outdir / "index.jsonl.tmp"
    tmp.write_text("".join(json.dumps(l, ensure_ascii=False) + "\n" for l in linhas),
                   encoding="utf-8")
    os.replace(tmp, outdir / "index.jsonl")


def gravar_linha(outdir: Path, linha: dict) -> None:
    linhas = [l for l in _ler(outdir) if l["slug"] != linha["slug"]]
    linhas.append(linha)
    _escrever(outdir, linhas)


def lista(outdir: Path, n: int = 10) -> list[dict]:
    return list(reversed(_ler(outdir)))[:n]


def busca(outdir: Path, termo: str) -> list[dict]:
    t = termo.lower()

    def bate(l):
        campos = [l["slug"], l["titulo"], l["solicitacao"], str(l["genero"])] + list(l["tags"])
        return any(t in str(c).lower() for c in campos)

    return [l for l in _ler(outdir) if bate(l)]


def reindex(outdir: Path) -> int:
    from src.estado import carregar_estado
    linhas = []
    for w in sorted(p for p in outdir.iterdir() if p.is_dir()):
        pj, ej = w / "plano.json", w / "estado.json"
        if pj.exists() and ej.exists():
            linhas.append(linha_de(json.loads(pj.read_text(encoding="utf-8")),
                                   carregar_estado(w)))
    _escrever(outdir, linhas)
    return len(linhas)


def contexto_acervo(outdir: Path, solicitacao: str, n: int = 5) -> list[dict]:
    recentes = lista(outdir, n)
    matches = [l for tok in solicitacao.lower().split() if len(tok) > 3
               for l in busca(outdir, tok)]
    vistos, saida = set(), []
    for l in recentes + matches:
        if l["slug"] not in vistos:
            vistos.add(l["slug"])
            saida.append(l)
    return saida

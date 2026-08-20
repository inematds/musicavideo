"""Referência visual MEDIDA para o planejamento do clipe.

Os templates de clipe são esqueletos genéricos. Isto aqui traz o que funcionou
de verdade: paleta, look, movimento de câmera e ritmo de corte extraídos de
vídeos reais pelo `analisevideo` (banco em ~/projetos/output/analisevideo/).

Banco ausente = lista vazia, sem erro: a referência é um bônus, não um requisito.
"""
import json
import os
import unicodedata
from pathlib import Path

PESO_TIPO_CLIPE = 3.0     # análise de clipe musical vale mais que de infográfico
PESO_TAG = 2.0
PESO_MOOD = 2.0
MAX_REFS = 3
CORTE_RELATIVO = 0.4     # descarta referência fraca perto da melhor (evita carona)


def _banco() -> Path:
    return Path(os.environ.get("MUSICAVIDEO_ANALISEVIDEO",
                               str(Path.home() / "projetos/output/analisevideo")))


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return s.lower()


def _tokens(*textos) -> set:
    saida = set()
    for t in textos:
        if isinstance(t, (list, tuple)):
            saida |= _tokens(*t)
        else:
            saida |= {p for p in _norm(t).replace("/", " ").replace(",", " ").split()
                      if len(p) > 3}
    return saida


def _ler_index() -> list[dict]:
    arq = _banco() / "index.jsonl"
    if not arq.exists():
        return []
    linhas = []
    for l in arq.read_text(encoding="utf-8", errors="ignore").splitlines():
        if l.strip():
            try:
                linhas.append(json.loads(l))
            except json.JSONDecodeError:
                continue
    return linhas


def _pontuar(linha: dict, alvo: set) -> float:
    p = 0.0
    if "clipe" in _norm(linha.get("tipo", "")) or "music" in _norm(linha.get("tipo", "")):
        p += PESO_TIPO_CLIPE
    p += PESO_TAG * len(alvo & _tokens(linha.get("tags", [])))
    p += PESO_MOOD * len(alvo & _tokens(linha.get("mood", "")))
    p += len(alvo & _tokens(linha.get("look", ""), linha.get("resumo", ""),
                            linha.get("titulo", "")))
    return p


def referencias_visuais(solicitacao: str, mood, genero: str, n: int = MAX_REFS) -> list[dict]:
    """As N análises do acervo que mais casam com a música que está sendo planejada."""
    alvo = _tokens(solicitacao, mood or [], genero or "")
    pontuadas = [(_pontuar(l, alvo), l) for l in _ler_index()]
    pontuadas = [(p, l) for p, l in pontuadas if p > 0]
    if not pontuadas:
        return []
    pontuadas.sort(key=lambda x: (-x[0], x[1].get("slug", "")))
    minimo = pontuadas[0][0] * CORTE_RELATIVO
    return [l for p, l in pontuadas[:n] if p >= minimo]


def _camera_notavel(slug: str, limite: int = 3) -> list[str]:
    """Movimentos de câmera com timecode, da análise completa (quando existe)."""
    arq = _banco() / slug / "analise.json"
    if not arq.exists():
        return []
    try:
        d = json.loads(arq.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    blocos = d.get("camera") or []
    saida = []
    for b in blocos[:limite]:
        if isinstance(b, dict):
            partes = [str(b.get(k, "")) for k in ("timecode", "plano", "movimento", "nota")]
            saida.append(" · ".join(x for x in partes if x))
    return saida


def resumir_para_contexto(refs: list[dict]) -> str:
    """Resumo curto — o contexto do planejador não pode inchar com JSON cru."""
    if not refs:
        return ""
    linhas = []
    for r in refs:
        cpm = r.get("cortes_por_minuto")
        campos = [f"- **{r.get('slug')}** ({r.get('tipo', '?')})",
                  f"look: {r.get('look', '?')}",
                  f"paleta: {', '.join(r.get('paleta') or []) or '?'}",
                  f"câmera: {', '.join(r.get('movimentos') or []) or '?'}",
                  f"ritmo: {r.get('ritmo', '?')}"
                  + (f", {cpm:g} cortes/min" if isinstance(cpm, (int, float)) else "")]
        if r.get("bpm"):
            campos.append(f"bpm: {r['bpm']}")
        if r.get("referencias"):
            campos.append("refs: " + ", ".join(map(str, r["referencias"][:3])))
        linhas.append(" | ".join(campos))
        for c in _camera_notavel(r.get("slug", "")):
            linhas.append(f"    · {c}")
    return "\n".join(linhas)[:1800]

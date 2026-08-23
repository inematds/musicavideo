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
LIMITE_RESUMO = 2600     # com a montagem junto, 1800 cortava a 3ª referência


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


def _analise(slug: str) -> dict:
    """A análise COMPLETA da referência. O `index.jsonl` é uma projeção que
    deixa `montagem` e `pos_producao` de fora — e é justamente ali que está
    como os planos se LIGAM. São 3 refs por plano: abrir o arquivo é barato."""
    arq = _banco() / slug / "analise.json"
    if not arq.exists():
        return {}
    try:
        d = json.loads(arq.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return {}          # análise quebrada não derruba o planejamento
    return d if isinstance(d, dict) else {}


def _camera_notavel(d: dict, limite: int = 3) -> list[str]:
    """Movimentos de câmera com timecode, da análise completa (quando existe)."""
    saida = []
    for b in (d.get("camera") or [])[:limite]:
        if isinstance(b, dict):
            partes = [str(b.get(k, "")) for k in ("timecode", "plano", "movimento", "nota")]
            saida.append(" · ".join(x for x in partes if x))
    return saida


def _montagem_notavel(d: dict) -> list[str]:
    """COMO os planos se ligam — o dado que o índice descarta.

    Sem isto o planejador nunca viu a palavra "whip pan" vinda de um vídeo que
    funcionou de verdade: ele recebia adjetivo ("acelerado") e devolvia ritmo
    parelho. Aqui vai o medido: transições usadas, corte no beat, speedramp.
    """
    m = d.get("montagem") or {}
    if not isinstance(m, dict) or not m:
        return []
    campos = []
    if m.get("tipos_de_transicao"):
        campos.append("transições: " + ", ".join(map(str, m["tipos_de_transicao"][:4])))
    marcas = [nome for chave, nome in (("corte_no_beat", "corte no beat"),
                                       ("match_cut", "match cut"),
                                       ("jump_cut", "jump cut"),
                                       ("uso_de_slowmo_speedramp", "slowmo/speedramp"))
              if m.get(chave)]
    if marcas:
        campos.append("usa: " + ", ".join(marcas))
    if m.get("cortes_estimados"):
        campos.append(f"{m['cortes_estimados']} cortes no total")
    pos = d.get("pos_producao") or {}
    if isinstance(pos, dict):
        if pos.get("lut_sugerida"):
            campos.append(f"LUT: {pos['lut_sugerida']}")
        if pos.get("sound_design"):
            campos.append(f"som: {pos['sound_design']}")
    return [f"    ▸ montagem — {' | '.join(campos)}"] if campos else []


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
        completa = _analise(r.get("slug", ""))
        linhas += _montagem_notavel(completa)
        for c in _camera_notavel(completa):
            linhas.append(f"    · {c}")
    return "\n".join(linhas)[:LIMITE_RESUMO]

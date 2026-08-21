"""Validação FECHADA dos contratos (spec §8): campo desconhecido é erro."""
import re

_ESTADOS = {"planejado", "aprovado", "gerando", "revisao", "pronto", "erro"}
_PARTES = ("musica", "capa", "clipe")
_ACENTOS = re.compile(r"[áàâãéêíóôõúüçÁÀÂÃÉÊÍÓÔÕÚÜÇ]")


def _chaves(d: dict, obrig: set, opc: set, ctx: str, erros: list):
    for k in d:
        if k not in obrig | opc:
            erros.append(f"{ctx}: campo desconhecido '{k}'")
    for k in obrig:
        if k not in d:
            erros.append(f"{ctx}: campo obrigatório '{k}' ausente")


def _motor_ok(m, ctx, erros):
    if not (isinstance(m, str) and re.fullmatch(r"[a-z0-9_-]+:[A-Za-z0-9._/-]+", m)):
        erros.append(f"{ctx}: motor inválido '{m}' (esperado provider:modelo)")


def _listas(d: dict, campos: tuple, ctx: str, erros: list):
    """Campo de lista que vem como string vira lista de LETRAS lá na frente."""
    for k in campos:
        if k in d and not isinstance(d[k], list):
            erros.append(f"{ctx}.{k}: deve ser lista, veio {type(d[k]).__name__}")


def validar_plano(plano: dict) -> list[str]:
    erros: list[str] = []
    _chaves(plano, {"schema_version", "slug", "criado_em", "solicitacao", "pesquisa",
                    "estilo_ref", "titulo", "musica", "capa", "clipe"}, set(), "plano", erros)
    if plano.get("schema_version") != "1":
        erros.append('plano: schema_version deve ser "1"')
    m = plano.get("musica", {})
    _chaves(m, {"motor", "params", "estilo", "estrutura", "letra"}, set(), "musica", erros)
    if "motor" in m:
        _motor_ok(m["motor"], "musica", erros)
    est = m.get("estilo", {})
    _chaves(est, {"genero", "bpm", "tom", "mood", "instrumentacao", "voz", "prompt_estilo"},
            set(), "musica.estilo", erros)
    _listas(est, ("mood", "instrumentacao"), "musica.estilo", erros)
    _listas(m, ("estrutura",), "musica", erros)
    le = m.get("letra", {})
    _chaves(le, {"origem", "texto", "texto_original", "idioma"}, set(), "musica.letra", erros)
    if le.get("origem") not in (None, "gerada", "rascunho_usuario", "final_usuario"):
        erros.append(f"musica.letra: origem inválida '{le.get('origem')}'")
    if le.get("origem") == "final_usuario" and not le.get("texto"):
        erros.append("musica.letra: origem final_usuario exige texto não vazio")
    c = plano.get("capa", {})
    _chaves(c, {"motor", "params", "template", "conceito", "prompt_imagem",
                "prompt_negativo", "paleta"}, set(), "capa", erros)
    if "motor" in c:
        _motor_ok(c["motor"], "capa", erros)
    _listas(c, ("paleta",), "capa", erros)
    v = plano.get("clipe", {})
    _chaves(v, {"motor", "params", "template", "sincronia", "decupagem"}, set(), "clipe", erros)
    if "motor" in v:
        _motor_ok(v["motor"], "clipe", erros)
    _listas(v, ("decupagem",), "clipe", erros)
    for i, shot in enumerate(v.get("decupagem", []) or []):
        _chaves(shot, {"n", "secao", "duracao_s", "camera", "descricao", "prompt"},
                {"prompt_alt"}, f"clipe.decupagem[{i}]", erros)
    return erros


# Comparar com artista é o jeito mais natural de descrever som — e é recusado
# pelo provedor. No MVD#89 (2026-08-21) o `prompt_estilo` terminava com
# "Wardruna meets anthem rock": o plano validou, o portão abriu, a fase custou
# uma vaga na fila de IO e o Suno recusou na hora de gerar. O erro só aparecia
# onde ele custa.
#
# Duas famílias, e nenhuma tenta ser um catálogo de música: a construção
# comparativa (que é o que o filtro do provedor procura) e uma lista curta de
# nomes vistos em recusa real, que cresce por evidência, não por palpite.
_COMPARACAO = re.compile(
    r"\b(?:meets|in the style of|style of|sounds? like|similar to|inspired by|"
    r"reminiscent of|à la|a la|tribute to|cover of|vibes? of)\b",
    re.IGNORECASE,
)
_ARTISTAS = re.compile(
    r"\b(?:wardruna|heilung|danheim|hans zimmer|ludovico einaudi|beyonc[ée]|"
    r"taylor swift|drake|the weeknd|billie eilish|adele|coldplay|radiohead|"
    r"pink floyd|metallica|nirvana|queen|beatles|rolling stones)\b",
    re.IGNORECASE,
)


def referencias_a_artista(txt: str) -> list[str]:
    """Trechos do prompt que o provedor tende a recusar. Vazio = limpo."""
    achados = [m.group(0) for m in _ARTISTAS.finditer(txt)]
    achados += [m.group(0) for m in _COMPARACAO.finditer(txt)]
    vistos, unicos = set(), []
    for a in achados:
        if a.lower() in vistos:
            continue
        vistos.add(a.lower())
        unicos.append(a)
    return unicos


def campos_prompt_en(plano: dict) -> list[str]:
    """Prompts que vão pro provedor DEVEM ser EN (Agnes 400 em PT legítimo)."""
    erros = []
    alvos = [("musica.estilo.prompt_estilo", plano["musica"]["estilo"].get("prompt_estilo", "")),
             ("capa.prompt_imagem", plano["capa"].get("prompt_imagem", "")),
             ("capa.prompt_negativo", plano["capa"].get("prompt_negativo", ""))]
    for i, s in enumerate(plano["clipe"].get("decupagem", []) or []):
        alvos.append((f"clipe.decupagem[{i}].prompt", s.get("prompt", "")))
        if s.get("prompt_alt"):
            alvos.append((f"clipe.decupagem[{i}].prompt_alt", s["prompt_alt"]))
    for nome, txt in alvos:
        if _ACENTOS.search(txt or ""):
            erros.append(f"{nome}: prompt de provedor deve ser em INGLÊS (achei acento)")
        for achado in referencias_a_artista(txt or ""):
            erros.append(
                f"{nome}: prompt cita artista/comparação ('{achado}') — provedor recusa. "
                "Descreva o som ou a imagem por características, nunca por comparação"
            )
    return erros


def validar_estado(estado: dict) -> list[str]:
    erros: list[str] = []
    _chaves(estado, {"schema_version", "slug", "atualizado_em", "fase", "telegram",
                     "teto_usd", "partes", "custo_total_usd", "historico"}, set(), "estado", erros)
    if estado.get("fase") not in ("plano", "execucao", "entregue"):
        erros.append(f"estado: fase inválida '{estado.get('fase')}'")
    for p in _PARTES:
        d = estado.get("partes", {}).get(p)
        if d is None:
            erros.append(f"estado: parte '{p}' ausente")
            continue
        _chaves(d, {"estado", "aprovado_em", "ajustes", "tentativas", "custo_estimado_usd",
                    "custo_real_usd", "artefato", "erro", "meta"}, set(), f"estado.{p}", erros)
        if d.get("estado") not in _ESTADOS:
            erros.append(f"estado.{p}: estado inválido '{d.get('estado')}'")
    return erros

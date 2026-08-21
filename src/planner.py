"""Fase 1: monta o contexto, chama o Fable, valida e grava plano.json + PLANO.md."""
import difflib
import json
import re
import subprocess
import unicodedata
from pathlib import Path

from src.esquemas import validar_plano, campos_prompt_en
from src.estado import (novo_estado, salvar_estado, carregar_estado, transicao, _agora)
from src.indexer import linha_de, gravar_linha, contexto_acervo
from src.referencias import referencias_visuais, resumir_para_contexto
from src.registry import carregar_registry, disponibilidade, resolver_motor, validar_params

RAIZ = Path(__file__).resolve().parents[1]
PARTES = ("musica", "capa", "clipe")
DUR_SHOT_PADRAO = 5          # segundos por shot (limite prático do Agnes)
COBERTURA_MINIMA = 0.9       # o clipe tem que cobrir ao menos 90% da faixa
MOTORES_DEFAULT = {"musica": "kie:suno-v4.5",
                   "capa": "agnes:agnes-image-2.1-flash",
                   "clipe": "agnes:agnes-video-v2.0"}


def derivar_slug(solicitacao: str, outdir: Path) -> str:
    s = unicodedata.normalize("NFKD", solicitacao).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:40].rstrip("-")
    base, n = s, 2
    while (outdir / s).exists():
        s = f"{base}-{n}"
        n += 1
    return s


def chamar_fable(prompt: str) -> str:
    try:
        r = subprocess.run(["claude", "-p", prompt, "--model", "fable"],
                           capture_output=True, text=True, timeout=900)
    except FileNotFoundError:
        raise RuntimeError("binário 'claude' não encontrado — o planner precisa do Claude Code no PATH")
    if r.returncode != 0:
        raise RuntimeError(f"claude -p falhou: {r.stderr[:300]}")
    return r.stdout


def _extrair_json(texto: str) -> dict:
    m = re.search(r"\{.*\}", texto, re.S)
    if not m:
        raise ValueError("resposta do planejador não contém JSON")
    return json.loads(m.group(0))


def _arquivo_estilos() -> Path:
    e = RAIZ / "data/estilos.json"
    return e if e.exists() else RAIZ / "tests/fixtures/estilos.json"


def montar_contexto(solicitacao: str, opts: dict, outdir: Path) -> str:
    partes = [
        "Você é o planejador do musicavideo. Responda APENAS um JSON no schema plano.json v1 "
        "(schema_version, slug, criado_em, solicitacao, pesquisa, estilo_ref, titulo, musica, capa, clipe).",
        "Estrutura exata: musica{motor,params,estilo{genero,bpm,tom,mood,instrumentacao,voz,prompt_estilo},"
        "estrutura[{secao,inicio_s,duracao_s}],letra{origem,texto,texto_original,idioma}}; capa{motor,params,template,conceito,"
        "prompt_imagem,prompt_negativo,paleta}; clipe{motor,params,template,sincronia,"
        "decupagem[{n,secao,duracao_s,camera,descricao,prompt,prompt_alt}]}. NENHUM campo a mais.",
        "PLANO B: cada shot leva também `prompt_alt` — a MESMA cena e a mesma duração "
        "contada pelo lado seguro, para quando o filtro de conteúdo barrar o prompt "
        "principal. No alt: sem rostos em close, sem violência, sem marcas, sem texto "
        "legível; prefira objeto, ambiente, silhueta, luz e sombra. O alt tem que "
        "cumprir o MESMO papel narrativo no mesmo instante da música.",
        "PROIBIDO citar artista, banda, compositor ou obra em QUALQUER prompt de provedor "
        "(prompt_estilo, prompt_imagem, prompt_negativo, decupagem[].prompt/prompt_alt) — nem por "
        "nome, nem por comparação (\"X meets Y\", \"in the style of\", \"sounds like\", \"à la\"). "
        "O provedor RECUSA a geração, e a recusa só aparece na hora de gastar. Descreva o som e a "
        "imagem por características: instrumentação, timbre, técnica vocal, andamento, textura, luz.",
        "REGRA: os campos musica.estilo.prompt_estilo, capa.prompt_imagem, capa.prompt_negativo e "
        "clipe.decupagem[].prompt DEVEM ser em INGLÊS (a API Agnes bloqueia português). "
        "conceito/descricao/letra/mood podem ser em português.",
        "Motores default: " + json.dumps(MOTORES_DEFAULT),
        f"DURAÇÃO: o clipe DEVE cobrir a música INTEIRA. A faixa terá ~{_dur_alvo(opts)}s, "
        f"então a decupagem precisa de ~{_n_shots_alvo(opts)} shots de {DUR_SHOT_PADRAO}s "
        f"(soma de duracao_s ≈ duração da faixa). Um clipe mais curto que a música é "
        f"REJEITADO na validação. Distribua os shots pelas seções da estrutura: mais shots "
        f"nos refrões, e variação real entre eles (nada de repetir o mesmo plano).",
        f"SOLICITAÇÃO: {solicitacao}",
        "ESTILOS: " + _arquivo_estilos().read_text(encoding="utf-8"),
        "TEMPLATES CAPA: " + (RAIZ / "data/templates-capa.json").read_text(encoding="utf-8"),
        "TEMPLATES CLIPE: " + (RAIZ / "data/templates-clipe.json").read_text(encoding="utf-8"),
        "ACERVO: " + json.dumps(contexto_acervo(outdir, solicitacao), ensure_ascii=False),
    ]
    refs = resumir_para_contexto(referencias_visuais(
        solicitacao, opts.get("mood") or [], opts.get("estilo") or ""))
    if refs:
        partes.append(
            "REFERÊNCIAS VISUAIS MEDIDAS (vídeos reais analisados quadro a quadro pelo "
            "analisevideo — paleta em hex, movimento de câmera, ritmo de corte que "
            "funcionaram de verdade). Use como base da decupagem e da paleta da capa; "
            "não copie o conteúdo, copie a LINGUAGEM visual:\n" + refs)
    if opts.get("estilo"):
        partes.append(f"ESTILO PEDIDO: {opts['estilo']}")
    if opts.get("idioma"):
        # Nos DOIS lugares, e por isso é explícito: a letra que vai ser cantada
        # e a frase final do prompt de estilo ("Lyrics in <idioma>"), que é o que
        # o Suno lê. Declarar só um dos dois produz faixa cantada num idioma e
        # pedida em outro.
        partes.append(
            f"IDIOMA DA LETRA: {opts['idioma']}. Escreva musica.letra.texto NESTE idioma, "
            f"declare musica.letra.idioma = \"{opts['idioma']}\", e termine o prompt_estilo "
            f"com \"Lyrics in {opts['idioma']}\" (o prompt_estilo continua em INGLÊS)."
        )
    if opts.get("pesquisa_md"):
        partes.append("PESQUISA:\n" + opts["pesquisa_md"])
    if opts.get("letra"):
        modo = ("FINAL (copiar VERBATIM em musica.letra.texto, origem final_usuario)"
                if opts.get("letra_final") else
                "RASCUNHO (terminar/ajustar; origem rascunho_usuario; guardar o original em texto_original)")
        partes.append(f"LETRA {modo}:\n" + Path(opts["letra"]).read_text(encoding="utf-8"))
    partes.append("Antes de responder, faça um passe de autocrítica: coerência letra↔estrutura↔decupagem, "
                  "prompts completos e em inglês, params válidos. Responda só o JSON final.")
    return "\n\n".join(partes)


def _dur_alvo(opts: dict) -> int:
    return int(opts.get("duracao_s") or 180)


def _n_shots_alvo(opts: dict) -> int:
    return max(1, round(_dur_alvo(opts) / DUR_SHOT_PADRAO))


def cobertura_do_clipe(plano: dict) -> list[str]:
    """Clipe mais curto que a música vira vídeo em loop — que não é um clipe."""
    dur_musica = int(plano.get("musica", {}).get("params", {}).get("duracao_s") or 180)
    dur_clipe = sum(s.get("duracao_s", 0) for s in plano.get("clipe", {}).get("decupagem", []) or [])
    if dur_clipe < dur_musica * COBERTURA_MINIMA:
        return [f"clipe.decupagem cobre {dur_clipe}s de uma música de ~{dur_musica}s — "
                f"decupe a música inteira (~{round(dur_musica / DUR_SHOT_PADRAO)} shots "
                f"de {DUR_SHOT_PADRAO}s)"]
    return []


def _validar_tudo(plano: dict, reg: dict) -> list[str]:
    erros = validar_plano(plano) + campos_prompt_en(plano) + cobertura_do_clipe(plano)
    for parte in PARTES:
        motor = plano.get(parte, {}).get("motor", "")
        try:
            _, modelo = resolver_motor(reg, motor)
            erros += validar_params(modelo, plano[parte].get("params", {}))
        except KeyError as e:
            erros.append(str(e))
    return erros


def _impor_deterministicos(plano: dict, slug: str, solicitacao: str, opts: dict) -> dict:
    plano.update({"schema_version": "1", "slug": slug, "criado_em": _agora(),
                  "solicitacao": solicitacao, "pesquisa": bool(opts.get("pesquisa_md"))})
    for parte, motor in MOTORES_DEFAULT.items():
        plano.setdefault(parte, {}).setdefault("motor", motor)
    for parte, motor in (opts.get("motor") or {}).items():
        plano[parte]["motor"] = motor
    # IDIOMA PEDIDO manda, e manda por último: o `setdefault` de pt-BR abaixo
    # existe para o caso de o modelo não declarar nada, não para vencer um
    # pedido explícito. Antes de 2026-08-21 não havia como pedir: pt-BR era
    # chumbado nos dois lugares (aqui e no prompt de estilo, em inglês).
    idioma = (opts.get("idioma") or "").strip()
    if idioma:
        plano.setdefault("musica", {}).setdefault("letra", {})["idioma"] = idioma
    if opts.get("letra"):
        original = Path(opts["letra"]).read_text(encoding="utf-8")
        le = plano.setdefault("musica", {}).setdefault("letra", {})
        if opts.get("letra_final"):        # a letra é lei
            plano["musica"]["letra"] = {"origem": "final_usuario", "texto": original,
                                        "texto_original": None,
                                        "idioma": idioma or le.get("idioma", "pt-BR")}
        else:                              # rascunho: origem e diff não dependem do LLM
            le["origem"] = "rascunho_usuario"
            le["texto_original"] = original
            le.setdefault("texto", original)
            le["idioma"] = idioma or le.get("idioma") or "pt-BR"
    return plano


def gerar_plano(solicitacao, slug, opts, outdir, chamar_llm=None) -> dict:
    chamar_llm = chamar_llm or chamar_fable
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    slug = slug or derivar_slug(solicitacao, outdir)
    w = outdir / slug
    if w.exists():
        if not opts.get("forca"):
            raise ValueError(f"slug '{slug}' já existe — use --forca para replanejar")
        if (w / "estado.json").exists():   # --forca não destrói o que já foi gerado e pago
            atual = carregar_estado(w)
            prontas = [p for p in PARTES if atual["partes"][p]["estado"] == "pronto"]
            if prontas:
                raise ValueError(
                    f"slug '{slug}' tem parte(s) pronta(s): {', '.join(prontas)}. "
                    f"--forca apagaria o estado e o custo já gasto. "
                    f"Use `ajusta {slug} <parte> \"...\" --refaz` para refazer só uma parte.")
    reg = carregar_registry()
    prompt = montar_contexto(solicitacao, opts, outdir)
    plano = _impor_deterministicos(_extrair_json(chamar_llm(prompt)), slug, solicitacao, opts)
    erros = _validar_tudo(plano, reg)
    if erros:   # 1 retry devolvendo os erros ao planejador
        texto = chamar_llm(prompt + "\n\nSEU JSON ANTERIOR TINHA ERROS, corrija:\n- "
                           + "\n- ".join(erros) + "\n\nJSON anterior:\n"
                           + json.dumps(plano, ensure_ascii=False))
        plano2 = _impor_deterministicos(_extrair_json(texto), slug, solicitacao, opts)
        plano2["criado_em"] = plano["criado_em"]
        plano = plano2
        erros = _validar_tudo(plano, reg)
        if erros:
            raise ValueError("plano inválido após retry:\n- " + "\n- ".join(erros))
    w.mkdir(parents=True, exist_ok=True)
    gravar_plano(w, plano, reg)
    estado = novo_estado(slug)
    salvar_estado(w, estado)
    gravar_linha(outdir, linha_de(plano, estado))
    return plano


def gravar_plano(w: Path, plano: dict, reg: dict | None = None) -> None:
    (w / "plano.json").write_text(json.dumps(plano, ensure_ascii=False, indent=2), encoding="utf-8")
    disp = disponibilidade(reg or carregar_registry())
    (w / "PLANO.md").write_text(render_plano_md(plano, disp), encoding="utf-8")


def diff_letra(plano: dict) -> str:
    le = plano["musica"]["letra"]
    if not le.get("texto_original"):
        return ""
    d = difflib.unified_diff(le["texto_original"].splitlines(), le["texto"].splitlines(),
                             "letra enviada", "letra do plano", lineterm="")
    return "\n".join(d)


def render_secao(plano: dict, parte: str) -> str:
    if parte == "musica":
        m = plano["musica"]
        e = m["estilo"]
        linhas = [f"## Música — `{m['motor']}`", "",
                  f"- **Gênero:** {e['genero']}  ·  **BPM:** {e['bpm']}  ·  **Tom:** {e['tom']}",
                  f"- **Mood:** {', '.join(e['mood'])}",
                  f"- **Instrumentação:** {', '.join(e['instrumentacao'])}",
                  f"- **Voz:** {json.dumps(e['voz'], ensure_ascii=False)}",
                  f"- **Params:** `{json.dumps(m['params'], ensure_ascii=False)}`", "",
                  "**Prompt de estilo (EN, vai pro Suno):**", "", f"> {e['prompt_estilo']}", "",
                  f"**Estrutura:** {_estrutura_txt(m['estrutura'])}", "",
                  f"**Letra** (origem: `{m['letra']['origem']}`, {m['letra']['idioma']}):", "",
                  "```", m["letra"]["texto"], "```"]
        d = diff_letra(plano)
        if d:
            linhas += ["", "**Diff do seu rascunho:**", "", "```diff", d, "```"]
        return "\n".join(linhas)
    if parte == "capa":
        c = plano["capa"]
        return "\n".join([f"## Capa — `{c['motor']}`", "",
                          f"- **Template:** {c['template']}  ·  **Paleta:** {', '.join(c['paleta'])}",
                          f"- **Params:** `{json.dumps(c['params'], ensure_ascii=False)}`", "",
                          f"**Conceito:** {c['conceito']}", "",
                          "**Prompt (EN):**", "", f"> {c['prompt_imagem']}", "",
                          f"**Negativo:** {c['prompt_negativo']}"])
    v = plano["clipe"]
    linhas = [f"## Clipe — `{v['motor']}`", "",
              f"- **Template:** {v['template']}  ·  **Sincronia:** {v['sincronia']}",
              f"- **Params:** `{json.dumps(v['params'], ensure_ascii=False)}`",
              f"- **Shots:** {len(v['decupagem'])}"
              f"  ·  **Duração total:** {sum(s['duracao_s'] for s in v['decupagem'])}s", "",
              "| # | seção | dur | câmera | descrição |", "|---|---|---|---|---|"]
    for s in v["decupagem"]:
        linhas.append(f"| {s['n']} | {s['secao']} | {s['duracao_s']}s | {s['camera']} | {s['descricao']} |")
    linhas += ["", "**Prompts (EN):**", ""]
    for s in v["decupagem"]:
        linhas.append(f"{s['n']}. {s['prompt']}")
    return "\n".join(linhas)


def _estrutura_txt(estrutura: list) -> str:
    """`musica.estrutura` aceita string ou dict — e o PLANO.md tem que sair dos dois.

    O esquema só exige que seja LISTA (`_listas`), e o schema mandado ao
    planejador não diz a forma dos itens. Em 2026-08-21 o Fable devolveu
    `[{"secao": "intro", "inicio_s": 0, "duracao_s": 15}, ...]` — plano válido,
    plano.json gravado, e o `' · '.join` estourou `TypeError` na hora de
    escrever o PLANO.md. O fluxo MVD#87 queimou as duas tentativas nisso.

    Falhar aqui é o pior lugar possível: o trabalho caro (a chamada ao modelo,
    a validação, o plano em disco) já aconteceu, e o que quebra é a formatação.
    """
    partes = []
    for item in estrutura:
        if isinstance(item, dict):
            nome = item.get("secao") or item.get("nome") or item.get("id") or "?"
            dur = item.get("duracao_s") or item.get("duracao")
            partes.append(f"{nome} ({dur}s)" if dur else str(nome))
        else:
            partes.append(str(item))
    return " · ".join(partes)


def render_plano_md(plano: dict, disp: dict) -> str:
    cab = [f"# {plano['titulo']}", "",
           f"**slug:** `{plano['slug']}`  ·  **criado:** {plano['criado_em']}",
           f"**solicitação:** {plano['solicitacao']}",
           f"**estilo de referência:** {plano['estilo_ref']}  ·  "
           f"**pesquisa:** {'sim' if plano['pesquisa'] else 'não'}", ""]
    corpo = [render_secao(plano, p) for p in PARTES]
    prov = ["## Disponibilidade dos provedores", ""]
    for nome, (ok, motivo) in sorted(disp.items()):
        prov.append(f"- **{nome}:** {'ok' if ok else motivo}")
    return "\n\n".join(cab + corpo + ["\n".join(prov)]) + "\n"


def precisa_reajuste(plano: dict, duracao_real: float) -> bool:
    """Vale mexer só se a diferença passar de um shot — abaixo disso o fade resolve."""
    dur_clipe = sum(x.get("duracao_s", 0) for x in plano["clipe"].get("decupagem", []) or [])
    return abs(duracao_real - dur_clipe) > DUR_SHOT_PADRAO


def reajustar_decupagem(workdir: Path, duracao_real: float, chamar_llm=None) -> dict:
    """Refaz a decupagem para a duração REAL da faixa aprovada.

    O plano é escrito antes de a música existir, então chuta a duração. Se a
    faixa vier bem diferente, as marcações param de bater: o refrão final da
    decupagem cai fora do refrão final da música."""
    chamar_llm = chamar_llm or chamar_fable
    workdir = Path(workdir)
    plano = json.loads((workdir / "plano.json").read_text(encoding="utf-8"))
    atual = sum(x.get("duracao_s", 0) for x in plano["clipe"]["decupagem"])
    alvo_shots = max(1, round(duracao_real / DUR_SHOT_PADRAO))
    prompt = ("Plano atual:\n" + json.dumps(plano, ensure_ascii=False)
              + f"\n\nA MÚSICA FICOU PRONTA e tem {duracao_real:.0f}s — a decupagem atual "
                f"cobre {atual}s. Reescreva APENAS a seção 'clipe' para cobrir "
                f"{duracao_real:.0f}s: {alvo_shots} shots de {DUR_SHOT_PADRAO}s, "
                f"redistribuídos pelas seções (mais nos refrões), mantendo o arco "
                f"narrativo e o estilo visual que já estavam lá. Aproveite os shots "
                f"existentes que continuarem fazendo sentido, com os mesmos prompts. "
                f"Prompts de provedor em INGLÊS, com prompt_alt em cada shot. "
                f"Responda só o JSON da seção clipe.")
    nova = _extrair_json(chamar_llm(prompt))
    candidato = dict(plano)
    candidato["clipe"] = nova
    coberto = sum(x.get("duracao_s", 0) for x in nova.get("decupagem", []) or [])
    if coberto < duracao_real * COBERTURA_MINIMA:
        raise ValueError(f"reajuste rejeitado: a nova decupagem cobre {coberto}s "
                         f"de {duracao_real:.0f}s de música")
    erros = _validar_tudo(candidato, carregar_registry())
    if erros:
        raise ValueError("reajuste inválido:\n- " + "\n- ".join(erros))
    plano["clipe"] = nova
    gravar_plano(workdir, plano)
    print(f"decupagem reajustada: {atual}s → {coberto}s "
          f"({len(nova['decupagem'])} shots) pela duração real da faixa")
    return plano


def reescritor_de_prompt(chamar_llm=None):
    """Devolve a função que o adapter usa quando o filtro barra um shot."""
    chamar_llm = chamar_llm or chamar_fable

    def reescrever(shot: dict, motivo: str) -> str:
        prompt = (f"Este prompt de vídeo foi BARRADO pelo filtro de conteúdo do "
                  f"provedor:\n{shot['prompt']}\n\nMotivo: {motivo[:200]}\n\n"
                  f"Reescreva para a MESMA cena, mesmo instante da música "
                  f"(seção '{shot.get('secao')}', câmera '{shot.get('camera')}'), "
                  f"pelo lado seguro: sem rostos em close, sem violência, sem marcas, "
                  f"sem texto legível — prefira objeto, ambiente, silhueta, luz e sombra. "
                  f"Responda SÓ o prompt novo, em inglês, numa linha.")
        try:
            texto = (chamar_llm(prompt) or "").strip().strip('"')
            return texto.splitlines()[-1].strip() if texto else ""
        except Exception:
            return ""

    return reescrever


# ---------------------------------------------------------------- portão

def aprovar_parte(outdir: Path, slug: str, parte: str) -> None:
    w = Path(outdir) / slug
    plano = json.loads((w / "plano.json").read_text(encoding="utf-8"))
    estado = carregar_estado(w)
    transicao(estado, parte, "ok")
    salvar_estado(w, estado)
    gravar_linha(Path(outdir), linha_de(plano, estado))


def ajustar_parte(outdir: Path, slug: str, parte: str, instrucao: str,
                  refaz: bool = False, chamar_llm=None) -> str:
    chamar_llm = chamar_llm or chamar_fable
    outdir = Path(outdir)
    w = outdir / slug
    plano = json.loads((w / "plano.json").read_text(encoding="utf-8"))
    estado = carregar_estado(w)
    antiga = plano[parte]
    letra_lei = (parte == "musica"
                 and antiga.get("letra", {}).get("origem") == "final_usuario")
    prompt = ("Plano atual:\n" + json.dumps(plano, ensure_ascii=False)
              + f"\n\nReescreva APENAS a seção '{parte}' seguindo: {instrucao}. "
                "Prompts de provedor em INGLÊS. Responda só o JSON da seção."
              + ("\nREGRA: musica.letra é IMUTÁVEL (final_usuario) — copie verbatim."
                 if letra_lei else ""))
    nova = _extrair_json(chamar_llm(prompt))
    if letra_lei and nova.get("letra", {}).get("texto") != antiga["letra"]["texto"]:
        raise ValueError("musica.letra é final_usuario — o ajusta não pode alterá-la")
    candidato = dict(plano)
    candidato[parte] = nova
    erros = _validar_tudo(candidato, carregar_registry())
    if erros:
        raise ValueError("ajuste inválido:\n- " + "\n- ".join(erros))
    if estado["partes"][parte]["estado"] == "pronto":
        if not refaz:
            raise ValueError(f"{parte} está pronto — use --refaz para replanejar")
        art = estado["partes"][parte]["artefato"]
        if art and (w / art).exists():
            raw = w / "raw"
            raw.mkdir(exist_ok=True, parents=True)
            n = 1
            while (raw / f"{art}-v{n}").exists():
                n += 1
            (w / art).rename(raw / f"{art}-v{n}")
        transicao(estado, parte, "refaz")
    transicao(estado, parte, "ajusta")
    plano[parte] = nova
    gravar_plano(w, plano)
    salvar_estado(w, estado)
    gravar_linha(outdir, linha_de(plano, estado))
    diff = "\n".join(difflib.unified_diff(
        json.dumps(antiga, ensure_ascii=False, indent=2).splitlines(),
        json.dumps(nova, ensure_ascii=False, indent=2).splitlines(),
        fromfile=f"{parte} (antes)", tofile=f"{parte} (depois)", lineterm=""))
    print(diff)
    return diff


# ---------------------------------------------------------------- comandos CLI

# Provedor que consome recurso do DONO — crédito de conta ou dinheiro. Trocar
# para um deles é decisão dele, não conveniência de quem está rodando o comando:
# em 2026-08-21, com a Agnes fora do ar no meio de um clipe, um `--motor
# clipe=kling:...` "óbvio" queimou 105 créditos antes de alguém perceber.
#
# Portão, e não aviso: instrução em prosa não segura ninguém — nem agente, nem
# eu às três da manhã. Os DEFAULTS do plano seguem intocados (a música nasce em
# `kie:suno-v4.5`, e isso é sabido e barato); o que exige autorização é TROCAR
# para um deles com `--motor`.
PROVEDORES_QUE_GASTAM = ("kie", "kling", "fal")


def exigir_autorizacao_de_motor(opts: dict) -> None:
    """Levanta se um `--motor` aponta para provedor pago sem `--autorizo-pago`."""
    if opts.get("autorizo_pago"):
        return
    pedidos = [(parte, motor) for parte, motor in (opts.get("motor") or {}).items()
               if motor.split(":", 1)[0].strip().lower() in PROVEDORES_QUE_GASTAM]
    if not pedidos:
        return
    lista = ", ".join(f"{parte}={motor}" for parte, motor in pedidos)
    raise ValueError(
        f"motor pago sem autorização: {lista}. "
        "kie, kling e fal consomem crédito ou dinheiro do dono da conta — "
        "confirme com ele e repita o comando com --autorizo-pago."
    )


def _parse_opts(args: list[str]) -> tuple[list[str], dict]:
    livres, opts = [], {}
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--pesquisa":
            opts["pesquisa"] = True
        elif a == "--forca":
            opts["forca"] = True
        elif a == "--letra-final":
            opts["letra_final"] = True
        elif a == "--sim":
            opts["sim"] = True
        elif a == "--telegram":
            opts["telegram"] = True
        elif a == "--refaz":
            opts["refaz"] = True
        elif a == "--completo":
            opts["completo"] = True
        elif a == "--sem-revisao":
            opts["sem_revisao"] = True
        elif a == "--faixa":
            i += 1
            opts["faixa"] = int(args[i])
        elif a in ("--estilo", "--letra", "--teto", "--idioma"):
            i += 1
            opts[a[2:]] = args[i]
        elif a == "--motor":
            i += 1
            parte, _, motor = args[i].partition("=")
            opts.setdefault("motor", {})[parte] = motor
        elif a == "--autorizo-pago":
            opts["autorizo_pago"] = True
        elif a == "--bruto":
            opts["bruto"] = True
        elif a == "--aprovar":
            opts["aprovar"] = True
        else:
            livres.append(a)
        i += 1
    if "teto" in opts:
        opts["teto"] = float(opts["teto"])
    return livres, opts


def cmd_plano(args) -> int:
    import sys
    from src.main import out_dir
    livres, opts = _parse_opts(args)
    if not livres:
        print('uso: plano "<solicitação>" [slug] [flags]', file=sys.stderr)
        return 1
    solicitacao = livres[0]
    slug = livres[1] if len(livres) > 1 else None
    # `--bruto`: o texto que a pessoa digitou no chat, INTEIRO, num argumento só.
    # Quem interpreta flags é o domínio — o bot não conhece `--estilo` nem
    # `--idioma`, e aspar tudo num argumento é o que impede texto de virar
    # comando. Sem isto, um `/musicavideo ... --idioma en-US` chegaria com o
    # `--idioma` DENTRO da solicitação, virando letra de música.
    if opts.get("bruto"):
        import shlex
        try:
            partes = shlex.split(solicitacao)
        except ValueError:
            partes = solicitacao.split()
        livres2, opts2 = _parse_opts(partes)
        if livres2:
            solicitacao = " ".join(livres2)
        opts = {**opts2, **{k: v for k, v in opts.items() if k != "bruto"}}
    try:
        exigir_autorizacao_de_motor(opts)
    except ValueError as e:
        import sys as _s
        print(f"erro: {e}", file=_s.stderr)
        return 1
    if opts.get("pesquisa"):
        from src.pesquisa import pesquisar
        opts["pesquisa_md"] = pesquisar(solicitacao)
    try:
        plano = gerar_plano(solicitacao, slug, opts, out_dir())
    except (ValueError, RuntimeError) as e:
        print(f"erro: {e}", file=sys.stderr)
        return 1
    w = out_dir() / plano["slug"]
    if opts.get("pesquisa_md"):
        (w / "pesquisa.md").write_text(opts["pesquisa_md"], encoding="utf-8")
    print((w / "PLANO.md").read_text(encoding="utf-8"))
    # RECIBO em `campo: valor`, nas últimas linhas: é o contrato que o bot lê
    # (`portao.mostrar: ["{{artefato:plano}}"]` e `{{anterior:slug}}` na fase
    # seguinte). Antes disto o formato era coincidência — um agente escrevia
    # três linhas de memória, e o slug real, com o `-2` da desambiguação, se
    # perdia entre uma fase e outra.
    print(f"\nslug: {plano['slug']}")
    print(f"titulo: {plano.get('titulo', '')}")
    print(f"plano: {w}/PLANO.md")
    return 0


def _valida_alvo(livres, uso, minimo=2):
    import sys
    from src.main import out_dir
    if len(livres) < minimo:
        print(f"uso: {uso}", file=sys.stderr)
        return None
    if livres[1] not in PARTES:
        print(f"erro: parte inválida '{livres[1]}' (musica|capa|clipe)", file=sys.stderr)
        return None
    w = out_dir() / livres[0]
    if not (w / "plano.json").exists():
        print(f"erro: slug '{livres[0]}' não encontrado em {out_dir()}", file=sys.stderr)
        return None
    return out_dir()


def cmd_ok(args) -> int:
    import sys
    from src.estado import TransicaoInvalida
    livres, _ = _parse_opts(args)
    od = _valida_alvo(livres, "ok <slug> <parte>")
    if od is None:
        return 1
    try:
        aprovar_parte(od, livres[0], livres[1])
    except TransicaoInvalida as e:
        print(f"erro: {e}", file=sys.stderr)
        return 1
    print(f"{livres[1]} aprovado — gere com: musicavideo faz {livres[0]} {livres[1]}")
    return 0


def cmd_ajusta(args) -> int:
    import sys
    from src.estado import TransicaoInvalida
    livres, opts = _parse_opts(args)
    od = _valida_alvo(livres, 'ajusta <slug> <parte> "<instrução>" [--refaz]', minimo=3)
    if od is None:
        return 1
    try:
        ajustar_parte(od, livres[0], livres[1], livres[2], refaz=bool(opts.get("refaz")))
    except (ValueError, RuntimeError, TransicaoInvalida) as e:
        print(f"erro: {e}", file=sys.stderr)
        return 1
    print(f"\n{livres[1]} replanejado — reveja com: musicavideo ver {livres[0]} {livres[1]}")
    return 0


def cmd_ver(args) -> int:
    import sys
    from src.main import out_dir
    livres, _ = _parse_opts(args)
    if not livres:
        print("uso: ver <slug> [musica|capa|clipe]", file=sys.stderr)
        return 1
    w = out_dir() / livres[0]
    if not (w / "plano.json").exists():
        print(f"erro: slug '{livres[0]}' não encontrado em {out_dir()}", file=sys.stderr)
        return 1
    if len(livres) > 1:
        if livres[1] not in PARTES:
            print(f"erro: parte inválida '{livres[1]}' (musica|capa|clipe)", file=sys.stderr)
            return 1
        plano = json.loads((w / "plano.json").read_text(encoding="utf-8"))
        print(render_secao(plano, livres[1]))
    else:
        print((w / "PLANO.md").read_text(encoding="utf-8"))
    return 0

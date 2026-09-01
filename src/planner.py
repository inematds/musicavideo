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
PISO_SHOT_S = 1.5            # abaixo disso o gerador não entrega plano legível
TETO_SHOT_S = 18.0           # 441 frames @24fps é o teto duro da Agnes

# RITMO: quantos cortes por minuto o clipe tem. O default é `auto` — quem
# decide é o planejador, a partir do bpm/gênero e das referências MEDIDAS (o
# acervo mostra 22-35 cortes/min nos clipes que performaram e 11-15 nos
# médios). A flag existe para DISCORDAR do que ele escolheu, e para o caso em
# que o custo é a parede: mais cortes = mais shots = mais horas de fila.
#
# `variado` é o único que compra dinâmica SEM pagar hora: a média fica em 5s
# (mesmo número de shots que hoje), mas a distribuição é desigual.
RITMOS = {
    "auto":     (None, "o planejador decide pelo bpm/gênero e pelas referências medidas"),
    "calmo":    (8.0,  "~8s por plano, poucos cortes — balada, ambiente"),
    "padrao":   (5.0,  "5s por plano, o de sempre"),
    "variado":  (5.0,  "média de 5s, distribuição desigual: refrão pica, verso respira"),
    "dinamico": (3.0,  "~3s por plano, 20-30 cortes/min — o regime dos virais do acervo"),
}
RITMO_PADRAO = "auto"
COBERTURA_MINIMA = 0.9       # o clipe tem que cobrir ao menos 90% da faixa
MOTORES_DEFAULT = {"musica": "kie:suno-v4.5",
                   "capa": "agnes:agnes-image-2.1-flash",
                   "clipe": "agnes:agnes-video-v2.0"}


def derivar_slug(solicitacao: str, outdir: Path) -> str:
    s = unicodedata.normalize("NFKD", solicitacao).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:40].rstrip("-")
    # RESERVA a pasta com mkdir, que é atômico no POSIX — não basta CHECAR se
    # existe. O plano leva minutos entre escolher o nome e salvar, e dois
    # fluxos com o mesmo começo de assunto (o corte é em 40 chars) rodando em
    # paralelo escolhiam o MESMO slug e iam escrever na mesma pasta: o segundo
    # plano sobrescrevia o do primeiro, e a música já paga do primeiro ficava
    # como `pronto`, barrando a fase do segundo com "estado 'pronto' não
    # permite faz" (MVD#144 x MVD#145).
    base, n = s, 2
    while True:
        try:
            (outdir / s).mkdir(parents=True, exist_ok=False)
            return s
        except FileExistsError:
            s = f"{base}-{n}"
            n += 1


def chamar_fable(prompt: str) -> str:
    try:
        # ID COMPLETO, nunca o apelido "fable": o serviço do bot roda com um
        # PATH sem ~/.local/bin e cai no /usr/bin/claude 2.1.63, que não conhece
        # o apelido e recusa com "may not exist or you may not have access"
        # (MVD#132/#134/#135). Mesmo modelo, mesmo plano — só o nome inteiro.
        # O prompt vai por STDIN, nunca em argv: o Linux limita UM argumento a
        # 128 KB (MAX_ARG_STRLEN), e na RETENTATIVA o prompt carrega o JSON
        # anterior inteiro + a lista de erros e estoura — o subprocess nem
        # chega a executar o claude, e o OSError subia como traceback puro
        # (MVD#139: "[Errno 7] Argument list too long").
        r = subprocess.run(["claude", "-p", "--model", "claude-fable-5"],
                           input=prompt, capture_output=True, text=True, timeout=900)
    except FileNotFoundError:
        raise RuntimeError("binário 'claude' não encontrado — o planner precisa do Claude Code no PATH")
    except OSError as e:
        # Rede de segurança: qualquer falha de execução vira mensagem, não
        # traceback — o `cmd_plano` só reconhece ValueError/RuntimeError.
        raise RuntimeError(f"não deu para executar o claude ({len(prompt)} chars de prompt): {e}")
    except subprocess.TimeoutExpired:
        # Sem isto, o estouro do timeout subia como traceback e o job morria com
        # "saiu com código 1" sem dizer por quê (MVD#132: 900,04 s exatos). O
        # `cmd_plano` só pega ValueError/RuntimeError — então tem que virar um.
        raise RuntimeError("claude -p não respondeu em 900 s — o planner desistiu")
    if r.returncode != 0:
        # O `claude` às vezes sai != 0 com stderr VAZIO (MVD#132) — a mensagem
        # virava "claude -p falhou:" sem causa nenhuma. Cai pro stdout e sempre
        # carrega o código de saída.
        causa = (r.stderr or "").strip() or (r.stdout or "").strip()[-300:] or "sem saída"
        raise RuntimeError(f"claude -p falhou (código {r.returncode}): {causa[:300]}")
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
        "(schema_version, slug, criado_em, solicitacao, pesquisa, estilo_ref, titulo, musica, "
        "capa, clipe, publicacao).",
        "Estrutura exata: musica{motor,params,estilo{genero,bpm,tom,mood,instrumentacao,voz,prompt_estilo},"
        "estrutura[{secao,inicio_s,duracao_s}],letra{origem,texto,texto_original,idioma}}; capa{motor,params,template,conceito,"
        "prompt_imagem,prompt_negativo,paleta,tagline}; clipe{motor,params,template,sincronia,"
        "decupagem[{n,secao,duracao_s,camera,descricao,prompt,prompt_alt}]}; "
        "publicacao{descricao}. NENHUM campo a mais.",
        "capa.tagline é a frase de CARTAZ que vai acima do título na capa: UMA linha, "
        "no máximo 8 palavras, em português, sem ponto final e sem aspas. Não é resumo "
        "nem slogan de marca — é a promessa do filme (\"o frio não perdoa · o mar não "
        "espera\"). Pode sair da própria letra. Só aparece nos templates de cena; nos "
        "de tipografia e abstrato ela é ignorada.",
        "publicacao.descricao é a DESCRIÇÃO do vídeo no YouTube, em português: 2 a 4 "
        "parágrafos curtos dizendo o que a peça É — do que a música fala, que som ela "
        "tem, o que se vê no clipe. Escreva para quem chegou pelo vídeo, não para quem "
        "leu o plano. Sem hashtag, sem CTA, sem link, sem emoji, sem citar artista ou "
        "obra, e sem repetir o título na primeira linha.",
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
        f"então a soma de duracao_s ≈ essa duração (~{_n_shots_alvo(opts)} shots). "
        f"Um clipe mais curto que a música é REJEITADO na validação. Distribua os shots "
        f"pelas seções da estrutura, com variação real entre eles (nada de repetir o "
        f"mesmo plano).",
        _instrucao_ritmo(opts),
        # BOCA: o gerador de vídeo não ouve a música. Sem áudio de referência
        # não existe fonema, então "mouth open in a sustained note" vira uma
        # boca parada aberta, ou um abre-e-fecha genérico que não corresponde a
        # som nenhum — e boca é justamente a região que os geradores fazem
        # pior (dentes e mandíbula deformam entre quadros). Medido no MVD
        # "Stay" (2026-08-25), onde 16 dos 42 planos pediam canto explícito.
        # CLOSE DE PARTE DO CORPO: nomear a pessoa ("a small girl's bare foot")
        # faz o modelo tentar desenhar a pessoa INTEIRA dentro do quadro
        # apertado — e ele erra o que não cabe. No MVD "Levanta a Poeira"
        # (2026-08-26) o último plano saiu com cabeça e pernas de criança sem
        # tronco nenhum. O conserto foi descrever só o pé, cortado no
        # tornozelo, sem citar de quem é.
        "CLOSE DE PARTE DO CORPO (pé, mão, olho, boca do violão): descreva SÓ A PARTE e "
        "diga que ela está cortada pela borda do quadro ('framed so tightly that only the "
        "foot and ankle are visible'). NUNCA nomeie a pessoa dona da parte ('a small girl's "
        "foot', 'the singer's hand'): o gerador tenta desenhar a pessoa inteira dentro do "
        "close e erra o que não cabe — sai corpo sem tronco, membro a mais, escala errada. "
        "Parte do corpo é objeto no quadro, não gente pequena.",
        # ESCOPO: a regra abaixo vale só para `clipe.decupagem[].prompt`. Sem
        # dizer isso, o planejador levava o vocabulário dela para a CAPA — e
        # saíram capas em série com queixo erguido e olhos fechados, todas com
        # a mesma pose (visto em 2026-08-26, em 8 planos seguidos).
        "CANTO (vale SÓ para clipe.decupagem[].prompt, NUNCA para capa.prompt_imagem) "
        "— NUNCA descreva a boca. Os prompts do clipe não podem conter "
        "'mouth open', 'singing', 'belting', 'lips', 'sustained note' nem equivalente: "
        "o gerador não ouve a faixa, então boca aberta vira careta parada e boca em "
        "movimento vira mímica que não bate com nada. Entregue a MESMA emoção pela "
        "postura e pela luz: cabeça inclinada para trás, olhos fechados com força, "
        "garganta e pescoço tensionados, veia saltada, mão fechada no pé do microfone, "
        "ombros subindo na inspiração, queixo erguido, lágrima. Nos closes, enquadre "
        "dos olhos para cima, de perfil, contra a luz ou com o microfone à frente da "
        "boca. O canto se lê no corpo, não na boca — e o público está OUVINDO a voz, "
        "então não precisa vê-la sendo produzida.",
        # A música não é julgada por qualidade técnica e sim por RESPOSTA do
        # público: emoção → reconhecimento → memória → repetição. Isto entra no
        # prompt porque é decisão de ESCRITA (onde cai o refrão, o que a pessoa
        # repete) — não é nota, não é previsão de hit, e não há como medir aqui.
        "POTENCIAL: escreva pensando em quem vai ouvir, não em quem vai avaliar. "
        "(a) HOOK: tem que existir UMA coisa que a pessoa lembra depois de ouvir uma vez "
        "— uma frase, uma melodia, uma palavra repetida. (b) OS 15 PRIMEIROS SEGUNDOS "
        "precisam dar motivo para continuar: nada de intro longa de preparação. "
        "(c) O REFRÃO tem que funcionar SOZINHO, fora da música. (d) IDENTIDADE: em 10s "
        "deve dar para dizer que é esta música e não outra igual. (e) Familiar o bastante "
        "para entrar, diferente o bastante para notar — genérico e hermético falham igual.",
        "CAPA — o olhar VARIA, e é escolha de composição, não fórmula. A capa é um "
        "retrato ou uma cena, não um plano de canto: não repita 'chin raised', "
        "'chin lifted', 'head tilted back' nem 'eyes closed' (isso é recurso do CLIPE, "
        "para não mostrar boca cantando). Escolha o que a música pede e diga qual é: "
        "olhar direto na lente, olhar fora de quadro, perfil, de costas, olhos baixos, "
        "de longe sem rosto legível, ou capa SEM pessoa nenhuma (objeto, paisagem, "
        "detalhe). Duas capas seguidas com a mesma pose é erro.",
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
            "analisevideo — paleta em hex, movimento de câmera, ritmo de corte e MONTAGEM "
            "que funcionaram de verdade). Use como base da decupagem e da paleta da capa; "
            "não copie o conteúdo, copie a LINGUAGEM visual. A linha `▸ montagem` diz como "
            "os planos se LIGAM naqueles vídeos (transições usadas, corte no beat, "
            "slowmo/speedramp): siga o que está medido ali, não o que é bonito no papel — "
            "e o que não aparece na medição não deve virar recurso do clipe:\n" + refs)
    if opts.get("estilo"):
        partes.append(f"ESTILO PEDIDO: {opts['estilo']}")
    if opts.get("origem") and not pedido_tem_assunto(solicitacao):
        # SEM ASSUNTO NOVO, quem descreve a música é a origem — senão o
        # planejador escreve sobre uma faixa que não conhece, sabendo só a
        # duração. Com assunto, o texto do pedido manda e isto não entra.
        ctx = contexto_da_origem(opts["origem"], outdir)
        if ctx:
            partes.append(ctx)
    if opts.get("faixa_pronta"):
        partes.append(
            f"MÚSICA JÁ EXISTE: o usuário trouxe a faixa pronta "
            f"({_dur_alvo(opts)}s). NÃO invente estrutura nem letra que contrariem "
            "o áudio: descreva a música como ela é (gênero, mood, instrumentação) "
            "e concentre o trabalho na CAPA e na DECUPAGEM DO CLIPE, que precisam "
            "cobrir a duração real. `musica.params.duracao_s` tem que ser essa."
        )
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


def duracao_de(arq) -> int:
    """Segundos de um arquivo de áudio/vídeo, pelo ffprobe."""
    import subprocess
    r = subprocess.run(["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                        "-of", "csv=p=0", str(arq)], capture_output=True, text=True)
    try:
        return int(round(float(r.stdout.strip())))
    except (TypeError, ValueError):
        raise ValueError(f"ffprobe não leu a duração de {arq}")


def _dur_alvo(opts: dict) -> int:
    # FAIXA PRONTA manda na duração: o clipe é decupado sobre a música REAL, não
    # sobre um palpite de 180s. Sem isto, a validação de cobertura compararia o
    # clipe com uma duração inventada e aprovaria um clipe curto demais.
    if opts.get("faixa_pronta"):
        return duracao_de(opts["faixa_pronta"])
    return int(opts.get("duracao_s") or 180)


def _ritmo(opts: dict) -> str:
    r = str(opts.get("ritmo") or RITMO_PADRAO).strip().lower()
    return r if r in RITMOS else RITMO_PADRAO


def media_shot_s(opts: dict) -> float:
    """A média de duração por shot do ritmo pedido. `auto` cai no padrão só
    para DIMENSIONAR o pedido — quem escolhe o ritmo de verdade é o planejador."""
    return RITMOS[_ritmo(opts)][0] or DUR_SHOT_PADRAO


def _n_shots_alvo(opts: dict) -> int:
    return max(1, round(_dur_alvo(opts) / media_shot_s(opts)))


def _instrucao_ritmo(opts: dict) -> str:
    """O parágrafo de RITMO do prompt. É aqui que o clipe deixa de ser slideshow."""
    nome = _ritmo(opts)
    comum = ("REGRA FIXA, valha qual for o ritmo: a duração NÃO é parelha entre os shots. "
             f"Refrão pica (planos curtos), verso respira, intro segura o plano. "
             f"Nenhum shot abaixo de {PISO_SHOT_S}s nem acima de {TETO_SHOT_S}s. "
             "Escreva em clipe.sincronia qual ritmo você escolheu, em cortes/min, e POR QUÊ "
             "(cite a referência medida que embasou).")
    if nome == "auto":
        return ("RITMO: você decide, pelo bpm, pelo gênero e pelas REFERÊNCIAS MEDIDAS abaixo "
                "(elas trazem cortes/min de vídeos reais que funcionaram). Não invente um "
                "número redondo: ancore no que está medido. " + comum)
    if nome == "variado":
        return (f"RITMO pedido: VARIADO — a MÉDIA fica em {DUR_SHOT_PADRAO}s por shot "
                f"(mantendo ~{_n_shots_alvo(opts)} shots), mas a distribuição é bem desigual: "
                f"2-3s no refrão pagos com 8-10s no verso. " + comum)
    return (f"RITMO pedido: {nome.upper()} — média de {media_shot_s(opts):g}s por shot "
            f"(~{_n_shots_alvo(opts)} shots). " + comum)


def cobertura_do_clipe(plano: dict) -> list[str]:
    """Clipe mais curto que a música vira vídeo em loop — que não é um clipe."""
    dur_musica = int(plano.get("musica", {}).get("params", {}).get("duracao_s") or 180)
    dur_clipe = sum(s.get("duracao_s", 0) for s in plano.get("clipe", {}).get("decupagem", []) or [])
    if dur_clipe < dur_musica * COBERTURA_MINIMA:
        return [f"clipe.decupagem cobre {dur_clipe}s de uma música de ~{dur_musica}s — "
                f"decupe a música inteira (a soma de duracao_s tem que chegar lá; "
                f"com planos de {DUR_SHOT_PADRAO}s isso dá "
                f"~{round(dur_musica / DUR_SHOT_PADRAO)} shots, mas o número depende "
                f"do ritmo que você escolheu)"]
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


# A frase de idioma que o PROVEDOR lê, no fim do `prompt_estilo`. Duas formas
# vistas em plano real: a que o prompt pede ("Lyrics in X") e a que o modelo
# inventa por conta ("language = portuguese or spanish...", MVD#96).
_IDIOMA_NO_ESTILO = re.compile(
    r"[.,;]?\s*(?:lyrics?\s+in|sung\s+in|vocals?\s+in|language\s*[=:])\s*[^.;]*",
    re.IGNORECASE,
)


def _sem_acento(txt: str) -> str:
    """ASCII puro: o `prompt_estilo` é recusado com acento (`campos_prompt_en`),
    e o idioma entra dentro dele. `português` viraria erro de validação."""
    return "".join(c for c in unicodedata.normalize("NFKD", txt)
                   if not unicodedata.combining(c))


def _impor_idioma_no_estilo(plano: dict, idioma: str) -> None:
    """`Lyrics in <idioma>` no fim do `prompt_estilo`, por CÓDIGO.

    O idioma vale em dois lugares: a letra escrita e a frase que o Suno lê. O
    campo `musica.letra.idioma` já era chumbado aqui; a frase do estilo era só
    INSTRUÇÃO no prompt — se o modelo não obedecesse, saía faixa cantada num
    idioma e pedida em outro, sem nada conferir. Metade garantida não garante
    nada: quem canta é o provedor, e ele só lê esta frase.

    A frase anterior (do modelo ou de um plano velho) é REMOVIDA antes: duas
    declarações de idioma no mesmo prompt é o que produz o portunhol acidental.
    """
    est = plano.setdefault("musica", {}).setdefault("estilo", {})
    base = _IDIOMA_NO_ESTILO.sub("", str(est.get("prompt_estilo") or "")).strip(" .,;")
    frase = f"Lyrics in {_sem_acento(idioma).strip()}"
    est["prompt_estilo"] = f"{base}. {frase}" if base else frase


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
    if opts.get("faixa_pronta"):
        # A duração REAL manda sobre o que o modelo escreveu: ela é medida, não
        # opinada, e é ela que ancora o clipe.
        plano.setdefault("musica", {}).setdefault("params", {})["duracao_s"] = _dur_alvo(opts)
    if idioma:
        plano.setdefault("musica", {}).setdefault("letra", {})["idioma"] = idioma
        _impor_idioma_no_estilo(plano, idioma)
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


def resolver_faixa_pronta(ref: str, outdir: Path) -> str:
    """Aceita caminho de arquivo OU referência ao acervo: `MVD#125:2`.

    O `--faixa-pronta` só entendia caminho, e no bot isso vira uma linha
    impossível de digitar no celular. O acervo JÁ é endereçável por `MVD#N`
    (`src/mvd.py`), que é como se fala das produções no chat — faltava só ligar
    as duas pontas. Formatos aceitos, todos equivalentes:

        MVD#125:2   MVD#125 2   mvd125:2   <slug>:2   MVD#125   <caminho.mp3>

    Sem número de faixa, vale a faixa APROVADA da produção de origem (o que a
    pessoa quer dizer com "a música do MVD#125"), com `faixa-1.mp3` de reserva.
    """
    from src import mvd as mvd_mod
    texto = str(ref).strip()
    if Path(texto).exists():
        return texto
    if "/" in texto or texto.lower().endswith((".mp3", ".wav", ".m4a", ".flac")):
        raise ValueError(f"faixa pronta não encontrada: {texto}")
    corpo, _, n = texto.replace(" faixa ", ":").replace(" ", ":").partition(":")
    achados = mvd_mod.resolver_todos(Path(outdir), corpo)
    if len(achados) > 1:
        # AMBIGUIDADE NÃO SE ESCOLHE EM SILÊNCIO: copiar a faixa errada é
        # invisível — o plano sai coerente, com a música errada dentro.
        raise ValueError(
            f"{corpo} está em {len(achados)} produções: "
            + ", ".join(achados)
            + ". Use o slug em vez do número (ex.: "
            + f"--faixa-pronta {achados[0]}:{n or '1'})")
    slug = achados[0] if achados else None
    if not slug:
        raise ValueError(f"faixa pronta: não achei produção nem arquivo em {ref!r}")
    w = Path(outdir) / slug
    candidatos = [w / f"faixa-{n}.mp3"] if n.strip().isdigit() else []
    if not candidatos:
        try:
            e = json.loads((w / "estado.json").read_text(encoding="utf-8"))
            aprovada = e["partes"]["musica"].get("artefato")
            if aprovada:
                candidatos.append(w / aprovada)
        except (OSError, ValueError, KeyError):
            pass
        candidatos += [w / "faixa-1.mp3", w / "faixa.mp3"]
    for c in candidatos:
        if c.exists():
            return str(c)
    raise ValueError(f"faixa pronta: {slug} não tem {candidatos[0].name}")


def pedido_tem_assunto(solicitacao: str) -> bool:
    """O texto do pedido diz alguma coisa além das flags?

    `--faixa-pronta MVD#125:2` e nada mais é pedido VAZIO: o `--bruto` entrega
    o texto do chat inteiro, e quando a pessoa só cola a flag, o que sobra como
    "solicitação" é a própria flag. Quem manda um assunto junto ("clipe mais
    escuro, foco na cantora") continua mandando no plano.
    """
    texto = re.sub(r"--[\w-]+(\s+\S+)?", " ", str(solicitacao or ""))
    return len(texto.split()) >= 3


def origem_de(caminho_faixa, outdir) -> dict | None:
    """De onde veio a faixa, quando ela veio do próprio acervo.

    Devolve `{mvd, slug, faixa, titulo}` — ou None se o arquivo não mora numa
    produção. Guarda SLUG e número: o número é o nome humano (é o que se cita
    no chat) mas muda — cinco produções foram renumeradas em 2026-09-01 —,
    então quem precisa achar a origem depois usa o slug, que é a chave durável.
    O número é lido AGORA do estado da origem, nunca deduzido do nome da pasta.
    """
    arq = Path(caminho_faixa)
    outdir = Path(outdir)
    try:
        w = arq.parent.resolve()
        if w.parent.resolve() != outdir.resolve() or not (w / "estado.json").exists():
            return None
    except OSError:
        return None
    dados = {"slug": w.name, "faixa": arq.name, "mvd": None, "titulo": None}
    try:
        dados["mvd"] = json.loads((w / "estado.json").read_text(encoding="utf-8")).get("mvd")
    except (OSError, ValueError):
        pass
    try:
        dados["titulo"] = json.loads((w / "plano.json").read_text(encoding="utf-8")).get("titulo")
    except (OSError, ValueError):
        pass
    return dados


def descreve_origem(origem: dict | None) -> str:
    """`MVD#125 — Construí em Silêncio (agora-eu-cobro), faixa 2`."""
    if not origem:
        return ""
    n = (origem.get("faixa") or "").replace("faixa-", "").replace(".mp3", "")
    partes = [x for x in (origem.get("mvd"), origem.get("titulo")) if x]
    txt = " — ".join(partes) if partes else origem.get("slug", "?")
    if origem.get("slug") and origem.get("titulo"):
        txt += f" ({origem['slug']})"
    return txt + (f", faixa {n}" if n and n.isdigit() else "")


def contexto_da_origem(origem: dict | None, outdir) -> str:
    """O que a origem sabe sobre a música — para quando o pedido não diz nada.

    Uma cópia sem texto (`--faixa-pronta MVD#125:2` e mais nada) deixava o
    planejador sem assunto: ele conhecia a duração do áudio e nada mais. Aqui a
    origem empresta solicitação, estilo, letra e título — que descrevem a MESMA
    música — e o pedido explícito é uma decupagem NOVA. A decupagem da origem
    NÃO entra: mostrar o que não se deve copiar é como se copia.
    """
    if not origem:
        return ""
    w = Path(outdir) / origem["slug"]
    try:
        p = json.loads((w / "plano.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    letra = ((p.get("musica") or {}).get("letra") or {}).get("texto") or ""
    est = json.dumps((p.get("musica") or {}).get("estilo") or {}, ensure_ascii=False)
    return ("A MÚSICA VEM DE OUTRA PRODUÇÃO e o pedido não trouxe assunto novo — "
            f"use o que a origem sabe sobre ELA MESMA ({descreve_origem(origem)}):\n"
            f"- pedido original: {p.get('solicitacao')}\n"
            f"- título: {p.get('titulo')}\n"
            f"- estilo medido: {est}\n"
            f"- letra:\n{letra}\n"
            "ESCREVA UMA DECUPAGEM NOVA para esta música: outro recorte visual, outros "
            "planos. Não é para repetir o clipe da origem — é o mesmo áudio ganhando "
            "leitura própria. Capa idem.")


def gerar_plano(solicitacao, slug, opts, outdir, chamar_llm=None) -> dict:
    """Resolve o slug (reservando a pasta) e devolve a reserva se o plano falhar."""
    # A FAIXA é conferida ANTES de qualquer coisa: caminho errado tem que
    # aparecer agora, e não depois de uma chamada de modelo — que custa tempo e
    # devolveria um erro do ffprobe, que não diz o que fazer.
    if opts.get("faixa_pronta"):
        # aceita `MVD#125:2` além de caminho — resolvido ANTES do modelo
        opts["faixa_pronta"] = resolver_faixa_pronta(opts["faixa_pronta"], outdir)
        # DE ONDE VEIO fica registrado: sem isso, a única pista de que duas
        # produções compartilham a música é reconhecer a letra ouvindo.
        opts["origem"] = origem_de(opts["faixa_pronta"], outdir)
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    slug_dado = slug is not None
    reservada = None
    if not slug_dado:
        slug = derivar_slug(solicitacao, outdir)
        reservada = outdir / slug
    try:
        return _gerar_plano(solicitacao, slug, opts, outdir, chamar_llm, slug_dado)
    except BaseException:
        # Plano que falhou não pode deixar a reserva pra trás: sem isto, cada
        # `/refazer` acharia a pasta vazia ocupada e iria para `-2`, `-3`... O
        # `rmdir` só apaga pasta VAZIA — o que tem artefato pago fica de pé.
        if reservada is not None:
            try:
                reservada.rmdir()
            except OSError:
                pass
        raise


def _gerar_plano(solicitacao, slug, opts, outdir, chamar_llm, slug_dado) -> dict:
    chamar_llm = chamar_llm or chamar_fable
    outdir = Path(outdir)
    # Um slug DERIVADO já vem com a pasta reservada (vazia) por `derivar_slug`,
    # então o portão do `--forca` abaixo só vale para o slug que a pessoa passou.
    w = outdir / slug
    if slug_dado and w.exists():
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
    # O NÚMERO NASCE COM A PRODUÇÃO. O bot manda `--mvd {{ref}}` (`MVD146`), e é
    # ele quem numera — o fluxo já tem o número, e é esse que a pessoa cita.
    # Antes o número só aparecia num `reindex` posterior, e até lá o painel e a
    # vitrine mostravam a produção sem identificação nenhuma; pior, quem numerava
    # depois tinha de ADIVINHAR de qual fluxo a pasta veio, casando prefixo de
    # slug — e errava quando dois pedidos começavam igual.
    from src.mvd import numero_de, formatar, _gravar_teto, _teto
    n_mvd = numero_de(opts.get("mvd"))
    if n_mvd is not None:
        # UM NÚMERO, UMA PRODUÇÃO. Gravar `--mvd` sem olhar quem já tem o
        # número foi o que criou MVD#146..#150 com duas produções cada: uma
        # nascida fora do bot pega `topo_bot + 1`, e horas depois o bot cria
        # esse fluxo e força o mesmo número aqui.
        from src.mvd import liberar_numero
        for slug_mex, antes, depois in liberar_numero(outdir, n_mvd, slug):
            print(f"mvd: {slug_mex} saiu de {antes} para {depois} "
                  f"— {formatar(n_mvd)} é do fluxo do bot")
        estado["mvd"] = formatar(n_mvd)
        # o teto sobe junto: quem nascer FORA do bot tem de continuar acima disto
        _gravar_teto(outdir, max(n_mvd, _teto(outdir)))
    if opts.get("origem"):
        plano["origem"] = opts["origem"]
        print(f"origem: {descreve_origem(opts['origem'])}")
    if opts.get("faixa_pronta"):
        # A FAIXA JÁ EXISTE: copiada para dentro do slug e marcada `pronto`, com
        # custo zero. Copiar (e não referenciar) é o que faz o pacote e a
        # montagem continuarem funcionando sem saber de onde ela veio — e o
        # arquivo do usuário não é movido nem alterado.
        import shutil
        origem = Path(opts["faixa_pronta"])
        if not origem.exists():
            raise ValueError(f"faixa pronta não encontrada: {origem}")
        destino = w / f"faixa-1{origem.suffix.lower() or '.mp3'}"
        shutil.copy2(origem, destino)
        m = estado["partes"]["musica"]
        m.update({"estado": "pronto", "artefato": destino.name, "aprovado_em": _agora(),
                  "meta": {"origem": "usuario", "arquivo_original": str(origem)}})
        estado["historico"].append(
            {"quando": _agora(), "evento": "musica", "detalhe": f"faixa do usuário: {origem.name}"})
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
           *( [f"**origem:** {descreve_origem(plano['origem'])}"] if plano.get("origem") else [] ),
           f"**estilo de referência:** {plano['estilo_ref']}  ·  "
           f"**pesquisa:** {'sim' if plano['pesquisa'] else 'não'}", ""]
    corpo = [render_secao(plano, p) for p in PARTES]
    # A descrição do YouTube entra no PLANO.md porque é AQUI que mexer é de
    # graça — depois do render ela seria só um texto que ninguém releu.
    from src.entrega import tags_de
    pub = (plano.get("publicacao") or {}).get("descricao", "").strip()
    corpo.append("\n".join(
        ["## Publicação (YouTube)", "",
         f"- **Título:** {plano['titulo']}",
         f"- **Tags:** {', '.join(tags_de(plano)) or '—'}", "",
         "**Descrição:**", "", pub or
         "_(sem descrição no plano — a entrega não monta o pacote de canal; "
         "use `ajusta` ou replaneje)_"]))
    prov = ["## Disponibilidade dos provedores", ""]
    for nome, (ok, motivo) in sorted(disp.items()):
        prov.append(f"- **{nome}:** {'ok' if ok else motivo}")
    return "\n\n".join(cab + corpo + ["\n".join(prov)]) + "\n"


def precisa_reajuste(plano: dict, duracao_real: float) -> bool:
    """Vale mexer só se a diferença passar de um shot — abaixo disso o fade resolve."""
    dur_clipe = sum(x.get("duracao_s", 0) for x in plano["clipe"].get("decupagem", []) or [])
    return abs(duracao_real - dur_clipe) > DUR_SHOT_PADRAO


def reajustar_decupagem(workdir: Path, duracao_real: float, chamar_llm=None,
                        nucleo: dict | None = None) -> dict:
    """Refaz a decupagem para a duração REAL da faixa aprovada.

    O plano é escrito antes de a música existir, então chuta a duração. Se a
    faixa vier bem diferente, as marcações param de bater: o refrão final da
    decupagem cai fora do refrão final da música."""
    chamar_llm = chamar_llm or chamar_fable
    workdir = Path(workdir)
    plano = json.loads((workdir / "plano.json").read_text(encoding="utf-8"))
    decup = plano["clipe"]["decupagem"]
    atual = sum(x.get("duracao_s", 0) for x in decup)
    # O RITMO JÁ FOI DECIDIDO — o reajuste só ESCALA. Até 2026-08-23 esta linha
    # recalculava `duracao_real / 5` e pedia shots parelhos, o que apagava,
    # depois da faixa pronta, qualquer ritmo que o plano tivesse: o clipe era
    # planejado com refrão picado e renderizado como slideshow.
    media = round(atual / len(decup), 1) if decup else DUR_SHOT_PADRAO
    alvo_shots = max(1, round(duracao_real / media)) if media else 1
    curtos = min((x.get("duracao_s", 0) for x in decup), default=DUR_SHOT_PADRAO)
    longos = max((x.get("duracao_s", 0) for x in decup), default=DUR_SHOT_PADRAO)
    prompt = ("Plano atual:\n" + json.dumps(plano, ensure_ascii=False)
              + f"\n\nA MÚSICA FICOU PRONTA e tem {duracao_real:.0f}s — a decupagem atual "
                f"cobre {atual}s. Reescreva APENAS a seção 'clipe' para cobrir "
                f"{duracao_real:.0f}s MANTENDO O RITMO que já está lá: os planos hoje vão "
                f"de {curtos:g}s a {longos:g}s, média {media:g}s — conserve essa variação "
                f"(refrão picado, verso respirando), NÃO iguale as durações. Isso dá "
                f"~{alvo_shots} shots, "
                + (f"O NÚCLEO da faixa (o trecho de 12s mais forte, MEDIDO na onda) "
                   f"está em {nucleo['inicio_s']}-{nucleo['fim_s']}s: é ali que vai o "
                   f"melhor plano do clipe e o ritmo mais picado — é esse trecho que "
                   f"vira Short. " if nucleo else "")
              + f"Redistribua pelas seções (mais nos refrões), mantendo o arco "
                f"narrativo e o estilo visual que já estavam lá. Aproveite os shots "
                f"existentes que continuarem fazendo sentido, com os mesmos prompts. "
                f"Prompts de provedor em INGLÊS, com prompt_alt em cada shot. "
                f"NUNCA descreva a boca cantando ('mouth open', 'singing', 'belting'): "
                f"o gerador não ouve a faixa e devolve careta. O canto se lê no corpo — "
                f"cabeça para trás, olhos fechados, garganta tensionada, microfone à frente. "
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
        # `--flag=valor` e `--flag valor` são a MESMA coisa. As duas formas são
        # digitadas, e antes só a segunda funcionava: `--idioma=en-US` não casava
        # com nada, sobrava nos argumentos livres e virava parte da SOLICITAÇÃO —
        # ou seja, pedido de idioma virava letra de música, em silêncio. Pior
        # ainda vindo do chat do bot, onde os campos DELE usam `=` e a mão vai
        # sozinha (2026-08-21).
        if a.startswith("--") and "=" in a:
            nome, _, valor = a.partition("=")
            args = args[:i] + [nome, valor] + args[i + 1:]
            a = nome
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
        elif a in ("--estilo", "--letra", "--teto", "--idioma", "--versao", "--tagline",
                   "--ritmo", "--inicio", "--mvd"):
            i += 1
            opts[a[2:]] = args[i]
        elif a == "--motor":
            i += 1
            parte, _, motor = args[i].partition("=")
            opts.setdefault("motor", {})[parte] = motor
        elif a == "--autorizo-pago":
            opts["autorizo_pago"] = True
        elif a == "--nova":
            opts["nova"] = True
        elif a == "--bruto":
            opts["bruto"] = True
        elif a == "--aprovar":
            opts["aprovar"] = True
        elif a in ("--faixa-pronta", "--musica-pronta"):
            i += 1
            opts["faixa_pronta"] = args[i]
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
    except Exception as e:
        # PORTA DOS FUNDOS: qualquer exceção inesperada sai como uma linha de
        # erro com o TIPO, nunca como traceback. O bot corta a cauda da saída,
        # então um traceback chega ao chat só com o cabeçalho e a causa se perde
        # (MVD#139: o OSError real estava na última linha, invisível).
        print(f"erro: {type(e).__name__}: {e}", file=sys.stderr)
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


def retimar_decupagem_para(decupagem: list, alvo_s: float,
                           minimo: int = 4, maximo: int = 12) -> list:
    """Reescala as durações dos shots para caber num motor com piso e teto.

    Determinístico, sem LLM: a decupagem já foi decidida, o que muda é só o
    relógio. Nasceu do `agnes-video-2.5-flash`, que só aceita `seconds` inteiro
    em [4, 12] — um shot de 3 s planejado para o v2.0 viraria 4 s no pedido, e
    49 arredondamentos desses empurram o clipe para longe da música.

    Preserva o PESO relativo de cada shot e fecha a soma no alvo (a duração
    real da faixa), distribuindo o resto nos shots com mais folga. Se o alvo não
    couber entre `n*minimo` e `n*maximo`, entrega o extremo possível — encurtar
    o clipe é problema da montagem, não deste cálculo.
    """
    if not decupagem:
        return decupagem
    n = len(decupagem)
    alvo = int(round(max(n * minimo, min(n * maximo, alvo_s))))
    pesos = [max(0.1, float(s.get("duracao_s") or 0)) for s in decupagem]
    total = sum(pesos)
    novas = [min(maximo, max(minimo, int(round(p / total * alvo)))) for p in pesos]
    # fecha a soma exata, um segundo por vez, em quem tem folga
    while sum(novas) != alvo:
        passo = 1 if sum(novas) < alvo else -1
        cands = [i for i, v in enumerate(novas) if minimo <= v + passo <= maximo]
        if not cands:
            break
        i = max(cands, key=lambda i: pesos[i] / novas[i] * passo)
        novas[i] += passo
    saida = []
    for shot, dur in zip(decupagem, novas):
        s = dict(shot)
        s["duracao_s"] = dur
        saida.append(s)
    return saida

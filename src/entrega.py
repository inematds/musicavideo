"""Fase 3: PACOTE.md, pacote de publicação e envio opcional no Telegram."""
import json
import os
import shutil
import unicodedata
import urllib.request
import uuid
from pathlib import Path

from providers.base import ler_env_chave
from src.estado import carregar_estado, salvar_estado, registrar
from src.indexer import linha_de, gravar_linha

PARTES = ("musica", "capa", "clipe")
ROTULO = {"musica": "Faixa", "capa": "Capa", "clipe": "Clipe"}


def gerar_pacote(outdir: Path, slug: str) -> Path:
    outdir = Path(outdir)
    w = outdir / slug
    plano = json.loads((w / "plano.json").read_text(encoding="utf-8"))
    estado = carregar_estado(w)
    linhas = [f"# {plano['titulo']}", "",
              f"**slug:** `{slug}`  ·  **solicitação:** {plano['solicitacao']}", "",
              "| parte | estado | arquivo | motor | custo (US$) |", "|---|---|---|---|---|"]
    faltando = []
    for p in PARTES:
        d = estado["partes"][p]
        art = d["artefato"] or "—"
        linhas.append(f"| {ROTULO[p]} | {d['estado']} | {art} | {plano[p]['motor']} "
                      f"| {d['custo_real_usd']:.4f} |")
        if d["estado"] != "pronto":
            faltando.append(p)
    linhas += ["", f"**Custo total gasto:** US$ {estado['custo_total_usd']['gasto']:.4f}",
               "", f"**Pasta:** `{w}`"]
    if faltando:
        linhas += ["", f"⚠️ Entrega parcial — **falta:** {', '.join(faltando)}.",
                   "", f"Retomar com: `musicavideo faz {slug}`"]
    else:
        linhas += ["", "✅ Pacote completo."]
    alvo = w / "PACOTE.md"
    alvo.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    return alvo


# ------------------------------------------------------- pacote de publicação
#
# O destino (yt-pub) NÃO deve refazer nada: sai daqui vídeo, título, descrição e
# capa prontos. Onde o pacote entra no canal é assunto do bot — este módulo só
# monta a pasta e diz onde ela está; o domínio não conhece caminho de disco de
# canal nenhum.

TAGS_MAX = 15


def _tag(t: str) -> str:
    t = unicodedata.normalize("NFD", str(t)).encode("ascii", "ignore").decode()
    return " ".join(t.lower().split())


def tags_de(plano: dict) -> list[str]:
    """Determinístico: gênero + mood + instrumentação. Sem modelo — tag é
    rótulo, não texto, e um modelo aqui só traria variação sem ganho."""
    e = (plano.get("musica") or {}).get("estilo") or {}
    cru = []
    g = e.get("genero")
    cru += (g if isinstance(g, list) else [g]) if g else []
    cru += list(e.get("mood") or [])[:4]
    cru += list(e.get("instrumentacao") or [])[:3]
    if plano.get("estilo_ref"):
        cru.append(str(plano["estilo_ref"]).replace("-", " "))
    vistas, saida = set(), []
    for t in cru:
        n = _tag(t)
        if n and n not in vistas and len(n) <= 30:
            vistas.add(n)
            saida.append(n)
    return saida[:TAGS_MAX]


def montar_publicacao(outdir: Path, slug: str) -> Path | None:
    """Monta `<slug>/publicacao/` com o mp4, a capa 16:9 e o manifest.

    Devolve None (com o motivo impresso) quando falta peça — pacote pela metade
    faria o destino inventar o que falta, que é exatamente o que não queremos."""
    outdir = Path(outdir)
    w = outdir / slug
    plano = json.loads((w / "plano.json").read_text(encoding="utf-8"))
    try:
        estado = carregar_estado(w)
    except (OSError, ValueError):
        estado = None
    descricao = ((plano.get("publicacao") or {}).get("descricao") or "").strip()
    if not descricao:
        # NÃO aponta para `ajusta`: ele só conhece musica|capa|clipe (partes com
        # máquina de estados), e mandar para lá seria mandar para um "parte
        # inválida". O bloco é editável no plano.json, ou vem de um replanejamento.
        print("publicação: o plano não tem `publicacao.descricao` — sem pacote de "
              "canal (o destino teria que inventar a descrição). "
              f"Escreva o bloco em {w / 'plano.json'} "
              '(publicacao: {"descricao": "..."}) e rode `musicavideo pacote '
              f"{slug}`, ou replaneje.")
        return None
    clipe = w / "clipe.mp4"
    if not clipe.exists():
        print("publicação: clipe.mp4 ainda não existe — sem pacote de canal")
        return None
    crua = w / "raw" / "capa-crua.png"
    destino = w / "publicacao"
    tmp = w / ".publicacao-tmp"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)

    # AS DUAS FAIXAS VIRAM DOIS VÍDEOS. O Suno entrega duas músicas, não duas
    # versões da mesma: cada uma tem sua trilha, sua capa (o selo de versão
    # existe por isso) e merece sua publicação. O vídeo é o mesmo material, a
    # música é que muda — e é a música que a pessoa vem ouvir.
    from src.montagem import faixas_existentes
    from src.executor import faixa_aprovada
    aprovada = faixa_aprovada(w, estado) if estado else None
    faixas = faixas_existentes(w)
    pecas = []
    for f in faixas:
        n = f.stem.split("-")[-1]
        n = int(n) if n.isdigit() else 1
        versao = w / f"clipe-{n}.mp4"
        if not versao.exists():
            versao = clipe if len(faixas) == 1 else None
        if versao and versao.exists():
            pecas.append((n, versao, aprovada is not None and f.name == aprovada.name))
    if not pecas:
        pecas = [(1, clipe, True)]

    clips = []
    for n, arquivo, eh_aprovada in pecas:
        sufixo = "" if len(pecas) == 1 else f"-{n}"
        nome_mp4 = f"{slug}{sufixo}.mp4"
        shutil.copy2(arquivo, tmp / nome_mp4)
        titulo = plano["titulo"] if len(pecas) == 1 else f"{plano['titulo']} (faixa {n})"
        clip = {"filename": nome_mp4, "title": titulo,
                "description": descricao, "tags": tags_de(plano)}
        if crua.exists():
            from src.arte import compor_capa_yt, ArteError
            thumb = f"capa-yt{sufixo}.jpg"
            try:
                compor_capa_yt(crua, plano["titulo"], plano["capa"].get("paleta"),
                               plano["capa"].get("template", ""), tmp / thumb,
                               tagline=plano["capa"].get("tagline", ""),
                               versao=None if len(pecas) == 1 else n)
                clip["thumbnail"] = thumb
            except (ArteError, OSError, ValueError) as e:
                print(f"publicação: sem capa 16:9 da faixa {n} ({e}) — vai sem thumbnail")
        else:
            print("publicação: não há raw/capa-crua.png — o pacote vai sem thumbnail")
        clips.append(clip)
    # Sem `privacy` e sem `publish_at` de propósito: agendamento e visibilidade
    # são decisão do canal, não da peça.
    manifesto = {"titulo": plano["titulo"], "clips": clips}
    (tmp / "manifest.json").write_text(
        json.dumps(manifesto, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    shutil.rmtree(destino, ignore_errors=True)
    tmp.rename(destino)       # troca atômica: ninguém lê pasta pela metade
    return destino


def _post_multipart(url: str, campos: dict, arquivo_campo: str, arquivo: Path) -> dict:
    b = uuid.uuid4().hex
    corpo = b""
    for k, v in campos.items():
        corpo += (f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n').encode()
    corpo += (f'--{b}\r\nContent-Disposition: form-data; name="{arquivo_campo}"; '
              f'filename="{arquivo.name}"\r\n'
              f'Content-Type: application/octet-stream\r\n\r\n').encode()
    corpo += arquivo.read_bytes() + f"\r\n--{b}--\r\n".encode()
    req = urllib.request.Request(url, data=corpo,
                                 headers={"Content-Type": f"multipart/form-data; boundary={b}"},
                                 method="POST")
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read().decode())


def resumo_de_estilo(plano: dict) -> str:
    """Gênero, andamento e mood numa linha — o que identifica a MÚSICA.

    Vai junto do mp3 e da capa porque nesse momento a decisão é sobre o som:
    ouvir a faixa olhando a capa e saber de que música se trata. No vídeo
    final não vai: lá a peça já está pronta e o que importa é o título.
    """
    e = (plano.get("musica") or {}).get("estilo") or {}
    partes = [str(e.get("genero") or "").strip()]
    if e.get("bpm"):
        partes.append(f"{e['bpm']} bpm")
    if e.get("tom"):
        partes.append(str(e["tom"]))
    mood = e.get("mood") or []
    if isinstance(mood, list) and mood:
        partes.append(", ".join(map(str, mood[:3])))
    elif mood:
        partes.append(str(mood))
    return " · ".join(x for x in partes if x)


def link_do_clipe(workdir: Path) -> str:
    """O endereço do clipe para o fecho da entrega.

    `MUSICAVIDEO_LINK_BASE` (ex.: `http://192.168.2.99:5400/musicavideo`) faz o
    link apontar para o painel, que já serve o arquivo com suporte a arrastar a
    barra. Sem a variável, vai o caminho absoluto — o bot sabe transformar em
    link, e caminho errado é melhor que link inventado.
    """
    w = Path(workdir)
    base = os.environ.get("MUSICAVIDEO_LINK_BASE", "").rstrip("/")
    if base:
        return f"{base}/{w.name}/clipe.mp4"
    return str(w / "clipe.mp4")


def enviar_telegram(workdir: Path, estado: dict, plano: dict, http=None) -> None:
    if not estado.get("telegram"):
        return                                   # desligado por default
    token = ler_env_chave(["TELEGRAM_BOT_TOKEN"])
    chat = ler_env_chave(["TELEGRAM_CHAT_ID", "ALLOWED_CHAT_ID"])
    if not (token and chat):
        print("telegram: token/chat_id não encontrados nos .env autorizados — pulando envio")
        return
    base = f"https://api.telegram.org/bot{token}"
    from src.executor import faixa_aprovada
    from src.montagem import faixas_existentes
    w = Path(workdir)
    aprovada = faixa_aprovada(w, estado)
    # AS DUAS FAIXAS, SEMPRE. O Suno entrega duas e elas são músicas
    # diferentes — mandar só a aprovada tira do dono justamente o que ele
    # decide de ouvido. A marca de qual está aprovada vai na legenda.
    estilo = resumo_de_estilo(plano)
    sufixo_estilo = f"\n{estilo}" if estilo else ""
    envios = [(f, "sendAudio", "audio",
               f"{plano['titulo']} — {f.stem.split('-')[-1] if '-' in f.stem else '1'}"
               + (" ✓ aprovada" if aprovada and f.name == aprovada.name else "")
               + sufixo_estilo)
              for f in faixas_existentes(w)]
    # capa acompanha o som (título + estilo); o vídeo final leva só o título —
    # e vai DEPOIS da capa, para a capa ser o frame que anuncia a peça.
    envios += [(w / "capa.png", "sendPhoto", "photo", f"{plano['titulo']}{sufixo_estilo}"),
               (w / "clipe.mp4", "sendVideo", "video", plano["titulo"])]
    # FECHO: a capa outra vez, agora com o título e o LINK. É a mensagem que
    # fica valendo no chat — quem rolar a conversa depois acha a peça por ela,
    # sem precisar caçar o vídeo no meio dos áudios.
    if (w / "clipe.mp4").exists():
        envios.append((w / "capa.png", "sendPhoto", "photo",
                       f"{plano['titulo']}\n{link_do_clipe(w)}"))
    for arq, metodo, campo, legenda in envios:
        if arq.exists():
            _post_multipart(f"{base}/{metodo}",
                            {"chat_id": chat, "caption": legenda}, campo, arq)


def entregar(outdir: Path, slug: str) -> Path:
    outdir = Path(outdir)
    w = outdir / slug
    pacote = gerar_pacote(outdir, slug)
    plano = json.loads((w / "plano.json").read_text(encoding="utf-8"))
    estado = carregar_estado(w)
    enviar_telegram(w, estado, plano)
    if all(estado["partes"][p]["estado"] == "pronto" for p in PARTES):
        pacote_canal = montar_publicacao(outdir, slug)
        if pacote_canal:
            # RECIBO: é por esta linha que o bot acha o pacote e o leva ao canal
            # declarado no alvo. Mesmo idioma `campo: valor` do executor.
            print(f"publicacao: {pacote_canal}")
    if all(estado["partes"][p]["estado"] == "pronto" for p in PARTES):
        estado["fase"] = "entregue"
        registrar(estado, "entrega", detalhe="pacote completo")
    salvar_estado(w, estado)
    gravar_linha(outdir, linha_de(plano, estado))
    print(f"pacote em {pacote}")
    return pacote

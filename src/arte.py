"""A ARTE da capa: o título composto POR CIMA da imagem gerada.

O gerador entrega um fundo — quem escreve o título é aqui, e de forma
determinística: nada de modelo decidindo posição de texto. O template da capa
(`data/templates-capa.json`) DECLARA a tipografia (fonte, posição, quanto da
largura ocupar, tratamento de contraste); esta função obedece.

Determinístico de propósito: recompor a arte não custa crédito nenhum, então dá
pra mexer no título quantas vezes quiser sem gerar imagem de novo.
"""
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

RAIZ = Path(__file__).resolve().parent.parent
FONTES = RAIZ / "data" / "fontes"
FONTE_FALLBACK = "DejaVuSans-Bold.ttf"

# Usado quando o template não declara tipografia (template novo, plano antigo).
TIPOGRAFIA_PADRAO = {
    "fonte": FONTE_FALLBACK, "posicao": "base", "largura_alvo": 0.7,
    "alinhamento": "centro", "caixa_alta": True, "max_linhas": 2,
    "entrelinha": 1.0, "tracking": 0.02, "contraste": "sombra",
    # `simples` = título sobre a imagem; `poster` = cartaz de cinema (tagline,
    # título no terço inferior, filete, billing block). Ver compor_poster.
    "estilo": "simples",
}

MARGEM = 0.07          # respiro nas bordas, em fração do lado
BRANCO = (255, 255, 255)
PRETO = (18, 18, 18)


class ArteError(Exception):
    pass


# ------------------------------------------------------------------ template

def tipografia_de(template_id: str) -> dict:
    arq = RAIZ / "data" / "templates-capa.json"
    tipo = dict(TIPOGRAFIA_PADRAO)
    try:
        d = json.loads(arq.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return tipo
    for t in d.get("templates", []):
        if t.get("id") == template_id:
            tipo.update(t.get("tipografia") or {})
            break
    return tipo


def _fonte(nome: str, tamanho: int) -> ImageFont.FreeTypeFont:
    for cand in (FONTES / nome, FONTES / FONTE_FALLBACK):
        if cand.exists():
            return ImageFont.truetype(str(cand), tamanho)
    raise ArteError(f"nenhuma fonte disponível em {FONTES}")


# --------------------------------------------------------------- texto e cor

def quebrar(titulo: str, max_linhas: int) -> list[str]:
    """Quebra o título em até `max_linhas`, equilibrando o comprimento — sem
    linha órfã de uma palavra curta quando dá pra dividir melhor."""
    palavras = titulo.split()
    if not palavras:
        return [""]
    if len(palavras) == 1 or max_linhas <= 1:
        return [" ".join(palavras)]
    n = min(max_linhas, len(palavras))
    melhor, melhor_custo = None, None
    for k in range(1, n + 1):
        linhas, custo = _reparte(palavras, k)
        if melhor_custo is None or custo < melhor_custo:
            melhor, melhor_custo = linhas, custo
    return melhor


def _reparte(palavras: list[str], k: int) -> tuple[list[str], float]:
    """Divide em exatamente k linhas por ganância balanceada; custo = desvio."""
    alvo = (sum(len(p) for p in palavras) + len(palavras) - 1) / k
    linhas, atual = [], []
    for p in palavras:
        restam_linhas = k - len(linhas)
        cabe = len(" ".join(atual + [p])) <= alvo * 1.35
        # nunca deixar linhas a mais do que palavras restantes
        if atual and (not cabe) and restam_linhas > 1:
            linhas.append(" ".join(atual))
            atual = [p]
        else:
            atual.append(p)
    if atual:
        linhas.append(" ".join(atual))
    while len(linhas) > k:                       # junta as duas menores no fim
        linhas[-2] = linhas[-2] + " " + linhas[-1]
        linhas.pop()
    # O corpo da fonte cai com a linha MAIS LARGA — então o que se minimiza é o
    # máximo, não a variância. Desequilíbrio e linha a mais entram só como
    # desempate: duas linhas certas valem mais que uma linha comprida e minúscula.
    comps = [len(x) for x in linhas]
    custo = max(comps) + 0.3 * (max(comps) - min(comps)) + 0.5 * k
    return linhas, custo


def _hex_rgb(c: str):
    c = (c or "").strip().lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    if len(c) != 6:
        return None
    try:
        return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return None


def _lum(rgb) -> float:
    r, g, b = (x / 255 for x in rgb)
    f = lambda v: v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def contraste(a, b) -> float:
    la, lb = _lum(a), _lum(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def cor_do_texto(fundo_medio, paleta: list[str]):
    """A paleta do plano tem prioridade — mas só se ler de verdade sobre o
    fundo. Contraste < 4.5 é texto que some no thumbnail."""
    cands = [c for c in (_hex_rgb(x) for x in (paleta or [])) if c]
    cands = sorted(cands, key=lambda c: contraste(c, fundo_medio), reverse=True)
    if cands and contraste(cands[0], fundo_medio) >= 4.5:
        return cands[0]
    return BRANCO if contraste(BRANCO, fundo_medio) >= contraste(PRETO, fundo_medio) else PRETO


# ------------------------------------------------------------------ desenho

def _passo(fonte, corpo: int, tipo: dict) -> int:
    """Entrelinha nunca menor que a altura REAL da fonte: com `entrelinha` justa,
    o til de VERÃO batia na linha de cima (Montserrat Black tem acento alto)."""
    a, d = fonte.getmetrics()
    return max(int(corpo * float(tipo.get("entrelinha", 1.0))), int((a + d) * 0.98))


def _largura(draw, texto, fonte, tracking_px) -> int:
    if not texto:
        return 0
    l = draw.textlength(texto, font=fonte)
    return int(l + tracking_px * max(len(texto) - 1, 0))


def _escrever(draw, x, y, texto, fonte, tracking_px, cor):
    if tracking_px <= 0:
        draw.text((x, y), texto, font=fonte, fill=cor)
        return
    for ch in texto:
        draw.text((x, y), ch, font=fonte, fill=cor)
        x += draw.textlength(ch, font=fonte) + tracking_px


def _scrim(img, caixa, forca=0.55):
    x0, y0, x1, y1 = caixa
    capa = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(capa).rectangle([x0, y0, x1, y1], fill=(0, 0, 0, int(255 * forca)))
    return Image.alpha_composite(img, capa)


def _gradiente(img, posicao, altura_frac=0.55, forca=0.75):
    W, H = img.size
    h = max(int(H * altura_frac), 1)
    faixa = Image.new("L", (1, h))
    for i in range(h):
        t = i / max(h - 1, 1)
        faixa.putpixel((0, i), int(255 * forca * (t ** 1.6)))
    if posicao == "topo":
        faixa = faixa.transpose(Image.FLIP_TOP_BOTTOM)
        topo = 0
    else:
        topo = H - h
    alpha = Image.new("L", (W, H), 0)
    alpha.paste(faixa.resize((W, h)), (0, topo))
    escuro = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    escuro.putalpha(alpha)
    return Image.alpha_composite(img, escuro)


# -------------------------------------------------------------------- compor

def compor_capa(bruta: Path, titulo: str, paleta: list[str] | None,
                template_id: str, destino: Path) -> Path:
    """Escreve `titulo` sobre `bruta` e salva em `destino`. Idempotente: sempre
    parte da imagem crua, então recompor não empilha texto sobre texto."""
    bruta, destino = Path(bruta), Path(destino)
    if not bruta.exists():
        raise ArteError(f"imagem crua não encontrada: {bruta}")
    titulo = (titulo or "").strip()
    tipo = tipografia_de(template_id)
    img = Image.open(bruta).convert("RGBA")
    if not titulo:
        img.convert("RGB").save(destino)
        return destino
    W, H = img.size
    if tipo.get("caixa_alta", True):
        titulo = titulo.upper()
    linhas = quebrar(titulo, int(tipo.get("max_linhas", 2)))
    alvo_px = float(tipo.get("largura_alvo", 0.7)) * W
    tracking_frac = float(tipo.get("tracking", 0.0))
    draw = ImageDraw.Draw(img)

    # busca binária no corpo da fonte até a linha mais larga bater o alvo
    lo, hi, escolhido = 8, max(int(H * 0.9), 10), None
    while lo <= hi:
        meio = (lo + hi) // 2
        f = _fonte(tipo["fonte"], meio)
        tr = tracking_frac * meio
        larg = max(_largura(draw, l, f, tr) for l in linhas)
        alt = int(_passo(f, meio, tipo) * len(linhas))
        if larg <= alvo_px and alt <= H * (1 - 2 * MARGEM):
            escolhido, lo = (meio, f, tr, larg, alt), meio + 1
        else:
            hi = meio - 1
    if escolhido is None:
        f = _fonte(tipo["fonte"], 8)
        escolhido = (8, f, 0.0, max(_largura(draw, l, f, 0) for l in linhas),
                     int(8 * len(linhas)))
    corpo, fonte, tracking_px, larg_bloco, alt_bloco = escolhido
    passo = _passo(fonte, corpo, tipo)

    posicao = tipo.get("posicao", "base")
    margem = int(min(W, H) * MARGEM)
    if posicao == "topo":
        y0 = margem
    elif posicao == "centro":
        y0 = (H - alt_bloco) // 2
    else:
        y0 = H - margem - alt_bloco

    # cor lida do PEDAÇO onde o texto vai cair, não da imagem inteira
    regiao = img.convert("RGB").crop((0, max(y0 - passo // 4, 0), W,
                                      min(y0 + alt_bloco + passo // 4, H)))
    medio = tuple(int(v) for v in regiao.resize((1, 1)).getpixel((0, 0)))

    trat = tipo.get("contraste", "sombra")
    if trat == "scrim":
        img = _scrim(img, (0, max(y0 - margem // 2, 0), W,
                           min(y0 + alt_bloco + margem // 2, H)))
        medio = (0, 0, 0)
    elif trat == "gradiente":
        img = _gradiente(img, "topo" if posicao == "topo" else "base")
        medio = tuple(int(v * 0.35) for v in medio)
    draw = ImageDraw.Draw(img)

    cor = cor_do_texto(medio, paleta or [])
    sombra = trat == "sombra"
    alinhamento = tipo.get("alinhamento", "centro")
    y = y0
    for linha in linhas:
        lw = _largura(draw, linha, fonte, tracking_px)
        if alinhamento == "esquerda":
            x = margem
        elif alinhamento == "direita":
            x = W - margem - lw
        else:
            x = (W - lw) // 2
        if sombra:
            desl = max(corpo // 22, 2)
            escura = PRETO if _lum(cor) > 0.4 else BRANCO
            _escrever(draw, x + desl, y + desl, linha, fonte, tracking_px,
                      escura + (140,) if len(escura) == 3 else escura)
        _escrever(draw, x, y, linha, fonte, tracking_px, cor)
        y += passo
    img.convert("RGB").save(destino)
    return destino


# --------------------------------------------------------- capa 16:9 (YouTube)

# `thumbnails.set` do YouTube: 1280x720 e teto de 2 MB — por isso JPG, e por
# isso a quadrada não serve (subir 1:1 dá letterbox no player).
YT_LARGURA, YT_ALTURA = 1280, 720
YT_TETO_BYTES = 2 * 1024 * 1024


def _fundo_16x9(crua: Image.Image) -> Image.Image:
    """A crua é 1:1. Em vez de cortar (perde metade da arte) ou deixar barra
    preta, o quadrado vai inteiro no centro e as laterais são ele mesmo,
    ampliado e borrado — o truque de capa de álbum em player widescreen."""
    from PIL import ImageFilter
    lado = min(crua.size)
    quadro = crua.crop(((crua.width - lado) // 2, (crua.height - lado) // 2,
                        (crua.width + lado) // 2, (crua.height + lado) // 2))
    fundo = quadro.resize((YT_LARGURA, YT_LARGURA)).crop(
        (0, (YT_LARGURA - YT_ALTURA) // 2, YT_LARGURA, (YT_LARGURA + YT_ALTURA) // 2))
    fundo = fundo.filter(ImageFilter.GaussianBlur(28))
    centro = quadro.resize((YT_ALTURA, YT_ALTURA))
    fundo.paste(centro, ((YT_LARGURA - YT_ALTURA) // 2, 0))
    return fundo


def compor_capa_yt(bruta: Path, titulo: str, paleta: list[str] | None,
                   template_id: str, destino: Path, tagline: str = "",
                   versao: int | None = None) -> Path:
    """A MESMA crua, na proporção que o YouTube quer. Não gera imagem nova:
    recompor a thumbnail é de graça, gerar é que custa."""
    bruta, destino = Path(bruta), Path(destino)
    if not bruta.exists():
        raise ArteError(f"imagem crua não encontrada: {bruta}")
    base = _fundo_16x9(Image.open(bruta).convert("RGB"))
    tmp = destino.with_suffix(".base.png")
    base.save(tmp)
    try:
        compor(tmp, titulo, paleta, template_id, destino, tagline=tagline, versao=versao)
        # A composição salva no formato da extensão; para JPG o teto de 2 MB
        # manda, então cai a qualidade até caber em vez de o upload dar 400.
        q = 92
        while destino.stat().st_size > YT_TETO_BYTES and q > 55:
            q -= 10
            Image.open(destino).convert("RGB").save(destino, "JPEG", quality=q)
    finally:
        tmp.unlink(missing_ok=True)
    return destino


# ------------------------------------------------------------------- PÔSTER
#
# O que separa "título sobre imagem" de CARTAZ, e por que cada peça está aqui:
#
#   degradê na base  dá CHÃO ao texto. Sem ele o bloco flutua sobre a cena.
#   tagline          uma linha, pequena, tracking largo, na cor de acento.
#   título           terço inferior, quase toda a largura, sombra dura.
#   filete           risco curto separando título e créditos.
#   billing block    linha condensada minúscula — é o que o olho lê como cinema.
#
# Tudo determinístico: recompor não custa nada, e a decisão de posição é do
# TEMPLATE, não de um modelo.

ACENTO_PADRAO = (214, 158, 114)
CREDITOS_PADRAO = "MUSICAVIDEO  ·  INEMA.CLUB  ·  TRILHA ORIGINAL"


def _base_escura(img: Image.Image, altura=0.52, forca=0.88) -> Image.Image:
    W, H = img.size
    h = max(int(H * altura), 1)
    faixa = Image.new("L", (1, h))
    for i in range(h):
        faixa.putpixel((0, i), int(255 * forca * ((i / max(h - 1, 1)) ** 1.7)))
    alpha = Image.new("L", (W, H), 0)
    alpha.paste(faixa.resize((W, h)), (0, H - h))
    escuro = Image.new("RGBA", (W, H), (8, 10, 14, 255))
    escuro.putalpha(alpha)
    return Image.alpha_composite(img.convert("RGBA"), escuro)


def _corpo_que_cabe(draw, texto: str, arq: str, alvo_px: float,
                    tracking: float, teto: int):
    """Maior corpo cujo texto ainda cabe em `alvo_px`. Devolve (corpo, fonte, tracking_px)."""
    lo, hi, melhor = 8, max(teto, 9), None
    while lo <= hi:
        m = (lo + hi) // 2
        f = _fonte(arq, m)
        if _largura(draw, texto, f, tracking * m) <= alvo_px:
            melhor, lo = (m, f, tracking * m), m + 1
        else:
            hi = m - 1
    if melhor is None:
        f = _fonte(arq, 8)
        melhor = (8, f, 0.0)
    return melhor


def marcar_versao(img: Image.Image, versao: int, acento=ACENTO_PADRAO) -> Image.Image:
    """O selo de VERSÃO, grande, no alto à direita.

    O Suno entrega DUAS faixas por música e cada uma vira um clipe. Sem marca,
    as duas capas ficam idênticas e escolher vira adivinhação — no thumbnail do
    celular tem que dar para ver qual é qual de longe.
    """
    W, H = img.size
    draw = ImageDraw.Draw(img)
    corpo = int(H * 0.20)
    f = _fonte(TIPOGRAFIA_POSTER["titulo"], corpo)
    txt = str(versao)
    lw = int(draw.textlength(txt, font=f))
    cx = W - int(W * 0.075) - lw
    cy = int(H * 0.055)
    frot = _fonte(TIPOGRAFIA_POSTER["tagline"], max(int(corpo * 0.13), 11))
    tr = frot.size * 0.3
    lr = _largura(draw, "VERSÃO", frot, tr)
    _escrever(draw, cx + (lw - lr) // 2, cy, "VERSÃO", frot, tr, acento)
    y = cy + int(corpo * 0.22)
    d = max(corpo // 40, 3)
    draw.text((cx + d, y + d), txt, font=f, fill=PRETO)
    draw.text((cx, y), txt, font=f, fill=acento)
    return img


TIPOGRAFIA_POSTER = {
    "titulo": "BebasNeue-Regular.ttf",     # condensada: o mais perto de cartaz que temos
    "tagline": "Montserrat-Black.ttf",
    "creditos": "DejaVuSans-Bold.ttf",
}


def compor_poster(bruta: Path, titulo: str, destino: Path, *,
                  tagline: str = "", creditos: str = CREDITOS_PADRAO,
                  versao: int | None = None, acento=ACENTO_PADRAO) -> Path:
    """Capa em estilo cartaz de cinema. Sempre parte da imagem CRUA."""
    bruta, destino = Path(bruta), Path(destino)
    if not bruta.exists():
        raise ArteError(f"imagem crua não encontrada: {bruta}")
    img = _base_escura(Image.open(bruta).convert("RGB"))
    W, H = img.size
    draw = ImageDraw.Draw(img)
    margem = int(W * 0.075)
    util = W - 2 * margem

    alto = (titulo or "").strip().upper()
    if not alto:
        img.convert("RGB").save(destino, quality=95)
        return destino
    linhas = [alto]
    corpo, ftit, trk = _corpo_que_cabe(draw, alto, TIPOGRAFIA_POSTER["titulo"],
                                       util, 0.03, int(H * 0.30))
    palavras = alto.split()
    if corpo < H * 0.075 and len(palavras) > 1:      # ficou miúdo: quebra em duas
        meio = len(palavras) // 2 + len(palavras) % 2
        linhas = [" ".join(palavras[:meio]), " ".join(palavras[meio:])]
        corpo, ftit, trk = _corpo_que_cabe(draw, max(linhas, key=len),
                                           TIPOGRAFIA_POSTER["titulo"], util, 0.03,
                                           int(H * 0.22))
    passo = int(corpo * 0.92)
    base_y = H - int(H * 0.135) - passo * len(linhas)

    if tagline.strip():
        ctag, ftag, ttag = _corpo_que_cabe(draw, tagline.upper(),
                                           TIPOGRAFIA_POSTER["tagline"], util * 0.8,
                                           0.28, max(int(corpo * 0.16), 12))
        lt = _largura(draw, tagline.upper(), ftag, ttag)
        _escrever(draw, (W - lt) // 2, base_y - int(ctag * 2.6), tagline.upper(),
                  ftag, ttag, acento)

    for i, linha in enumerate(linhas):
        lw = _largura(draw, linha, ftit, trk)
        x, y = (W - lw) // 2, base_y + i * passo
        d = max(corpo // 40, 2)
        _escrever(draw, x + d, y + d, linha, ftit, trk, (0, 0, 0))
        _escrever(draw, x, y, linha, ftit, trk, (242, 240, 236))

    if creditos.strip():
        fio_y = H - int(H * 0.105)
        draw.line([(W // 2 - util // 6, fio_y), (W // 2 + util // 6, fio_y)],
                  fill=acento, width=max(H // 700, 1))
        ccr, fcr, tcr = _corpo_que_cabe(draw, creditos, TIPOGRAFIA_POSTER["creditos"],
                                        util * 0.92, 0.14, max(int(H * 0.022), 10))
        lc = _largura(draw, creditos, fcr, tcr)
        _escrever(draw, (W - lc) // 2, fio_y + int(ccr * 0.9), creditos,
                  fcr, tcr, (170, 172, 176))

    if versao is not None:
        img = marcar_versao(img, versao, acento)
    img.convert("RGB").save(destino, quality=95)
    return destino


def compor(bruta: Path, titulo: str, paleta, template_id: str, destino: Path, *,
           tagline: str = "", creditos: str = CREDITOS_PADRAO,
           versao: int | None = None) -> Path:
    """Porta única: o TEMPLATE decide se a capa é `simples` ou `poster`."""
    if tipografia_de(template_id).get("estilo") == "poster":
        return compor_poster(bruta, titulo, destino, tagline=tagline,
                             creditos=creditos, versao=versao)
    return compor_capa(bruta, titulo, paleta, template_id, destino)


# ------------------------------------------------------------------ miniatura
#
# O card da grade desenha um quadrado de ~260px e estava puxando a capa
# INTEIRA: 1024px de PNG, ~1,2 MB cada. Com duas faixas por produção, abrir a
# vitrine pedia dezenas de megabytes para desenhar miniaturas — e quem paga é
# quem abre no celular. A capa cheia continua existindo: ela é o que o clique
# "abrir em tamanho real" mostra, e é o que vai para o YouTube.

MINI_LARGURA = 480
MINI_QUALIDADE = 78


def miniatura(origem: Path, destino: Path | None = None,
              largura: int = MINI_LARGURA, qualidade: int = MINI_QUALIDADE) -> Path:
    """`capa.png` -> `capa-thumb.jpg`, redimensionada e em JPEG.

    JPEG e não PNG de propósito: capa é fotografia, e o PNG guarda cada pixel
    de um material que já vai ser reduzido a um terço do tamanho na tela.
    """
    origem = Path(origem)
    destino = Path(destino) if destino else origem.with_name(origem.stem + "-thumb.jpg")
    img = Image.open(origem)
    if img.width > largura:
        altura = round(img.height * largura / img.width)
        img = img.resize((largura, altura), Image.LANCZOS)
    img.convert("RGB").save(destino, "JPEG", quality=qualidade, optimize=True,
                            progressive=True)
    return destino


def garantir_miniaturas(w: Path) -> list[Path]:
    """As miniaturas de todas as capas da produção, criando o que faltar.

    Refazer só quando a capa é mais nova que a miniatura: recompor uma capa
    (`musicavideo arte`) tem de atualizar o card, mas rodar de novo não pode
    custar CPU à toa.
    """
    w = Path(w)
    feitas = []
    for capa in sorted(w.glob("capa.png")) + sorted(w.glob("capa-v*.png")):
        alvo = capa.with_name(capa.stem + "-thumb.jpg")
        try:
            if alvo.exists() and alvo.stat().st_mtime >= capa.stat().st_mtime:
                feitas.append(alvo)
                continue
            feitas.append(miniatura(capa, alvo))
        except (OSError, ValueError):
            continue                  # capa ilegível não derruba a publicação
    return feitas

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
        entre = float(tipo.get("entrelinha", 1.0))
        alt = int(meio * entre * len(linhas))
        if larg <= alvo_px and alt <= H * (1 - 2 * MARGEM):
            escolhido, lo = (meio, f, tr, larg, alt), meio + 1
        else:
            hi = meio - 1
    if escolhido is None:
        f = _fonte(tipo["fonte"], 8)
        escolhido = (8, f, 0.0, max(_largura(draw, l, f, 0) for l in linhas),
                     int(8 * len(linhas)))
    corpo, fonte, tracking_px, larg_bloco, alt_bloco = escolhido
    passo = int(corpo * float(tipo.get("entrelinha", 1.0)))

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

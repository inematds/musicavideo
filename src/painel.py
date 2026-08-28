"""Painel de consulta (somente leitura) dos dois acervos que vivem em
~/projetos/output: os pacotes do musicavideo e as análises do analisevideo.

Servidor stdlib enraizado na pasta output — é o que faz o <video>/<audio>
tocar de verdade (file:// não serve range requests). Render por requisição:
os index.jsonl são reescritos a cada mudança de estado, página assada nasce velha.
"""
import json
import os
import socket
import sys
from datetime import datetime
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from src import subida
from src.nuvem import (situacao as situacao_nuvem, situacao_faixa as situacao_faixa_nuvem,
                       aprovar as aprovar_nuvem)
from src.versao import NOME, VERSAO


def raiz_output() -> Path:
    return Path(os.environ.get("INEMA_OUTPUT",
                str(Path.home() / "projetos/output")))


def _mvd_do_estado(w: Path) -> str:
    """O `mvd` gravado na produção, que é a fonte de verdade do número."""
    try:
        return str(json.loads((w / "estado.json").read_text(encoding="utf-8")).get("mvd") or "")
    except (OSError, ValueError):
        return ""


def _linhas(idx: Path) -> list[dict]:
    if not idx.exists():
        return []
    out = []
    for linha in idx.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha:
            continue
        try:
            out.append(json.loads(linha))
        except ValueError:
            continue
    return out


def _faixa(w: Path) -> str | None:
    """A faixa aprovada — o Suno entrega duas e o nome varia por slug."""
    est = w / "estado.json"
    if est.exists():
        try:
            art = json.loads(est.read_text(encoding="utf-8"))["partes"]["musica"].get("artefato")
        except (ValueError, KeyError, OSError):
            art = None
        if art and (w / art).exists():
            return art
    for nome in ("faixa-1.mp3", "faixa.mp3"):
        if (w / nome).exists():
            return nome
    achadas = sorted(w.glob("faixa*.mp3"))
    return achadas[0].name if achadas else None


def _documento(w: Path, limite: int = 120000) -> str | None:
    """PACOTE + PLANO, nessa ordem, no mesmo painel de leitura.

    O `PACOTE.md` é um resumo de entrega (estado, custo, pasta) — cabe em 20
    linhas. O que a pessoa quer ler quando abre um card é o PLANO: letra,
    estilo, decupagem plano a plano. Mostrar só o pacote fazia o card parecer
    vazio justamente nas produções em que o plano é mais rico.
    """
    partes = []
    for nome in ("PACOTE.md", "PLANO.md"):
        txt = _texto(w / nome, limite)
        if txt:
            partes.append(txt.strip())
    if not partes:
        return None
    return ("\n\n" + "─" * 60 + "\n\n").join(partes)[:limite]


def _texto(p: Path, limite: int = 40000) -> str | None:
    if not p.exists():
        return None
    try:
        return p.read_text(encoding="utf-8")[:limite]
    except OSError:
        return None


LIXEIRA = ".lixo"


def _url(base: Path, rel: str) -> str | None:
    """URL do arquivo com a data dele no fim: `capa.png?v=1756...`.

    O caminho de um artefato NUNCA muda — `capa.png` é sempre `capa.png` —, só
    o conteúdo. Sem isto o navegador serve a versão que já tem em cache e a capa
    refeita simplesmente não aparece (2026-08-23: as 6 capas foram regeradas e
    o painel continuou mostrando as antigas).
    """
    arq = base / rel
    if not arq.exists():
        return None
    return f"{base.name}/{rel}?v={int(arq.stat().st_mtime)}"


# Rótulo de cada capa que o pipeline produz. A quadrada é a do álbum; a
# `capa-yt.jpg` é a 16:9 do YouTube — hoje DERIVADA da quadrada (miolo no
# centro, laterais preenchidas com ela mesma borrada), e é a que aparece no
# feed. Refazer a imagem em cada proporção é o item 1 do MELHORIAS.
CAPAS = [("capa.png", "quadrada 1:1"),
         ("publicacao/capa-yt.jpg", "YouTube 16:9"),
         ("capa-v1.png", "variante · faixa 1"),
         ("capa-v2.png", "variante · faixa 2"),
         ("capa-crua.png", "sem texto")]


def _likes_da(base: Path, mvd: str, n: str) -> int:
    """Curtidas desta FAIXA. A vitrine conta por versão (`MVD#113:1`); acervo
    antigo tem só a chave da produção, e é ela que vale como reserva."""
    d = _likes(base)
    if not mvd:
        return 0
    return int(d.get(f"{mvd}:{n}") or (d.get(mvd, 0) if not n else 0) or 0)


def _faixas(base: Path, slug: str, aprovada: str | None,
            mvd: str = "") -> list[dict]:
    """TODAS as faixas do slug, não só a aprovada.

    O Suno entrega duas, e antes elas só apareciam quando havia dois clipes
    montados — a segunda música ficava invisível no painel mesmo estando no
    disco, e é justamente ouvindo as duas que se escolhe qual aprovar.
    """
    saida = []
    for f in sorted((base / slug).glob("faixa*.mp3")):
        url = _url(base, f"{slug}/{f.name}")
        if not url:
            continue
        # Cada faixa anda com a SUA capa e o SEU clipe: `faixa-2.mp3` com
        # `capa-v2.png` e `clipe-2.mp4`. Empilhados, dá para ver e ouvir a
        # versão inteira sem caçar arquivo pelo nome — e é comparando as duas
        # na mesma tela que se escolhe qual aprovar.
        n = f.stem.rpartition("-")[2] if "-" in f.stem else ""
        saida.append({"url": url, "nome": f.name, "n": n,
                      "aprovada": f.name == aprovada,
                      "likes": _likes_da(base, mvd, n),
                      "capa": _url(base, f"{slug}/capa-v{n}.png") if n else None,
                      "clipe": (_url(base, f"{slug}/clipe-{n}.mp4") if n else None)
                               or _url(base, f"{slug}/clipe.mp4")})
    return saida


def _prompts(w: Path) -> dict | None:
    """O que FOI PEDIDO aos provedores, tirado do `plano.json`.

    O PLANO.md conta a história; estes são os textos literais que o Suno e o
    Agnes leram. É o que se quer ver quando um clipe sai diferente do plano —
    e ficava só dentro do JSON, invisível no painel.
    """
    try:
        p = json.loads((w / "plano.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    est = (p.get("musica") or {}).get("estilo") or {}
    capa = p.get("capa") or {}
    shots = [{"n": c.get("n"), "secao": c.get("secao", ""), "camera": c.get("camera", ""),
              "prompt": c.get("prompt", ""), "alt": c.get("prompt_alt", "")}
             for c in ((p.get("clipe") or {}).get("decupagem") or [])]
    d = {"estilo": est.get("prompt_estilo", ""),
         "imagem": capa.get("prompt_imagem", ""),
         "negativo": capa.get("prompt_negativo", ""),
         "conceito": capa.get("conceito", ""),
         "tagline": capa.get("tagline", ""),
         "shots": shots}
    return d if any(d.values()) else None


def _likes(base: Path) -> dict:
    """O que o público curtiu na vitrine, trazido pelo `publica-hf`.

    Vive num arquivo e não numa chamada de rede: o painel local tem que abrir
    com a internet fora, e like é informação de apoio, não o acervo.
    """
    try:
        return json.loads((base.parent / "likes.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _capas(base: Path, slug: str) -> list[dict]:
    saida = []
    for rel, rotulo in CAPAS:
        url = _url(base, f"{slug}/{rel}")
        if url:
            saida.append({"url": url, "rotulo": rotulo})
    return saida


def _tamanho(w: Path) -> int:
    """Bytes da pasta. É o número que faz querer apagar: cada recorte são
    centenas de MB, e eles acumulam sem aparecer em lugar nenhum."""
    total = 0
    for f in w.rglob("*"):
        try:
            if f.is_file():
                total += f.stat().st_size
        except OSError:
            continue
    return total


def _derivados(base: Path, ja_listados: set) -> list[dict]:
    """Pasta com clipe que o índice NÃO conhece — recorte, teste, remontagem.

    Elas existem no disco e não apareciam no painel: sem card, não há como ver
    nem como apagar, e o disco enche em silêncio. O sufixo depois do último `-`
    vira o rótulo (`-variado` → "variado"), e a pasta de origem, quando existe,
    agrupa o derivado embaixo do clipe pai.
    """
    saida = []
    for w in sorted(base.iterdir() if base.is_dir() else []):
        if not w.is_dir() or w.name.startswith(".") or w.name in ja_listados:
            continue
        clipes = sorted(w.glob("clipe*.mp4"))
        if not clipes:
            continue
        origem, _, rotulo = w.name.rpartition("-")
        if not (origem and (base / origem).is_dir()):
            origem, rotulo = "", "avulso"
        versoes = [{"n": v.stem.split("-")[-1],
                    "clipe": _url(base, f"{w.name}/{v.name}"),
                    "faixa": _url(base, f"{w.name}/faixa-{v.stem.split('-')[-1]}.mp3"),
                    "aprovada": False}
                   for v in sorted(w.glob("clipe-*.mp4"))]
        faixa = _faixa(w)
        saida.append({
            "fonte": "musicavideo", "slug": w.name, "titulo": w.name,
            "derivado": rotulo, "origem": origem,
            "quando": datetime.fromtimestamp(w.stat().st_mtime).isoformat(timespec="seconds"),
            "solicitacao": "", "genero": "", "bpm": None, "tom": "",
            "estados": {}, "motores": {}, "custo": 0, "tags": [],
            "bytes": _tamanho(w),
            "capa": _url(base, f"{w.name}/capa.png"),
            "capas": _capas(base, w.name),
            "clipe": _url(base, f"{w.name}/clipe.mp4"),
            "faixa": _url(base, f"{w.name}/{faixa}") if faixa else None,
            "faixas": _faixas(base, w.name, faixa),
            "versoes": versoes, "doc": None, "prompts": _prompts(w),
        })
    return saida


def para_lixeira(base: Path, slug: str) -> Path:
    """Apagar do painel MOVE, não destrói: engano tem volta.

    O painel roda na LAN quando sobe com `--lan`, e um clique errado não pode
    torrar horas de render. Esvaziar a lixeira é decisão de terminal.
    """
    base = Path(base).resolve()
    alvo = (base / slug).resolve()
    if alvo.parent != base or not alvo.is_dir() or alvo.name.startswith("."):
        raise ValueError(f"caminho fora do acervo: {slug}")
    lixo = base / LIXEIRA
    lixo.mkdir(exist_ok=True)
    destino = lixo / alvo.name
    n = 2
    while destino.exists():
        destino = lixo / f"{alvo.name}-{n}"
        n += 1
    alvo.rename(destino)
    return destino


def coletar(raiz: Path) -> dict:
    mv = []
    base = raiz / "musicavideo"
    # A fila se esvazia sozinha: nada subindo + alguém aprovado = começa. É o
    # que impede `aprovado` de virar beco agora que não há cron.
    try:
        subida.proxima(base)   # `base` JÁ é a pasta do acervo
    except OSError:
        pass
    subindo_agora = subida.em_andamento()
    for l in _linhas(base / "index.jsonl"):
        w = base / l.get("slug", "")
        if not w.is_dir():
            continue
        faixa = _faixa(w)
        # O NÚMERO vem do estado, nunca do índice. O `index.jsonl` só é
        # reescrito por quem mexe em estado ou por um `reindex`, então uma
        # renumeração feita direto no `estado.json` ficava invisível para o
        # painel e para a vitrine — foi assim que a vitrine passou dias
        # mostrando `MVD-013` enquanto o disco já dizia `MVD#113`.
        mvd_atual = _mvd_do_estado(w) or l.get("mvd") or ""
        versoes = []
        for v in sorted(w.glob("clipe-*.mp4")):
            n = v.stem.split("-")[-1]
            trilha = w / f"faixa-{n}.mp3"
            versoes.append({"n": n, "clipe": _url(base, f"{l['slug']}/{v.name}"),
                            "faixa": _url(base, f"{l['slug']}/{trilha.name}") if trilha.exists() else None,
                            "aprovada": bool(faixa) and faixa == trilha.name})
        # A SITUAÇÃO NA VITRINE É DE CADA FAIXA. O Suno entrega duas músicas
        # por pedido e elas são músicas diferentes: uma pode estar publicada e
        # a outra nem ter sido escolhida. O card mostra uma faixa por vez, e é
        # por isso que o selo (e o botão) da nuvem moram na faixa.
        subindo = subindo_agora == l.get("slug")
        faixas_do_card = _faixas(base, l["slug"], faixa, mvd_atual)
        for f in faixas_do_card:
            f["nuvem"] = ("subindo" if subindo
                          else situacao_faixa_nuvem(w, f.get("n") or "1"))
        for v in versoes:
            v["nuvem"] = ("subindo" if subindo
                          else situacao_faixa_nuvem(w, v.get("n") or "1"))
        mv.append({
            "fonte": "musicavideo",
            "slug": l.get("slug"),
            "mvd": mvd_atual,
            "titulo": l.get("titulo") or l.get("slug"),
            "quando": l.get("criado_em", ""),
            "solicitacao": l.get("solicitacao", ""),
            "genero": l.get("genero", ""),
            "bpm": l.get("bpm"),
            "tom": l.get("tom", ""),
            "estados": l.get("estados", {}),
            "motores": l.get("motores", {}),
            "custo": l.get("custo_gasto_usd", 0),
            "tags": l.get("tags", []),
            "capa": _url(base, f"{l['slug']}/capa.png"),
            "capas": _capas(base, l["slug"]),
            "clipe": _url(base, f"{l['slug']}/clipe.mp4"),
            "faixa": _url(base, f"{l['slug']}/{faixa}") if faixa else None,
            "faixas": faixas_do_card,
            "versoes": versoes,
            "bytes": _tamanho(w),
            "doc": _documento(w),
            "prompts": _prompts(w),
            "nuvem": ("subindo" if subindo_agora == l.get("slug")
                      else situacao_nuvem(w)),
            "likes": _likes(base).get(mvd_atual, 0),
            "docs": [d for d in (_url(base, f"{l['slug']}/PACOTE.md"),
                                 _url(base, f"{l['slug']}/PLANO.md")) if d],
        })

    mv += _derivados(base, {x["slug"] for x in mv})

    av = []
    base = raiz / "analisevideo"
    for l in _linhas(base / "index.jsonl"):
        w = base / l.get("slug", "")
        if not w.is_dir():
            continue
        fontes = sorted(w.glob("fonte.*"))
        av.append({
            "fonte": "analisevideo",
            "slug": l.get("slug"),
            "titulo": l.get("titulo") or l.get("slug"),
            "quando": l.get("quando", ""),
            "url": l.get("url", ""),
            "canal": l.get("canal", ""),
            "duracao_s": l.get("duracao_s"),
            "tipo": l.get("tipo", ""),
            "resumo": l.get("resumo", ""),
            "look": l.get("look", ""),
            "paleta": l.get("paleta", []) or [],
            "movimentos": l.get("movimentos", []) or [],
            "ritmo": l.get("ritmo", ""),
            "cortes_por_minuto": l.get("cortes_por_minuto"),
            "musica": l.get("musica"),
            "bpm": l.get("bpm"),
            "mood": l.get("mood", ""),
            "tags": l.get("tags", []) or [],
            "referencias": l.get("referencias", []) or [],
            "video": f"analisevideo/{l['slug']}/{fontes[0].name}" if fontes else None,
            "doc": _texto(w / "analise.md"),
        })

    mv.sort(key=lambda x: x.get("quando") or "", reverse=True)
    av.sort(key=lambda x: x.get("quando") or "", reverse=True)
    return {"musicavideo": mv, "analisevideo": av}


PAGINA = r"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{NOME_APP} V{VERSAO_APP}</title><style>
:root{--bg:#0d0b09;--card:#171310;--linha:#2b241d;--txt:#ece5da;--dim:#a2968a;--amb:#f0a92b}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--txt);
font:15px/1.5 system-ui,-apple-system,Segoe UI,sans-serif}
header{padding:20px 22px 0;position:sticky;top:0;background:var(--bg);z-index:5}
h1{margin:0 0 12px;font-size:19px;letter-spacing:.5px}
h1 span{color:var(--amb)}
.tabs{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
/* Os selos ficam SOBRE a capa: a versão à esquerda, o clipe à direita. */
.card{position:relative}
.selos{position:absolute;top:8px;left:8px;right:8px;z-index:2;display:flex;gap:6px;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;pointer-events:none}
/* `flex:0 0 auto` + `nowrap`: sem isso, card com clipe E nuvem espremia os dois
   selos até um cobrir o outro — o selo que some é justamente o que se queria ler. */
.selos .n{background:#000a;color:var(--txt);font-size:10.5px;letter-spacing:.5px;border-radius:99px;padding:1px 7px;white-space:nowrap;flex:0 0 auto}
.selos .n.ok{background:var(--amb);color:#1a1206;font-weight:600}
.selos .dir{display:flex;gap:6px}
/* O selo da nuvem é BOTÃO: precisa receber o clique que a barra de selos
   descarta (`pointer-events:none` existe para não roubar o clique da capa). */
.selos button.n{font:inherit;font-size:10.5px;line-height:1.5;border:0;cursor:pointer;pointer-events:auto}
.selos button.n:hover{filter:brightness(1.15)}
.selos button.n:disabled{cursor:default}
/* Os quatro estados de nuvem, cada um com a sua cor — dá para varrer a grade
   sem ler: âmbar cheio já está lá fora, contorno âmbar está a caminho. */
.selos .n.nv.ok{background:var(--amb);color:#1a1206;font-weight:600}
.selos .n.nv.aguarda{background:#000a;color:var(--amb);box-shadow:inset 0 0 0 1px var(--amb)}
.selos .n.nv.subindo{background:var(--amb);color:#1a1206;font-weight:600;animation:pulso 1.4s ease-in-out infinite}
@keyframes pulso{50%{opacity:.55}}
.selos .n.nv.sai{background:#000a;color:#e06c6c;box-shadow:inset 0 0 0 1px #7a3030}
/* `local` e secundario, mas tem de ser LEGIVEL: sobre capa clara o cinza
   apagado sumia, e "nao foi para a nuvem" e metade da resposta que o selo da. */
.selos .n.nv.local{background:#000c;color:#c9c9d2;box-shadow:inset 0 0 0 1px #4a4a55}
button.tab{background:var(--card);color:var(--dim);border:1px solid var(--linha);
border-radius:99px;padding:7px 15px;cursor:pointer;font-size:14px}
button.tab[aria-selected=true]{color:#1a1206;background:var(--amb);border-color:var(--amb);font-weight:600}
input#q{flex:1;min-width:200px;background:var(--card);border:1px solid var(--linha);
border-radius:8px;color:var(--txt);padding:8px 12px;font-size:14px}
#grade{display:grid;gap:14px;padding:18px 22px 60px;
grid-template-columns:repeat(auto-fill,minmax(280px,1fr))}
.card{background:var(--card);border:1px solid var(--linha);border-radius:12px;
overflow:hidden;cursor:pointer}
.card:hover{border-color:var(--amb)}
.card .thumb{width:100%;aspect-ratio:16/9;object-fit:cover;background:#0a0806;display:block}
/* capa é QUADRADA: recortada em 16/9 o título some. Inteira, com o fundo
   escuro nas laterais, é o que ela é. */
.card .thumb.capa{object-fit:contain}
/* As DUAS capas já na grade, lado a lado: a escolha entre a versão 1 e a 2 é a
   pergunta mais frequente do painel, e ela não precisa de um clique para
   começar. Cada uma com o seu play. */
.duas{display:grid;grid-template-columns:repeat(auto-fit,minmax(92px,1fr));gap:10px;
padding:10px 10px 4px}
.duas>div{position:relative;display:flex;flex-direction:column;gap:5px}
.duas img{width:100%;aspect-ratio:1;object-fit:cover;display:block;background:#0a0806;
border:1px solid var(--linha);border-radius:8px}
.duas audio{width:100%;height:32px;display:block}
.duas .n{position:absolute;top:6px;left:6px;background:#0009;color:var(--txt);
font-size:10.5px;letter-spacing:.5px;border-radius:99px;padding:1px 7px}
.duas .n.ok{background:var(--amb);color:#1a1206;font-weight:600}
.capas{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:12px}
.capas a{display:block;text-decoration:none;color:var(--dim);font-size:11.5px;text-align:center}
.capas img{display:block;max-height:190px;max-width:min(46vw,320px);width:auto;
border:1px solid var(--linha);border-radius:8px;background:#0a0806;margin-bottom:4px}
.capas a:hover img{border-color:var(--amb)}
.faixas{display:flex;flex-direction:column;gap:8px;margin-top:10px}
.faixas audio{width:100%;margin-top:3px}
.versaocapa{display:flex;flex-direction:column;align-items:flex-start;gap:5px;
padding-bottom:14px;border-bottom:1px solid var(--linha)}
.versaocapa:last-child{border-bottom:0}
.versaocapa img{display:block;max-height:300px;max-width:min(72vw,400px);width:auto;
border:1px solid var(--linha);border-radius:8px;background:#0a0806}
.versaocapa a:hover img{border-color:var(--amb)}
details.prompts{margin-top:14px;border:1px solid var(--linha);border-radius:10px;
background:#120f0c}
details.prompts>summary{cursor:pointer;padding:9px 12px;color:var(--amb);font-size:13.5px;
list-style:none}
details.prompts>summary::-webkit-details-marker{display:none}
details.prompts>summary::before{content:"▸ ";color:var(--dim)}
details.prompts[open]>summary::before{content:"▾ "}
details.prompts .corpo{padding:0 12px 12px}
details.prompts h4{margin:12px 0 4px;font-size:12px;letter-spacing:.6px;
text-transform:uppercase;color:var(--dim);font-weight:600}
details.prompts p{margin:0;font-size:13.5px;white-space:pre-wrap;word-break:break-word}
details.prompts .shot{border-top:1px solid var(--linha);padding-top:8px;margin-top:8px}
details.prompts .shot .meta{display:block;margin-bottom:3px}
details.prompts .alt{color:var(--dim);font-size:12.5px;margin-top:4px}
audio.nocard{width:100%;height:30px;margin:8px 0 2px;display:block}
a.pill.nocard{text-decoration:none;color:var(--amb);border-color:#5a4626}
a.pill.nocard:hover{background:#2a1f12}
.embed{position:relative;width:100%;aspect-ratio:16/9;background:#000;border-radius:10px;overflow:hidden}
.embed iframe{position:absolute;inset:0;width:100%;height:100%;border:0}
.card .b{padding:11px 13px}
.card h3{margin:0 0 5px;font-size:15px;line-height:1.3}
.meta{color:var(--dim);font-size:12.5px}
.pal{display:flex;gap:4px;margin-top:7px}
.pal i{width:16px;height:16px;border-radius:4px;display:block}
.pill{display:inline-block;font-size:11px;border:1px solid var(--linha);border-radius:99px;
padding:1px 8px;margin:5px 5px 0 0;color:var(--dim)}
.pill.ok{color:#7fd18a;border-color:#2f5133}.pill.err{color:#e58b7b;border-color:#5a2f28}
.pill.dv{color:#e0b25c;border-color:#5a4626;margin-right:7px}
.pill.mvd{color:var(--amb);border-color:#5a4626;letter-spacing:.6px;font-size:10.5px}
button.pill.nuvem{background:transparent;cursor:pointer;font:inherit;font-size:12px;
padding:5px 12px;border-radius:8px;color:var(--dim);border:1px solid var(--linha)}
button.pill.nuvem:hover{border-color:var(--amb);color:var(--txt)}
button.pill.nuvem.on{color:#1a1206;background:var(--amb);border-color:var(--amb);font-weight:600}
button.pill.nuvem:disabled{opacity:.6;cursor:default}
button.perigo{background:transparent;color:#e58b7b;border:1px solid #5a2f28;border-radius:8px;
padding:5px 12px;font:inherit;font-size:12px;cursor:pointer}
button.perigo:hover{background:#2a1714}button.perigo:disabled{opacity:.6;cursor:default}
dialog{background:var(--card);color:var(--txt);border:1px solid var(--linha);border-radius:14px;
max-width:900px;width:92vw;padding:0}
dialog::backdrop{background:#000b}
.dh{display:flex;justify-content:space-between;gap:12px;align-items:center;
padding:14px 18px;border-bottom:1px solid var(--linha);position:sticky;top:0;background:var(--card)}
.dh h2{margin:0;font-size:17px}
.dh button{background:none;border:1px solid var(--linha);color:var(--dim);border-radius:8px;
padding:4px 11px;cursor:pointer}
.db{padding:16px 18px 24px;max-height:72vh;overflow:auto}
.db video,.db img{width:100%;border-radius:10px;background:#000}
.db audio{width:100%;margin-top:10px}
pre{white-space:pre-wrap;word-wrap:break-word;max-height:60vh;overflow:auto;
background:#0a0806;border:1px solid var(--linha);
border-radius:10px;padding:13px;font-size:13px;color:#d6ccc0;margin-top:14px}
a{color:var(--amb)}
.vazio{color:var(--dim);padding:40px 22px}
</style></head><body>
<header><h1>{NOME_APP} <span>V{VERSAO_APP}</span></h1>
<div class="tabs">
<button class="tab" data-f="musicavideo" aria-selected="true">clipes &amp; músicas</button>
<button class="tab" data-f="analisevideo" aria-selected="false">análises de vídeo</button>
<input id="q" placeholder="buscar por título, tag, gênero, look, resumo…">
<span id="conta" class="meta"></span>
</div></header>
<div id="grade"></div>
<dialog id="dlg"><div class="dh"><h2 id="dt"></h2><button id="fecha">fechar</button></div>
<div class="db" id="dc"></div></dialog>
<script>
const E=s=>String(s??"").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
let DADOS={musicavideo:[],analisevideo:[]},aba="musicavideo";
const grade=document.getElementById("grade"),dlg=document.getElementById("dlg");
function alvo(){const q=document.getElementById("q").value.toLowerCase().trim();
 let l=DADOS[aba]||[];
 if(q)l=l.filter(x=>JSON.stringify(x).toLowerCase().includes(q));return l}
// UMA MÚSICA, UM CARD — o mesmo formato da vitrine (V2).
// O Suno entrega duas faixas por pedido e cada uma é uma música diferente:
// mesma letra, mesmo material de vídeo, outra interpretação. Empilhadas dentro
// de um card só, obrigavam a escolher antes de ouvir. Aqui cada uma tem o seu
// card — e as AÇÕES continuam sendo da PRODUÇÃO (a pasta), no modal: é a pasta
// que vai para a lixeira e é a pasta que sobe para a nuvem.
function musicas(l){const fora=[];
 l.forEach(x=>{const fs=(x.faixas||[]);
  if(!fs.length){fora.push({x:x,f:null});return}
  fs.forEach(f=>fora.push({x:x,f:{...f,capa:f.capa||x.capa}}))});
 return fora}
function cardMV(m){const x=m.x,f=m.f;
 const capa=(f&&f.capa)||x.capa;
 const t=capa?`<img class="thumb capa" loading=lazy src="${E(capa)}" alt="">`:`<div class=thumb></div>`;
 const sel=f?`<span class="n${f.aprovada?" ok":""}">v${E(f.n||"?")}${f.aprovada?" ✓":""}</span>`:"";
 // O selo responde a pergunta que o card faz: tem vídeo aqui?
 const vd=f&&f.clipe?`<span class="n clipe">▶ clipe</span>`:"";
 // A NUVEM na capa, não no corpo: "já subiu ou não?" é a pergunta que se faz
 // varrendo a grade com o olho, e uma pill lá embaixo obriga a ler. Os quatro
 // estados aparecem — inclusive o `local`, apagado, porque "não foi" também é
 // resposta e sem ele a ausência de selo se confunde com card sem informação.
 const NV={publicado:["☁ na nuvem","ok","tirar da vitrine"],
           subindo:["☁ subindo…","subindo","subindo agora"],
           aprovado:["☁ na fila","aguarda","cancelar a subida"],
           remover:["☁ sai","sai","voltar a subir"],
           local:["☁ subir","local","subir esta faixa para a vitrine"]};
 // O BOTÃO NA CAPA, e por faixa. Subir era decisão que só existia dentro do
 // modal e valia para a produção inteira — as duas músicas juntas, mesmo
 // quando só uma prestava. Aqui cada card (que já é uma faixa) tem o seu
 // gesto, à vista, sem abrir nada.
 const est=(f?f.nuvem:x.nuvem)||"local";
 const nvi=NV[est]||NV.local;
 const nuv=`<button class="n nv ${nvi[1]} nocard" title="${E(nvi[2])}"
   data-slug="${E(x.slug)}" data-faixa="${E(f&&f.n||"")}" data-em="${E(est)}"
   ${est==="subindo"?"disabled":""}>${E(nvi[0])}</button>`;
 const som=f?`<audio class=nocard controls preload=none src="${E(f.url)}"></audio>`
  :(x.faixa?`<audio class=nocard controls preload=none src="${E(x.faixa)}"></audio>`:"");
 const st=Object.entries(x.estados||{}).map(([k,v])=>
  `<span class="pill ${v==="pronto"?"ok":(v==="erro"?"err":"")}">${E(k)}: ${E(v)}</span>`).join("");
 const dv=x.derivado?`<span class="pill dv">${E(x.derivado)}</span>`:"";
 const id=x.mvd?`<span class="pill mvd">${E(x.mvd)}</span>`:"";
 const nlk=f?(f.likes||0):(x.likes||0);
 const lk=nlk?`<span class="pill" title="curtidas na vitrine">♥ ${E(nlk)}</span>`:"";
 return `<div class=selos>${sel}<span class=dir>${nuv}${vd}</span></div>${t}${som}<div class=b><h3>${dv}${E(x.titulo)}</h3>${id}${lk}
 <div class=meta>${x.origem?"de "+E(x.origem)+" · ":""}${E(x.genero)}${x.bpm?" · "+E(x.bpm)+" bpm":""}${x.tom?" · "+E(x.tom):""}</div>
 <div>${st}</div></div>`}
// Enquanto houver algo subindo, a grade se atualiza sozinha. Sem isto o selo
// `subindo…` ficaria pulsando para sempre numa página que já não é verdade —
// e o dono teria de recarregar para descobrir que terminou.
let relogio=null;
function vigia(){
 const subindo=(DADOS.musicavideo||[]).some(x=>x.nuvem==="subindo"
  ||(x.faixas||[]).some(f=>f.nuvem==="subindo"));
 if(subindo&&!relogio){relogio=setInterval(()=>{
   fetch("__dados.json").then(r=>r.json()).then(d=>{DADOS=d;pinta()}).catch(()=>{})},10000)}
 if(!subindo&&relogio){clearInterval(relogio);relogio=null}}
function MB(b){return b>=1073741824?(b/1073741824).toFixed(1)+" GB":Math.round(b/1048576)+" MB"}
// 24 das 30 análises são do YouTube: a miniatura oficial (img.youtube.com) dá
// a CARA do vídeo analisado no card, sem baixar nada. Quem não é YouTube cai
// no degradê da paleta, que já era o comportamento.
function ytid(u){const m=/(?:youtube\.com\/(?:watch\?v=|embed\/|shorts\/)|youtu\.be\/)([\w-]{6,})/.exec(u||"");
 return m?m[1]:""}
function cardAV(x){const g=(x.paleta||[]).slice(0,5);
 const yid=ytid(x.url);
 const t=x.video?`<video class="thumb nocard" src="${E(x.video)}#t=1" preload=metadata controls></video>`
  :(yid?`<img class=thumb loading=lazy src="https://img.youtube.com/vi/${E(yid)}/hqdefault.jpg" alt="">`
  :`<div class=thumb style="background:linear-gradient(120deg,${g.length?g.map(E).join(","):"#1a1512,#2b241d"})"></div>`);
 const p=(x.paleta||[]).slice(0,6).map(c=>`<i style="background:${E(c)}"></i>`).join("");
 const fonte=x.url?`<a class="pill nocard" href="${E(x.url)}" target=_blank rel=noopener>assistir no canal ↗</a>`:"";
 return `${t}<div class=b><h3>${E(x.titulo)}</h3>
 <div class=meta>${E(x.tipo)}${x.canal?" · "+E(x.canal):""}${x.duracao_s?" · "+E(x.duracao_s)+"s":""}</div>
 ${fonte}
 <div class=pal>${p}</div>
 <div>${(x.tags||[]).slice(0,4).map(g=>`<span class=pill>${E(g)}</span>`).join("")}</div></div>`}
// Um só caminho para o gesto da nuvem, venha ele do card ou do modal: manda o
// slug e (quando houver) a FAIXA, e repinta com o que o servidor respondeu.
function nuvemToggle(b,depois){const em=b.dataset.em;
 const ligar=em==="local"||em==="remover";
 const antes=b.textContent;b.disabled=true;b.textContent="…";
 return fetch("__nuvem",{method:"POST",body:JSON.stringify(
   {slug:b.dataset.slug,faixa:b.dataset.faixa||null,aprovar:ligar})})
  .then(r=>r.json()).then(r=>{if(!r.ok){b.disabled=false;b.textContent="falhou: "+r.erro;return}
   return fetch("__dados.json").then(r=>r.json()).then(d=>{DADOS=d;pinta();
     if(depois)depois(d)})})
  .catch(e=>{b.disabled=false;b.textContent=antes+" (falhou)"})}
function pinta(){const bruto=alvo();
 const l=aba==="musicavideo"?musicas(bruto):bruto;
 grade.innerHTML=l.length?"":`<div class=vazio>nada por aqui ainda.</div>`;
 document.getElementById("conta").textContent=aba==="musicavideo"
  ?`${l.length} músicas · ${bruto.length} produções`:`${l.length} análises`;
 l.forEach((m,i)=>{const d=document.createElement("div");d.className="card";
  d.innerHTML=aba==="musicavideo"?cardMV(m):cardAV(m);
  // O clique abre a PRODUÇÃO, já na aba desta faixa: as ações (lixeira, nuvem)
  // são da pasta, e comparar as duas continua a um clique de distância.
  d.onclick=()=>abre(aba==="musicavideo"?m.x:m, aba==="musicavideo"&&m.f?m.f.n:null);
  // tocar não é abrir: quem clica no player (ou no link da fonte) quer ouvir/ver
  // ali mesmo. Sem isto, arrastar a barra do áudio abre o modal por cima.
  d.querySelectorAll(".nocard").forEach(el=>el.addEventListener("click",ev=>ev.stopPropagation()));
  const nb=d.querySelector("button.nv");
  if(nb)nb.onclick=()=>nuvemToggle(nb);
  grade.appendChild(d)});
 vigia()}
// O mesmo botão nos dois lugares: no modal, ao lado de cada música (uma faixa)
// e no rodapé (todas). `data-faixa` vazio = a produção inteira.
function botaoNuvem(x,f){const N={local:["subir para a nuvem","nuvem"],
  subindo:["subindo agora…","nuvem ok"],
  aprovado:["na fila — cancelar","nuvem ok"],
  publicado:["na vitrine — tirar do ar","nuvem ok"],
  remover:["marcada para sair","nuvem"]};
 const est=(f?f.nuvem:x.nuvem)||"local";const r=N[est]||N.local;
 const rot=f?r[0].replace("para a nuvem","esta faixa"):(est==="local"?"subir as duas faixas":r[0]);
 return `<button class="pill nuvem nocard ${E(est!=="local"?"on":"")}"
   data-slug="${E(x.slug)}" data-faixa="${E(f&&f.n||"")}" data-em="${E(est)}"
   ${est==="subindo"?"disabled":""}>${E(rot)}</button>`}
function abre(x,foco){document.getElementById("dt").textContent=
  (x.mvd?x.mvd+" · ":"")+(x.titulo||x.slug);
 let h="";
 // as capas primeiro, e clicáveis: o card mostra miniatura, aqui se vê inteira
 // e o clique abre o arquivo no tamanho real, em outra aba.
 // as variantes por faixa saem daqui: elas aparecem empilhadas embaixo, cada
 // uma com a sua música e o link do clipe. Repetidas nos dois lugares, a
 // fileira do topo só empurrava o conteúdo para baixo.
 const temV=(x.faixas||[]).some(f=>f.capa);
 const capas=(x.capas||[]).filter(c=>!(temV&&/capa-v\d+\.png/.test(c.url)));
 if(capas.length)h+=`<div class=capas>`+capas.map(c=>
  `<a href="${E(c.url)}" target=_blank rel=noopener title="abrir em tamanho real">
   <img src="${E(c.url)}" alt="${E(c.rotulo)}"><span>${E(c.rotulo)} ↗</span></a>`).join("")+`</div>`;
 const vs=x.versoes||[];
 if(vs.length>1){   // o Suno entrega duas faixas: mesmo video, trilhas diferentes
  h+=`<div class=tabs style="margin-bottom:10px">`+vs.map((v,i)=>
   `<button class=tab data-v="${i}" aria-selected="${v.aprovada}">faixa ${E(v.n)}${v.aprovada?" ✓":""}</button>`).join("")+`</div>`;
  vs.forEach((v,i)=>{h+=`<div class=versao data-v="${i}" hidden>
   <video src="${E(v.clipe)}" controls playsinline preload=none></video>
   <p class=meta>${E(v.clipe.split("/").pop())} · trilha ${E(v.n)}${v.aprovada?" · aprovada (é o clipe.mp4)":""}</p></div>`});
 }
 else if(x.clipe)h+=`<video src="${E(x.clipe)}" controls playsinline></video>`;
 else if(x.video)h+=`<video src="${E(x.video)}" controls playsinline></video>`;
 else if(ytid(x.url))h+=`<div class=embed><iframe src="https://www.youtube-nocookie.com/embed/${E(ytid(x.url))}"
   title="vídeo analisado" allow="accelerometer; clipboard-write; encrypted-media; picture-in-picture"
   allowfullscreen loading=lazy></iframe></div>`;
 else if(x.capa&&!(x.capas||[]).length)h+=`<img src="${E(x.capa)}">`;
 // as faixas SEMPRE, mesmo sem dois clipes montados: é ouvindo as duas que
 // se escolhe qual aprovar.
 if((x.faixas||[]).length)h+=`<div class=faixas>`+x.faixas.map(f=>
  `<div class=versaocapa>${f.capa?`<a href="${E(f.capa)}" target=_blank rel=noopener
     title="abrir em tamanho real"><img src="${E(f.capa)}" alt="capa da versão ${E(f.n)}"></a>`:""}
   <span class=meta>${f.n?`versão ${E(f.n)} · `:""}${E(f.nome)}${f.aprovada?" · aprovada ✓":""}</span>
   <audio src="${E(f.url)}" controls preload=none></audio>
   ${f.clipe?`<a class="pill nocard" href="${E(f.clipe)}" target=_blank rel=noopener>assistir o clipe ↗</a>`:""}
   ${botaoNuvem(x,f)}
   </div>`).join("")+`</div>`;
 else if(x.faixa)h+=`<audio src="${E(x.faixa)}" controls></audio>`;
 if(x.url)h+=`<p><a href="${E(x.url)}" target=_blank rel=noopener>fonte original</a></p>`;
 if(x.resumo)h+=`<p>${E(x.resumo)}</p>`;
 if(x.solicitacao)h+=`<p class=meta>“${E(x.solicitacao)}”</p>`;
 if(x.motores)h+=Object.entries(x.motores).map(([k,v])=>`<span class=pill>${E(k)}: ${E(v)}</span>`).join("");
 if((x.paleta||[]).length)h+=`<div class=pal style="margin-top:10px">`+x.paleta.map(c=>`<i title="${E(c)}" style="background:${E(c)}"></i>`).join("")+`</div>`;
 if((x.tags||[]).length)h+=`<div>`+x.tags.map(g=>`<span class=pill>${E(g)}</span>`).join("")+`</div>`;
 h+=`<p class=meta style="margin-top:12px">${E(x.slug)}${x.custo!==undefined?" · US$ "+E(x.custo):""}${x.bytes?" · "+MB(x.bytes):""}</p>`;
 // SUBIR é decisão, não consequência de ficar pronto: um clique marca, e quem
 // sobe de fato é o `publica-hf`, rodado à mão. O botão diz em que pé está.
 if(x.fonte==="musicavideo"){
  // O botão da PRODUÇÃO continua, agora dizendo o que faz: as duas faixas de
  // uma vez. Escolher uma é o botão que fica ao lado de cada música, acima.
  h+=`<p>${botaoNuvem(x,null)}</p>`;
  h+=`<p><button id=apagar class=perigo data-slug="${E(x.slug)}">mandar para a lixeira</button>
  <span class=meta>não apaga: move para <code>.lixo/</code></span></p>`}
 if((x.docs||[]).length)h+=`<p>`+x.docs.map(d=>
  `<a class="pill nocard" href="${E(d)}" target=_blank rel=noopener>abrir ${E(d.split("?")[0].split("/").pop())} ↗</a>`).join(" ")+`</p>`;
 // O que foi PEDIDO aos provedores, palavra por palavra. Fechado por padrão:
 // é texto longo e só interessa quando o resultado saiu diferente do plano.
 if(x.prompts){const P=x.prompts;let c="";
  if(P.conceito)c+=`<h4>conceito da capa</h4><p>${E(P.conceito)}</p>`;
  if(P.tagline)c+=`<h4>tagline</h4><p>${E(P.tagline)}</p>`;
  if(P.estilo)c+=`<h4>estilo da música (Suno)</h4><p>${E(P.estilo)}</p>`;
  if(P.imagem)c+=`<h4>capa</h4><p>${E(P.imagem)}</p>`;
  if(P.negativo)c+=`<h4>capa · negativo</h4><p>${E(P.negativo)}</p>`;
  if((P.shots||[]).length)c+=`<h4>decupagem · ${P.shots.length} planos</h4>`+P.shots.map(sh=>
   `<div class=shot><span class=meta>${E(sh.n)}. ${E(sh.secao)}${sh.camera?" · "+E(sh.camera):""}</span>
    <p>${E(sh.prompt)}</p>${sh.alt?`<p class=alt>alt: ${E(sh.alt)}</p>`:""}</div>`).join("");
  if(c)h+=`<details class=prompts><summary>ver os prompts que foram para os provedores</summary>
   <div class=corpo>${c}</div></details>`}
 if(x.doc)h+=`<pre>${E(x.doc)}</pre>`;
 document.getElementById("dc").innerHTML=h;
 const dc=document.getElementById("dc"),bts=[...dc.querySelectorAll(".tab")],pns=[...dc.querySelectorAll(".versao")];
 const mostra=i=>{pns.forEach((p,j)=>{p.hidden=j!==i;if(j!==i){const v=p.querySelector("video");if(v)v.pause()}});
  bts.forEach((b,j)=>b.setAttribute("aria-selected",j===i))};
 if(pns.length){bts.forEach((b,i)=>b.onclick=()=>mostra(i));
  // Abrir já na faixa do card clicado. Sem foco (ou faixa que sumiu), vale a
  // aprovada — que era o comportamento de antes.
  const iFoco=foco!=null?vs.findIndex(v=>String(v.n)===String(foco)):-1;
  mostra(iFoco>=0?iFoco:Math.max(0,vs.findIndex(v=>v.aprovada)))}
 dc.querySelectorAll("button.nuvem").forEach(nb=>nb.onclick=()=>nuvemToggle(nb,d=>{
   // reabre no mesmo lugar: o estado mudou e o modal precisa dizer a verdade
   const novo=(d.musicavideo||[]).find(y=>y.slug===nb.dataset.slug);
   if(novo)abre(novo,foco)}));
 const ap=dc.querySelector("#apagar");
 if(ap)ap.onclick=()=>{if(!confirm("Mandar "+ap.dataset.slug+" para a lixeira?"))return;
  ap.disabled=true;ap.textContent="movendo…";
  fetch("__apagar",{method:"POST",body:JSON.stringify({slug:ap.dataset.slug})})
   .then(r=>r.json()).then(r=>{if(!r.ok){ap.disabled=false;ap.textContent="falhou: "+r.erro;return}
    dlg.close();return fetch("__dados.json").then(r=>r.json()).then(d=>{DADOS=d;pinta()})})
   .catch(e=>{ap.disabled=false;ap.textContent="falhou: "+e})};
 dlg.showModal()}
document.getElementById("fecha").onclick=()=>{document.getElementById("dc").innerHTML="";dlg.close()};
dlg.addEventListener("close",()=>document.getElementById("dc").innerHTML="");
document.querySelectorAll(".tab").forEach(b=>b.onclick=()=>{
 aba=b.dataset.f;document.querySelectorAll(".tab").forEach(o=>o.setAttribute("aria-selected",o===b));pinta()});
document.getElementById("q").oninput=pinta;
fetch("__dados.json").then(r=>r.json()).then(d=>{DADOS=d;pinta()});
</script></body></html>"""


def _ip_da_rede() -> str:
    """O IP que o resto da rede enxerga. `gethostname` costuma cair no loopback
    (é o que o /etc/hosts diz), e aí o link impresso não abre em lugar nenhum."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))          # não manda pacote: só resolve a rota
        return s.getsockname()[0]
    except OSError:
        return socket.gethostbyname(socket.gethostname())
    finally:
        s.close()


class Handler(SimpleHTTPRequestHandler):
    def guess_type(self, path):
        """`.md` como texto puro, para ABRIR na aba.

        O tipo registrado é `text/markdown`, e com ele o navegador baixa o
        arquivo em vez de mostrar — o link do PACOTE/PLANO virava um download
        que ninguém pediu.
        """
        if str(path).lower().endswith(".md"):
            return "text/plain; charset=utf-8"
        return super().guess_type(path)

    def do_GET(self):  # noqa: N802
        if self.path in ("/", "/index.html"):
            pagina = PAGINA.replace("{NOME_APP}", NOME).replace("{VERSAO_APP}", VERSAO)
            return self._envia(pagina.encode("utf-8"), "text/html; charset=utf-8")
        if self.path.startswith("/__dados.json"):
            dados = json.dumps(coletar(Path(self.directory)), ensure_ascii=False)
            return self._envia(dados.encode("utf-8"), "application/json; charset=utf-8")
        return super().do_GET()

    def do_POST(self):  # noqa: N802
        """Só uma rota, e ela MOVE para a lixeira — nunca apaga de verdade."""
        if self.path == "/__nuvem":
            try:
                n = int(self.headers.get("Content-Length") or 0)
                p = json.loads(self.rfile.read(n) or b"{}")
                w = Path(self.directory) / "musicavideo" / (p.get("slug") or "")
                if w.parent != Path(self.directory) / "musicavideo" or not w.is_dir():
                    raise ValueError(f"caminho fora do acervo: {p.get('slug')}")
                ligar = bool(p.get("aprovar", True))
                # `faixa` vazia = a produção inteira, que é o gesto antigo e
                # continua valendo (o botão do rodapé do modal).
                fx = str(p.get("faixa") or "").strip() or None
                estado = aprovar_nuvem(w, ligar, faixa=fx)
                # Aprovar deixa de ser só marcar: o botão diz "subir para a
                # nuvem" e agora sobe. Sem isto o card ficava em `aprovado` para
                # sempre — o cron que fechava esse ciclo foi retirado na v1.3.0.
                if ligar and estado == "aprovado":
                    subida.iniciar(w.name, outdir=w.parent)
                    estado = "subindo"
            except (ValueError, OSError, KeyError) as e:
                corpo = json.dumps({"ok": False, "erro": str(e)})
                return self._envia(corpo.encode("utf-8"), "application/json; charset=utf-8")
            corpo = json.dumps({"ok": True, "nuvem": estado})
            return self._envia(corpo.encode("utf-8"), "application/json; charset=utf-8")
        if self.path != "/__apagar":
            return self.send_error(404)
        try:
            n = int(self.headers.get("Content-Length") or 0)
            slug = json.loads(self.rfile.read(n) or b"{}").get("slug", "")
            destino = para_lixeira(Path(self.directory) / "musicavideo", slug)
        except (ValueError, OSError) as e:
            corpo = json.dumps({"ok": False, "erro": str(e)})
            return self._envia(corpo.encode("utf-8"), "application/json; charset=utf-8")
        corpo = json.dumps({"ok": True, "lixeira": destino.name})
        return self._envia(corpo.encode("utf-8"), "application/json; charset=utf-8")

    def send_head(self):
        """Range mínimo: sem isso o navegador não consegue arrastar o vídeo."""
        faixa = self.headers.get("Range", "")
        if not faixa.startswith("bytes="):
            return super().send_head()
        caminho = self.translate_path(self.path)
        if not os.path.isfile(caminho):
            return super().send_head()
        tam = os.path.getsize(caminho)
        ini, _, fim = faixa[6:].partition("-")
        try:
            ini = int(ini) if ini else 0
            fim = int(fim) if fim else tam - 1
        except ValueError:
            return super().send_head()
        ini, fim = max(0, ini), min(fim, tam - 1)
        if ini > fim:
            self.send_error(416)
            return None
        f = open(caminho, "rb")
        f.seek(ini)
        self.send_response(206)
        self.send_header("Content-Type", self.guess_type(caminho))
        self.send_header("Content-Range", f"bytes {ini}-{fim}/{tam}")
        self.send_header("Content-Length", str(fim - ini + 1))
        self.send_header("Accept-Ranges", "bytes")
        self.end_headers()
        self._resto = fim - ini + 1
        return f

    def copyfile(self, source, outputfile):
        limite = getattr(self, "_resto", None)
        if limite is None:
            return super().copyfile(source, outputfile)
        self._resto = None
        while limite > 0:
            bloco = source.read(min(64 * 1024, limite))
            if not bloco:
                break
            outputfile.write(bloco)
            limite -= len(bloco)

    def _envia(self, corpo: bytes, tipo: str):
        self.send_response(200)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(corpo)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(corpo)

    def handle_one_request(self):
        """Fechar o modal aborta o download do vídeo — isso é o navegador
        trabalhando, não erro. Sem isto o terminal vira um muro de traceback."""
        try:
            super().handle_one_request()
        except (BrokenPipeError, ConnectionResetError):
            self.close_connection = True

    def log_message(self, *a):  # silêncio: o terminal é do usuário
        pass


def cmd_painel(args: list[str]) -> int:
    porta, host = int(os.environ.get("MUSICAVIDEO_PAINEL_PORTA", 5400)), "127.0.0.1"
    resto = []
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--lan":
            host = "0.0.0.0"
        elif a == "--porta":
            i += 1
            porta = int(args[i])
        else:
            resto.append(a)
        i += 1
    if resto:
        try:
            porta = int(resto[0])
        except ValueError:
            print(f"não entendi '{resto[0]}' — uso: painel [--porta N] [--lan]", file=sys.stderr)
            return 1

    raiz = raiz_output()
    if not raiz.is_dir():
        print(f"não achei a pasta de acervo: {raiz}", file=sys.stderr)
        return 1
    d = coletar(raiz)
    srv, pedida = None, porta
    for tentativa in range(porta, porta + 12):     # porta ocupada nao e motivo pra falhar
        try:
            srv = ThreadingHTTPServer((host, tentativa), partial(Handler, directory=str(raiz)))
            porta = tentativa
            break
        except OSError:
            continue
    if srv is None:
        print(f"portas {pedida}..{pedida + 11} ocupadas — use --porta N", file=sys.stderr)
        return 1
    if porta != pedida:
        print(f"{pedida} ocupada — subindo na {porta}")
    visivel = host if host != "0.0.0.0" else _ip_da_rede()
    print(f"painel em http://{visivel}:{porta}   "
          f"({len(d['musicavideo'])} pacotes · {len(d['analisevideo'])} análises)")
    if host == "0.0.0.0":
        print("LAN ligada — qualquer um na rede vê o acervo inteiro.")
    print("ctrl-c para parar.")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\npainel parado.")
    finally:
        srv.server_close()
    return 0

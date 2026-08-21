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
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def raiz_output() -> Path:
    return Path(os.environ.get("INEMA_OUTPUT",
                str(Path.home() / "projetos/output")))


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


def _texto(p: Path, limite: int = 40000) -> str | None:
    if not p.exists():
        return None
    try:
        return p.read_text(encoding="utf-8")[:limite]
    except OSError:
        return None


def coletar(raiz: Path) -> dict:
    mv = []
    base = raiz / "musicavideo"
    for l in _linhas(base / "index.jsonl"):
        w = base / l.get("slug", "")
        if not w.is_dir():
            continue
        faixa = _faixa(w)
        mv.append({
            "fonte": "musicavideo",
            "slug": l.get("slug"),
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
            "capa": f"musicavideo/{l['slug']}/capa.png" if (w / "capa.png").exists() else None,
            "clipe": f"musicavideo/{l['slug']}/clipe.mp4" if (w / "clipe.mp4").exists() else None,
            "faixa": f"musicavideo/{l['slug']}/{faixa}" if faixa else None,
            "doc": _texto(w / "PACOTE.md") or _texto(w / "PLANO.md"),
        })

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
<title>Painel INEMA — clipes e análises</title><style>
:root{--bg:#0d0b09;--card:#171310;--linha:#2b241d;--txt:#ece5da;--dim:#a2968a;--amb:#f0a92b}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--txt);
font:15px/1.5 system-ui,-apple-system,Segoe UI,sans-serif}
header{padding:20px 22px 0;position:sticky;top:0;background:var(--bg);z-index:5}
h1{margin:0 0 12px;font-size:19px;letter-spacing:.5px}
h1 span{color:var(--amb)}
.tabs{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
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
.card .b{padding:11px 13px}
.card h3{margin:0 0 5px;font-size:15px;line-height:1.3}
.meta{color:var(--dim);font-size:12.5px}
.pal{display:flex;gap:4px;margin-top:7px}
.pal i{width:16px;height:16px;border-radius:4px;display:block}
.pill{display:inline-block;font-size:11px;border:1px solid var(--linha);border-radius:99px;
padding:1px 8px;margin:5px 5px 0 0;color:var(--dim)}
.pill.ok{color:#7fd18a;border-color:#2f5133}.pill.err{color:#e58b7b;border-color:#5a2f28}
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
pre{white-space:pre-wrap;word-wrap:break-word;background:#0a0806;border:1px solid var(--linha);
border-radius:10px;padding:13px;font-size:13px;color:#d6ccc0;margin-top:14px}
a{color:var(--amb)}
.vazio{color:var(--dim);padding:40px 22px}
</style></head><body>
<header><h1>painel <span>INEMA</span> — o que já foi feito</h1>
<div class="tabs">
<button class="tab" data-f="musicavideo" aria-selected="true">clipes &amp; músicas</button>
<button class="tab" data-f="analisevideo" aria-selected="false">análises de vídeo</button>
<input id="q" placeholder="buscar por título, tag, gênero, look, resumo…">
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
function cardMV(x){const t=x.capa?`<img class=thumb loading=lazy src="${E(x.capa)}">`:`<div class=thumb></div>`;
 const st=Object.entries(x.estados||{}).map(([k,v])=>
  `<span class="pill ${v==="pronto"?"ok":(v==="erro"?"err":"")}">${E(k)}: ${E(v)}</span>`).join("");
 return `${t}<div class=b><h3>${E(x.titulo)}</h3>
 <div class=meta>${E(x.genero)}${x.bpm?" · "+E(x.bpm)+" bpm":""}${x.tom?" · "+E(x.tom):""}</div>
 <div>${st}</div></div>`}
function cardAV(x){const g=(x.paleta||[]).slice(0,5);
 const t=x.video?`<video class=thumb src="${E(x.video)}#t=1" preload=metadata muted></video>`
  :`<div class=thumb style="background:linear-gradient(120deg,${g.length?g.map(E).join(","):"#1a1512,#2b241d"})"></div>`;
 const p=(x.paleta||[]).slice(0,6).map(c=>`<i style="background:${E(c)}"></i>`).join("");
 return `${t}<div class=b><h3>${E(x.titulo)}</h3>
 <div class=meta>${E(x.tipo)}${x.canal?" · "+E(x.canal):""}${x.duracao_s?" · "+E(x.duracao_s)+"s":""}</div>
 <div class=pal>${p}</div>
 <div>${(x.tags||[]).slice(0,4).map(g=>`<span class=pill>${E(g)}</span>`).join("")}</div></div>`}
function pinta(){const l=alvo();
 grade.innerHTML=l.length?"":`<div class=vazio>nada por aqui ainda.</div>`;
 l.forEach((x,i)=>{const d=document.createElement("div");d.className="card";
  d.innerHTML=aba==="musicavideo"?cardMV(x):cardAV(x);d.onclick=()=>abre(x);grade.appendChild(d)})}
function abre(x){document.getElementById("dt").textContent=x.titulo||x.slug;
 let h="";
 if(x.clipe)h+=`<video src="${E(x.clipe)}" controls playsinline></video>`;
 else if(x.video)h+=`<video src="${E(x.video)}" controls playsinline></video>`;
 else if(x.capa)h+=`<img src="${E(x.capa)}">`;
 if(x.faixa)h+=`<audio src="${E(x.faixa)}" controls></audio>`;
 if(x.url)h+=`<p><a href="${E(x.url)}" target=_blank rel=noopener>fonte original</a></p>`;
 if(x.resumo)h+=`<p>${E(x.resumo)}</p>`;
 if(x.solicitacao)h+=`<p class=meta>“${E(x.solicitacao)}”</p>`;
 if(x.motores)h+=Object.entries(x.motores).map(([k,v])=>`<span class=pill>${E(k)}: ${E(v)}</span>`).join("");
 if((x.paleta||[]).length)h+=`<div class=pal style="margin-top:10px">`+x.paleta.map(c=>`<i title="${E(c)}" style="background:${E(c)}"></i>`).join("")+`</div>`;
 if((x.tags||[]).length)h+=`<div>`+x.tags.map(g=>`<span class=pill>${E(g)}</span>`).join("")+`</div>`;
 h+=`<p class=meta style="margin-top:12px">${E(x.slug)}${x.custo!==undefined?" · US$ "+E(x.custo):""}</p>`;
 if(x.doc)h+=`<pre>${E(x.doc)}</pre>`;
 document.getElementById("dc").innerHTML=h;dlg.showModal()}
document.getElementById("fecha").onclick=()=>{document.getElementById("dc").innerHTML="";dlg.close()};
dlg.addEventListener("close",()=>document.getElementById("dc").innerHTML="");
document.querySelectorAll(".tab").forEach(b=>b.onclick=()=>{
 aba=b.dataset.f;document.querySelectorAll(".tab").forEach(o=>o.setAttribute("aria-selected",o===b));pinta()});
document.getElementById("q").oninput=pinta;
fetch("__dados.json").then(r=>r.json()).then(d=>{DADOS=d;pinta()});
</script></body></html>"""


class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        if self.path in ("/", "/index.html"):
            return self._envia(PAGINA.encode("utf-8"), "text/html; charset=utf-8")
        if self.path.startswith("/__dados.json"):
            dados = json.dumps(coletar(Path(self.directory)), ensure_ascii=False)
            return self._envia(dados.encode("utf-8"), "application/json; charset=utf-8")
        return super().do_GET()

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

    def log_message(self, *a):  # silêncio: o terminal é do usuário
        pass


def cmd_painel(args: list[str]) -> int:
    porta, host = 5300, "127.0.0.1"
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
    srv = ThreadingHTTPServer((host, porta), partial(Handler, directory=str(raiz)))
    visivel = host if host != "0.0.0.0" else (socket.gethostbyname(socket.gethostname()))
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

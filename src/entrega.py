"""Fase 3: PACOTE.md + envio opcional no Telegram (desligado por default)."""
import json
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


def enviar_telegram(workdir: Path, estado: dict, plano: dict, http=None) -> None:
    if not estado.get("telegram"):
        return                                   # desligado por default
    token = ler_env_chave(["TELEGRAM_BOT_TOKEN"])
    chat = ler_env_chave(["TELEGRAM_CHAT_ID", "ALLOWED_CHAT_ID"])
    if not (token and chat):
        print("telegram: token/chat_id não encontrados nos .env autorizados — pulando envio")
        return
    base = f"https://api.telegram.org/bot{token}"
    envios = [("faixa.mp3", "sendAudio", "audio"), ("capa.png", "sendPhoto", "photo"),
              ("clipe.mp4", "sendVideo", "video")]
    for nome, metodo, campo in envios:
        arq = Path(workdir) / nome
        if arq.exists():
            _post_multipart(f"{base}/{metodo}",
                            {"chat_id": chat, "caption": plano["titulo"]}, campo, arq)


def entregar(outdir: Path, slug: str) -> Path:
    outdir = Path(outdir)
    w = outdir / slug
    pacote = gerar_pacote(outdir, slug)
    plano = json.loads((w / "plano.json").read_text(encoding="utf-8"))
    estado = carregar_estado(w)
    enviar_telegram(w, estado, plano)
    if all(estado["partes"][p]["estado"] == "pronto" for p in PARTES):
        estado["fase"] = "entregue"
        registrar(estado, "entrega", detalhe="pacote completo")
    salvar_estado(w, estado)
    gravar_linha(outdir, linha_de(plano, estado))
    print(f"pacote em {pacote}")
    return pacote

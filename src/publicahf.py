"""publica-hf: leva o acervo aprovado para o Hugging Face e escreve o manifesto.

O painel local só existe onde o acervo existe — os `<video>` tocam porque um
servidor Python está enraizado na pasta de saída. Este comando é a outra metade:
os arquivos vão para um dataset do HF (que serve range request, medido) e os
metadados viram um `manifest.json` que a vitrine (`musicavideo-pub`) lê.

Duas regras que economizam gigabytes e evitam divergência:

- **Só os finais.** `raw/` inteiro fica na máquina: 1209 dos 1365 mp4 do acervo
  são shots intermediários. E o `clipe.mp4` não sobe quando existe versionado —
  28 dos 29 são cópia byte a byte de um `clipe-N.mp4`, e o manifesto guarda qual
  é a aprovada, que era a única informação que a cópia carregava.
- **Um coletor só.** O manifesto sai do mesmo `painel.coletar()` que a tela
  local usa, com as URLs reescritas para o HF. Dois coletores divergiriam, e
  ninguém saberia qual dos painéis está certo.
"""
import json
import os
import re
from pathlib import Path

from src import painel
from src.mvd import resolver
from src.nuvem import a_remover, ler as ler_nuvem, marcar_publicado, marcar_removido, pendentes

# O namespace do HF é o nome EXATO da conta: `Inematds`, com maiúscula (o
# GitHub é `inematds`, minúsculo — os dois não são a mesma string). Com a grafia
# errada o `create_repo` volta 403 "you don't have the rights", que parece falta
# de permissão no token e é só o nome trocado. Medido em 2026-08-27.
REPO_PADRAO = "Inematds/musicavideo-acervo"
BASE_HF = "https://huggingface.co/datasets/{repo}/resolve/main/"

# O que a vitrine mostra, e nada além. Ordem importa só para o log.
PADROES = ("capa.png", "capa-v*.png", "capa-crua.png", "publicacao/capa-yt.jpg",
           "faixa-*.mp3", "clipe-*.mp4", "plano.json", "PACOTE.md", "PLANO.md")


def token() -> str | None:
    """O HF_TOKEN sai do ambiente ou dos .env do ecossistema, em runtime.

    Nunca é copiado para dentro deste repo: a chave mora onde já morava.
    """
    for k in ("HF_TOKEN", "HUGGINGFACE_TOKEN"):
        if (os.environ.get(k) or "").strip():
            return os.environ[k].strip()
    for env in (Path.home() / "projetos/wifi/.env", Path.home() / "projetos/inemavox/.env"):
        try:
            for linha in env.read_text(encoding="utf-8").splitlines():
                nome, _, valor = linha.strip().partition("=")
                if nome.strip() in ("HF_TOKEN", "LIBPROMPTVI_HF_TOKEN") and valor.strip():
                    return valor.strip().strip('"').strip("'")
        except OSError:
            continue
    return None


def arquivos_de(w: Path) -> list[Path]:
    """Os finais desta produção, já sem o que é cópia ou intermediário."""
    achados: list[Path] = []
    for padrao in PADROES:
        achados += sorted(w.glob(padrao))
    versionados = [f for f in achados if re.fullmatch(r"clipe-\d+\.mp4", f.name)]
    if not versionados and (w / "clipe.mp4").exists():
        # Produção antiga, sem clipe por versão: aí o `clipe.mp4` É o final.
        achados.append(w / "clipe.mp4")
    return [f for f in achados if f.is_file()]


def _url_hf(repo: str, slug: str, rel: str) -> str:
    return BASE_HF.format(repo=repo) + f"{slug}/{rel}"


def _reescreve(valor, slug: str, repo: str):
    """`musicavideo/slug/capa.png?v=123` -> a URL do HF.

    O prefixo é `musicavideo/` porque o painel local serve a partir da PASTA DE
    SAÍDA, um nível acima do acervo — as URLs dele nascem com o nome do acervo
    na frente. Reescrever esperando só o slug deixa passar a URL local intacta,
    e o navegador da vitrine tenta buscar um caminho relativo que não existe
    (medido em 2026-08-27: as capas vieram todas quebradas).

    Recursivo: o dicionário do coletor tem URL em vários níveis (capa, capas,
    faixas, versões, docs).
    """
    if isinstance(valor, str) and valor.startswith(f"musicavideo/{slug}/"):
        rel = valor[len(f"musicavideo/{slug}/"):].split("?")[0]
        return _url_hf(repo, slug, rel)
    if isinstance(valor, list):
        return [_reescreve(v, slug, repo) for v in valor]
    if isinstance(valor, dict):
        return {k: _reescreve(v, slug, repo) for k, v in valor.items()}
    return valor


def manifesto(outdir: Path, repo: str, slugs: list[str]) -> dict:
    """O dicionário do painel, com URLs do HF e só o que está publicado.

    A aba de análises entra como TEXTO: nada de `fonte.mp4` — é vídeo de
    terceiros baixado do YouTube, e re-hospedar seria redistribuição. O vídeo
    analisado aparece pelo embed oficial, que a vitrine monta a partir da `url`.
    """
    dados = painel.coletar(outdir.parent)
    mv = []
    for x in dados.get("musicavideo", []):
        if x.get("slug") not in slugs:
            continue
        item = _reescreve(x, x["slug"], repo)
        item["clipe"] = None            # a cópia não sobe; quem manda é `faixas[].clipe`
        item["doc"] = None              # o texto vem do PACOTE/PLANO no próprio HF
        mv.append(item)
    av = []
    for a in dados.get("analisevideo", []):
        a = dict(a)
        a["video"] = None               # NUNCA o fonte.mp4
        av.append(a)
    return {"schema": "musicavideo-pub/1", "repo": repo,
            "musicavideo": mv, "analisevideo": av}


def publicar(outdir: Path, repo: str = REPO_PADRAO, alvos: list[str] | None = None,
             dry: bool = False, so_manifesto: bool = False, log=print) -> dict:
    """Sobe o que está aprovado e grava o manifesto. Devolve o resumo.

    `so_manifesto` reescreve só o `manifest.json`: metadado errado (uma URL, um
    título) não pode custar o reenvio de gigabytes de vídeo que não mudaram.
    """
    if so_manifesto:
        alvos, dry = [], False
    slugs = [] if so_manifesto else [s for s in (
        [resolver(outdir, a) for a in alvos] if alvos else pendentes(outdir)) if s]
    remover = a_remover(outdir) if not alvos else []
    plano = {s: arquivos_de(outdir / s) for s in slugs}
    bytes_totais = sum(f.stat().st_size for fs in plano.values() for f in fs)
    for s in slugs:
        log(f"  {s}: {len(plano[s])} arquivos")
    log(f"{len(slugs)} produções, {len(sum(plano.values(), []))} arquivos, "
        f"{bytes_totais / 1073741824:.2f} GB"
        + (f" · a remover: {', '.join(remover)}" if remover else ""))
    if dry:
        return {"dry": True, "slugs": slugs, "bytes": bytes_totais, "remover": remover}

    from huggingface_hub import HfApi
    tk = token()
    if not tk:
        raise RuntimeError("sem HF_TOKEN — nem no ambiente nem nos .env conhecidos")
    api = HfApi(token=tk)
    api.create_repo(repo, repo_type="dataset", exist_ok=True, private=False)

    for s in slugs:
        for f in plano[s]:
            api.upload_file(path_or_fileobj=str(f), path_in_repo=f"{s}/{f.relative_to(outdir / s)}",
                            repo_id=repo, repo_type="dataset")
        marcar_publicado(outdir / s)
        log(f"  ✓ {s}")
    for s in remover:
        try:
            api.delete_folder(path_in_repo=s, repo_id=repo, repo_type="dataset")
        except Exception as e:                       # pasta que já não existe lá
            log(f"  (remoção de {s}: {e})")
        marcar_removido(outdir / s)
        log(f"  ✗ {s} retirado")

    publicados = [w.name for w in sorted(p for p in outdir.iterdir() if p.is_dir())
                  if ler_nuvem(w).get("publicado_em")]
    man = manifesto(outdir, repo, publicados)
    destino = outdir / "manifest.json"
    destino.write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
    api.upload_file(path_or_fileobj=str(destino), path_in_repo="manifest.json",
                    repo_id=repo, repo_type="dataset")
    log(f"manifest.json: {len(man['musicavideo'])} produções, "
        f"{len(man['analisevideo'])} análises")
    return {"slugs": slugs, "removidos": remover, "bytes": bytes_totais,
            "manifesto": len(man["musicavideo"])}

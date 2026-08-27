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

# MÍDIA, e nada além. O HF é onde ficam os arquivos pesados, que o navegador
# busca direto (e que precisam de range request para o vídeo navegar).
#
# TEXTO NÃO VEM PARA CÁ. Letra, prompts, decupagem, PACOTE e PLANO viajam DENTRO
# do manifesto, que vive no repo do app: são quilobytes, são o que a vitrine
# renderiza como HTML, e mantê-los aqui obrigaria a vitrine a fazer uma segunda
# viagem de rede para mostrar o que já podia vir pronto na página.
PADROES = ("capa.png", "capa-v*.png", "capa-crua.png", "publicacao/capa-yt.jpg",
           "faixa-*.mp3", "clipe-*.mp4")


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
        item["docs"] = []               # não há .md no HF para linkar: o texto vem aqui
        mv.append(item)                 # `doc` e `prompts` seguem inteiros, como texto
    av = []
    for a in dados.get("analisevideo", []):
        a = dict(a)
        a["video"] = None               # NUNCA o fonte.mp4
        av.append(a)
    return {"schema": "musicavideo-pub/1", "repo": repo,
            "musicavideo": mv, "analisevideo": av}


def baixar_likes(outdir: Path, base_url: str | None = None) -> dict:
    """Traz as contagens de like da vitrine para o acervo local.

    É a metade que fecha o ciclo. Sem isto o único sinal de público que o
    projeto tem morreria na nuvem: quem produz continuaria escolhendo no escuro,
    que é exatamente o que a vitrine existe para resolver.

    Grava `likes.json` na pasta de saída — o painel local lê de lá. Falhar aqui
    não é erro de acervo: vitrine fora do ar, `likes.json` velho, e nada mais.
    """
    import urllib.request
    base = (base_url or os.environ.get("MUSICAVIDEO_PUB_URL")
            or "https://musicavideo-pub.vercel.app").rstrip("/")
    if not base:
        return {}
    from src.mvd import usados
    from src.mvd import formatar
    saida = {}
    for slug, n in usados(outdir).items():
        mvd = formatar(n)
        try:
            with urllib.request.urlopen(f"{base}/api/like?mvd={mvd}", timeout=15) as r:
                saida[mvd] = int(json.load(r).get("n") or 0)
        except Exception:
            continue
    if saida:
        (outdir / "likes.json").write_text(json.dumps(saida, indent=1), encoding="utf-8")
    return saida


APP = Path.home() / "projetos/musicavideo-pub"


def gravar_no_app(man: dict, app: Path | None = None, log=print) -> Path | None:
    """O manifesto vive no REPO DO APP, não no HF.

    Ele é texto e é o que a vitrine renderiza: no repo, ele viaja no build, sai
    junto com o deploy e não exige uma viagem de rede por visita. No HF ele
    obrigaria a vitrine a buscar antes de desenhar — e a página ficaria refém do
    HF estar de pé para mostrar até o próprio título.
    """
    app = app or APP
    if not (app / "package.json").exists():
        log(f"app não encontrado em {app} — manifesto ficou só no acervo")
        return None
    alvo = app / "data" / "manifest.json"
    alvo.parent.mkdir(parents=True, exist_ok=True)
    alvo.write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
    kb = alvo.stat().st_size / 1024
    log(f"manifesto no app: {alvo} ({kb:.0f} KB)")
    return alvo


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
    gravar_no_app(man, log=log)
    log(f"manifest.json: {len(man['musicavideo'])} produções, "
        f"{len(man['analisevideo'])} análises")
    return {"slugs": slugs, "removidos": remover, "bytes": bytes_totais,
            "manifesto": len(man["musicavideo"])}

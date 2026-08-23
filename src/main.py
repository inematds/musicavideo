"""Dispatch dos subcomandos do musicavideo. Exit codes: 0 ok; 1 uso/validação;
2 parte terminou em erro; 3 teto estourado."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def out_dir() -> Path:
    return Path(os.environ.get("MUSICAVIDEO_OUT",
                str(Path.home() / "projetos/output/musicavideo")))


USO = """uso: musicavideo <comando> ...
  plano "<solicitação>" [slug] [--pesquisa] [--estilo X] [--idioma X] [--letra arq [--letra-final]]
        [--faixa-pronta arq.mp3] [--motor parte=prov:modelo] [--ritmo auto|calmo|padrao|variado|dinamico] [--forca]
  ver <slug> [musica|capa|clipe]
  ajusta <slug> <parte> "<instrução>" [--refaz]
  ok <slug> <parte>
  faz <slug> [parte] [--sim] [--telegram] [--sem-revisao] [--motor parte=prov:modelo]
  revisa  <slug> [parte]              # o que está esperando você olhar
  aprova  <slug> <parte> [--faixa N]  # fecha a parte
  reprova <slug> <parte> ["4,17,23"]  # descarta e devolve pro faz
  tudo "<solicitação>" [--teto N] [demais flags de plano] [--sim] [--telegram]
  monta <slug> [--completo]      # casa o clipe com CADA faixa (não gasta)
  curto <slug> [--inicio N]      # Short 9:16 de 12s do núcleo da faixa (não gasta)
  arte  <slug> ["<título>"] [--versao N] [--tagline "..."]   # recompõe (não gasta)
  pacote <slug>                  # gera o PACOTE.md sob demanda
  custo <slug> | lista [N] | busca "<termo>" | reindex
  painel [--porta N] [--lan]     # navegador: acervo do musicavideo + analisevideo"""

COMANDOS = {}   # nome -> callable(argv) -> int; preenchido pelas próximas tasks


def _cmd_lista(args):
    from src.indexer import lista
    for l in lista(out_dir(), int(args[0]) if args else 10):
        print(f"{l['slug']:40s} {l['estados']}  US${l['custo_gasto_usd']}")
    return 0


def _cmd_busca(args):
    if not args:
        print('uso: busca "<termo>"', file=sys.stderr)
        return 1
    from src.indexer import busca
    for l in busca(out_dir(), args[0]):
        print(f"{l['slug']:40s} {l['titulo']}")
    return 0


def _cmd_painel(args):
    from src.painel import cmd_painel
    return cmd_painel(args)


def _cmd_reindex(args):
    from src.indexer import reindex
    print(f"reindexadas: {reindex(out_dir())} linhas")
    return 0


def _cmd_plano(args):
    from src.planner import cmd_plano
    return cmd_plano(args)


def _cmd_ver(args):
    from src.planner import cmd_ver
    return cmd_ver(args)


def _cmd_ok(args):
    from src.planner import cmd_ok
    return cmd_ok(args)


def _cmd_ajusta(args):
    from src.planner import cmd_ajusta
    return cmd_ajusta(args)


def _cmd_faz(args):
    from src.executor import cmd_faz
    return cmd_faz(args)


def _cmd_monta(args):
    from src.executor import cmd_monta
    return cmd_monta(args)


def _cmd_revisa(args):
    from src.executor import cmd_revisa
    return cmd_revisa(args)


def _cmd_aprova(args):
    from src.executor import cmd_aprova
    return cmd_aprova(args)


def _cmd_reprova(args):
    from src.executor import cmd_reprova
    return cmd_reprova(args)


def _cmd_pacote(args):
    from src.executor import cmd_pacote
    return cmd_pacote(args)


def _cmd_custo(args):
    from src.executor import cmd_custo
    return cmd_custo(args)


def _cmd_tudo(args):
    """Sem portão: planeja, aprova as 3 partes e executa respeitando o teto."""
    import src.planner as pl
    from src.executor import faz
    from src.estado import carregar_estado, salvar_estado
    if not args:
        print('uso: tudo "<solicitação>" [--teto N] [--sim] [--telegram] [--estilo X] '
              '[--letra arq [--letra-final]] [--pesquisa]', file=sys.stderr)
        return 1
    livres, opts = pl._parse_opts(args)
    if not livres:
        print('uso: tudo "<solicitação>" [flags]', file=sys.stderr)
        return 1
    solicitacao = livres[0]
    if opts.get("pesquisa"):
        from src.pesquisa import pesquisar
        opts["pesquisa_md"] = pesquisar(solicitacao)
    try:
        plano = pl.gerar_plano(solicitacao, livres[1] if len(livres) > 1 else None,
                               opts, out_dir())
    except (ValueError, RuntimeError) as e:
        print(f"erro: {e}", file=sys.stderr)
        return 1
    slug = plano["slug"]
    for parte in ("musica", "capa", "clipe"):
        pl.aprovar_parte(out_dir(), slug, parte)
    if opts.get("teto") is not None:
        w = out_dir() / slug
        e = carregar_estado(w)
        e["teto_usd"] = float(opts["teto"])
        salvar_estado(w, e)
    # `tudo` é o modo sem portão: nem o do plano, nem o do artefato.
    # Ainda assim respeita a ordem — música primeiro, depois capa e clipe.
    rc = faz(out_dir(), slug, ["musica"], sim=bool(opts.get("sim")),
             telegram=bool(opts.get("telegram")), motor_override=opts.get("motor"),
             sem_revisao=True)
    if rc != 0:
        return rc
    return faz(out_dir(), slug, ["capa", "clipe"], sim=bool(opts.get("sim")),
               telegram=bool(opts.get("telegram")), motor_override=opts.get("motor"),
               sem_revisao=True)


def _cmd_arte(args):
    """Recompõe o título sobre a capa CRUA. Não chama provedor, não gasta nada —
    é o comando pra ajustar a arte sem pagar a imagem de novo."""
    import json
    from src.arte import compor, ArteError
    from src.planner import _parse_opts
    if not args:
        print('uso: arte <slug> ["<título>"] [--versao N] [--tagline "..."]', file=sys.stderr)
        return 1
    livres, opts = _parse_opts(args)
    w = out_dir() / livres[0]
    plano_arq = w / "plano.json"
    if not plano_arq.exists():
        print(f"erro: slug '{livres[0]}' não encontrado em {out_dir()}", file=sys.stderr)
        return 1
    plano = json.loads(plano_arq.read_text(encoding="utf-8"))
    bruta = w / "raw" / "capa-crua.png"
    if not bruta.exists():
        print("erro: não há capa crua (raw/capa-crua.png) — gere a capa antes "
              "com `musicavideo faz <slug> capa`", file=sys.stderr)
        return 1
    titulo = livres[1] if len(livres) > 1 else plano.get("titulo", "")
    # A TAGLINE vem do plano quando existe (o planejador escreve), e a linha de
    # comando vence — é assim que se experimenta sem replanejar.
    tagline = opts.get("tagline") or plano["capa"].get("tagline", "")
    versao = int(opts["versao"]) if str(opts.get("versao", "")).isdigit() else None
    # UMA capa por versão quando o selo é pedido: as duas faixas do Suno viram
    # dois clipes, e capa sem marca faz escolher no chute.
    saida = w / (f"capa-v{versao}.png" if versao else "capa.png")
    try:
        destino = compor(bruta, titulo, plano["capa"].get("paleta"),
                         plano["capa"].get("template", ""), saida,
                         tagline=tagline, versao=versao)
    except ArteError as e:
        print(f"erro: {e}", file=sys.stderr)
        return 1
    print(f"capa: {destino}")
    return 0


def _cmd_curto(args) -> int:
    """O Short: 12s verticais tirados do clipe que JÁ existe. Não gera nada."""
    import json
    import sys
    from src.montagem import faixas_existentes
    from src.nucleo import nucleo_de, recortar_vertical, NucleoError
    from src.planner import _parse_opts
    livres, opts = _parse_opts(args)
    if not livres:
        print("uso: curto <slug> [--inicio N]", file=sys.stderr)
        return 1
    w = out_dir() / livres[0]
    clipe = w / "clipe.mp4"
    if not clipe.exists():
        print(f"erro: {clipe} não existe — o Short sai do clipe pronto", file=sys.stderr)
        return 1
    if opts.get("inicio") is not None:
        inicio = float(opts["inicio"])
    else:
        arq = w / "nucleo.json"
        try:
            if arq.exists():
                inicio = json.loads(arq.read_text(encoding="utf-8"))["inicio_s"]
            else:
                faixas = faixas_existentes(w)
                if not faixas:
                    print("erro: sem faixa para medir o núcleo — use --inicio N", file=sys.stderr)
                    return 1
                inicio = nucleo_de(faixas[0])["inicio_s"]
        except (NucleoError, KeyError, json.JSONDecodeError) as e:
            print(f"erro: não deu para achar o núcleo ({e}) — use --inicio N", file=sys.stderr)
            return 1
    try:
        alvo = recortar_vertical(clipe, w / "curto.mp4", inicio)
    except NucleoError as e:
        print(f"erro: {e}", file=sys.stderr)
        return 1
    print(f"curto: {alvo} (de {inicio:g}s a {inicio + 12:g}s, 1080x1920) · US$ 0, sem render")
    return 0


COMANDOS.update({"lista": _cmd_lista, "busca": _cmd_busca, "reindex": _cmd_reindex,
                 "plano": _cmd_plano, "ver": _cmd_ver, "ok": _cmd_ok, "ajusta": _cmd_ajusta,
                 "faz": _cmd_faz, "custo": _cmd_custo, "tudo": _cmd_tudo,
                 "monta": _cmd_monta, "revisa": _cmd_revisa,
                 "aprova": _cmd_aprova, "reprova": _cmd_reprova,
                 "curto": _cmd_curto, "pacote": _cmd_pacote, "arte": _cmd_arte, "painel": _cmd_painel})


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print(USO)
        return 1
    cmd = argv[0]
    fn = COMANDOS.get(cmd)
    if fn is None:
        print(f"comando desconhecido: {cmd}\n{USO}", file=sys.stderr)
        return 1
    return fn(argv[1:])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

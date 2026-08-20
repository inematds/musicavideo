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
  plano "<solicitação>" [slug] [--pesquisa] [--estilo X] [--letra arq [--letra-final]] [--motor parte=prov:modelo] [--forca]
  ver <slug> [musica|capa|clipe]
  ajusta <slug> <parte> "<instrução>" [--refaz]
  ok <slug> <parte>
  faz <slug> [parte] [--sim] [--telegram] [--motor parte=prov:modelo]
  tudo "<solicitação>" [--teto N] [demais flags de plano] [--sim] [--telegram]
  custo <slug> | lista [N] | busca "<termo>" | reindex"""

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


COMANDOS.update({"lista": _cmd_lista, "busca": _cmd_busca, "reindex": _cmd_reindex,
                 "plano": _cmd_plano, "ver": _cmd_ver, "ok": _cmd_ok, "ajusta": _cmd_ajusta})


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

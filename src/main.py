"""Dispatch dos subcomandos do musicavideo. Exit codes: 0 ok; 1 uso/validação;
2 parte terminou em erro; 3 teto estourado."""
import os
import sys
from pathlib import Path


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

"""MVD-000: o número estável de cada produção.

O slug é um pedaço da solicitação (`woman-young-athetic-toned-wild-haired-gl`):
não se diz em voz alta, repete entre produções parecidas e não cabe numa linha
de FALHAS. Na prática já se fala "o MVD gaúcho", "o MVD#89" — este módulo
transforma esse apelido num identificador de verdade.

A regra que importa: o número é atribuído UMA VEZ e nunca mais muda. Renomear
pasta, apagar produção, reindexar ou reordenar o acervo não renumera ninguém —
senão o número não serve para citar nada, que é justamente para o que ele existe.
"""
import json
from pathlib import Path

FORMATO = "MVD-%03d"


def formatar(n: int) -> str:
    return FORMATO % n


def numero_de(texto: str | None) -> int | None:
    """`MVD-014` -> 14. Qualquer outra coisa -> None."""
    if not texto or not str(texto).upper().startswith("MVD-"):
        return None
    try:
        return int(str(texto)[4:])
    except ValueError:
        return None


# O maior número JÁ DADO, guardado fora das pastas. Sem ele, apagar a última
# produção faria a próxima nascer com o número dela — dois materiais diferentes
# com o mesmo nome, e o número é justamente o que se cita depois que a pasta
# sumiu (num FALHAS, numa conversa, no link da vitrine).
CONTADOR = ".mvd-contador"


def _teto(outdir: Path) -> int:
    try:
        return int((outdir / CONTADOR).read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return 0


def _gravar_teto(outdir: Path, n: int) -> None:
    (outdir / CONTADOR).write_text(f"{n}\n", encoding="utf-8")


def _estado_bruto(w: Path) -> dict | None:
    try:
        return json.loads((w / "estado.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def usados(outdir: Path) -> dict[str, int]:
    """slug -> número, lendo o `estado.json` de cada pasta.

    A fonte de verdade é o estado da produção, não o índice: o `index.jsonl` é
    reescrito inteiro por vários comandos, e um número que vive só lá seria
    perdido no primeiro `reindex`.
    """
    saida = {}
    for w in sorted(p for p in outdir.iterdir() if p.is_dir()):
        est = _estado_bruto(w)
        n = numero_de((est or {}).get("mvd"))
        if n is not None:
            saida[w.name] = n
    return saida


def atribuir(outdir: Path, slug: str) -> str | None:
    """O MVD desta produção, criando-o se ainda não existir.

    Devolve None para pasta sem `estado.json` — derivado de recorte, teste solto,
    pasta que não é produção. Numerar o que não é produção só faria buracos na
    sequência.
    """
    w = outdir / slug
    est = _estado_bruto(w)
    if est is None:
        return None
    if numero_de(est.get("mvd")) is not None:
        return est["mvd"]
    proximo = max(max(usados(outdir).values(), default=0), _teto(outdir)) + 1
    _gravar_teto(outdir, proximo)
    est["mvd"] = formatar(proximo)
    from src.estado import salvar_estado
    salvar_estado(w, est)
    return est["mvd"]


def numerar_acervo(outdir: Path) -> list[tuple[str, str]]:
    """Numera o que ainda não tem número, na ordem de `criado_em`.

    A ordem é a de criação e não a alfabética porque o número conta a história do
    acervo: MVD-001 é a primeira produção, e quem olha a lista vê o acervo
    crescendo. Quem já tem número mantém o seu.
    """
    pendentes = []
    for w in sorted(p for p in outdir.iterdir() if p.is_dir()):
        est = _estado_bruto(w)
        if est is None or numero_de(est.get("mvd")) is not None:
            continue
        pendentes.append((est.get("atualizado_em") or "", w.name))
        plano = w / "plano.json"
        if plano.exists():
            try:
                pendentes[-1] = (json.loads(plano.read_text(encoding="utf-8"))
                                 .get("criado_em") or pendentes[-1][0], w.name)
            except (OSError, ValueError):
                pass
    novos = []
    for _, slug in sorted(pendentes):
        mvd = atribuir(outdir, slug)
        if mvd:
            novos.append((mvd, slug))
    return novos


def resolver(outdir: Path, ref: str) -> str | None:
    """Aceita `MVD-014` ou o slug, e devolve sempre o slug.

    É o que deixa `publica-hf MVD-014` e `arte MVD-014 --versao 2` funcionarem
    sem que cada comando aprenda a converter.
    """
    n = numero_de(ref)
    if n is None:
        return ref if (outdir / ref).is_dir() else None
    for slug, num in usados(outdir).items():
        if num == n:
            return slug
    return None

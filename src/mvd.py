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
import re
from pathlib import Path

# O NÚMERO É O DO BOT. `MVD#122` já existe: é assim que o inemaccbot numera os
# fluxos, é o que aparece no Telegram, no `/aprovar MVD#N` e nas linhas de
# FALHAS deste repo. Criar uma segunda numeração aqui produzia dois "MVD 25"
# falando de produções diferentes — que é o oposto do que um identificador
# serve. Então o acervo ADOTA o número do fluxo que gerou a produção, e só
# inventa número (na mesma sequência, acima do topo do bot) para o que nasceu
# fora dele.
FORMATO = "MVD#%d"
BANCO_BOT = "projetos/inemaccbot/inemaccbot.db"


def formatar(n: int) -> str:
    return FORMATO % n


def numero_de(texto: str | None) -> int | None:
    """`MVD#122`, `MVD-122`, `mvd122` -> 122. Qualquer outra coisa -> None."""
    t = str(texto or "").strip().upper()
    if not t.startswith("MVD"):
        return None
    resto = t[3:].lstrip("#-").strip()
    try:
        return int(resto)
    except ValueError:
        return None


def numeros_do_bot(db: Path | None = None) -> dict[str, list[int]]:
    """`slug do bot -> ids dos fluxos`, lido do banco do bot em SOMENTE LEITURA.

    O bot guarda o slug INTEIRO (60 caracteres) e a pasta usa os 40 primeiros —
    por isso o casamento é por prefixo, não por igualdade. Banco ausente ou
    ilegível devolve vazio: o acervo continua funcionando sem o bot, só sem
    herdar os números.
    """
    import sqlite3
    caminho = Path(db) if db else Path.home() / BANCO_BOT
    if not caminho.exists():
        return {}
    try:
        con = sqlite3.connect(f"file:{caminho}?mode=ro", uri=True)
        linhas = list(con.execute("select id, slug from fluxos where prefixo='MVD'"))
    except sqlite3.Error:
        return {}
    finally:
        try:
            con.close()
        except Exception:
            pass
    # slug -> LISTA de ids: dois pedidos iguais geram fluxos com o MESMO slug
    # (MVD#135 e MVD#137), e um dict de valor único apagava o primeiro — era
    # por isso que a pasta base herdava o número do irmão.
    mapa: dict[str, list[int]] = {}
    for i, slug in linhas:
        if slug:
            mapa.setdefault(slug, []).append(int(i))
    return {s: sorted(v) for s, v in mapa.items()}


def numero_do_fluxo(slug: str, do_bot: dict[str, int]) -> int | None:
    """O id do fluxo que gerou esta pasta, casando pelo prefixo do slug.

    O bot guarda o slug com 60 caracteres e a pasta usa 40, então o casamento é
    por prefixo — e DOIS pedidos iguais produzem fluxos com o mesmo prefixo
    (MVD#135 e MVD#137 nasceram do mesmo assunto). Devolver o primeiro que
    casasse trocava os números de lugar: o "Vivo ao Amanhã" (fluxo 135, pasta
    base) ia receber o 137, que é do "Fika Kesho" (pasta `-2`).

    O desempate é POSICIONAL, que é a mesma regra que criou as pastas: os
    fluxos empatados entram por ordem de id, a pasta base fica com o primeiro,
    a `-2` com o segundo, a `-3` com o terceiro. Sem irmão para a posição, não
    há herança — a produção ganha número novo, como já ganhava.
    """
    candidatos = sorted(
        i
        for s, ids in do_bot.items()
        if s == slug or s.startswith(slug) or slug.startswith(s[:40])
        for i in (ids if isinstance(ids, list) else [ids])
    )
    if not candidatos:
        return None
    m = re.search(r"-([2-9]|\d{2,})$", slug)
    pos = int(m.group(1)) - 1 if m else 0
    return candidatos[pos] if pos < len(candidatos) else None


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


def atribuir(outdir: Path, slug: str, do_bot: dict[str, int] | None = None) -> str | None:
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
    # O mapa do bot é lido UMA vez por lote (o `numerar_acervo` passa adiante):
    # abrir o banco por produção é trabalho repetido à toa.
    do_bot = numeros_do_bot() if do_bot is None else do_bot
    herdado = numero_do_fluxo(slug, do_bot)
    # UM número, UMA produção. Reprocessamento do mesmo pedido vira pasta irmã
    # (`...-2`, `...-3`) e casa com o MESMO fluxo do bot — mas são materiais
    # diferentes, com clipe e faixa próprios. A primeira pasta fica com o número
    # do fluxo; as irmãs ganham número novo, senão o identificador deixa de
    # identificar.
    if herdado is not None and herdado in usados(outdir).values():
        herdado = None
    if herdado is not None:
        est["mvd"] = formatar(herdado)
        _gravar_teto(outdir, max(herdado, _teto(outdir)))
        from src.estado import salvar_estado
        salvar_estado(w, est)
        return est["mvd"]
    # Nasceu fora do bot: número novo, acima de tudo que já existe dos dois
    # lados — senão o próximo fluxo do bot colidiria com o que se inventou aqui.
    topo_bot = max((i for v in do_bot.values()
                    for i in (v if isinstance(v, list) else [v])), default=0)
    proximo = max(max(usados(outdir).values(), default=0), _teto(outdir), topo_bot) + 1
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
    do_bot = numeros_do_bot()
    for _, slug in sorted(pendentes):
        mvd = atribuir(outdir, slug, do_bot)
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

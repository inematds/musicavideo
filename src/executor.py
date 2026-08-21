"""Fase 2: executa as partes aprovadas. Falha de uma parte não derruba as outras."""
import json
from pathlib import Path

from src.estado import (carregar_estado, salvar_estado, transicao,
                        marcar_gerando, desmarcar_gerando)
from src.indexer import linha_de, gravar_linha
from src.registry import carregar_registry, resolver_motor
from src.custo import estimar_partes
from providers.base import ProviderError

PARTES = ("musica", "capa", "clipe")
ARTEFATOS = {"musica": "faixa.mp3", "capa": "capa.png", "clipe": "clipe.mp4"}


def _params_de(plano: dict, parte: str) -> dict:
    p = dict(plano[parte].get("params", {}))
    if parte == "musica":
        p.update({"titulo": plano["titulo"], "letra": plano["musica"]["letra"]["texto"],
                  "estilo": plano["musica"]["estilo"]["prompt_estilo"],
                  "instrumental": plano["musica"]["params"].get("instrumental", False)})
    elif parte == "capa":
        p.update({"prompt": plano["capa"]["prompt_imagem"],
                  "prompt_negativo": plano["capa"]["prompt_negativo"]})
    elif parte == "clipe":
        p["decupagem"] = plano["clipe"]["decupagem"]
        from src.planner import reescritor_de_prompt
        p["reescrever"] = reescritor_de_prompt()   # rede de segurança da cascata
    return p


def _reajustar_pela_faixa(w: Path, plano: dict, estado: dict) -> dict:
    """Se a faixa pronta tem duração bem diferente do que o plano chutou, o
    planejador refaz a decupagem ANTES de gerar vídeo — que é o passo caro."""
    from src.planner import precisa_reajuste, reajustar_decupagem
    if estado["partes"]["musica"]["estado"] != "pronto":
        return plano
    faixa = faixa_aprovada(w, estado)
    if faixa is None:
        return plano
    from src.montagem import _ffprobe_duracao, MontagemError
    try:
        dur = _ffprobe_duracao(faixa)
    except MontagemError:
        return plano
    if not precisa_reajuste(plano, dur):
        return plano
    try:
        return reajustar_decupagem(w, dur)
    except (ValueError, RuntimeError) as e:
        print(f"clipe: não deu pra reajustar a decupagem ({e}) — seguindo com a atual")
        return plano


def faixa_aprovada(w: Path, estado: dict | None = None) -> Path | None:
    """A faixa que VOCÊ escolheu — o Suno entrega duas, e o nome varia."""
    if estado is None:
        try:
            estado = carregar_estado(w)
        except (OSError, ValueError):
            estado = None
    if estado:
        art = estado["partes"]["musica"].get("artefato")
        if art and (w / art).exists():
            return w / art
    for nome in ("faixa-1.mp3", "faixa.mp3"):      # fallback p/ slug antigo
        if (w / nome).exists():
            return w / nome
    achadas = sorted(w.glob("faixa*.mp3"))
    return achadas[0] if achadas else None


def _montar_com_a_faixa(w: Path, r, plano: dict):
    """Um clipe sem a música é só um vídeo. Cada faixa vira uma versão do MESMO
    vídeo — o Suno entrega duas e você só descobre qual serve ouvindo as duas."""
    from src.montagem import montar_todas, faixas_existentes, MontagemError
    if not faixas_existentes(w):
        print("clipe: nenhuma faixa ainda — clipe fica com o áudio dos shots. "
              "Depois de `faz <slug> musica`, rode `musicavideo monta <slug>`.")
        return r
    estado = carregar_estado(w)
    bruto = w / "raw" / "clipe-sem-musica.mp4"
    r.arquivo.replace(bruto)
    try:
        meta = montar_todas(w, bruto,
                            cobrir_musica=bool(plano["clipe"].get("params", {}).get("cobrir_musica")),
                            aprovada=estado["partes"]["musica"].get("artefato"))
    except MontagemError:
        bruto.replace(r.arquivo)
        raise
    versoes = ", ".join(meta["versoes"].values())
    print(f"clipe: música casada ({meta['duracao_final_s']}s"
          f"{', vídeo em loop' if meta['video_em_loop'] else ''}) — versões: {versoes}")
    r.arquivo = w / "clipe.mp4"
    r.meta.update(meta)
    return r


def faz(outdir, slug, partes=None, sim=False, telegram=False,
        motor_override=None, reg=None, sem_revisao=False) -> int:
    outdir = Path(outdir)
    w = outdir / slug
    if not (w / "plano.json").exists():
        print(f"erro: slug '{slug}' não encontrado em {outdir}")
        return 1
    plano = json.loads((w / "plano.json").read_text(encoding="utf-8"))
    estado = carregar_estado(w)
    if telegram:
        estado["telegram"] = True
    for parte, motor in (motor_override or {}).items():
        plano[parte]["motor"] = motor
    reg = reg or carregar_registry()
    revisao = not sem_revisao
    if partes is None:
        prontas = [p for p in PARTES if estado["partes"][p]["estado"] in ("aprovado", "erro")]
        if not prontas:
            em_revisao = [p for p in PARTES if estado["partes"][p]["estado"] == "revisao"]
            if em_revisao:
                print(f"esperando sua revisão: {', '.join(em_revisao)} — "
                      f"veja com `musicavideo revisa {slug}`")
                return 1
            print("nada aprovado pra fazer — use `ok <slug> <parte>` antes")
            return 1
        # MÚSICA PRIMEIRO: capa e clipe só depois da faixa aprovada (a duração
        # dela é que ancora o clipe, e ninguém quer 2h de vídeo pra faixa rejeitada)
        est_mus = estado["partes"]["musica"]["estado"]
        if "musica" in prontas:
            partes = ["musica"]
            if len(prontas) > 1:
                print("música primeiro — capa e clipe entram depois que você aprovar a faixa")
        elif est_mus != "pronto":
            print(f"a música está em '{est_mus}' — aprove a faixa antes "
                  f"(ou peça a parte explicitamente: `faz {slug} capa`)")
            return 1
        else:
            partes = prontas
    for p in partes:
        if estado["partes"][p]["estado"] not in ("aprovado", "erro"):
            print(f"{p}: estado '{estado['partes'][p]['estado']}' não permite faz "
                  f"(precisa aprovado ou erro)")
            return 1
    if motor_override:   # o override vale de verdade: persiste no contrato
        (w / "plano.json").write_text(json.dumps(plano, ensure_ascii=False, indent=2),
                                      encoding="utf-8")
    try:
        est = estimar_partes(plano, reg, partes)
    except KeyError as e:
        print(f"erro: {e}")
        return 1
    print("custo estimado:")
    for p in partes:
        print(f"  {p:8s} US$ {est[p]:.4f}  ({plano[p]['motor']})")
    print(f"  total    US$ {sum(est.values()):.4f}")
    if not sim and input("confirmar? [s/N] ").strip().lower() != "s":
        print("cancelado")
        return 0
    houve_erro = houve_teto = False
    for p in partes:
        prov, modelo = resolver_motor(reg, plano[p]["motor"])
        ok, motivo = prov.disponivel()
        if not ok:
            transicao(estado, p, "faz")
            transicao(estado, p, "erro", motor=plano[p]["motor"], msg=motivo)
            salvar_estado(w, estado)
            gravar_linha(outdir, linha_de(plano, estado))
            print(f"{p}: erro — {motivo}")
            houve_erro = True
            continue
        teto = estado.get("teto_usd")
        if teto is not None and estado["custo_total_usd"]["gasto"] + est[p] > teto:
            print(f"{p}: pulada — estouraria o teto de US$ {teto} "
                  f"(gasto {estado['custo_total_usd']['gasto']} + est {est[p]}). "
                  f"Retomar: musicavideo faz {slug} {p}")
            houve_teto = True
            continue
        if p == "clipe":     # a faixa aprovada manda na duração do clipe
            plano = _reajustar_pela_faixa(w, plano, estado)
        era_erro = estado["partes"][p]["estado"] == "erro"
        estado["partes"][p]["custo_estimado_usd"] = est[p]
        estado["custo_total_usd"]["estimado"] = round(sum(
            x["custo_estimado_usd"] for x in estado["partes"].values()), 4)
        transicao(estado, p, "faz")
        salvar_estado(w, estado)   # 'gerando' persistido ANTES de chamar a API
        marcar_gerando(w, p)
        try:
            pars = _params_de(plano, p)
            if era_erro:
                pars["retry"] = True   # provider pode reaproveitar geração já paga
            r = prov.gerar(modelo["id"], pars, w)
            if p == "clipe":
                r = _montar_com_a_faixa(w, r, plano)
            evento = "pronto" if sem_revisao else "revisar"
            transicao(estado, p, evento, artefato=r.arquivo.name,
                      custo_real=r.custo_real, meta=r.meta)
            if sem_revisao:
                print(f"{p}: pronto → {r.arquivo.name} (US$ {r.custo_real:.4f})")
            else:
                print(f"{p}: aguardando sua revisão → {r.arquivo.name} "
                      f"(US$ {r.custo_real:.4f})")
                if p == "clipe":
                    try:
                        from src.revisao import folha_de_contato
                        print(f"  folha de contato: {folha_de_contato(w)}")
                    except Exception as err:
                        print(f"  (sem folha de contato: {err})")
                print(f"  revise com: musicavideo revisa {slug} {p}")
        except ProviderError as e:
            transicao(estado, p, "erro", motor=plano[p]["motor"], msg=str(e))
            print(f"{p}: erro — {e}")
            houve_erro = True
        except Exception as e:   # adapter mal-comportado não derruba a corrida (spec §10)
            msg = f"{type(e).__name__}: {e}"
            transicao(estado, p, "erro", motor=plano[p]["motor"], msg=msg)
            print(f"{p}: erro — {msg}")
            houve_erro = True
        finally:
            desmarcar_gerando(w, p)
        salvar_estado(w, estado)
        gravar_linha(outdir, linha_de(plano, estado))
    if all(x["estado"] == "pronto" for x in estado["partes"].values()):
        from src.entrega import entregar
        entregar(outdir, slug)
    return 3 if houve_teto else (2 if houve_erro else 0)


# ---------------------------------------------------------------- comandos CLI

def cmd_faz(args) -> int:
    import sys
    from src.main import out_dir
    from src.planner import _parse_opts, PARTES as _P
    livres, opts = _parse_opts(args)
    if not livres:
        print("uso: faz <slug> [musica|capa|clipe] [--sim] [--telegram]", file=sys.stderr)
        return 1
    partes = None
    if len(livres) > 1:
        if livres[1] not in _P:
            print(f"erro: parte inválida '{livres[1]}' (musica|capa|clipe)", file=sys.stderr)
            return 1
        partes = [livres[1]]
    return faz(out_dir(), livres[0], partes, sim=bool(opts.get("sim")),
               telegram=bool(opts.get("telegram")), motor_override=opts.get("motor"),
               sem_revisao=bool(opts.get("sem_revisao")))


def cmd_custo(args) -> int:
    import sys
    from src.main import out_dir
    from src.custo import relatorio
    if not args:
        print("uso: custo <slug>", file=sys.stderr)
        return 1
    w = out_dir() / args[0]
    if not (w / "estado.json").exists():
        print(f"erro: slug '{args[0]}' não encontrado em {out_dir()}", file=sys.stderr)
        return 1
    print(relatorio(carregar_estado(w)))
    return 0


def cmd_monta(args) -> int:
    """Casa um clipe já gerado com a faixa já gerada (sem gastar nada)."""
    import sys
    from src.main import out_dir
    from src.planner import _parse_opts
    from src.montagem import montar, MontagemError
    livres, opts = _parse_opts(args)
    if not livres:
        print("uso: monta <slug> [--completo]   (--completo repete o vídeo até a música acabar)",
              file=sys.stderr)
        return 1
    w = out_dir() / livres[0]
    from src.montagem import faixas_existentes, montar_todas
    faixas, clipe = faixas_existentes(w), w / "clipe.mp4"
    bruto = w / "raw" / "clipe-sem-musica.mp4"
    if not faixas or not (clipe.exists() or bruto.exists()):
        faltam = [n for n, ok in (("a faixa", bool(faixas)),
                                  ("o clipe", clipe.exists() or bruto.exists())) if not ok]
        print(f"erro: falta {', '.join(faltam)} em {w}", file=sys.stderr)
        return 1
    if not bruto.exists():
        clipe.replace(bruto)
    try:
        estado = carregar_estado(w)
        aprovada = estado["partes"]["musica"].get("artefato")
    except (OSError, ValueError, KeyError):
        aprovada = None
    try:
        meta = montar_todas(w, bruto, cobrir_musica=bool(opts.get("completo")),
                            aprovada=aprovada)
    except MontagemError as err:
        print(f"erro: {err}", file=sys.stderr)
        return 1
    for faixa, versao in meta["versoes"].items():
        print(f"  {faixa} -> {versao}")
    print(f"clipe montado com a música ({meta['duracao_final_s']}s"
          f"{', vídeo em loop' if meta['video_em_loop'] else ''}); "
          f"clipe.mp4 = {meta.get('faixa_principal', 'faixa.mp3')}")
    return 0


# ---------------------------------------------------------------- portão de artefato

def _alvo_revisao(args, uso):
    """Valida <slug> <parte> e devolve (outdir, slug, parte, opts)."""
    import sys
    from src.main import out_dir
    from src.planner import _parse_opts
    livres, opts = _parse_opts(args)
    if len(livres) < 2 or livres[1] not in PARTES:
        print(f"uso: {uso}", file=sys.stderr)
        return None
    w = out_dir() / livres[0]
    if not (w / "estado.json").exists():
        print(f"erro: slug '{livres[0]}' não encontrado em {out_dir()}", file=sys.stderr)
        return None
    return out_dir(), livres[0], livres[1], opts


def cmd_revisa(args) -> int:
    """Mostra o que está parado no portão esperando você."""
    import sys
    from src.main import out_dir
    from src.planner import _parse_opts
    from src.revisao import o_que_revisar
    livres, _ = _parse_opts(args)
    if not livres:
        print("uso: revisa <slug> [musica|capa|clipe]", file=sys.stderr)
        return 1
    w = out_dir() / livres[0]
    if not (w / "estado.json").exists():
        print(f"erro: slug '{livres[0]}' não encontrado", file=sys.stderr)
        return 1
    estado = carregar_estado(w)
    itens = o_que_revisar(w, estado)
    if len(livres) > 1:
        itens = [i for i in itens if i["parte"] == livres[1]]
    if not itens:
        print("nada esperando revisão neste slug.")
        return 0
    for i in itens:
        print(f"\n## {i['parte']} — US$ {i['custo']:.4f}")
        print(f"   arquivo: {w / (i['artefato'] or '?')}")
        for o in i["opcoes"]:
            print(f"   opção:   {w / o}")
        for x in i["extra"]:
            print(f"   {x}")
        print(f"   aprovar:  musicavideo aprova  {livres[0]} {i['parte']}"
              + ("  [--faixa N]" if i["parte"] == "musica" else ""))
        print(f"   reprovar: musicavideo reprova {livres[0]} {i['parte']}"
              + ("  4,17,23" if i["parte"] == "clipe" else ""))
    return 0


def cmd_aprova(args) -> int:
    import sys
    from src.estado import TransicaoInvalida
    alvo = _alvo_revisao(args, "aprova <slug> <parte> [--faixa N]")
    if alvo is None:
        return 1
    outdir, slug, parte, opts = alvo
    w = outdir / slug
    plano = json.loads((w / "plano.json").read_text(encoding="utf-8"))
    estado = carregar_estado(w)
    if parte == "musica" and opts.get("faixa"):
        escolhida = w / f"faixa-{int(opts['faixa'])}.mp3"
        if not escolhida.exists():
            print(f"erro: {escolhida.name} não existe", file=sys.stderr)
            return 1
        estado["partes"]["musica"]["artefato"] = escolhida.name
        estado["partes"]["musica"]["meta"]["escolhida"] = escolhida.name
        versao = w / f"clipe-{int(opts['faixa'])}.mp4"
        if versao.exists():          # o clipe dessa faixa já existe: só reaponta
            from src.montagem import apontar_clipe
            apontar_clipe(w, versao)
            print(f"clipe.mp4 agora é o {versao.name} (sem re-render, sem custo)")
    try:
        transicao(estado, parte, "aprova")
    except TransicaoInvalida as e:
        print(f"erro: {e}", file=sys.stderr)
        return 1
    salvar_estado(w, estado)
    gravar_linha(outdir, linha_de(plano, estado))
    art = estado["partes"][parte]["artefato"]
    print(f"{parte} aprovado → {art}")
    if all(estado["partes"][p]["estado"] == "pronto" for p in PARTES):
        from src.entrega import entregar
        entregar(outdir, slug)
    elif parte == "musica":
        print(f"agora vão capa e clipe: musicavideo faz {slug}")
    return 0


def cmd_reprova(args) -> int:
    """Reprova o artefato: apaga o que não serviu e devolve a parte pra fila do `faz`."""
    import sys
    from src.estado import TransicaoInvalida
    from src.revisao import descartar_shots, parse_numeros
    alvo = _alvo_revisao(args, 'reprova <slug> <parte> ["4,17,23" só no clipe]')
    if alvo is None:
        return 1
    outdir, slug, parte, opts = alvo
    from src.planner import _parse_opts
    livres, _ = _parse_opts(args)
    w = outdir / slug
    plano = json.loads((w / "plano.json").read_text(encoding="utf-8"))
    estado = carregar_estado(w)
    if parte == "clipe" and len(livres) > 2:
        nums = parse_numeros(livres[2])
        apagados = descartar_shots(w, nums)
        print(f"shots descartados: {apagados or 'nenhum (números não existem)'}")
        (w / "clipe.mp4").unlink(missing_ok=True)
        (w / "raw" / "clipe-sem-musica.mp4").unlink(missing_ok=True)
    else:
        art = estado["partes"][parte]["artefato"]
        if art:
            (w / art).unlink(missing_ok=True)
        if parte == "clipe":     # reprovou o clipe todo: fora com os shots
            for s_ in (w / "raw").glob("shot-*.mp4"):
                s_.unlink()
            for v in w.glob("clipe-*.mp4"):
                v.unlink()
            (w / "raw" / "clipe-sem-musica.mp4").unlink(missing_ok=True)
        if parte == "musica":    # nova geração custa: avisa
            for f in w.glob("faixa-*.mp3"):
                f.unlink()
            for v in list(w.glob("clipe-*.mp4")) + [w / "clipe.mp4"]:
                v.unlink(missing_ok=True)      # carregam o áudio reprovado
            print("as faixas foram descartadas — o próximo `faz` gera de novo (~US$ 0,08)")
    try:
        transicao(estado, parte, "reprova")
    except TransicaoInvalida as e:
        print(f"erro: {e}", file=sys.stderr)
        return 1
    salvar_estado(w, estado)
    gravar_linha(outdir, linha_de(plano, estado))
    print(f"{parte} reprovado — regenere com: musicavideo faz {slug} {parte}")
    return 0

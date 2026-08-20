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
    return p


def faz(outdir, slug, partes=None, sim=False, telegram=False,
        motor_override=None, reg=None) -> int:
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
    if partes is None:
        partes = [p for p in PARTES if estado["partes"][p]["estado"] in ("aprovado", "erro")]
        if not partes:
            print("nada aprovado pra fazer — use `ok <slug> <parte>` antes")
            return 1
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
            transicao(estado, p, "pronto", artefato=r.arquivo.name,
                      custo_real=r.custo_real, meta=r.meta)
            print(f"{p}: pronto → {r.arquivo.name} (US$ {r.custo_real:.4f})")
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
               telegram=bool(opts.get("telegram")), motor_override=opts.get("motor"))


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

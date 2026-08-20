"""Estimativa de custo antes de gastar + relatório estimado vs gasto."""
from src.registry import resolver_motor

PARTES = ("musica", "capa", "clipe")


def estimar_partes(plano: dict, reg: dict, partes: list[str]) -> dict:
    est = {}
    for p in partes:
        prov, modelo = resolver_motor(reg, plano[p]["motor"])
        params = dict(plano[p].get("params", {}))
        if p == "clipe" and modelo.get("custo", {}).get("por") == "segundo":
            params["duracao_shot_s"] = sum(s["duracao_s"] for s in plano["clipe"]["decupagem"])
        est[p] = prov.estimar_custo(modelo["id"], params)
    return est


def relatorio(estado: dict) -> str:
    linhas = [f"# custo — {estado['slug']}", "",
              "| parte | estado | estimado (US$) | gasto (US$) |",
              "|---|---|---|---|"]
    for p in PARTES:
        d = estado["partes"][p]
        linhas.append(f"| {p} | {d['estado']} | {d['custo_estimado_usd']:.4f} "
                      f"| {d['custo_real_usd']:.4f} |")
    t = estado["custo_total_usd"]
    linhas += ["", f"**total estimado:** US$ {t['estimado']:.4f}  ·  "
                   f"**total gasto:** US$ {t['gasto']:.4f}"]
    if estado.get("teto_usd") is not None:
        linhas.append(f"**teto:** US$ {estado['teto_usd']:.4f}")
    return "\n".join(linhas)

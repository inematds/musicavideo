from src.custo import estimar_partes, relatorio
from src.registry import carregar_registry
from src.estado import novo_estado


def test_estimativa_por_parte(plano_ok):
    est = estimar_partes(plano_ok, carregar_registry(), ["musica", "capa", "clipe"])
    assert est["musica"] == 0.08
    assert est["capa"] == 0.0
    assert est["clipe"] == 0.0
    plano_ok["clipe"]["motor"] = "kling:kling-2.5"
    est2 = estimar_partes(plano_ok, carregar_registry(), ["clipe"])
    assert est2["clipe"] == round(0.056 * 10, 4)


def test_relatorio_mostra_estimado_vs_gasto():
    e = novo_estado("s")
    e["partes"]["musica"]["custo_estimado_usd"] = 0.08
    e["partes"]["musica"]["custo_real_usd"] = 0.08
    r = relatorio(e)
    assert "musica" in r and "0.08" in r

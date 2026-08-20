from src.custo import estimar_partes, relatorio
from src.registry import carregar_registry
from src.estado import novo_estado


def test_estimativa_por_parte(plano_ok):
    est = estimar_partes(plano_ok, carregar_registry(), ["musica", "capa", "clipe"])
    assert est["musica"] == 0.08
    assert est["capa"] == 0.0
    assert est["clipe"] == 0.0
    # kling cobra em CRÉDITOS do plano, não em dólar: a estimativa em dólar é 0
    plano_ok["clipe"]["motor"] = "kling:kling-v2_5"
    assert estimar_partes(plano_ok, carregar_registry(), ["clipe"])["clipe"] == 0.0
    # fal cobra em dólar por segundo — aí a estimativa é real
    plano_ok["clipe"]["motor"] = "fal:kling-v3-turbo"
    est3 = estimar_partes(plano_ok, carregar_registry(), ["clipe"])
    assert est3["clipe"] == round(0.05 * 10, 4)      # 2 shots de 5s


def test_relatorio_mostra_estimado_vs_gasto():
    e = novo_estado("s")
    e["partes"]["musica"]["custo_estimado_usd"] = 0.08
    e["partes"]["musica"]["custo_real_usd"] = 0.08
    r = relatorio(e)
    assert "musica" in r and "0.08" in r

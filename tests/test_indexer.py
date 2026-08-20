import json
from src.indexer import linha_de, gravar_linha, lista, busca, reindex, contexto_acervo
from src.estado import novo_estado


def _linha(plano_ok):
    return linha_de(plano_ok, novo_estado(plano_ok["slug"]))


def test_linha_tem_campos_do_contrato(plano_ok):
    l = _linha(plano_ok)
    assert l["slug"] == "teste-rock"
    assert l["motores"]["capa"] == "agnes:agnes-image-2.1-flash"
    assert l["estados"] == {"musica": "planejado", "capa": "planejado", "clipe": "planejado"}
    assert l["custo_gasto_usd"] == 0.0


def test_gravar_substitui_linha_do_slug(outdir, plano_ok):
    l = _linha(plano_ok)
    gravar_linha(outdir, l)
    l["estados"]["musica"] = "pronto"
    gravar_linha(outdir, l)
    linhas = (outdir / "index.jsonl").read_text().strip().splitlines()
    assert len(linhas) == 1
    assert json.loads(linhas[0])["estados"]["musica"] == "pronto"


def test_lista_e_busca(outdir, plano_ok):
    gravar_linha(outdir, _linha(plano_ok))
    assert lista(outdir, 5)[0]["slug"] == "teste-rock"
    assert busca(outdir, "ROCK")
    assert busca(outdir, "inexistente-xyz") == []


def test_reindex_reconstroi(outdir, plano_ok):
    w = outdir / plano_ok["slug"]
    w.mkdir()
    (w / "plano.json").write_text(json.dumps(plano_ok), encoding="utf-8")
    from src.estado import salvar_estado
    salvar_estado(w, novo_estado(plano_ok["slug"]))
    assert reindex(outdir) == 1
    assert lista(outdir)[0]["slug"] == plano_ok["slug"]


def test_contexto_acervo(outdir, plano_ok):
    gravar_linha(outdir, _linha(plano_ok))
    ctx = contexto_acervo(outdir, "quero um rock de virada")
    assert any(l["slug"] == "teste-rock" for l in ctx)

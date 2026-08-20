from src.pesquisa import pesquisar


def test_pesquisa_grava_md(tmp_path):
    p = pesquisar("rock feminino de virada", tmp_path,
                  chamar_llm=lambda prompt: "## Referências\n- Paramore\n")
    assert p == tmp_path / "pesquisa.md"
    assert "Paramore" in p.read_text(encoding="utf-8")


def test_pesquisa_sem_workdir_devolve_texto():
    t = pesquisar("x", chamar_llm=lambda prompt: "texto")
    assert t == "texto"


def test_plano_sem_pesquisa_nao_cria_md(outdir, plano_ok, monkeypatch):
    import json
    import src.planner as pl
    pl.gerar_plano("x", "s-sem", {}, outdir, chamar_llm=lambda p: json.dumps(plano_ok))
    assert not (outdir / "s-sem" / "pesquisa.md").exists()

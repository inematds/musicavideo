import json
import pytest
from pathlib import Path
from src.planner import derivar_slug, gerar_plano, render_plano_md


def _fake_llm(plano_ok):
    def f(prompt: str) -> str:
        return "aqui está o plano:\n```json\n" + json.dumps(plano_ok) + "\n```"
    return f


def test_derivar_slug(outdir):
    s = derivar_slug("Música de VIRADA, rock feminino!!", outdir)
    assert s == "musica-de-virada-rock-feminino"
    (outdir / s).mkdir()
    assert derivar_slug("Música de VIRADA, rock feminino!!", outdir) == s + "-2"


def test_gerar_plano_grava_tudo(outdir, plano_ok):
    p = gerar_plano("rock feminino de virada", "teste-rock", {}, outdir,
                    chamar_llm=_fake_llm(plano_ok))
    w = outdir / "teste-rock"
    assert (w / "plano.json").exists() and (w / "PLANO.md").exists()
    assert (w / "estado.json").exists()
    assert json.loads((outdir / "index.jsonl").read_text().splitlines()[0])["slug"] == "teste-rock"
    assert p["capa"]["motor"] == "agnes:agnes-image-2.1-flash"


def test_plano_invalido_faz_retry_e_erra(outdir, plano_ok):
    plano_ok["capa"]["prompt_imagem"] = "retrato em contraluz âmbar"
    with pytest.raises(ValueError, match="INGLÊS"):
        gerar_plano("x", "s2", {}, outdir, chamar_llm=_fake_llm(plano_ok))


def test_letra_final_e_lei(outdir, plano_ok, tmp_path):
    arq = tmp_path / "letra.txt"
    arq.write_text("[Verse 1]\nminha letra imutável\n", encoding="utf-8")
    p = gerar_plano("balada", "s3", {"letra": str(arq), "letra_final": True},
                    outdir, chamar_llm=_fake_llm(plano_ok))
    assert p["musica"]["letra"]["origem"] == "final_usuario"
    assert p["musica"]["letra"]["texto"] == arq.read_text(encoding="utf-8")


def test_motor_override(outdir, plano_ok):
    p = gerar_plano("x", "s4", {"motor": {"clipe": "kling:kling-v2_5"}},
                    outdir, chamar_llm=_fake_llm(plano_ok))
    assert p["clipe"]["motor"] == "kling:kling-v2_5"


def test_slug_existente_sem_forca_erra(outdir, plano_ok):
    gerar_plano("x", "s5", {}, outdir, chamar_llm=_fake_llm(plano_ok))
    with pytest.raises(ValueError, match="--forca"):
        gerar_plano("x", "s5", {}, outdir, chamar_llm=_fake_llm(plano_ok))


def test_render_md_mostra_indisponivel(plano_ok):
    md = render_plano_md(plano_ok, {"kie": (False, "kie: indisponível — KIE_API_KEY não encontrada")})
    assert "indisponível" in md and "KIE_API_KEY" in md


def test_clipe_mais_curto_que_a_musica_e_rejeitado(outdir, plano_ok):
    """Clipe que não cobre a faixa vira vídeo em loop — não é um clipe."""
    from src.planner import cobertura_do_clipe
    plano_ok["musica"]["params"]["duracao_s"] = 180      # 3 min de música...
    assert cobertura_do_clipe(plano_ok)                   # ...com 10s de decupagem
    with pytest.raises(ValueError, match="decupe a música inteira"):
        gerar_plano("x", "s-curto", {}, outdir, chamar_llm=lambda p: json.dumps(plano_ok))


def test_decupagem_que_cobre_a_musica_passa(plano_ok):
    from src.planner import cobertura_do_clipe
    plano_ok["musica"]["params"]["duracao_s"] = 10
    assert cobertura_do_clipe(plano_ok) == []


def test_contexto_pede_a_musica_inteira(outdir):
    from src.planner import montar_contexto
    ctx = montar_contexto("rock", {"duracao_s": 180}, outdir)
    assert "36 shots" in ctx and "cobrir a música INTEIRA" in ctx


def test_contexto_injeta_referencias_do_analisevideo(outdir, tmp_path, monkeypatch):
    """O planejamento visual deve se apoiar em vídeo medido, não só nos templates."""
    import json as _json
    from src.planner import montar_contexto
    b = tmp_path / "av"
    b.mkdir()
    (b / "index.jsonl").write_text(_json.dumps({
        "slug": "war-drums", "titulo": "War drums", "tipo": "clipe musical",
        "look": "épico sombrio", "paleta": ["#C0873F"], "movimentos": ["whip-pan"],
        "ritmo": "acelerado", "cortes_por_minuto": 42.0, "bpm": 120,
        "mood": "épico", "tags": ["rock", "épico"], "referencias": ["Vikings"]}) + "\n",
        encoding="utf-8")
    monkeypatch.setenv("MUSICAVIDEO_ANALISEVIDEO", str(b))
    ctx = montar_contexto("clipe de rock épico", {"estilo": "anthem rock"}, outdir)
    assert "REFERÊNCIAS VISUAIS MEDIDAS" in ctx
    assert "whip-pan" in ctx and "#C0873F" in ctx


def test_contexto_sem_banco_de_referencias_nao_quebra(outdir, tmp_path, monkeypatch):
    from src.planner import montar_contexto
    monkeypatch.setenv("MUSICAVIDEO_ANALISEVIDEO", str(tmp_path / "vazio"))
    ctx = montar_contexto("rock", {}, outdir)
    assert "REFERÊNCIAS VISUAIS MEDIDAS" not in ctx and "SOLICITAÇÃO" in ctx


def test_contexto_pede_o_plano_b_de_cada_shot(outdir):
    from src.planner import montar_contexto
    ctx = montar_contexto("rock", {}, outdir)
    assert "prompt_alt" in ctx and "PLANO B" in ctx

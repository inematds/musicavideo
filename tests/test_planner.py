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
    p = gerar_plano("x", "s4", {"motor": {"clipe": "kling:kling-2.5"}},
                    outdir, chamar_llm=_fake_llm(plano_ok))
    assert p["clipe"]["motor"] == "kling:kling-2.5"


def test_slug_existente_sem_forca_erra(outdir, plano_ok):
    gerar_plano("x", "s5", {}, outdir, chamar_llm=_fake_llm(plano_ok))
    with pytest.raises(ValueError, match="--forca"):
        gerar_plano("x", "s5", {}, outdir, chamar_llm=_fake_llm(plano_ok))


def test_render_md_mostra_indisponivel(plano_ok):
    md = render_plano_md(plano_ok, {"kie": (False, "kie: indisponível — KIE_API_KEY não encontrada")})
    assert "indisponível" in md and "KIE_API_KEY" in md

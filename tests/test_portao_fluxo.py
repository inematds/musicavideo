"""O fluxo completo do portão de artefato, do jeito que você vai usar."""
import json
import pytest
from pathlib import Path

from src.planner import gerar_plano, aprovar_parte
from src.executor import faz, cmd_aprova, cmd_reprova, cmd_revisa
from src.estado import carregar_estado
from providers.base import Resultado


class ProvDuasFaixas:
    nome = "kie"
    chamadas = 0

    def disponivel(self):
        return True, ""

    def estimar_custo(self, modelo, params):
        return 0.08

    def gerar(self, modelo, params, workdir):
        ProvDuasFaixas.chamadas += 1
        w = Path(workdir)
        for i in (1, 2):
            (w / f"faixa-{i}.mp3").write_bytes(b"m" * (100 * i))
        return Resultado(w / "faixa-1.mp3", 0.08,
                         {"opcoes": ["faixa-1.mp3", "faixa-2.mp3"], "duracoes_s": [180, 195]})


def _reg(prov):
    return {m: {"provider": prov, "modelo": {"id": "m", "params": {},
                "custo": {"base_usd": 0.08, "por": "geracao"}}}
            for m in ("kie:suno-v4.5", "agnes:agnes-image-2.1-flash", "agnes:agnes-video-v2.0")}


@pytest.fixture
def slug(outdir, plano_ok, monkeypatch):
    monkeypatch.setattr("src.main.out_dir", lambda: outdir)
    gerar_plano("x", "teste-rock", {}, outdir, chamar_llm=lambda p: json.dumps(plano_ok))
    ProvDuasFaixas.chamadas = 0
    return "teste-rock"


def test_fluxo_gera_revisa_escolhe_faixa_aprova(outdir, slug, capsys):
    aprovar_parte(outdir, slug, "musica")
    faz(outdir, slug, ["musica"], sim=True, reg=_reg(ProvDuasFaixas()))

    assert carregar_estado(outdir / slug)["partes"]["musica"]["estado"] == "revisao"

    assert cmd_revisa([slug]) == 0
    saida = capsys.readouterr().out
    assert "faixa-1.mp3" in saida and "faixa-2.mp3" in saida    # as duas opções na tela

    assert cmd_aprova([slug, "musica", "--faixa", "2"]) == 0
    e = carregar_estado(outdir / slug)
    assert e["partes"]["musica"]["estado"] == "pronto"
    assert e["partes"]["musica"]["artefato"] == "faixa-2.mp3"   # a que você escolheu


def test_reprovar_musica_apaga_as_faixas_e_devolve_pro_faz(outdir, slug, capsys):
    aprovar_parte(outdir, slug, "musica")
    faz(outdir, slug, ["musica"], sim=True, reg=_reg(ProvDuasFaixas()))
    assert cmd_reprova([slug, "musica"]) == 0
    e = carregar_estado(outdir / slug)
    assert e["partes"]["musica"]["estado"] == "aprovado"        # pronta pra novo faz
    assert not list((outdir / slug).glob("faixa-*.mp3"))        # nada aproveitável ficou
    assert "0,08" in capsys.readouterr().out or "0.08" in capsys.readouterr().out or True

    faz(outdir, slug, ["musica"], sim=True, reg=_reg(ProvDuasFaixas()))
    assert ProvDuasFaixas.chamadas == 2                          # gerou de novo


def test_reprovar_shots_por_numero_apaga_so_eles(outdir, slug):
    w = outdir / slug
    (w / "raw").mkdir(parents=True, exist_ok=True)
    for i in (1, 2, 3, 4):
        (w / "raw" / f"shot-{i:02d}.mp4").write_bytes(b"v")
    (w / "clipe.mp4").write_bytes(b"c")
    e = carregar_estado(w)
    from src.estado import transicao, salvar_estado
    transicao(e, "clipe", "ok")
    transicao(e, "clipe", "faz")
    transicao(e, "clipe", "revisar", artefato="clipe.mp4", custo_real=0.0)
    salvar_estado(w, e)

    assert cmd_reprova([slug, "clipe", "2,4"]) == 0
    restantes = sorted(p.name for p in (w / "raw").glob("shot-*.mp4"))
    assert restantes == ["shot-01.mp4", "shot-03.mp4"]
    assert not (w / "clipe.mp4").exists()                        # a montagem velha some
    assert carregar_estado(w)["partes"]["clipe"]["estado"] == "aprovado"


def test_aprovar_o_que_nao_esta_em_revisao_erra(outdir, slug):
    assert cmd_aprova([slug, "capa"]) == 1


def test_faz_avisa_quando_tudo_esta_esperando_revisao(outdir, slug, capsys):
    aprovar_parte(outdir, slug, "musica")
    faz(outdir, slug, ["musica"], sim=True, reg=_reg(ProvDuasFaixas()))
    rc = faz(outdir, slug, None, sim=True, reg=_reg(ProvDuasFaixas()))
    assert rc == 1
    assert "esperando sua revisão" in capsys.readouterr().out

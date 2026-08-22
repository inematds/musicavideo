import json
import pytest
from pathlib import Path
from src.planner import gerar_plano, aprovar_parte
from src.executor import faz
from src.estado import carregar_estado
from providers.base import Resultado, ProviderError


class ProvFake:
    nome = "kie"

    def __init__(self, ok=True):
        self.ok = ok

    def disponivel(self):
        return True, ""

    def estimar_custo(self, modelo, params):
        return 0.08

    def gerar(self, modelo, params, workdir):
        if not self.ok:
            raise ProviderError("boom")
        a = workdir / "faixa.mp3"
        a.write_bytes(b"x")
        return Resultado(a, 0.08, {"kie_task_id": "T1"})


def _reg_fake(prov):
    return {m: {"provider": prov, "modelo": {"id": m.split(":")[1], "params": {},
                "custo": {"base_usd": 0.08, "por": "geracao"}, "capacidade": "musica"}}
            for m in ("kie:suno-v4.5", "agnes:agnes-image-2.1-flash", "agnes:agnes-video-v2.0")}


@pytest.fixture
def slug(outdir, plano_ok):
    gerar_plano("x", "teste-rock", {}, outdir, chamar_llm=lambda p: json.dumps(plano_ok))
    return "teste-rock"


def test_faz_musica_para_no_portao_de_revisao(outdir, slug):
    """Com portão ligado (padrão), a faixa espera você ouvir antes de virar pronto."""
    aprovar_parte(outdir, slug, "musica")
    rc = faz(outdir, slug, ["musica"], sim=True, reg=_reg_fake(ProvFake()))
    assert rc == 0
    e = carregar_estado(outdir / slug)
    assert e["partes"]["musica"]["estado"] == "revisao"
    assert e["partes"]["musica"]["artefato"] == "faixa.mp3"
    assert e["custo_total_usd"]["gasto"] == 0.08     # o custo conta na geração
    idx = json.loads((outdir / "index.jsonl").read_text().splitlines()[0])
    assert idx["estados"]["musica"] == "revisao"


def test_sem_revisao_vai_direto_pra_pronto(outdir, slug):
    aprovar_parte(outdir, slug, "musica")
    rc = faz(outdir, slug, ["musica"], sim=True, sem_revisao=True, reg=_reg_fake(ProvFake()))
    assert rc == 0
    assert carregar_estado(outdir / slug)["partes"]["musica"]["estado"] == "pronto"


def test_faz_parte_nao_aprovada_erra_uso(outdir, slug):
    assert faz(outdir, slug, ["musica"], sim=True, reg=_reg_fake(ProvFake())) == 1


def test_erro_de_provider_nao_derruba_e_exit_2(outdir, slug):
    aprovar_parte(outdir, slug, "musica")
    rc = faz(outdir, slug, ["musica"], sim=True, reg=_reg_fake(ProvFake(ok=False)))
    assert rc == 2
    e = carregar_estado(outdir / slug)
    assert e["partes"]["musica"]["estado"] == "erro"
    assert e["partes"]["musica"]["erro"]["msg"] == "boom"


def test_teto_pula_parte_exit_3(outdir, slug):
    aprovar_parte(outdir, slug, "musica")
    w = outdir / slug
    e = carregar_estado(w)
    e["teto_usd"] = 0.01
    from src.estado import salvar_estado
    salvar_estado(w, e)
    rc = faz(outdir, slug, ["musica"], sim=True, reg=_reg_fake(ProvFake()))
    assert rc == 3
    assert carregar_estado(w)["partes"]["musica"]["estado"] == "aprovado"


class ProvDuasFaixas(ProvFake):
    """O Suno entrega DUAS: as duas ficam no disco, pagas no mesmo custo."""

    def gerar(self, modelo, params, workdir):
        a = workdir / "faixa-1.mp3"
        a.write_bytes(b"x")
        (workdir / "faixa-2.mp3").write_bytes(b"y")
        return Resultado(a, 0.08, {"kie_task_id": "T1"})


def test_recibo_declara_a_segunda_faixa(outdir, slug, capsys):
    """A faixa-2 existia e nunca era ouvida — o recibo só declarava a escolhida.

    O bot entrega o que o recibo declara (MVD#96, 2026-08-22): sem a linha
    `musica_alt:`, a segunda variação fica no disco, paga, e ninguém sabe.
    """
    aprovar_parte(outdir, slug, "musica")
    faz(outdir, slug, ["musica"], sim=True, sem_revisao=True, reg=_reg_fake(ProvDuasFaixas()))
    linhas = capsys.readouterr().out.splitlines()
    assert f"musica: {outdir / slug / 'faixa-1.mp3'}" in linhas
    assert f"musica_alt: {outdir / slug / 'faixa-2.mp3'}" in linhas


def test_uma_faixa_so_nao_inventa_alternativa(outdir, slug, capsys):
    aprovar_parte(outdir, slug, "musica")
    faz(outdir, slug, ["musica"], sim=True, sem_revisao=True, reg=_reg_fake(ProvFake()))
    saida = capsys.readouterr().out
    assert "musica_alt:" not in saida

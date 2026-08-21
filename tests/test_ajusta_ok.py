import json
import pytest
from src.planner import gerar_plano, ajustar_parte, aprovar_parte
from src.estado import carregar_estado, TransicaoInvalida


def _fake_llm(plano):
    return lambda prompt: json.dumps(plano)


def _fake_ajuste(secao):
    return lambda prompt: json.dumps(secao)


@pytest.fixture
def slug_pronto(outdir, plano_ok):
    gerar_plano("rock feminino", "teste-rock", {}, outdir, chamar_llm=_fake_llm(plano_ok))
    return "teste-rock"


def test_ok_abre_portao(outdir, slug_pronto):
    aprovar_parte(outdir, slug_pronto, "musica")
    e = carregar_estado(outdir / slug_pronto)
    assert e["partes"]["musica"]["estado"] == "aprovado"


def test_ajusta_reescreve_so_a_parte_e_mostra_diff(outdir, slug_pronto, plano_ok):
    nova = dict(plano_ok["capa"], conceito="Novo conceito de capa")
    diff = ajustar_parte(outdir, slug_pronto, "capa", "muda o conceito",
                         chamar_llm=_fake_ajuste(nova))
    assert "Novo conceito" in diff
    plano = json.loads((outdir / slug_pronto / "plano.json").read_text())
    assert plano["capa"]["conceito"] == "Novo conceito de capa"
    assert plano["musica"] == plano_ok["musica"]


def test_ajusta_derruba_aprovacao(outdir, slug_pronto, plano_ok):
    aprovar_parte(outdir, slug_pronto, "capa")
    ajustar_parte(outdir, slug_pronto, "capa", "x",
                  chamar_llm=_fake_ajuste(plano_ok["capa"] | {"conceito": "outro"}))
    e = carregar_estado(outdir / slug_pronto)
    assert e["partes"]["capa"]["estado"] == "planejado"
    assert e["partes"]["capa"]["ajustes"] == 1


def test_ajusta_recusa_mudar_letra_final(outdir, plano_ok):
    plano_ok["musica"]["letra"] = {"origem": "final_usuario", "texto": "IMUTÁVEL",
                                   "texto_original": None, "idioma": "pt-BR"}
    gerar_plano("x", "s-lei", {}, outdir, chamar_llm=_fake_llm(plano_ok))
    mexida = json.loads(json.dumps(plano_ok["musica"]))
    mexida["letra"]["texto"] = "TROCADA"
    with pytest.raises(ValueError, match="final_usuario"):
        ajustar_parte(outdir, "s-lei", "musica", "troca a letra",
                      chamar_llm=_fake_ajuste(mexida))


def test_ok_duas_vezes_erra(outdir, slug_pronto):
    aprovar_parte(outdir, slug_pronto, "musica")
    with pytest.raises(TransicaoInvalida):
        aprovar_parte(outdir, slug_pronto, "musica")


# `--aprovar` é o que o FLUXO DO BOT usa: quem abriu o portão no chat aprovou o
# plano inteiro, então a fase promove `planejado → aprovado` sozinha. Nasceu com
# o evento ERRADO (`aprova`, que é o portão do artefato lá na frente) e derrubou
# a fase de música do MVD#91 com TransicaoInvalida — sem teste que a exercitasse.
def test_aprovar_promove_planejado_e_gera(outdir, slug_pronto):
    from src.executor import faz
    from tests.test_executor import ProvFake, _reg_fake
    from src.estado import carregar_estado as ler

    r = faz(outdir, slug_pronto, ["musica"], sim=True, sem_revisao=True,
            aprovar=True, reg=_reg_fake(ProvFake()))
    assert r == 0
    assert ler(outdir / slug_pronto)["partes"]["musica"]["estado"] == "pronto"


def test_aprovar_e_idempotente_em_parte_ja_aprovada(outdir, slug_pronto):
    """Retentativa não pode morrer em TransicaoInvalida."""
    from src.estado import salvar_estado, transicao
    from src.executor import faz
    from tests.test_executor import ProvFake, _reg_fake

    w = outdir / slug_pronto
    e = carregar_estado(w)
    transicao(e, "musica", "ok")          # já aprovada
    salvar_estado(w, e)
    assert faz(outdir, slug_pronto, ["musica"], sim=True, sem_revisao=True,
               aprovar=True, reg=_reg_fake(ProvFake())) == 0

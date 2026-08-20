"""Portão de artefato: nada vira `pronto` sem você olhar."""
import pytest

from src.estado import novo_estado, transicao, TransicaoInvalida
from src.esquemas import validar_estado


def test_gerando_vai_para_revisao_nao_para_pronto():
    e = novo_estado("s")
    transicao(e, "capa", "ok")
    transicao(e, "capa", "faz")
    transicao(e, "capa", "revisar", artefato="capa.png", custo_real=0.0)
    assert e["partes"]["capa"]["estado"] == "revisao"
    assert e["partes"]["capa"]["artefato"] == "capa.png"
    assert validar_estado(e) == []


def test_aprova_fecha_a_parte():
    e = novo_estado("s")
    transicao(e, "capa", "ok")
    transicao(e, "capa", "faz")
    transicao(e, "capa", "revisar", artefato="capa.png", custo_real=0.0)
    transicao(e, "capa", "aprova")
    assert e["partes"]["capa"]["estado"] == "pronto"


def test_reprova_volta_pra_aprovado_pra_regerar():
    e = novo_estado("s")
    transicao(e, "clipe", "ok")
    transicao(e, "clipe", "faz")
    transicao(e, "clipe", "revisar", artefato="clipe.mp4", custo_real=0.0)
    transicao(e, "clipe", "reprova")
    assert e["partes"]["clipe"]["estado"] == "aprovado"   # pronto pra novo `faz`


def test_nao_da_pra_aprovar_o_que_nao_esta_em_revisao():
    e = novo_estado("s")
    with pytest.raises(TransicaoInvalida):
        transicao(e, "musica", "aprova")


def test_ajusta_a_partir_da_revisao_volta_pro_plano():
    e = novo_estado("s")
    transicao(e, "musica", "ok")
    transicao(e, "musica", "faz")
    transicao(e, "musica", "revisar", artefato="faixa-1.mp3", custo_real=0.08)
    transicao(e, "musica", "ajusta")
    assert e["partes"]["musica"]["estado"] == "planejado"


def test_custo_conta_na_revisao_nao_na_aprovacao():
    """O dinheiro sai quando gera, não quando você aprova."""
    e = novo_estado("s")
    transicao(e, "musica", "ok")
    transicao(e, "musica", "faz")
    transicao(e, "musica", "revisar", artefato="faixa-1.mp3", custo_real=0.08)
    assert e["custo_total_usd"]["gasto"] == 0.08
    transicao(e, "musica", "aprova")
    assert e["custo_total_usd"]["gasto"] == 0.08          # não dobra

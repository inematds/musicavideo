import json
import pytest
from pathlib import Path
from src.estado import (novo_estado, carregar_estado, salvar_estado,
                        transicao, TransicaoInvalida)
from src.esquemas import validar_estado


def test_novo_estado_valida(outdir):
    e = novo_estado("meu-slug")
    assert validar_estado(e) == []
    assert all(e["partes"][p]["estado"] == "planejado" for p in ("musica", "capa", "clipe"))


def test_fluxo_feliz():
    e = novo_estado("s")
    transicao(e, "musica", "ok")
    assert e["partes"]["musica"]["estado"] == "aprovado"
    assert e["partes"]["musica"]["aprovado_em"] is not None
    transicao(e, "musica", "faz")
    assert e["partes"]["musica"]["estado"] == "gerando"
    transicao(e, "musica", "pronto", artefato="faixa.mp3", custo_real=0.08)
    assert e["partes"]["musica"]["estado"] == "pronto"
    assert e["partes"]["musica"]["artefato"] == "faixa.mp3"


def test_transicoes_invalidas():
    e = novo_estado("s")
    with pytest.raises(TransicaoInvalida):
        transicao(e, "musica", "faz")
    transicao(e, "musica", "ok")
    transicao(e, "musica", "faz")
    transicao(e, "musica", "pronto", artefato="faixa.mp3", custo_real=0)
    with pytest.raises(TransicaoInvalida):
        transicao(e, "musica", "ajusta")


def test_erro_permite_retry_e_ajusta():
    e = novo_estado("s")
    transicao(e, "capa", "ok")
    transicao(e, "capa", "faz")
    transicao(e, "capa", "erro", motor="agnes:agnes-image-2.1-flash", msg="503")
    assert e["partes"]["capa"]["erro"]["msg"] == "503"
    transicao(e, "capa", "faz")
    assert e["partes"]["capa"]["estado"] == "gerando"
    transicao(e, "capa", "erro", motor="m", msg="x")
    transicao(e, "capa", "ajusta")
    assert e["partes"]["capa"]["estado"] == "planejado"


def test_refaz_de_pronto():
    e = novo_estado("s")
    transicao(e, "clipe", "ok")
    transicao(e, "clipe", "faz")
    transicao(e, "clipe", "pronto", artefato="clipe.mp4", custo_real=0)
    transicao(e, "clipe", "refaz")
    assert e["partes"]["clipe"]["estado"] == "planejado"


def test_persistencia_atomica_e_interrompido(outdir):
    w = outdir / "s"
    w.mkdir()
    e = novo_estado("s")
    transicao(e, "musica", "ok")
    transicao(e, "musica", "faz")
    salvar_estado(w, e)
    assert not list(w.glob("*.tmp"))
    e2 = carregar_estado(w)
    assert e2["partes"]["musica"]["estado"] == "erro"
    assert e2["partes"]["musica"]["erro"]["msg"] == "interrompido"

"""Procedência: de qual produção veio a música desta produção."""
import json
import pytest

from src.planner import (origem_de, descreve_origem, pedido_tem_assunto,
                         contexto_da_origem, montar_contexto)


def _origem_no_disco(base, slug="agora-eu-cobro", mvd="MVD#125"):
    w = base / slug
    w.mkdir(parents=True)
    (w / "faixa-1.mp3").write_bytes(b"a")
    (w / "faixa-2.mp3").write_bytes(b"b")
    (w / "estado.json").write_text(json.dumps({"slug": slug, "mvd": mvd}), encoding="utf-8")
    (w / "plano.json").write_text(json.dumps({
        "slug": slug, "titulo": "Construí em Silêncio",
        "solicitacao": "música de virada, rock feminino",
        "musica": {"estilo": {"genero": "female anthem rock", "bpm": 120},
                   "letra": {"texto": "eu construí em silêncio"}},
        "clipe": {"decupagem": [{"n": 1, "prompt": "NAO DEVE VAZAR"}]}}), encoding="utf-8")
    return w


def test_origem_de_le_o_numero_do_estado_nao_do_nome(tmp_path):
    """Numero muda (5 producoes renumeradas em 2026-09-01); slug e' a chave."""
    _origem_no_disco(tmp_path)
    o = origem_de(tmp_path / "agora-eu-cobro/faixa-2.mp3", tmp_path)
    assert o == {"slug": "agora-eu-cobro", "faixa": "faixa-2.mp3",
                 "mvd": "MVD#125", "titulo": "Construí em Silêncio"}
    assert descreve_origem(o) == ("MVD#125 — Construí em Silêncio "
                                  "(agora-eu-cobro), faixa 2")


def test_arquivo_fora_do_acervo_nao_tem_origem(tmp_path):
    assert origem_de("/tmp/qualquer.mp3", tmp_path) is None


def test_pedido_so_com_flag_e_pedido_sem_assunto():
    assert not pedido_tem_assunto("--faixa-pronta MVD#125:2")
    assert not pedido_tem_assunto("--faixa-pronta /tmp/a.mp3 --idioma pt-BR")
    assert pedido_tem_assunto("clipe mais escuro, foco na cantora --faixa-pronta MVD#125:2")


def test_contexto_da_origem_pede_decupagem_nova_sem_mostrar_a_antiga(tmp_path):
    """Mostrar a decupagem da origem e' como ela seria copiada."""
    _origem_no_disco(tmp_path)
    o = origem_de(tmp_path / "agora-eu-cobro/faixa-1.mp3", tmp_path)
    ctx = contexto_da_origem(o, tmp_path)
    assert "DECUPAGEM NOVA" in ctx.upper()
    assert "eu construí em silêncio" in ctx      # letra: descreve a musica
    assert "female anthem rock" in ctx           # estilo medido
    assert "NAO DEVE VAZAR" not in ctx           # a decupagem da origem NAO entra


def test_sem_assunto_o_contexto_puxa_a_origem(tmp_path, monkeypatch):
    _origem_no_disco(tmp_path)
    monkeypatch.setattr("src.planner.duracao_de", lambda a: 185)
    o = origem_de(tmp_path / "agora-eu-cobro/faixa-2.mp3", tmp_path)
    opts = {"faixa_pronta": str(tmp_path / "agora-eu-cobro/faixa-2.mp3"), "origem": o}
    ctx = montar_contexto("--faixa-pronta MVD#125:2", opts, tmp_path)
    assert "DECUPAGEM NOVA" in ctx.upper()
    assert "MÚSICA JÁ EXISTE" in ctx


def test_com_assunto_o_texto_do_pedido_manda(tmp_path, monkeypatch):
    """Quem escreve um pedido junto nao quer o assunto da origem por cima."""
    _origem_no_disco(tmp_path)
    monkeypatch.setattr("src.planner.duracao_de", lambda a: 185)
    o = origem_de(tmp_path / "agora-eu-cobro/faixa-2.mp3", tmp_path)
    opts = {"faixa_pronta": str(tmp_path / "agora-eu-cobro/faixa-2.mp3"), "origem": o}
    ctx = montar_contexto("clipe noturno na chuva, so a cantora e o carro", opts, tmp_path)
    assert "clipe noturno na chuva" in ctx
    assert "pedido original" not in ctx          # a origem nao sobrepoe o pedido


def test_indice_carrega_a_origem_para_o_painel(tmp_path):
    from src.indexer import linha_de
    plano = {"slug": "s", "titulo": "t", "criado_em": "2026-09-01", "solicitacao": "x",
             "estilo_ref": "", "origem": {"slug": "agora-eu-cobro", "mvd": "MVD#125",
                                          "faixa": "faixa-2.mp3", "titulo": "Construí em Silêncio"},
             "musica": {"estilo": {"genero": "g", "bpm": 1, "tom": "C", "mood": []}, "motor": "m"},
             "capa": {"motor": "m"}, "clipe": {"motor": "m"}}
    estado = {"mvd": "MVD#154", "custo_total_usd": {"gasto": 0.0},
              "partes": {p: {"estado": "pronto"} for p in ("musica", "capa", "clipe")}}
    assert linha_de(plano, estado)["origem"]["slug"] == "agora-eu-cobro"

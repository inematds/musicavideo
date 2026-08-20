"""A faixa real quase nunca tem a duração que o plano chutou."""
import json
import pytest
from pathlib import Path

from src.planner import reajustar_decupagem, precisa_reajuste


def _decup(n, dur=5):
    return [{"n": i, "secao": "refrão", "duracao_s": dur, "camera": "c",
             "descricao": f"d{i}", "prompt": f"shot {i}"} for i in range(1, n + 1)]


def test_diferenca_pequena_nao_mexe(plano_ok):
    plano_ok["clipe"]["decupagem"] = _decup(36)      # 180s
    assert precisa_reajuste(plano_ok, 182.0) is False   # 2s: dentro de um shot


def test_faixa_bem_mais_longa_pede_reajuste(plano_ok):
    plano_ok["clipe"]["decupagem"] = _decup(36)      # 180s
    assert precisa_reajuste(plano_ok, 210.0) is True


def test_faixa_mais_curta_tambem_pede(plano_ok):
    plano_ok["clipe"]["decupagem"] = _decup(36)
    assert precisa_reajuste(plano_ok, 150.0) is True


def test_reajuste_pede_a_duracao_certa_ao_planejador(outdir, plano_ok):
    plano_ok["clipe"]["decupagem"] = _decup(36)
    w = outdir / "s"
    w.mkdir(parents=True)
    (w / "plano.json").write_text(json.dumps(plano_ok), encoding="utf-8")
    visto = {}

    def fake_llm(prompt):
        visto["prompt"] = prompt
        novo = dict(plano_ok["clipe"], decupagem=_decup(42))     # 210s
        return json.dumps(novo)

    plano = reajustar_decupagem(w, 210.0, chamar_llm=fake_llm)
    assert "210" in visto["prompt"]                    # disse a duração real
    assert len(plano["clipe"]["decupagem"]) == 42
    gravado = json.loads((w / "plano.json").read_text(encoding="utf-8"))
    assert len(gravado["clipe"]["decupagem"]) == 42    # persistiu


def test_reajuste_recusa_decupagem_que_nao_cobre(outdir, plano_ok):
    plano_ok["clipe"]["decupagem"] = _decup(36)
    w = outdir / "s2"
    w.mkdir(parents=True)
    (w / "plano.json").write_text(json.dumps(plano_ok), encoding="utf-8")

    def llm_teimoso(prompt):
        return json.dumps(dict(plano_ok["clipe"], decupagem=_decup(10)))   # 50s

    with pytest.raises(ValueError, match="cobre"):
        reajustar_decupagem(w, 210.0, chamar_llm=llm_teimoso)

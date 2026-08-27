"""O número da produção: atribuído uma vez, nunca renumerado."""
import json

import pytest

from src import mvd
from src.estado import novo_estado, salvar_estado


def _producao(base, slug, criado_em="2026-01-01T00:00:00-03:00"):
    w = base / slug
    w.mkdir(parents=True)
    salvar_estado(w, novo_estado(slug))
    (w / "plano.json").write_text(json.dumps({"slug": slug, "criado_em": criado_em}),
                                  encoding="utf-8")
    return w


def test_atribui_e_grava_no_estado(tmp_path):
    _producao(tmp_path, "primeira")
    assert mvd.atribuir(tmp_path, "primeira") == "MVD-001"
    est = json.loads((tmp_path / "primeira" / "estado.json").read_text(encoding="utf-8"))
    assert est["mvd"] == "MVD-001"


def test_nao_renumera_quem_ja_tem(tmp_path):
    """É a regra inteira: número que muda não serve para citar produção nenhuma."""
    _producao(tmp_path, "velha")
    mvd.atribuir(tmp_path, "velha")
    _producao(tmp_path, "nova")
    mvd.atribuir(tmp_path, "nova")
    mvd.numerar_acervo(tmp_path)
    assert mvd.atribuir(tmp_path, "velha") == "MVD-001"
    assert mvd.atribuir(tmp_path, "nova") == "MVD-002"


def test_apagar_producao_nao_reaproveita_o_numero(tmp_path):
    """O buraco fica. Reaproveitar faria dois materiais diferentes com o mesmo
    nome — e o número é justamente o que se cita depois que a pasta sumiu."""
    _producao(tmp_path, "a")
    _producao(tmp_path, "b")
    mvd.numerar_acervo(tmp_path)
    assert mvd.usados(tmp_path) == {"a": 1, "b": 2}
    import shutil
    shutil.rmtree(tmp_path / "b")
    _producao(tmp_path, "c")
    assert mvd.atribuir(tmp_path, "c") == "MVD-003"


def test_numera_na_ordem_de_criacao_nao_na_alfabetica(tmp_path):
    _producao(tmp_path, "zebra", "2026-01-01T00:00:00-03:00")
    _producao(tmp_path, "abelha", "2026-06-01T00:00:00-03:00")
    assert mvd.numerar_acervo(tmp_path) == [("MVD-001", "zebra"), ("MVD-002", "abelha")]


def test_pasta_sem_estado_nao_ganha_numero(tmp_path):
    """Derivado de recorte e pasta de teste não são produção: numerar só faria
    buraco na sequência."""
    (tmp_path / "recorte-variado").mkdir()
    assert mvd.atribuir(tmp_path, "recorte-variado") is None
    assert mvd.numerar_acervo(tmp_path) == []


def test_resolver_aceita_mvd_e_slug(tmp_path):
    _producao(tmp_path, "hands-to-the-sky")
    mvd.numerar_acervo(tmp_path)
    assert mvd.resolver(tmp_path, "MVD-001") == "hands-to-the-sky"
    assert mvd.resolver(tmp_path, "mvd-001") == "hands-to-the-sky"
    assert mvd.resolver(tmp_path, "hands-to-the-sky") == "hands-to-the-sky"
    assert mvd.resolver(tmp_path, "MVD-999") is None
    assert mvd.resolver(tmp_path, "nao-existe") is None


@pytest.mark.parametrize("txt,esperado", [
    ("MVD-014", 14), ("mvd-002", 2), ("MVD-x", None), ("", None), (None, None),
    ("014", None),
])
def test_numero_de(txt, esperado):
    assert mvd.numero_de(txt) == esperado

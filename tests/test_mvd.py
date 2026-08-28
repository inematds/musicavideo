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
    assert mvd.atribuir(tmp_path, "primeira", {}) == "MVD#1"
    est = json.loads((tmp_path / "primeira" / "estado.json").read_text(encoding="utf-8"))
    assert est["mvd"] == "MVD#1"


def test_nao_renumera_quem_ja_tem(tmp_path):
    """É a regra inteira: número que muda não serve para citar produção nenhuma."""
    _producao(tmp_path, "velha")
    mvd.atribuir(tmp_path, "velha", {})
    _producao(tmp_path, "nova")
    mvd.atribuir(tmp_path, "nova", {})
    assert mvd.atribuir(tmp_path, "velha", {}) == "MVD#1"
    assert mvd.atribuir(tmp_path, "nova", {}) == "MVD#2"


def test_apagar_producao_nao_reaproveita_o_numero(tmp_path):
    """O buraco fica. Reaproveitar faria dois materiais diferentes com o mesmo
    nome — e o número é justamente o que se cita depois que a pasta sumiu."""
    _producao(tmp_path, "a")
    _producao(tmp_path, "b")
    mvd.atribuir(tmp_path, "a", {})
    mvd.atribuir(tmp_path, "b", {})
    assert mvd.usados(tmp_path) == {"a": 1, "b": 2}
    import shutil
    shutil.rmtree(tmp_path / "b")
    _producao(tmp_path, "c")
    assert mvd.atribuir(tmp_path, "c", {}) == "MVD#3"


def test_numera_na_ordem_de_criacao_nao_na_alfabetica(tmp_path, monkeypatch):
    _producao(tmp_path, "zebra", "2026-01-01T00:00:00-03:00")
    _producao(tmp_path, "abelha", "2026-06-01T00:00:00-03:00")
    monkeypatch.setattr(mvd, "numeros_do_bot", lambda db=None: {})
    assert mvd.numerar_acervo(tmp_path) == [("MVD#1", "zebra"), ("MVD#2", "abelha")]


def test_pasta_sem_estado_nao_ganha_numero(tmp_path, monkeypatch):
    """Derivado de recorte e pasta de teste não são produção: numerar só faria
    buraco na sequência."""
    (tmp_path / "recorte-variado").mkdir()
    assert mvd.atribuir(tmp_path, "recorte-variado", {}) is None
    monkeypatch.setattr(mvd, "numeros_do_bot", lambda db=None: {})
    assert mvd.numerar_acervo(tmp_path) == []


def test_resolver_aceita_mvd_e_slug(tmp_path):
    _producao(tmp_path, "hands-to-the-sky")
    mvd.atribuir(tmp_path, "hands-to-the-sky", {})
    assert mvd.resolver(tmp_path, "MVD#1") == "hands-to-the-sky"
    assert mvd.resolver(tmp_path, "mvd-1") == "hands-to-the-sky"
    assert mvd.resolver(tmp_path, "hands-to-the-sky") == "hands-to-the-sky"
    assert mvd.resolver(tmp_path, "MVD-999") is None
    assert mvd.resolver(tmp_path, "nao-existe") is None


@pytest.mark.parametrize("txt,esperado", [
    ("MVD#122", 122), ("MVD-014", 14), ("mvd-002", 2), ("MVD-x", None), ("", None),
    (None, None), ("014", None),
])
def test_numero_de(txt, esperado):
    assert mvd.numero_de(txt) == esperado


# --------------------------------------------- o número é o do bot, não nosso
def _banco_do_bot(tmp_path, linhas):
    import sqlite3
    db = tmp_path / "bot.db"
    con = sqlite3.connect(db)
    con.execute("create table fluxos (id integer, prefixo text, slug text)")
    con.executemany("insert into fluxos values (?,?,?)",
                    [(i, "MVD", s) for i, s in linhas])
    con.commit()
    con.close()
    return db


def test_casa_pasta_com_fluxo_pelo_prefixo_do_slug(tmp_path):
    """O bot guarda o slug INTEIRO; a pasta usa os 40 primeiros caracteres."""
    db = _banco_do_bot(tmp_path, [(122, "mulher-e-homens-muito-bem-vestido-elegante-o-clipe-muito-mov")])
    do_bot = mvd.numeros_do_bot(db)
    assert mvd.numero_do_fluxo("mulher-e-homens-muito-bem-vestido-elegan", do_bot) == 122
    assert mvd.numero_do_fluxo("outra-coisa-qualquer", do_bot) is None


def test_producao_do_bot_herda_o_numero_dele(tmp_path):
    """Dois "MVD 25" falando de produções diferentes é o oposto do que um
    identificador serve."""
    db = _banco_do_bot(tmp_path, [(122, "cancao-de-teste-com-slug-bem-comprido-para-truncar")])
    _producao(tmp_path, "cancao-de-teste-com-slug-bem-comprido-pa")
    assert mvd.atribuir(tmp_path, "cancao-de-teste-com-slug-bem-comprido-pa",
                        mvd.numeros_do_bot(db)) == "MVD#122"


def test_producao_fora_do_bot_nasce_acima_do_topo_dele(tmp_path):
    """Senão o próximo fluxo do bot colidiria com o que se inventou aqui."""
    db = _banco_do_bot(tmp_path, [(124, "outra-producao-qualquer-do-bot")])
    _producao(tmp_path, "nasceu-no-terminal")
    assert mvd.atribuir(tmp_path, "nasceu-no-terminal",
                        mvd.numeros_do_bot(db)) == "MVD#125"


def test_numero_de_aceita_as_duas_grafias():
    assert mvd.numero_de("MVD#122") == 122
    assert mvd.numero_de("mvd-122") == 122
    assert mvd.numero_de("MVD122") == 122
    assert mvd.numero_de("122") is None


def test_duas_pastas_do_mesmo_fluxo_nao_dividem_o_numero(tmp_path):
    """Reprocessar gera pasta irmã (`...-2`) que casa com o mesmo fluxo do bot.
    São materiais diferentes: só a primeira fica com o número do fluxo."""
    db = _banco_do_bot(tmp_path, [(91, "para-a-musica-eu-acho-que-existe-uma-narrativa-boa")])
    do_bot = mvd.numeros_do_bot(db)
    _producao(tmp_path, "para-a-musica-eu-acho-que-existe-uma-nar")
    _producao(tmp_path, "para-a-musica-eu-acho-que-existe-uma-nar-2")
    assert mvd.atribuir(tmp_path, "para-a-musica-eu-acho-que-existe-uma-nar", do_bot) == "MVD#91"
    assert mvd.atribuir(tmp_path, "para-a-musica-eu-acho-que-existe-uma-nar-2", do_bot) == "MVD#92"


def test_dois_fluxos_com_o_mesmo_slug_nao_trocam_de_numero(tmp_path):
    """MVD#135 e MVD#137 nasceram do MESMO pedido — slug idêntico no bot.

    A pasta base é do primeiro fluxo e a `-2` do segundo. Antes, o dict de
    valor único apagava o 135 e a pasta base herdava o 137 (do irmão).
    """
    slug_bot = "quero-contar-a-historia-da-africa-por-outro-angulo-nao-atrav"
    db = _banco_do_bot(tmp_path, [(135, slug_bot), (137, slug_bot)])
    do_bot = mvd.numeros_do_bot(db)
    base = "quero-contar-a-historia-da-africa-por-ou"
    assert mvd.numero_do_fluxo(base, do_bot) == 135
    assert mvd.numero_do_fluxo(base + "-2", do_bot) == 137
    # sem um terceiro fluxo, a `-3` não herda nada: ganha número novo
    assert mvd.numero_do_fluxo(base + "-3", do_bot) is None

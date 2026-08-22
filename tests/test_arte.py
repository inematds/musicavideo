"""A arte da capa: título composto por cima da imagem, determinístico."""
import json

import pytest
from PIL import Image

from src.arte import (compor_capa, quebrar, contraste, cor_do_texto,
                      tipografia_de, ArteError, BRANCO, PRETO)


def _fundo(tmp_path, cor=(20, 20, 30), lado=1024):
    p = tmp_path / "crua.png"
    Image.new("RGB", (lado, lado), cor).save(p)
    return p


def _difere(a: Image.Image, b: Image.Image) -> int:
    return sum(1 for x, y in zip(a.convert("RGB").getdata(),
                                 b.convert("RGB").getdata()) if x != y)


def test_todo_template_declara_tipografia():
    d = json.loads((__import__("src.arte", fromlist=["RAIZ"]).RAIZ /
                    "data/templates-capa.json").read_text(encoding="utf-8"))
    for t in d["templates"]:
        tipo = t["tipografia"]
        assert tipo["fonte"] and tipo["posicao"] in ("topo", "centro", "base")
        assert 0 < tipo["largura_alvo"] <= 1


def test_dominante_nao_pede_texto_ao_gerador():
    """Quem escreve o título é a composição — o gerador desenhava garatuja."""
    d = json.loads((__import__("src.arte", fromlist=["RAIZ"]).RAIZ /
                    "data/templates-capa.json").read_text(encoding="utf-8"))
    t = next(x for x in d["templates"] if x["id"] == "tipografia-dominante")
    assert "text" in t["negativo_base"]
    assert "typography as the main subject" not in t["prompt_base"]


def test_quebra_equilibrada():
    assert quebrar("VOZ", 2) == ["VOZ"]
    linhas = quebrar("A NOITE INTEIRA SEM DORMIR", 2)
    assert len(linhas) == 2
    assert abs(len(linhas[0]) - len(linhas[1])) <= 6
    assert " ".join(linhas) == "A NOITE INTEIRA SEM DORMIR"


def test_titulo_marca_a_imagem(tmp_path):
    bruta = _fundo(tmp_path)
    destino = tmp_path / "capa.png"
    compor_capa(bruta, "Chuva de Verão", ["#ffcc00"], "paisagem-simbolica", destino)
    assert _difere(Image.open(bruta), Image.open(destino)) > 5000


def test_posicao_obedece_o_template(tmp_path):
    """topo escreve em cima, base escreve embaixo — o template é quem manda."""
    bruta = _fundo(tmp_path)
    def faixa_alterada(template_id):
        d = tmp_path / f"{template_id}.png"
        compor_capa(bruta, "Chuva de Verão", ["#ffcc00"], template_id, d)
        a, b = Image.open(bruta).convert("RGB"), Image.open(d).convert("RGB")
        H = a.height
        ys = [i // a.width for i, (x, y) in enumerate(zip(a.getdata(), b.getdata()))
              if x != y]
        return sum(ys) / len(ys) / H
    assert faixa_alterada("paisagem-simbolica") < 0.4      # topo
    assert faixa_alterada("retrato-centralizado") > 0.6    # base


def test_titulo_grande_ocupa_a_largura_pedida(tmp_path):
    """`tipografia-dominante` promete 60%+ do quadro — tem que cumprir."""
    bruta = _fundo(tmp_path)
    destino = tmp_path / "capa.png"
    compor_capa(bruta, "SILÊNCIO", ["#ffffff"], "tipografia-dominante", destino)
    a, b = Image.open(bruta).convert("RGB"), Image.open(destino).convert("RGB")
    xs = [i % a.width for i, (x, y) in enumerate(zip(a.getdata(), b.getdata()))
          if x != y]
    largura = (max(xs) - min(xs)) / a.width
    assert largura >= 0.6


def test_cor_ilegivel_da_paleta_e_descartada(tmp_path):
    escuro = (10, 10, 10)
    assert cor_do_texto(escuro, ["#0a0a0a"]) == BRANCO      # paleta somia no fundo
    assert cor_do_texto((245, 245, 245), ["#111111"]) == (17, 17, 17)
    assert cor_do_texto((245, 245, 245), []) == PRETO
    assert contraste(BRANCO, PRETO) > 15


def test_sem_titulo_entrega_a_imagem_intacta(tmp_path):
    bruta = _fundo(tmp_path)
    destino = tmp_path / "capa.png"
    compor_capa(bruta, "   ", [], "minimal-abstrato", destino)
    assert _difere(Image.open(bruta), Image.open(destino)) == 0


def test_recompor_nao_empilha_texto(tmp_path):
    """Sempre parte da crua: rodar duas vezes dá o MESMO pixel."""
    bruta = _fundo(tmp_path)
    d1, d2 = tmp_path / "a.png", tmp_path / "b.png"
    compor_capa(bruta, "Chuva de Verão", ["#ffcc00"], "retrato-centralizado", d1)
    compor_capa(bruta, "Chuva de Verão", ["#ffcc00"], "retrato-centralizado", d2)
    assert _difere(Image.open(d1), Image.open(d2)) == 0


def test_template_desconhecido_cai_no_padrao(tmp_path):
    assert tipografia_de("nao-existe")["fonte"]
    bruta = _fundo(tmp_path)
    destino = tmp_path / "capa.png"
    compor_capa(bruta, "Qualquer Coisa", [], "nao-existe", destino)
    assert destino.exists()


def test_imagem_crua_faltando_e_erro_claro(tmp_path):
    with pytest.raises(ArteError):
        compor_capa(tmp_path / "nao-existe.png", "X", [], "minimal-abstrato",
                    tmp_path / "capa.png")

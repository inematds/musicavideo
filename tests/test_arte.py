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


# ------------------------------------------------------- estilo CARTAZ

def test_template_de_cena_e_poster_e_o_de_texto_nao():
    """Cartaz brigaria com um template cuja imagem JÁ é o título."""
    assert tipografia_de("paisagem-simbolica")["estilo"] == "poster"
    assert tipografia_de("retrato-centralizado")["estilo"] == "poster"
    assert tipografia_de("tipografia-dominante")["estilo"] == "simples"
    assert tipografia_de("minimal-abstrato")["estilo"] == "simples"


def test_compor_roteia_pelo_estilo_do_template(tmp_path):
    from src.arte import compor
    bruta = _fundo(tmp_path)
    a, b = tmp_path / "poster.png", tmp_path / "simples.png"
    compor(bruta, "Chuva de Verão", ["#ffcc00"], "paisagem-simbolica", a)
    compor(bruta, "Chuva de Verão", ["#ffcc00"], "minimal-abstrato", b)
    # o cartaz escurece a base inteira; o simples só escreve o título
    assert _difere(Image.open(bruta), Image.open(a)) > _difere(Image.open(bruta), Image.open(b))


def test_poster_escreve_tagline_e_creditos(tmp_path):
    from src.arte import compor_poster
    bruta = _fundo(tmp_path)
    com = tmp_path / "com.png"
    sem = tmp_path / "sem.png"
    compor_poster(bruta, "Chuva de Verão", com, tagline="o frio não perdoa")
    compor_poster(bruta, "Chuva de Verão", sem, tagline="", creditos="")
    assert _difere(Image.open(sem), Image.open(com)) > 1000


def test_selo_de_versao_muda_o_alto_da_imagem(tmp_path):
    """O selo tem que ser visível de longe: ele marca o TOPO, não o rodapé."""
    from src.arte import compor_poster
    bruta = _fundo(tmp_path)
    v1, v2 = tmp_path / "v1.png", tmp_path / "v2.png"
    compor_poster(bruta, "Chuva de Verão", v1, versao=1)
    compor_poster(bruta, "Chuva de Verão", v2, versao=2)
    a, b = Image.open(v1).convert("RGB"), Image.open(v2).convert("RGB")
    ys = [i // a.width for i, (x, y) in enumerate(zip(a.getdata(), b.getdata())) if x != y]
    assert ys, "as duas versões saíram idênticas — o selo não apareceu"
    assert sum(ys) / len(ys) / a.height < 0.35      # a diferença está no alto


def test_poster_sem_titulo_nao_quebra(tmp_path):
    from src.arte import compor_poster
    destino = tmp_path / "x.png"
    compor_poster(_fundo(tmp_path), "  ", destino, versao=1)
    assert destino.exists()

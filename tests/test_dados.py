import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]


def test_templates_capa():
    d = json.loads((RAIZ / "data/templates-capa.json").read_text(encoding="utf-8"))
    assert d["schema_version"] == "1"
    ids = {t["id"] for t in d["templates"]}
    assert ids == {"tipografia-dominante", "retrato-centralizado",
                   "paisagem-simbolica", "minimal-abstrato"}
    for t in d["templates"]:
        assert set(t) == {"id", "nome", "descricao", "composicao",
                          "quando_usar", "prompt_base", "negativo_base",
                          "tipografia"}


def test_templates_clipe():
    d = json.loads((RAIZ / "data/templates-clipe.json").read_text(encoding="utf-8"))
    ids = {t["id"] for t in d["templates"]}
    assert ids == {"performance", "narrativo", "lyric-video", "abstrato-loop"}
    for t in d["templates"]:
        assert set(t) == {"id", "nome", "descricao", "estrutura_shots",
                          "sincronia", "quando_usar"}


def test_fixture_estilos():
    d = json.loads((RAIZ / "tests/fixtures/estilos.json").read_text(encoding="utf-8"))
    assert d["schema_version"] == "1" and len(d["estilos"]) >= 1


def test_estilos_reais_semeados():
    d = json.loads((RAIZ / "data/estilos.json").read_text(encoding="utf-8"))
    ids = {e["id"] for e in d["estilos"]}
    assert {"uplifting-ambient-electronic", "corporate-tech-electro-pop",
            "uplifting-progressive-trance", "anthem-pop-rock",
            "female-anthem-rock"} <= ids
    ea = next(e for e in d["estilos"] if e["id"] == "uplifting-ambient-electronic")
    assert ea["bpm"] == 103 and ea["tom"] == "C maior"
    assert len(ea["prompt_suno_curto"]) <= 260
    assert len(ea["prompt_suno_longo"]) <= 1000
    tr = next(e for e in d["estilos"] if e["id"] == "uplifting-progressive-trance")
    assert tr["bpm"] == 132 and tr["voz"]["presenca"] == "instrumental"
    ap = next(e for e in d["estilos"] if e["id"] == "anthem-pop-rock")
    assert ap["bpm"] is None
    for e in d["estilos"]:
        assert e["fonte"]


# --- painel: derivados e lixeira (2026-08-23) --------------------------------

def test_painel_lista_pasta_derivada_que_nao_esta_no_indice(tmp_path):
    """Recorte não entra no index.jsonl — sem isto ele não aparece em lugar
    nenhum, e o disco enche em silêncio."""
    from src.painel import coletar
    base = tmp_path / "musicavideo"
    (base / "cancao").mkdir(parents=True)
    (base / "cancao" / "clipe.mp4").write_bytes(b"x" * 10)
    (base / "index.jsonl").write_text(
        '{"slug": "cancao", "titulo": "Canção", "criado_em": "2026-08-23"}\n', encoding="utf-8")
    (base / "cancao-variado").mkdir()
    (base / "cancao-variado" / "clipe.mp4").write_bytes(b"y" * 20)
    slugs = {x["slug"]: x for x in coletar(tmp_path)["musicavideo"]}
    assert "cancao-variado" in slugs
    d = slugs["cancao-variado"]
    assert d["derivado"] == "variado" and d["origem"] == "cancao"
    assert d["bytes"] == 20 and slugs["cancao"]["bytes"] == 10


def test_pasta_sem_clipe_nao_vira_card(tmp_path):
    from src.painel import coletar
    base = tmp_path / "musicavideo"
    (base / "so-plano").mkdir(parents=True)
    (base / "so-plano" / "plano.json").write_text("{}", encoding="utf-8")
    assert coletar(tmp_path)["musicavideo"] == []


def test_apagar_move_para_a_lixeira_e_nao_destroi(tmp_path):
    from src.painel import para_lixeira
    base = tmp_path / "musicavideo"
    (base / "cancao-variado" / "raw").mkdir(parents=True)
    (base / "cancao-variado" / "clipe.mp4").write_bytes(b"z")
    destino = para_lixeira(base, "cancao-variado")
    assert not (base / "cancao-variado").exists()
    assert (destino / "clipe.mp4").read_bytes() == b"z"
    assert destino.parent.name == ".lixo"


def test_apagar_recusa_caminho_fora_do_acervo(tmp_path):
    """O painel abre na LAN: caminho é entrada de fora, não vale confiar."""
    import pytest
    from src.painel import para_lixeira
    base = tmp_path / "musicavideo"
    (base / "cancao").mkdir(parents=True)
    (tmp_path / "outro").mkdir()
    for ruim in ("../outro", "/etc", "", ".lixo"):
        with pytest.raises(ValueError):
            para_lixeira(base, ruim)


def test_lixeira_nao_sobrescreve_apagado_anterior(tmp_path):
    from src.painel import para_lixeira
    base = tmp_path / "musicavideo"
    for _ in range(2):
        (base / "cancao").mkdir(parents=True)
        (base / "cancao" / "clipe.mp4").write_bytes(b"z")
        para_lixeira(base, "cancao")
    assert sorted(p.name for p in (base / ".lixo").iterdir()) == ["cancao", "cancao-2"]


def test_url_de_artefato_leva_a_data_para_furar_cache(tmp_path):
    """`capa.png` é sempre `capa.png`: sem carimbo, o navegador serve a versão
    velha e a capa refeita não aparece."""
    from src.painel import coletar
    base = tmp_path / "musicavideo"
    (base / "cancao").mkdir(parents=True)
    (base / "cancao" / "clipe.mp4").write_bytes(b"x")
    (base / "cancao" / "capa.png").write_bytes(b"p")
    (base / "index.jsonl").write_text(
        '{"slug": "cancao", "titulo": "C", "criado_em": "2026-08-23"}\n', encoding="utf-8")
    capa = coletar(tmp_path)["musicavideo"][0]["capa"]
    assert capa.startswith("musicavideo/cancao/capa.png?v=")
    assert capa.split("=")[-1].isdigit()


def test_artefato_ausente_continua_none(tmp_path):
    from src.painel import coletar
    base = tmp_path / "musicavideo"
    (base / "cancao").mkdir(parents=True)
    (base / "cancao" / "clipe.mp4").write_bytes(b"x")
    (base / "index.jsonl").write_text(
        '{"slug": "cancao", "titulo": "C", "criado_em": "2026-08-23"}\n', encoding="utf-8")
    assert coletar(tmp_path)["musicavideo"][0]["capa"] is None


def test_painel_lista_as_duas_faixas_mesmo_com_um_clipe_so(tmp_path):
    """O Suno entrega duas; a segunda ficava invisível quando só um clipe
    estava montado — e é ouvindo as duas que se escolhe qual aprovar."""
    from src.painel import coletar
    base = tmp_path / "musicavideo"
    (base / "cancao").mkdir(parents=True)
    for n in (1, 2):
        (base / "cancao" / f"faixa-{n}.mp3").write_bytes(b"m")
    (base / "cancao" / "clipe.mp4").write_bytes(b"v")
    (base / "cancao" / "estado.json").write_text(json.dumps(
        {"partes": {"musica": {"artefato": "faixa-2.mp3"}}}), encoding="utf-8")
    (base / "index.jsonl").write_text(
        '{"slug": "cancao", "titulo": "C", "criado_em": "2026-08-23"}\n', encoding="utf-8")
    fx = coletar(tmp_path)["musicavideo"][0]["faixas"]
    assert [f["nome"] for f in fx] == ["faixa-1.mp3", "faixa-2.mp3"]
    assert [f["aprovada"] for f in fx] == [False, True]


# --- painel: a nuvem por FAIXA (v2.1) ----------------------------------------

def _prod_com_duas_faixas(base, slug="p"):
    from src.estado import novo_estado, salvar_estado
    w = base / "musicavideo" / slug
    w.mkdir(parents=True)
    for nome in ("faixa-1.mp3", "faixa-2.mp3", "clipe-1.mp4", "clipe-2.mp4", "capa.png"):
        (w / nome).write_bytes(b"x")
    salvar_estado(w, novo_estado(slug))
    (base / "musicavideo" / "index.jsonl").write_text(
        '{"slug": "%s", "titulo": "T"}\n' % slug, encoding="utf-8")
    return w


def test_cada_faixa_carrega_a_propria_situacao_de_nuvem(tmp_path, monkeypatch):
    """O card é de UMA faixa: o selo (e o botão) da nuvem tem de ser dela."""
    from src import nuvem, subida
    from src.painel import coletar
    # `coletar` DRENA A FILA: ver o painel é o gesto que faz a subida começar.
    # Num teste isso vira upload de verdade — travar aqui é parte do teste.
    monkeypatch.setattr(subida, "proxima", lambda base, **k: None)
    monkeypatch.setattr(subida, "iniciar", lambda slug, **k: "fingido")
    w = _prod_com_duas_faixas(tmp_path)
    nuvem.aprovar(w, faixa="1")
    x = coletar(tmp_path)["musicavideo"][0]
    assert {f["n"]: f["nuvem"] for f in x["faixas"]} == {"1": "aprovado", "2": "local"}
    assert {v["n"]: v["nuvem"] for v in x["versoes"]} == {"1": "aprovado", "2": "local"}


def test_rota_da_nuvem_aprova_so_a_faixa_pedida(tmp_path, monkeypatch):
    """A rota é o que o botão do card chama — com `faixa`, ela não pode
    arrastar a outra música junto."""
    import json as _json
    from src import nuvem, painel, subida
    w = _prod_com_duas_faixas(tmp_path)
    monkeypatch.setattr(subida, "iniciar", lambda slug, **k: "fingido")
    corpo = _json.dumps({"slug": "p", "faixa": "2", "aprovar": True}).encode()

    class Fingido(painel.Handler):
        def __init__(self):                      # sem socket: só o miolo
            self.directory = str(tmp_path)
            self.path = "/__nuvem"
            self.headers = {"Content-Length": str(len(corpo))}
            self.rfile = __import__("io").BytesIO(corpo)
            self.enviado = None

        def _envia(self, dados, tipo):
            self.enviado = _json.loads(dados)

    h = Fingido()
    h.do_POST()
    assert h.enviado["ok"] is True
    assert h.enviado["nuvem"] == "subindo"
    assert nuvem.situacao_faixa(w, "2") == "aprovado"
    assert nuvem.situacao_faixa(w, "1") == "local"

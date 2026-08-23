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

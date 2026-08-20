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
                          "quando_usar", "prompt_base", "negativo_base"}


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

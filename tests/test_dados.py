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

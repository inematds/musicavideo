import json
import sys
from src.main import COMANDOS
from src.estado import carregar_estado


def test_tudo_respeita_teto(outdir, plano_ok, monkeypatch):
    import src.planner as pl
    monkeypatch.setattr(pl, "chamar_fable", lambda prompt: json.dumps(plano_ok))

    class ProvCaro:
        nome = "kie"

        def disponivel(self):
            return True, ""

        def estimar_custo(self, m, p):
            return 5.0

        def gerar(self, m, p, w):
            raise AssertionError("não deveria gerar")

    import src.executor as ex
    monkeypatch.setattr(ex, "carregar_registry", lambda: {
        m: {"provider": ProvCaro(), "modelo": {"id": m.split(":")[1], "params": {},
            "custo": {"base_usd": 5.0, "por": "geracao"}}}
        for m in ("kie:suno-v4.5", "agnes:agnes-image-2.1-flash", "agnes:agnes-video-v2.0")})
    rc = COMANDOS["tudo"](["rock de virada", "--teto", "1", "--sim"])
    assert rc == 3
    slug = json.loads((outdir / "index.jsonl").read_text().splitlines()[0])["slug"]
    e = carregar_estado(outdir / slug)
    assert all(p["estado"] == "aprovado" for p in e["partes"].values())

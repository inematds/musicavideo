import json
from pathlib import Path
import providers.agnes as agnes_mod

DECL = json.loads((Path(__file__).resolve().parents[1] / "providers/agnes.models.json").read_text())


def test_capa_posta_size_em_pixels_e_baixa(tmp_path, monkeypatch):
    def fake_http(url, metodo="GET", corpo=None, headers=None, **kw):
        assert url.endswith("/v1/images/generations")
        assert corpo["model"] == "agnes-image-2.1-flash"
        assert corpo["size"] == "1024x1024"
        assert "album cover" in corpo["prompt"]
        return {"data": [{"url": "http://tmp/img.png"}]}

    monkeypatch.setattr(agnes_mod, "http_json", fake_http)
    monkeypatch.setattr(agnes_mod, "baixar",
                        lambda url, destino, **kw: (destino.write_bytes(b"png"), destino)[-1])
    monkeypatch.setattr(agnes_mod, "ler_env_chave", lambda n: "k")
    r = agnes_mod.criar(DECL).gerar(
        "agnes-image-2.1-flash",
        {"tamanho": "1024x1024", "prompt": "album cover, portrait", "prompt_negativo": "text"},
        tmp_path)
    assert r.arquivo == tmp_path / "capa.png" and r.custo_real == 0.0


def test_custo_agnes_e_zero():
    prov = agnes_mod.criar(DECL)
    assert prov.estimar_custo("agnes-image-2.1-flash", {}) == 0.0
    assert prov.estimar_custo("agnes-video-v2.0", {"duracao_shot_s": 10}) == 0.0

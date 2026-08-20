import json
from pathlib import Path
import providers.inemaimg as im

DECL = json.loads((Path(__file__).resolve().parents[1] / "providers/inemaimg.models.json").read_text())


def test_disponivel_sem_servidor_da_motivo(monkeypatch):
    from providers.base import ProviderError
    monkeypatch.setattr(im, "http_json",
                        lambda *a, **k: (_ for _ in ()).throw(ProviderError("rede")))
    ok, motivo = im.criar(DECL).disponivel()
    assert ok is False and "localhost:8000" in motivo


def test_gerar_decodifica_base64(tmp_path, monkeypatch):
    import base64
    monkeypatch.setattr(im, "http_json", lambda url, metodo="GET", corpo=None, **k:
                        {"image": base64.b64encode(b"png-bytes").decode()}
                        if url.endswith("/generate") else {"status": "ok"})
    r = im.criar(DECL).gerar("flux2-klein",
                             {"tamanho": "1024x1024", "prompt": "album cover",
                              "prompt_negativo": ""}, tmp_path)
    assert (tmp_path / "capa.png").read_bytes() == b"png-bytes"

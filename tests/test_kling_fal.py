import json
from pathlib import Path
import providers.kling as kling_mod
import providers.fal as fal_mod

RAIZ = Path(__file__).resolve().parents[1]
DECL_K = json.loads((RAIZ / "providers/kling.models.json").read_text())
DECL_F = json.loads((RAIZ / "providers/fal.models.json").read_text())
DECUP = [{"n": 1, "secao": "i", "duracao_s": 5, "camera": "c", "descricao": "d",
          "prompt": "orbit shot, 5s"}]


def test_kling_custo_por_segundo():
    assert kling_mod.criar(DECL_K).estimar_custo("kling-2.5", {"duracao_shot_s": 10}) == 0.56


def test_kling_contrato_createtask(tmp_path, monkeypatch):
    def fake_http(url, metodo="GET", corpo=None, headers=None, **kw):
        if "createTask" in url:
            assert corpo["model"] == "kling/v2-5-turbo-text-to-video-pro"
            assert corpo["input"]["prompt"] == "orbit shot, 5s"
            return {"data": {"taskId": "K1"}}
        return {"data": {"state": "success",
                         "resultJson": json.dumps({"resultUrls": ["http://x/s.mp4"]})}}

    monkeypatch.setattr(kling_mod, "http_json", fake_http)
    monkeypatch.setattr(kling_mod, "baixar",
                        lambda url, destino, **kw: (destino.parent.mkdir(parents=True, exist_ok=True),
                                                    destino.write_bytes(b"v"), destino)[-1])
    monkeypatch.setattr(kling_mod, "ler_env_chave", lambda n: "k")
    monkeypatch.setattr(kling_mod, "concat_ffmpeg",
                        lambda shots, alvo: (alvo.write_bytes(b"f"), alvo)[-1])
    monkeypatch.setattr(kling_mod.time, "sleep", lambda s: None)
    r = kling_mod.criar(DECL_K).gerar("kling-2.5",
                                      {"resolucao": "720p", "decupagem": DECUP}, tmp_path)
    assert r.arquivo.name == "clipe.mp4" and r.custo_real == 0.28


def test_fal_contrato_queue(tmp_path, monkeypatch):
    def fake_http(url, metodo="GET", corpo=None, headers=None, **kw):
        if metodo == "POST":
            assert "queue.fal.run" in url and headers["Authorization"].startswith("Key ")
            return {"status_url": "http://q/st", "response_url": "http://q/resp"}
        if url == "http://q/st":
            return {"status": "COMPLETED"}
        return {"video": {"url": "http://x/s.mp4"}}

    monkeypatch.setattr(fal_mod, "http_json", fake_http)
    monkeypatch.setattr(fal_mod, "baixar",
                        lambda url, destino, **kw: (destino.parent.mkdir(parents=True, exist_ok=True),
                                                    destino.write_bytes(b"v"), destino)[-1])
    monkeypatch.setattr(fal_mod, "ler_env_chave", lambda n: "k")
    monkeypatch.setattr(fal_mod, "concat_ffmpeg",
                        lambda shots, alvo: (alvo.write_bytes(b"f"), alvo)[-1])
    monkeypatch.setattr(fal_mod.time, "sleep", lambda s: None)
    r = fal_mod.criar(DECL_F).gerar("kling-video-v2.5-turbo-pro",
                                    {"resolucao": "720p", "decupagem": DECUP}, tmp_path)
    assert r.arquivo.name == "clipe.mp4"

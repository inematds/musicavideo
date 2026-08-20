import json
from pathlib import Path
import providers.agnes as agnes_mod

DECL = json.loads((Path(__file__).resolve().parents[1] / "providers/agnes.models.json").read_text())


def test_num_frames_regra_8n1():
    from providers.agnes import num_frames_para
    assert num_frames_para(5, 24) == 121
    assert num_frames_para(3.4, 24) == 81
    assert num_frames_para(30, 24) == 441


def test_gerar_video_shots_poll_concat(tmp_path, monkeypatch):
    posts, polls = [], []

    def fake_http(url, metodo="GET", corpo=None, headers=None, **kw):
        if metodo == "POST":
            posts.append(corpo)
            assert corpo["model"] == "agnes-video-v2.0"
            assert corpo["num_frames"] == 121 and corpo["frame_rate"] == 24
            return {"video_id": f"V{len(posts)}"}
        polls.append(url)
        return {"status": "completed", "video_url": "http://tmp/shot.mp4"}

    monkeypatch.setattr(agnes_mod, "http_json", fake_http)
    monkeypatch.setattr(agnes_mod, "baixar",
                        lambda url, destino, **kw: (destino.parent.mkdir(parents=True, exist_ok=True),
                                                    destino.write_bytes(b"mp4"), destino)[-1])
    monkeypatch.setattr(agnes_mod, "ler_env_chave", lambda n: "k")
    monkeypatch.setattr(agnes_mod.time, "sleep", lambda s: None)
    monkeypatch.setattr(agnes_mod, "concat_ffmpeg",
                        lambda shots, alvo: (alvo.write_bytes(b"final"), alvo)[-1])
    decup = [{"n": 1, "secao": "intro", "duracao_s": 5, "camera": "dolly",
              "descricao": "x", "prompt": "slow dolly-in, workshop at dawn, 5s"},
             {"n": 2, "secao": "refrão", "duracao_s": 5, "camera": "orbit",
              "descricao": "y", "prompt": "orbit around woman, stage light, 5s"}]
    r = agnes_mod.criar(DECL).gerar("agnes-video-v2.0",
                                    {"resolucao": "1312x736", "duracao_shot_s": 5,
                                     "decupagem": decup}, tmp_path)
    assert len(posts) == 2
    assert r.arquivo == tmp_path / "clipe.mp4"
    assert r.meta["shots"] == 2 and r.meta["video_ids"] == ["V1", "V2"]


def test_shot_failed_vira_provider_error(tmp_path, monkeypatch):
    import pytest
    from providers.base import ProviderError
    monkeypatch.setattr(agnes_mod, "ler_env_chave", lambda n: "k")
    monkeypatch.setattr(agnes_mod.time, "sleep", lambda s: None)
    monkeypatch.setattr(agnes_mod, "http_json",
                        lambda url, metodo="GET", corpo=None, headers=None, **k:
                        {"video_id": "V1"} if metodo == "POST"
                        else {"status": "failed", "error": "nsfw"})
    with pytest.raises(ProviderError, match="failed"):
        agnes_mod.criar(DECL).gerar("agnes-video-v2.0",
                                    {"resolucao": "1312x736", "decupagem": [
                                        {"n": 1, "secao": "i", "duracao_s": 5, "camera": "c",
                                         "descricao": "d", "prompt": "p"}]}, tmp_path)

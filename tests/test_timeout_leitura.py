"""Timeout de LEITURA (provedor engasgado) é transitório, não falha.

Custou MVD#103, #119, #122 (ago/2026) e #174, #175 (2026-09-13): o `urlopen`
sobe `TimeoutError` cru quando conecta e fica >timeout sem devolver byte, e
nada pegava — o clipe caía com música e capa já pagas.
"""
import urllib.error
from pathlib import Path

import pytest

import providers.base as base
import providers.agnes as agnes_mod
from providers.base import ProviderError


def _sem_sleep(monkeypatch):
    monkeypatch.setattr(base.time, "sleep", lambda s: None)
    monkeypatch.setattr(agnes_mod.time, "sleep", lambda s: None)


def test_http_json_repete_em_timeout_de_leitura(monkeypatch):
    _sem_sleep(monkeypatch)
    chamadas = []

    class Resp:
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def read(self): return b'{"ok": true}'

    def fake_urlopen(req, timeout=None):
        chamadas.append(1)
        if len(chamadas) < 3:
            raise TimeoutError("The read operation timed out")
        return Resp()

    monkeypatch.setattr(base.urllib.request, "urlopen", fake_urlopen)
    assert base.http_json("http://x/y") == {"ok": True}
    assert len(chamadas) == 3


def test_http_json_esgota_e_vira_provider_error(monkeypatch):
    _sem_sleep(monkeypatch)

    def fake_urlopen(req, timeout=None):
        raise TimeoutError("The read operation timed out")

    monkeypatch.setattr(base.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(ProviderError, match="timeout de leitura"):
        base.http_json("http://x/y", tentativas=2)


def test_baixar_repete_em_timeout(tmp_path, monkeypatch):
    _sem_sleep(monkeypatch)
    n = []

    class Resp:
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def read(self): return b"mp4"

    def fake_urlopen(req, timeout=None):
        n.append(1)
        if len(n) == 1:
            raise TimeoutError("The read operation timed out")
        return Resp()

    monkeypatch.setattr(base.urllib.request, "urlopen", fake_urlopen)
    alvo = base.baixar("http://cdn/x.mp4", tmp_path / "raw" / "x.mp4")
    assert alvo.read_bytes() == b"mp4" and len(n) == 2


def test_baixar_esgota_vira_provider_error(tmp_path, monkeypatch):
    _sem_sleep(monkeypatch)

    def fake_urlopen(req, timeout=None):
        raise urllib.error.URLError("handshake operation timed out")

    monkeypatch.setattr(base.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(ProviderError, match="download falhou"):
        base.baixar("http://cdn/x.mp4", tmp_path / "x.mp4", tentativas=2)


def _adapter(monkeypatch):
    monkeypatch.setattr(agnes_mod, "ler_env_chave", lambda n: "k")
    return agnes_mod.criar({"nome": "agnes", "env_keys": ["AGNES_API_KEY"]})


def test_um_shot_insiste_no_poll_apos_timeout_de_leitura(tmp_path, monkeypatch):
    """Shot aceito; o status engasga uma vez; o shot sai (caso MVD#175)."""
    _sem_sleep(monkeypatch)
    seq = []

    def fake_http(url, metodo="GET", corpo=None, headers=None, **kw):
        seq.append(metodo)
        if metodo == "POST":
            return {"id": "task_1", "video_id": "video_1", "status": "queued"}
        if seq.count("GET") == 1:
            raise ProviderError("timeout de leitura (120s) em " + url)
        return {"status": "completed", "video_url": "http://cdn/shot.mp4"}

    monkeypatch.setattr(agnes_mod, "http_json", fake_http)
    monkeypatch.setattr(agnes_mod, "baixar",
                        lambda url, dest, **kw: (dest.parent.mkdir(parents=True, exist_ok=True),
                                                 dest.write_bytes(b"mp4"), dest)[-1])
    a = _adapter(monkeypatch)
    shot = {"n": 11, "duracao_s": 3.0, "prompt": "p"}
    out = a._um_shot("p", shot, "1312", "736", tmp_path)
    assert Path(out).exists()
    assert seq.count("GET") == 2


def test_um_shot_insiste_no_post_apos_timeout_de_leitura(tmp_path, monkeypatch):
    """POST engasga uma vez (caso MVD#174, shot 1); repete e segue."""
    _sem_sleep(monkeypatch)
    posts = []

    def fake_http(url, metodo="GET", corpo=None, headers=None, **kw):
        if metodo == "POST":
            posts.append(1)
            if len(posts) == 1:
                raise ProviderError("timeout de leitura (120s) em " + url)
            return {"id": "task_1", "video_id": "video_1", "status": "queued"}
        return {"status": "completed", "video_url": "http://cdn/shot.mp4"}

    monkeypatch.setattr(agnes_mod, "http_json", fake_http)
    monkeypatch.setattr(agnes_mod, "baixar",
                        lambda url, dest, **kw: (dest.parent.mkdir(parents=True, exist_ok=True),
                                                 dest.write_bytes(b"mp4"), dest)[-1])
    a = _adapter(monkeypatch)
    out = a._um_shot("p", {"n": 1, "duracao_s": 3.0, "prompt": "p"}, "1312", "736", tmp_path)
    assert Path(out).exists() and len(posts) == 2

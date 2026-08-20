import json
import pytest
from pathlib import Path
import providers.kie as kie_mod
from providers.base import ProviderError

DECL = json.loads((Path(__file__).resolve().parents[1] / "providers/kie.models.json").read_text())


def test_gerar_posta_polla_e_baixa(tmp_path, monkeypatch, plano_ok):
    chamadas = []

    def fake_http(url, metodo="GET", corpo=None, headers=None, **kw):
        chamadas.append((metodo, url, corpo))
        if url.endswith("/generate"):
            assert corpo["customMode"] is True
            assert corpo["model"] == "V4_5"
            assert corpo["style"] == plano_ok["musica"]["estilo"]["prompt_estilo"]
            assert corpo["prompt"] == plano_ok["musica"]["letra"]["texto"]
            return {"data": {"taskId": "T1"}}
        return {"data": {"status": "SUCCESS", "response": {"sunoData": [
                {"audioUrl": "http://x/faixa.mp3", "duration": 178}]}}}

    baixados = []
    monkeypatch.setattr(kie_mod, "http_json", fake_http)
    monkeypatch.setattr(kie_mod, "baixar",
                        lambda url, destino, **kw: (baixados.append(url),
                                                    destino.write_bytes(b"mp3"), destino)[-1])
    monkeypatch.setattr(kie_mod, "ler_env_chave", lambda nomes: "chave-fake")
    prov = kie_mod.criar(DECL)
    r = prov.gerar("suno-v4.5", {"titulo": plano_ok["titulo"],
                                 "letra": plano_ok["musica"]["letra"]["texto"],
                                 "estilo": plano_ok["musica"]["estilo"]["prompt_estilo"],
                                 "instrumental": False}, tmp_path)
    assert r.arquivo == tmp_path / "faixa.mp3" and r.arquivo.exists()
    assert r.custo_real == 0.08
    assert r.meta["kie_task_id"] == "T1"
    raws = list((tmp_path / "raw").glob("*.json"))
    assert any("T1" in p.read_text() for p in raws)


def test_falha_da_api_vira_provider_error(tmp_path, monkeypatch):
    monkeypatch.setattr(kie_mod, "ler_env_chave", lambda n: "k")
    monkeypatch.setattr(kie_mod, "http_json",
                        lambda *a, **k: (_ for _ in ()).throw(ProviderError("HTTP 500")))
    with pytest.raises(ProviderError):
        kie_mod.criar(DECL).gerar("suno-v4.5", {"titulo": "t", "letra": "l",
                                                "estilo": "s", "instrumental": False}, tmp_path)

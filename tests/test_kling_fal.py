import json
import subprocess
from pathlib import Path
import providers.kling as kling_mod
import providers.fal as fal_mod

RAIZ = Path(__file__).resolve().parents[1]
DECL_K = json.loads((RAIZ / "providers/kling.models.json").read_text())
DECL_F = json.loads((RAIZ / "providers/fal.models.json").read_text())
DECUP = [{"n": 1, "secao": "i", "duracao_s": 5, "camera": "c", "descricao": "d",
          "prompt": "orbit shot, 5s"}]


# ---- kling: CLI oficial, sem intermediário (testado de verdade em 2026-08-20)

def test_kling_monta_o_comando_do_cli_com_720p(tmp_path, monkeypatch):
    chamadas = []

    def fake_cli(args, timeout=900):
        chamadas.append(args)
        if args[0] == "account":
            return {"body": {"availableRemainCredits": 100.0 - 15 * (len(chamadas) > 2)}}
        if args[0] == "text_to_video":
            return {"ok": True, "body": {"generation_id": "G1"}}
        return {"body": {"tasks": [{"status": "succeed",
                                    "works": [{"url": "http://x/v.mp4"}]}]}}

    monkeypatch.setattr(kling_mod, "_kling_json", fake_cli)
    monkeypatch.setattr(kling_mod, "baixar",
                        lambda url, destino, **kw: (destino.parent.mkdir(parents=True, exist_ok=True),
                                                    destino.write_bytes(b"v"), destino)[-1])
    monkeypatch.setattr(kling_mod, "concat_ffmpeg",
                        lambda shots, alvo: (alvo.write_bytes(b"f"), alvo)[-1])
    monkeypatch.setattr(kling_mod.time, "sleep", lambda s: None)
    r = kling_mod.criar(DECL_K).gerar("kling-v2_5",
                                      {"resolucao": "720p", "decupagem": DECUP}, tmp_path)
    t2v = next(a for a in chamadas if a[0] == "text_to_video")
    assert t2v[1:3] == ["--model", "kling-video-v2_5"]
    assert "720p" in t2v                      # o menor valor, pra gastar menos
    assert t2v[-1] == "orbit shot, 5s"        # prompt é posicional, no fim
    assert r.arquivo.name == "clipe.mp4"
    assert r.meta["creditos_kling"] == 15.0   # medido pelo delta de `kling account`


def test_kling_sem_cli_fica_indisponivel_com_motivo(monkeypatch):
    monkeypatch.setattr(kling_mod.subprocess, "run",
                        lambda *a, **k: subprocess.CompletedProcess(a, 1))
    ok, motivo = kling_mod.criar(DECL_K).disponivel()
    assert ok is False and "CLI oficial" in motivo


def test_kling_nao_re_submete_sozinho(tmp_path, monkeypatch):
    """Todo job do Kling é cobrado: sem prompt_alt, falha é falha."""
    import pytest
    from providers.base import ProviderError
    tentativas = []

    def fake_cli(args, timeout=900):
        if args[0] == "account":
            return {"body": {"availableRemainCredits": 10.0}}
        tentativas.append(args)
        return {"ok": False, "body": {"erro": "recusado"}}

    monkeypatch.setattr(kling_mod, "_kling_json", fake_cli)
    monkeypatch.setattr(kling_mod.time, "sleep", lambda s: None)
    with pytest.raises(ProviderError, match="recusou"):
        kling_mod.criar(DECL_K).gerar("kling-v2_5",
                                      {"resolucao": "720p", "decupagem": DECUP}, tmp_path)
    assert len(tentativas) == 1                # UMA submissão, não duas


def test_kling_usa_o_prompt_alt_quando_recusado(tmp_path, monkeypatch):
    prompts = []

    def fake_cli(args, timeout=900):
        if args[0] == "account":
            return {"body": {"availableRemainCredits": 50.0}}
        if args[0] == "text_to_video":
            prompts.append(args[-1])
            if args[-1] == "perigoso":
                return {"ok": False, "body": {"erro": "recusado"}}
            return {"ok": True, "body": {"generation_id": "G2"}}
        return {"body": {"tasks": [{"status": "succeed", "works": [{"url": "http://x/v.mp4"}]}]}}

    monkeypatch.setattr(kling_mod, "_kling_json", fake_cli)
    monkeypatch.setattr(kling_mod, "baixar",
                        lambda url, destino, **kw: (destino.parent.mkdir(parents=True, exist_ok=True),
                                                    destino.write_bytes(b"v"), destino)[-1])
    monkeypatch.setattr(kling_mod, "concat_ffmpeg",
                        lambda shots, alvo: (alvo.write_bytes(b"f"), alvo)[-1])
    monkeypatch.setattr(kling_mod.time, "sleep", lambda s: None)
    shot = dict(DECUP[0], prompt="perigoso", prompt_alt="seguro")
    r = kling_mod.criar(DECL_K).gerar("kling-v2_5",
                                      {"resolucao": "720p", "decupagem": [shot]}, tmp_path)
    assert prompts == ["perigoso", "seguro"]
    assert r.meta["shots_com_alt"] == [1]


# ---- fal: contrato apenas, NÃO exercitado contra API real

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
    r = fal_mod.criar(DECL_F).gerar("kling-v3-turbo",
                                    {"resolucao": "720p", "decupagem": DECUP}, tmp_path)
    assert r.arquivo.name == "clipe.mp4"


def test_fal_custo_por_segundo():
    assert fal_mod.criar(DECL_F).estimar_custo("kling-v3-turbo", {"duracao_shot_s": 10}) == 0.5

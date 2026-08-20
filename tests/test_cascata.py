"""Shot barrado não pode encurtar o clipe: a duração é o que ancora imagem e música."""
import json
import pytest
from pathlib import Path

import providers.agnes as agnes_mod
from providers.base import ProviderError

DECL = json.loads((Path(__file__).resolve().parents[1] / "providers/agnes.models.json").read_text())
BARRA = 'HTTP 400 em .../v1/videos: {"code":"content_policy_violation"}'


def _shot(n, prompt="original", alt=None, secao="refrão"):
    s = {"n": n, "secao": secao, "duracao_s": 5, "camera": "c",
         "descricao": f"d{n}", "prompt": prompt}
    if alt:
        s["prompt_alt"] = alt
    return s


def _mocks(monkeypatch, barrados: set, montados: dict):
    """Barra os prompts listados; qualquer outro passa."""
    posts = []

    def fake_http(url, metodo="GET", corpo=None, headers=None, **kw):
        if metodo == "POST":
            posts.append(corpo["prompt"])
            if corpo["prompt"] in barrados:
                raise ProviderError(BARRA)
            return {"video_id": "V"}
        return {"status": "completed", "video_url": "http://x/s.mp4"}

    monkeypatch.setattr(agnes_mod, "http_json", fake_http)
    monkeypatch.setattr(agnes_mod, "baixar",
                        lambda url, destino, **kw: (destino.parent.mkdir(parents=True, exist_ok=True),
                                                    destino.write_bytes(b"m" * 20000), destino)[-1])
    monkeypatch.setattr(agnes_mod, "ler_env_chave", lambda n: "k")
    monkeypatch.setattr(agnes_mod.time, "sleep", lambda s: None)
    monkeypatch.setattr(agnes_mod, "concat_ffmpeg",
                        lambda shots, alvo: (montados.update(n=len(shots),
                                                             nomes=[p.name for p in shots]),
                                             alvo.write_bytes(b"f"), alvo)[-1])
    return posts


def test_prompt_alt_salva_o_shot_barrado(tmp_path, monkeypatch):
    montados = {}
    posts = _mocks(monkeypatch, {"perigoso"}, montados)
    decup = [_shot(1, "ok1"), _shot(2, "perigoso", alt="versao segura"), _shot(3, "ok3")]
    r = agnes_mod.criar(DECL).gerar("agnes-video-v2.0",
                                    {"resolucao": "1312x736", "decupagem": decup}, tmp_path)
    assert "versao segura" in posts               # tentou o plano B
    assert montados["n"] == 3                     # os 3 shots entraram
    assert r.meta["shots_barrados"] == []         # nenhum buraco
    assert r.meta.get("shots_com_alt") == [2]


def test_sem_alt_pede_reescrita_ao_planejador(tmp_path, monkeypatch):
    montados = {}
    posts = _mocks(monkeypatch, {"perigoso"}, montados)
    decup = [_shot(1, "ok1"), _shot(2, "perigoso"), _shot(3, "ok3")]
    r = agnes_mod.criar(DECL).gerar(
        "agnes-video-v2.0", {"resolucao": "1312x736", "decupagem": decup,
                             "reescrever": lambda shot, motivo: "reescrito neutro"}, tmp_path)
    assert "reescrito neutro" in posts
    assert montados["n"] == 3
    assert r.meta.get("shots_reescritos") == [2]


def test_tudo_barrado_preenche_com_vizinho_da_mesma_secao(tmp_path, monkeypatch):
    """Última linha de defesa: a duração se mantém, mesmo perdendo variedade."""
    montados = {}
    _mocks(monkeypatch, {"perigoso", "alt-tambem-barra"}, montados)
    copiados = []
    monkeypatch.setattr(agnes_mod, "variacao_de",
                        lambda origem, alvo: (copiados.append((origem.name, alvo.name)),
                                              alvo.write_bytes(b"v" * 20000), alvo)[-1])
    decup = [_shot(1, "ok1", secao="refrão"),
             _shot(2, "perigoso", alt="alt-tambem-barra", secao="refrão"),
             _shot(3, "ok3", secao="refrão")]
    r = agnes_mod.criar(DECL).gerar("agnes-video-v2.0",
                                    {"resolucao": "1312x736", "decupagem": decup}, tmp_path)
    assert copiados and copiados[0][1] == "shot-02.mp4"   # o buraco foi preenchido
    assert montados["n"] == 3                              # duração preservada
    assert r.meta.get("shots_preenchidos") == [2]


def test_sem_vizinho_na_secao_o_buraco_fica_registrado(tmp_path, monkeypatch):
    montados = {}
    _mocks(monkeypatch, {"perigoso"}, montados)
    decup = [_shot(1, "ok1", secao="intro"),
             _shot(2, "perigoso", secao="ponte"),      # única da seção, sem alt
             _shot(3, "ok3", secao="outro"),
             _shot(4, "ok4", secao="verso"),
             _shot(5, "ok5", secao="verso")]
    r = agnes_mod.criar(DECL).gerar("agnes-video-v2.0",
                                    {"resolucao": "1312x736", "decupagem": decup}, tmp_path)
    assert r.meta["shots_barrados"] == [2]
    assert montados["n"] == 4                              # aí sim encurtou — e está dito

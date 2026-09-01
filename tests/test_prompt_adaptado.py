"""Adaptacao do TEXTO do prompt por provedor (o plano nasce antes do motor)."""
import json
from pathlib import Path

from providers.base import (adaptar_prompt, regras_de_prompt, parece_portugues,
                            ProviderError)

RAIZ = Path(__file__).resolve().parents[1]
AGNES = json.loads((RAIZ / "providers/agnes.models.json").read_text())
ORIGINAL = ("Static wide shot at night on a vast dark African plain, a small campfire "
            "in the lower third, ember sparks drifting upward, cinematic 24fps, no text")


def test_sem_regras_o_texto_passa_intacto():
    assert adaptar_prompt(None, ORIGINAL) == ORIGINAL
    assert adaptar_prompt({}, ORIGINAL) == ORIGINAL


def test_v20_e_identidade_no_texto():
    """REGRESSAO: 58 producoes do acervo foram escritas para o v2.0.

    A camada existe para o motor NOVO; se ela mexer no caminho antigo, muda o
    resultado de tudo que ja foi feito."""
    regras = regras_de_prompt(AGNES, "agnes-video-v2.0")
    assert adaptar_prompt(regras, ORIGINAL) == ORIGINAL


def test_25_tira_o_fps_que_e_heranca_do_v20():
    """`frame_rate` nao existe na 2.5 — pedir fps no texto e' lixo do v2.0."""
    regras = regras_de_prompt(AGNES, "agnes-video-2.5-flash")
    saida = adaptar_prompt(regras, ORIGINAL)
    assert "24fps" not in saida and "cinematic" not in saida
    assert saida.endswith("drifting upward, no text")   # sem virgula orfa
    assert "ember sparks" in saida                       # nao comeu o resto


def test_acrescentar_nao_duplica():
    r = {"acrescentar": ["no text"]}
    assert adaptar_prompt(r, "uma cena, no text") == "uma cena, no text"
    assert adaptar_prompt(r, "uma cena") == "uma cena, no text"


def test_portugues_vira_erro_que_fala():
    """Sem isso e' um 400 que o _barrou() le como censura (shot 'BARRADO')."""
    assert parece_portugues("Plano aberto de uma mulher que caminha para o sol")
    assert not parece_portugues(ORIGINAL)
    try:
        adaptar_prompt({"idioma": "en"}, "Plano de uma mulher que caminha para o sol")
    except ProviderError as e:
        assert "português" in str(e)
    else:
        raise AssertionError("devia ter levantado")


def test_nome_proprio_com_acento_nao_e_falso_positivo():
    assert not parece_portugues("Wide shot of Maracanã stadium at dusk, no text")


def test_todo_provider_de_video_tem_o_seam():
    """A camada so vale se estiver em TODOS os caminhos de saida de texto."""
    for arq in ("agnes.py", "fal.py", "kling.py", "inemaimg.py"):
        src = (RAIZ / "providers" / arq).read_text()
        assert "adaptar_prompt(regras_de_prompt(" in src, arq


def test_cascata_inteira_passa_pela_adaptacao(tmp_path, monkeypatch):
    """prompt, prompt_alt e reescrito saem TODOS pelo _um_shot — e adaptados."""
    import providers.agnes as ag
    enviados = []

    def fake_http(url, metodo="GET", corpo=None, headers=None, **kw):
        if metodo == "POST":
            enviados.append(corpo["prompt"])
            return {"video_id": f"V{len(enviados)}"}
        return {"status": "completed", "metadata": {"url": "http://x/s.mp4"}}

    monkeypatch.setattr(ag, "http_json", fake_http)
    monkeypatch.setattr(ag, "baixar", lambda u, alvo: (Path(alvo).parent.mkdir(
        parents=True, exist_ok=True), Path(alvo).write_bytes(b"x"), Path(alvo))[-1])
    monkeypatch.setattr(ag, "ler_env_chave", lambda n: "k")
    monkeypatch.setattr(ag.time, "sleep", lambda s: None)

    p = ag.Agnes(AGNES)
    shot = {"n": 1, "duracao_s": 5, "prompt": ORIGINAL}
    p._um_shot(ORIGINAL, shot, "1312", "736", tmp_path,
               modelo="agnes-video-2.5-flash")
    assert enviados and "24fps" not in enviados[0]
    p._um_shot(ORIGINAL, shot, "1312", "736", tmp_path, "-alt",
               modelo="agnes-video-2.5-flash")
    assert "24fps" not in enviados[1]
    # o v2.0 continua recebendo o texto original
    p._um_shot(ORIGINAL, shot, "1312", "736", tmp_path, modelo="agnes-video-v2.0")
    assert enviados[2] == ORIGINAL

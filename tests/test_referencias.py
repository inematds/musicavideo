import json
import pytest

from src.referencias import referencias_visuais, resumir_para_contexto


@pytest.fixture
def banco(tmp_path, monkeypatch):
    """Um banco do analisevideo em miniatura."""
    linhas = [
        {"slug": "war-drums-viking", "titulo": "Viking war drums",
         "tipo": "clipe musical", "look": "épico sombrio, alto contraste",
         "paleta": ["#1B1B22", "#C0873F"], "movimentos": ["dolly-in", "orbital", "whip-pan"],
         "ritmo": "acelerado", "cortes_por_minuto": 42.0, "bpm": 120,
         "mood": "épico/determinado", "tags": ["rock", "épico", "batalha", "tambores"],
         "referencias": ["300", "Vikings"]},
        {"slug": "tornado-infografico", "titulo": "Tornado",
         "tipo": "motion graphics explicativo", "look": "infográfico didático",
         "paleta": ["#5DA9E9"], "movimentos": ["estatico"], "ritmo": "lento",
         "cortes_por_minuto": 0.0, "bpm": None, "mood": "neutro/educativo",
         "tags": ["infografico", "ciencia", "didatico"], "referencias": ["Kurzgesagt"]},
        {"slug": "balada-intimista", "titulo": "Balada",
         "tipo": "clipe musical", "look": "quente e granulado",
         "paleta": ["#E8A13C"], "movimentos": ["steadicam"], "ritmo": "lento",
         "cortes_por_minuto": 8.0, "bpm": 70, "mood": "melancólico",
         "tags": ["balada", "intimista", "romance"], "referencias": []},
    ]
    b = tmp_path / "analisevideo"
    b.mkdir()
    (b / "index.jsonl").write_text(
        "".join(json.dumps(l, ensure_ascii=False) + "\n" for l in linhas), encoding="utf-8")
    monkeypatch.setenv("MUSICAVIDEO_ANALISEVIDEO", str(b))
    return b


def test_acha_referencia_pelo_mood_e_tags(banco):
    refs = referencias_visuais("clipe de rock épico sobre batalha",
                               mood=["épico", "determinada"], genero="anthem rock")
    assert refs and refs[0]["slug"] == "war-drums-viking"


def test_infografico_nao_ganha_de_clipe_musical(banco):
    refs = referencias_visuais("rock pesado", mood=["épico"], genero="rock")
    assert all(r["slug"] != "tornado-infografico" for r in refs[:1])


def test_sem_banco_devolve_vazio(tmp_path, monkeypatch):
    monkeypatch.setenv("MUSICAVIDEO_ANALISEVIDEO", str(tmp_path / "nao-existe"))
    assert referencias_visuais("qualquer coisa", mood=[], genero="") == []


def test_resumo_e_compacto_e_traz_o_que_importa(banco):
    refs = referencias_visuais("rock épico", mood=["épico"], genero="rock")
    txt = resumir_para_contexto(refs)
    assert "war-drums-viking" in txt
    assert "dolly-in" in txt and "#C0873F" in txt and "42" in txt
    assert len(txt) < 2000            # não pode inchar o contexto do planejador


def test_resumo_vazio_nao_quebra():
    assert resumir_para_contexto([]) == ""


def test_referencia_fraca_nao_pega_carona(banco):
    """Infográfico não deve entrar como referência de clipe de rock."""
    refs = referencias_visuais("clipe de rock épico sobre batalha",
                               mood=["épico"], genero="anthem rock")
    assert all(r["slug"] != "tornado-infografico" for r in refs)


def test_resumo_leva_a_montagem_medida(banco):
    """O `index.jsonl` não projeta `montagem` — o resumo tem que abrir o
    `analise.json` da referência escolhida, senão a ligação entre planos some."""
    d = banco / "war-drums-viking"
    d.mkdir()
    (d / "analise.json").write_text(json.dumps({
        "montagem": {"cortes_estimados": 65, "cortes_por_minuto": 42.0,
                     "tipos_de_transicao": ["corte seco", "whip pan de IA"],
                     "match_cut": False, "jump_cut": False, "corte_no_beat": True,
                     "uso_de_slowmo_speedramp": True},
        "pos_producao": {"lut_sugerida": "Teal & Gold", "sound_design": "impactos nos drops"},
    }, ensure_ascii=False), encoding="utf-8")
    txt = resumir_para_contexto(referencias_visuais("rock épico", mood=["épico"], genero="rock"))
    assert "whip pan de IA" in txt
    assert "corte no beat" in txt and "slowmo/speedramp" in txt
    assert "match cut" not in txt          # false não vira sugestão
    assert "Teal & Gold" in txt and "impactos nos drops" in txt


def test_analise_quebrada_nao_derruba_o_resumo(banco):
    d = banco / "war-drums-viking"
    d.mkdir()
    (d / "analise.json").write_text("{isso não é json", encoding="utf-8")
    txt = resumir_para_contexto(referencias_visuais("rock épico", mood=["épico"], genero="rock"))
    assert "war-drums-viking" in txt      # segue com o que o índice já tinha

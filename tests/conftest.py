import os
import sys
import pytest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))


@pytest.fixture
def outdir(tmp_path, monkeypatch):
    d = tmp_path / "out"
    d.mkdir()
    monkeypatch.setenv("MUSICAVIDEO_OUT", str(d))
    return d


@pytest.fixture
def plano_ok():
    return {
        "schema_version": "1", "slug": "teste-rock", "criado_em": "2026-08-20T14:00:00-03:00",
        "solicitacao": "rock feminino de virada", "pesquisa": False,
        "estilo_ref": None, "titulo": "Agora Eu Cobro",
        "musica": {
            "motor": "kie:suno-v4.5",
            "params": {"duracao_s": 10, "instrumental": False},   # 2 shots de 5s cobrem
            "estilo": {"genero": "Female Anthem Rock", "bpm": 120, "tom": "E menor",
                       "mood": ["determinada", "vitoriosa"],
                       "instrumentacao": ["electric guitar", "bass", "drums"],
                       "voz": {"tipo": "feminina", "registro": "médio-agudo",
                               "entrega": "belting com grit", "harmonias": "backing nos refrões"},
                       "prompt_estilo": "Female anthem rock, 120 bpm, E minor, powerful female belting vocals, driving guitars"},
            "estrutura": ["intro", "verso 1", "refrão", "verso 2", "refrão", "ponte", "refrão final"],
            "letra": {"origem": "gerada", "texto": "[Verse 1]\nConstrui no silencio...",
                      "texto_original": None, "idioma": "pt-BR"}
        },
        "capa": {
            "motor": "agnes:agnes-image-2.1-flash",
            "params": {"tamanho": "1024x1024"},
            "template": "retrato-centralizado",
            "conceito": "Mulher de perfil em contraluz âmbar, punho fechado",
            "prompt_imagem": "album cover, three-quarter portrait of a determined woman in amber backlight, closed fist, cinematic, space for bold title, 1:1",
            "prompt_negativo": "text, watermark, logo, front-facing symmetric pose",
            "paleta": ["#E8A13C", "#1A1A2E"]
        },
        "clipe": {
            "motor": "agnes:agnes-video-v2.0",
            "params": {"resolucao": "1312x736", "duracao_shot_s": 5},
            "template": "narrativo",
            "sincronia": "um shot por seção da música",
            "decupagem": [
                {"n": 1, "secao": "intro", "duracao_s": 5, "camera": "dolly-in lento",
                 "descricao": "oficina escura ao amanhecer, ferramentas na bancada",
                 "prompt": "slow dolly-in, dark workshop at dawn, tools on a bench, warm amber light, cinematic, 5s"},
                {"n": 2, "secao": "refrão", "duracao_s": 5, "camera": "orbit",
                 "descricao": "mulher ergue a cabeça sob luz forte",
                 "prompt": "slow orbit around a woman raising her head under strong stage light, amber and teal, cinematic, 5s"}
            ]
        }
    }

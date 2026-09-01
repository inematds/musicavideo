import json
from pathlib import Path
import providers.agnes as agnes_mod

DECL = json.loads((Path(__file__).resolve().parents[1] / "providers/agnes.models.json").read_text())


def test_num_frames_regra_8n1():
    from providers.agnes import num_frames_para
    assert num_frames_para(5, 24) == 121
    assert num_frames_para(3.4, 24) == 81
    # teto por resolucao, medido 2026-08-31: 720p=481, 1080p=241, 480p=961
    assert num_frames_para(30, 24) == 481
    assert num_frames_para(30, 24, altura=736) == 481
    assert num_frames_para(30, 24, altura=1080) == 241
    assert num_frames_para(60, 24, altura=480) == 961


def test_modelo_do_plano_chega_no_corpo():
    """O corpo hardcodava agnes-video-v2.0: pedir 2.5-flash renderizava em v2.0."""
    from providers.agnes import corpo_video
    assert corpo_video("agnes-video-v2.0", "p", 7, 1312, 736)["model"] == "agnes-video-v2.0"
    assert corpo_video("agnes-video-2.5-flash", "p", 7, 1312, 736)["model"] == "agnes-video-2.5-flash"


def test_corpo_da_familia_25_e_outro_contrato():
    """2.5 nao aceita frame_rate/width/num_frames e exige mode+seconds string."""
    from providers.agnes import corpo_video
    c = corpo_video("agnes-video-2.5-flash", "p", 7, 1312, 736)
    assert c["mode"] == "text" and c["seconds"] == "7" and c["n"] == 1
    assert c["size"] == "720P" and c["aspect_ratio"] == "16:9"
    assert not {"frame_rate", "width", "height", "num_frames"} & set(c)
    # seconds e' limitado a [4, 12] pela API
    assert corpo_video("agnes-video-2.5-flash", "p", 3, 1312, 736)["seconds"] == "4"
    assert corpo_video("agnes-video-2.5-flash", "p", 18, 1312, 736)["seconds"] == "12"
    assert corpo_video("agnes-video-2.5-flash", "p", 5, 736, 1312)["aspect_ratio"] == "9:16"


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
    assert r.meta["shots"] == 2
    assert r.meta["shots_barrados"] == [] and r.meta["shots_preenchidos"] == []
    # os ids das chamadas ficam no raw/, um json por shot
    assert len(list((tmp_path / "raw").glob("agnes-shot-*.json"))) == 2


# O MVD#89 (2026-08-21): o POST devolve o id, mas o endpoint de status ainda não
# conhece a task e responde `404 task not found`. O adaptador tratava isso como
# falha fatal e abortava o shot — quando as tasks abortadas COMPLETARAM em 73s.
# Vídeo gerado e jogado fora, duas vezes, e o diagnóstico virou "a Agnes caiu",
# o que levou a trocar de motor e gastar crédito de outro provedor à toa.
def test_404_no_poll_e_task_ainda_nao_visivel_nao_falha(tmp_path, monkeypatch):
    from providers.base import ProviderError
    chamadas = {"polls": 0}

    def fake_http(url, metodo="GET", corpo=None, headers=None, **kw):
        if metodo == "POST":
            return {"video_id": "V1"}
        chamadas["polls"] += 1
        if chamadas["polls"] <= 3:          # a janela em que a task não existe
            raise ProviderError('HTTP 404 em .../agnesapi: {"error":{"code":404}}')
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
              "descricao": "x", "prompt": "slow dolly-in, 5s"}]
    r = agnes_mod.criar(DECL).gerar("agnes-video-v2.0",
                                    {"resolucao": "1312x736", "duracao_shot_s": 5,
                                     "decupagem": decup}, tmp_path)
    assert r.meta["shots"] == 1
    assert chamadas["polls"] == 4      # insistiu nos três 404 e pegou o completed


# Erro que NÃO é 404 continua abortando o shot: 401 é chave errada, e insistir
# nele seria esconder o problema atrás de um timeout de 15 minutos.
def test_erro_que_nao_e_404_continua_abortando(tmp_path, monkeypatch):
    import pytest
    from providers.base import ProviderError

    def fake_http(url, metodo="GET", corpo=None, headers=None, **kw):
        if metodo == "POST":
            return {"video_id": "V1"}
        raise ProviderError("HTTP 401 em .../agnesapi: unauthorized")

    monkeypatch.setattr(agnes_mod, "http_json", fake_http)
    monkeypatch.setattr(agnes_mod, "ler_env_chave", lambda n: "k")
    monkeypatch.setattr(agnes_mod.time, "sleep", lambda s: None)
    decup = [{"n": 1, "secao": "intro", "duracao_s": 5, "camera": "dolly",
              "descricao": "x", "prompt": "slow dolly-in, 5s"}]
    with pytest.raises(ProviderError):
        agnes_mod.criar(DECL).gerar("agnes-video-v2.0",
                                    {"resolucao": "1312x736", "duracao_shot_s": 5,
                                     "decupagem": decup}, tmp_path)


# `resolucao` como RÓTULO (`1080p`) é vocabulário de OUTRO provedor chegando
# pelo plano — e `"1080p".split("x")` estoura ValueError. Foi o MVD#90
# (2026-08-21): 47 shots planejados, nenhum gerado, música já paga.
def test_resolucao_como_rotulo_nao_estoura(tmp_path, monkeypatch):
    corpos = []

    def fake_http(url, metodo="GET", corpo=None, headers=None, **kw):
        if metodo == "POST":
            corpos.append(corpo)
            return {"video_id": "V1"}
        return {"status": "completed", "video_url": "http://tmp/shot.mp4"}

    monkeypatch.setattr(agnes_mod, "http_json", fake_http)
    monkeypatch.setattr(agnes_mod, "baixar",
                        lambda url, destino, **kw: (destino.parent.mkdir(parents=True, exist_ok=True),
                                                    destino.write_bytes(b"mp4"), destino)[-1])
    monkeypatch.setattr(agnes_mod, "ler_env_chave", lambda n: "k")
    monkeypatch.setattr(agnes_mod.time, "sleep", lambda s: None)
    monkeypatch.setattr(agnes_mod, "concat_ffmpeg",
                        lambda shots, alvo: (alvo.write_bytes(b"final"), alvo)[-1])
    decup = [{"n": 1, "secao": "intro", "duracao_s": 5, "camera": "d",
              "descricao": "x", "prompt": "slow dolly-in, 5s"}]
    agnes_mod.criar(DECL).gerar("agnes-video-v2.0",
                                {"resolucao": "1080p", "duracao_shot_s": 5,
                                 "decupagem": decup}, tmp_path)
    assert (corpos[0]["width"], corpos[0]["height"]) == (1920, 1080)


# FILA CHEIA é o provedor dizendo "retry later", não falha. Abortar ali derrubou
# o clipe do MVD#91 com a música pronta e paga.
def test_503_fila_cheia_espera_e_repete(tmp_path, monkeypatch):
    from providers.base import ProviderError
    tentativas = {"post": 0}

    def fake_http(url, metodo="GET", corpo=None, headers=None, **kw):
        if metodo == "POST":
            tentativas["post"] += 1
            if tentativas["post"] <= 2:
                raise ProviderError('HTTP 503 em .../v1/videos: {"code":"video_queue_full"}')
            return {"video_id": "V1"}
        return {"status": "completed", "video_url": "http://tmp/shot.mp4"}

    monkeypatch.setattr(agnes_mod, "http_json", fake_http)
    monkeypatch.setattr(agnes_mod, "baixar",
                        lambda url, destino, **kw: (destino.parent.mkdir(parents=True, exist_ok=True),
                                                    destino.write_bytes(b"mp4"), destino)[-1])
    monkeypatch.setattr(agnes_mod, "ler_env_chave", lambda n: "k")
    monkeypatch.setattr(agnes_mod.time, "sleep", lambda s: None)
    monkeypatch.setattr(agnes_mod, "concat_ffmpeg",
                        lambda shots, alvo: (alvo.write_bytes(b"final"), alvo)[-1])
    decup = [{"n": 1, "secao": "intro", "duracao_s": 5, "camera": "d",
              "descricao": "x", "prompt": "slow dolly-in, 5s"}]
    r = agnes_mod.criar(DECL).gerar("agnes-video-v2.0",
                                    {"resolucao": "1312x736", "duracao_shot_s": 5,
                                     "decupagem": decup}, tmp_path)
    assert r.meta["shots"] == 1
    assert tentativas["post"] == 3      # esperou as duas recusas e conseguiu


# Erro que NÃO é fila cheia continua abortando na hora.
def test_500_no_post_continua_abortando(tmp_path, monkeypatch):
    import pytest
    from providers.base import ProviderError

    def fake_http(url, metodo="GET", corpo=None, headers=None, **kw):
        raise ProviderError("HTTP 500 em .../v1/videos: boom")

    monkeypatch.setattr(agnes_mod, "http_json", fake_http)
    monkeypatch.setattr(agnes_mod, "ler_env_chave", lambda n: "k")
    monkeypatch.setattr(agnes_mod.time, "sleep", lambda s: None)
    decup = [{"n": 1, "secao": "intro", "duracao_s": 5, "camera": "d",
              "descricao": "x", "prompt": "p"}]
    with pytest.raises(ProviderError):
        agnes_mod.criar(DECL).gerar("agnes-video-v2.0",
                                    {"resolucao": "1312x736", "duracao_shot_s": 5,
                                     "decupagem": decup}, tmp_path)


def test_todos_os_shots_falhando_vira_provider_error(tmp_path, monkeypatch):
    """Um shot falho é pulado; TODOS falhando não dá clipe nenhum."""
    import pytest
    from providers.base import ProviderError
    monkeypatch.setattr(agnes_mod, "ler_env_chave", lambda n: "k")
    monkeypatch.setattr(agnes_mod.time, "sleep", lambda s: None)
    monkeypatch.setattr(agnes_mod, "http_json",
                        lambda url, metodo="GET", corpo=None, headers=None, **k:
                        {"video_id": "V1"} if metodo == "POST"
                        else {"status": "failed", "error": "nsfw"})
    with pytest.raises(ProviderError, match="pouco pra montar"):
        agnes_mod.criar(DECL).gerar("agnes-video-v2.0",
                                    {"resolucao": "1312x736", "decupagem": [
                                        {"n": 1, "secao": "i", "duracao_s": 5, "camera": "c",
                                         "descricao": "d", "prompt": "p"}]}, tmp_path)


def _decup(n):
    return [{"n": i, "secao": "s", "duracao_s": 5, "camera": "c", "descricao": "d",
             "prompt": f"shot {i}"} for i in range(1, n + 1)]


def test_shot_barrado_pelo_filtro_e_preenchido_pra_manter_a_duracao(tmp_path, monkeypatch):
    """Barrado sem alt e sem reescritor: preenche com vizinho da seção — a duração fica."""
    from providers.base import ProviderError
    montados = {}

    def fake_http(url, metodo="GET", corpo=None, headers=None, **kw):
        if metodo == "POST":
            if corpo["prompt"] == "shot 3":
                raise ProviderError('HTTP 400 em .../v1/videos: {"code":"content_policy_violation"}')
            return {"video_id": "V"}
        return {"status": "completed", "video_url": "http://x/s.mp4"}

    monkeypatch.setattr(agnes_mod, "http_json", fake_http)
    monkeypatch.setattr(agnes_mod, "baixar",
                        lambda url, destino, **kw: (destino.parent.mkdir(parents=True, exist_ok=True),
                                                    destino.write_bytes(b"m" * 20000), destino)[-1])
    monkeypatch.setattr(agnes_mod, "ler_env_chave", lambda n: "k")
    monkeypatch.setattr(agnes_mod.time, "sleep", lambda s: None)
    monkeypatch.setattr(agnes_mod, "concat_ffmpeg",
                        lambda shots, alvo: (montados.update(n=len(shots)),
                                             alvo.write_bytes(b"f"), alvo)[-1])
    monkeypatch.setattr(agnes_mod, "variacao_de",
                        lambda origem, alvo: (alvo.write_bytes(b"v" * 20000), alvo)[-1])
    r = agnes_mod.criar(DECL).gerar("agnes-video-v2.0",
                                    {"resolucao": "1312x736", "decupagem": _decup(10)}, tmp_path)
    assert r.meta["shots_barrados"] == []       # ninguém ficou de fora
    assert r.meta["shots_preenchidos"] == [3]   # o 3 entrou por substituição
    assert montados["n"] == 10                  # duração preservada


def test_muitos_shots_barrados_e_erro(tmp_path, monkeypatch):
    import pytest
    from providers.base import ProviderError
    monkeypatch.setattr(agnes_mod, "http_json",
                        lambda url, metodo="GET", corpo=None, headers=None, **kw:
                        (_ for _ in ()).throw(ProviderError("HTTP 400 content_policy_violation")))
    monkeypatch.setattr(agnes_mod, "ler_env_chave", lambda n: "k")
    monkeypatch.setattr(agnes_mod.time, "sleep", lambda s: None)
    with pytest.raises(ProviderError, match="pouco pra montar"):
        agnes_mod.criar(DECL).gerar("agnes-video-v2.0",
                                    {"resolucao": "1312x736", "decupagem": _decup(5)}, tmp_path)


def test_shots_ja_baixados_sao_reaproveitados(tmp_path, monkeypatch):
    """Retomar uma corrida interrompida não pode regerar o que já está no disco."""
    posts = []
    (tmp_path / "raw").mkdir()
    for i in (1, 2):
        (tmp_path / "raw" / f"shot-{i:02d}.mp4").write_bytes(b"x" * 20000)

    def fake_http(url, metodo="GET", corpo=None, headers=None, **kw):
        if metodo == "POST":
            posts.append(corpo["prompt"])
            return {"video_id": "V"}
        return {"status": "completed", "video_url": "http://x/s.mp4"}

    monkeypatch.setattr(agnes_mod, "http_json", fake_http)
    monkeypatch.setattr(agnes_mod, "baixar",
                        lambda url, destino, **kw: (destino.write_bytes(b"m" * 20000), destino)[-1])
    monkeypatch.setattr(agnes_mod, "ler_env_chave", lambda n: "k")
    monkeypatch.setattr(agnes_mod.time, "sleep", lambda s: None)
    monkeypatch.setattr(agnes_mod, "concat_ffmpeg",
                        lambda shots, alvo: (alvo.write_bytes(b"f"), alvo)[-1])
    agnes_mod.criar(DECL).gerar("agnes-video-v2.0",
                                {"resolucao": "1312x736", "decupagem": _decup(4)}, tmp_path)
    assert posts == ["shot 3", "shot 4"]   # 1 e 2 vieram do disco


# --- cota diária: espera, não falha (2026-08-26) -----------------------------

MSG_COTA = ('HTTP 429 em https://apihub.agnes-ai.com/v1/videos: {"error":{"code":"",'
            '"message":"Daily API usage limit reached. Please try again after '
            '**2026-08-26 00:00 UTC**. (request id: 2026...)"}}')


def test_reconhece_a_cota_diaria_e_nao_confunde_com_fila_cheia():
    from providers.agnes import _cota_diaria
    from providers.base import ProviderError
    assert _cota_diaria(ProviderError(MSG_COTA))
    assert not _cota_diaria(ProviderError("HTTP 503 video_queue_full: queue is full"))
    assert not _cota_diaria(ProviderError("HTTP 400 content_policy"))


def test_espera_ate_o_horario_que_a_propria_api_informa():
    """O reset vem escrito na mensagem — ler é melhor que chutar."""
    import calendar
    from providers.agnes import segundos_ate_reset
    agora = calendar.timegm((2026, 8, 25, 21, 30, 0, 0, 0, 0))   # 2h30 antes
    s = segundos_ate_reset(MSG_COTA, agora)
    assert 2.4 * 3600 < s < 2.6 * 3600


def test_sem_horario_legivel_espera_uma_hora():
    from providers.agnes import segundos_ate_reset
    assert segundos_ate_reset("HTTP 429 quota exceeded") == 3600.0


def test_espera_tem_teto_e_piso():
    import calendar
    from providers.agnes import TETO_ESPERA_COTA_S, segundos_ate_reset
    agora = calendar.timegm((2026, 8, 1, 0, 0, 0, 0, 0, 0))      # 25 dias antes
    assert segundos_ate_reset(MSG_COTA, agora) == TETO_ESPERA_COTA_S
    depois = calendar.timegm((2026, 8, 26, 3, 0, 0, 0, 0, 0))    # reset já passou
    assert segundos_ate_reset(MSG_COTA, depois) == 60.0


def test_cota_dorme_e_retoma_em_vez_de_derrubar(monkeypatch, tmp_path):
    """O clipe não pode morrer por um limite que se resolve sozinho."""
    from providers import agnes
    from providers.base import ProviderError
    dormidas, tentativas = [], {"n": 0}

    def falso_post(url, metodo="GET", corpo=None, headers=None, **k):
        tentativas["n"] += 1
        if tentativas["n"] == 1:
            raise ProviderError(MSG_COTA)
        return {"video_id": "v1"}

    monkeypatch.setattr(agnes, "http_json", falso_post)
    monkeypatch.setattr(agnes.time, "sleep", lambda s: dormidas.append(s))
    monkeypatch.setattr(agnes, "segundos_ate_reset", lambda *a, **k: 7200.0)
    monkeypatch.setattr(agnes, "baixar", lambda url, alvo: alvo)
    ag = agnes.Agnes({"env_keys": ["AGNES_API_KEY"], "modelos": []})
    monkeypatch.setattr(ag, "_headers", lambda: {})

    # o POST passa na segunda; o polling é curto-circuitado devolvendo url logo
    def falso_json(url, metodo="GET", corpo=None, headers=None, **k):
        if "/videos" in url and metodo == "POST":
            return falso_post(url, metodo, corpo, headers)
        return {"status": "completed", "video_url": "http://x/v.mp4"}

    monkeypatch.setattr(agnes, "http_json", falso_json)
    try:
        ag._um_shot("p", {"n": 1, "duracao_s": 5}, "1312", "736", tmp_path)
    except Exception:
        pass                      # o polling do teste é raso; o que importa é a espera
    assert 7200.0 in dormidas and tentativas["n"] >= 2


def test_troca_de_conta_antes_de_dormir(monkeypatch, tmp_path):
    """A cota é diária e POR CONTA: a reserva tem o dia inteiro, então trocar
    devolve o render na hora. Dormir é o último recurso."""
    from providers import agnes
    from providers.base import ProviderError
    dormidas, tentativas = [], {"n": 0}
    monkeypatch.setattr(agnes, "ler_env_chave", lambda nomes: "k-" + nomes[0])
    monkeypatch.setattr(agnes.time, "sleep", lambda s: dormidas.append(s))
    monkeypatch.setattr(agnes, "baixar", lambda url, alvo: alvo)

    def falso(url, metodo="GET", corpo=None, headers=None, **k):
        if "/videos" in url and metodo == "POST":
            tentativas["n"] += 1
            if tentativas["n"] == 1:
                raise ProviderError(MSG_COTA)
            return {"video_id": "v1"}
        return {"status": "completed", "video_url": "http://x/v.mp4"}

    monkeypatch.setattr(agnes, "http_json", falso)
    ag = agnes.Agnes({"env_keys": ["AGNES_API_KEY", "AGNES_API_KEY_2"], "modelos": []})
    try:
        ag._um_shot("p", {"n": 1, "duracao_s": 5}, "1312", "736", tmp_path)
    except Exception:
        pass
    assert ag._conta == 1                     # virou para a reserva
    assert dormidas == []                     # e NÃO dormiu
    assert "AGNES_API_KEY_2" in ag._headers()["Authorization"]


def test_sem_reserva_ainda_dorme(monkeypatch, tmp_path):
    from providers import agnes
    monkeypatch.setattr(agnes, "ler_env_chave",
                        lambda nomes: "k" if nomes[0] == "AGNES_API_KEY" else None)
    ag = agnes.Agnes({"env_keys": ["AGNES_API_KEY", "AGNES_API_KEY_2"], "modelos": []})
    assert ag._chaves() == ["AGNES_API_KEY"]
    assert ag._proxima_conta() is False


def test_indisponivel_so_quando_nao_ha_chave_nenhuma(monkeypatch):
    from providers import agnes
    monkeypatch.setattr(agnes, "ler_env_chave", lambda nomes: None)
    ag = agnes.Agnes({"env_keys": ["AGNES_API_KEY", "AGNES_API_KEY_2"], "modelos": []})
    ok, motivo = ag.disponivel()
    assert ok is False and "AGNES_API_KEY" in motivo


def test_poll_da_25_e_outro_endpoint():
    """O /agnesapi do v2.0 responde 404 para task da 2.5 — e 404 ali significa
    'ainda nao registrada', entao o codigo esperava o timeout inteiro."""
    from providers.agnes import url_status, url_do_video
    assert url_status("agnes-video-v2.0", "V1").endswith("/agnesapi?video_id=V1")
    assert url_status("agnes-video-2.5-flash", "V1").endswith("/v1/videos/V1")
    assert url_do_video({"video_url": "u1"}) == "u1"
    assert url_do_video({"metadata": {"url": "u2"}}) == "u2"
    assert url_do_video({"status": "completed"}) is None

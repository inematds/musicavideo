import json
from src.planner import gerar_plano
from src.estado import carregar_estado, salvar_estado, transicao
from src.entrega import gerar_pacote, entregar, enviar_telegram


def _preparar(outdir, plano_ok, prontas=("musica", "capa", "clipe")):
    gerar_plano("x", "teste-rock", {}, outdir, chamar_llm=lambda p: json.dumps(plano_ok))
    w = outdir / "teste-rock"
    e = carregar_estado(w)
    art = {"musica": "faixa.mp3", "capa": "capa.png", "clipe": "clipe.mp4"}
    for p in prontas:
        transicao(e, p, "ok")
        transicao(e, p, "faz")
        (w / art[p]).write_bytes(b"x")
        transicao(e, p, "pronto", artefato=art[p], custo_real=0.05)
    salvar_estado(w, e)
    return w


def test_pacote_completo(outdir, plano_ok):
    w = _preparar(outdir, plano_ok)
    pac = gerar_pacote(outdir, "teste-rock")
    md = pac.read_text(encoding="utf-8")
    assert "faixa.mp3" in md and "capa.png" in md and "clipe.mp4" in md


def test_pacote_parcial_lista_o_que_falta(outdir, plano_ok):
    _preparar(outdir, plano_ok, prontas=("musica",))
    md = gerar_pacote(outdir, "teste-rock").read_text(encoding="utf-8")
    assert "falta" in md.lower() and "clipe" in md.lower()


def test_entregar_marca_fase_entregue(outdir, plano_ok):
    _preparar(outdir, plano_ok)
    entregar(outdir, "teste-rock")
    assert carregar_estado(outdir / "teste-rock")["fase"] == "entregue"


def test_telegram_desligado_nao_envia(outdir, plano_ok, monkeypatch):
    w = _preparar(outdir, plano_ok)
    chamadas = []
    import src.entrega as ent
    monkeypatch.setattr(ent, "_post_multipart", lambda *a, **k: chamadas.append(a))
    e = carregar_estado(w)
    plano = json.loads((w / "plano.json").read_text())
    enviar_telegram(w, e, plano)
    assert chamadas == []
    e["telegram"] = True
    monkeypatch.setattr(ent, "ler_env_chave", lambda n: "tok" if "TOKEN" in n[0] else "123")
    enviar_telegram(w, e, plano)
    # faixa, capa, clipe e o FECHO (capa outra vez, com o link)
    assert len(chamadas) == 4


def test_telegram_manda_AS_DUAS_faixas(outdir, plano_ok, monkeypatch):
    """O Suno entrega duas e elas são músicas diferentes — mandar só a
    aprovada tira do dono o que ele decide de ouvido."""
    w = _preparar(outdir, plano_ok)
    (w / "faixa.mp3").unlink(missing_ok=True)
    for n in (1, 2):
        (w / f"faixa-{n}.mp3").write_bytes(b"m")
    e = carregar_estado(w)
    e["telegram"] = True
    e["partes"]["musica"]["artefato"] = "faixa-2.mp3"
    chamadas = []
    import src.entrega as ent
    monkeypatch.setattr(ent, "_post_multipart",
                        lambda url, campos, campo, arq: chamadas.append((campo, arq.name, campos["caption"])))
    monkeypatch.setattr(ent, "ler_env_chave", lambda n: "tok" if "TOKEN" in n[0] else "123")
    plano = json.loads((w / "plano.json").read_text())
    enviar_telegram(w, e, plano)
    audios = [c for c in chamadas if c[0] == "audio"]
    assert [a[1] for a in audios] == ["faixa-1.mp3", "faixa-2.mp3"]
    assert "✓ aprovada" in [a[2] for a in audios if a[1] == "faixa-2.mp3"][0]
    assert "✓ aprovada" not in [a[2] for a in audios if a[1] == "faixa-1.mp3"][0]
    assert [c[0] for c in chamadas if c[0] != "audio"] == ["photo", "video", "photo"]


def test_legendas_mp3_e_capa_levam_estilo_e_o_video_so_o_titulo(outdir, plano_ok, monkeypatch):
    """Com o som na mão a decisão é sobre a música (título + estilo); com o
    vídeo pronto a peça já se explica, e o que importa é o título."""
    w = _preparar(outdir, plano_ok)
    (w / "faixa.mp3").unlink(missing_ok=True)
    (w / "faixa-1.mp3").write_bytes(b"m")
    e = carregar_estado(w)
    e["telegram"] = True
    chamadas = []
    import src.entrega as ent
    monkeypatch.setattr(ent, "_post_multipart",
                        lambda url, campos, campo, arq: chamadas.append((campo, campos["caption"])))
    monkeypatch.setattr(ent, "ler_env_chave", lambda n: "tok" if "TOKEN" in n[0] else "123")
    plano = json.loads((w / "plano.json").read_text())
    estilo = ent.resumo_de_estilo(plano)
    assert estilo                                   # o plano de teste tem gênero
    enviar_telegram(w, e, plano)
    audio = [c[1] for c in chamadas if c[0] == "audio"][0]
    capa = [c[1] for c in chamadas if c[0] == "photo"][0]
    video = [c[1] for c in chamadas if c[0] == "video"][0]
    assert estilo in audio and plano["titulo"] in audio
    assert estilo in capa and plano["titulo"] in capa
    assert video == plano["titulo"]                 # vídeo: só o título
    assert [c[0] for c in chamadas][-3:] == ["photo", "video", "photo"]


def test_resumo_de_estilo_aguenta_plano_magro():
    from src.entrega import resumo_de_estilo
    assert resumo_de_estilo({}) == ""
    assert resumo_de_estilo({"musica": {"estilo": {"genero": "forró"}}}) == "forró"


def test_fecho_manda_a_capa_de_novo_com_titulo_e_link(outdir, plano_ok, monkeypatch):
    """A última mensagem é a que fica valendo no chat: capa + título + link."""
    w = _preparar(outdir, plano_ok)
    e = carregar_estado(w)
    e["telegram"] = True
    chamadas = []
    import src.entrega as ent
    monkeypatch.setattr(ent, "_post_multipart",
                        lambda url, campos, campo, arq: chamadas.append((campo, arq.name, campos["caption"])))
    monkeypatch.setattr(ent, "ler_env_chave", lambda n: "tok" if "TOKEN" in n[0] else "123")
    monkeypatch.setenv("MUSICAVIDEO_LINK_BASE", "http://painel/musicavideo")
    plano = json.loads((w / "plano.json").read_text())
    enviar_telegram(w, e, plano)
    campo, nome, legenda = chamadas[-1]
    assert (campo, nome) == ("photo", "capa.png")
    assert legenda.startswith(plano["titulo"])
    assert legenda.endswith("http://painel/musicavideo/teste-rock/clipe.mp4")
    assert [c[0] for c in chamadas][-3:] == ["photo", "video", "photo"]


def test_sem_clipe_nao_ha_fecho(outdir, plano_ok, monkeypatch):
    w = _preparar(outdir, plano_ok, prontas=("musica", "capa"))
    (w / "clipe.mp4").unlink(missing_ok=True)
    e = carregar_estado(w)
    e["telegram"] = True
    chamadas = []
    import src.entrega as ent
    monkeypatch.setattr(ent, "_post_multipart",
                        lambda url, campos, campo, arq: chamadas.append(campo))
    monkeypatch.setattr(ent, "ler_env_chave", lambda n: "tok" if "TOKEN" in n[0] else "123")
    enviar_telegram(w, e, json.loads((w / "plano.json").read_text()))
    assert chamadas.count("photo") == 1 and "video" not in chamadas


def test_link_cai_no_caminho_quando_nao_ha_base(outdir, plano_ok, monkeypatch):
    from src.entrega import link_do_clipe
    monkeypatch.delenv("MUSICAVIDEO_LINK_BASE", raising=False)
    w = _preparar(outdir, plano_ok)
    assert link_do_clipe(w) == str(w / "clipe.mp4")

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
    assert len(chamadas) == 3


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
    assert [c[0] for c in chamadas if c[0] != "audio"] == ["photo", "video"]

"""O que sobe, o que não sobe, e como a URL local vira URL do HF."""
import json

from src import nuvem, publicahf
from src.estado import novo_estado, salvar_estado


def _producao(base, slug, arquivos):
    w = base / slug
    (w / "raw").mkdir(parents=True)
    (w / "publicacao").mkdir(parents=True)
    for nome in arquivos:
        f = w / nome
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(b"x" * 10)
    salvar_estado(w, novo_estado(slug))
    return w


def test_raw_nunca_sobe(tmp_path):
    """1209 dos 1365 mp4 do acervo são shots intermediários: eles são a maior
    parte do peso e não aparecem em painel nenhum."""
    w = _producao(tmp_path, "p", ["capa.png", "faixa-1.mp3", "clipe-1.mp4",
                                  "raw/shot-01.mp4", "raw/capa-crua.png"])
    nomes = {f.name for f in publicahf.arquivos_de(w)}
    assert nomes == {"capa.png", "faixa-1.mp3", "clipe-1.mp4"}


def test_clipe_mp4_nao_sobe_quando_ha_versionado(tmp_path):
    """Ele é cópia da versão aprovada — 28 dos 29 são byte a byte iguais a um
    `clipe-N.mp4`. O manifesto guarda qual é a aprovada, que é o que a cópia
    dizia."""
    w = _producao(tmp_path, "p", ["clipe.mp4", "clipe-1.mp4", "clipe-2.mp4"])
    nomes = sorted(f.name for f in publicahf.arquivos_de(w))
    assert nomes == ["clipe-1.mp4", "clipe-2.mp4"]


def test_producao_antiga_sem_versionado_sobe_o_clipe_mp4(tmp_path):
    w = _producao(tmp_path, "p", ["clipe.mp4"])
    assert [f.name for f in publicahf.arquivos_de(w)] == ["clipe.mp4"]


def test_url_local_vira_url_do_hf(tmp_path):
    """O painel serve da PASTA DE SAÍDA, então a URL nasce com `musicavideo/` na
    frente. Reescrever esperando só o slug deixava a URL local passar e a
    vitrine mostrava capa quebrada."""
    dado = {"capa": "musicavideo/p/capa.png?v=1",
            "faixas": [{"url": "musicavideo/p/faixa-1.mp3?v=2", "nome": "faixa-1.mp3"}],
            "titulo": "não é URL"}
    saida = publicahf._reescreve(dado, "p", "Conta/repo")
    base = "https://huggingface.co/datasets/Conta/repo/resolve/main/p/"
    assert saida["capa"] == base + "capa.png"
    assert saida["faixas"][0]["url"] == base + "faixa-1.mp3"
    assert saida["titulo"] == "não é URL"


def test_aprovar_marca_e_desmarcar_deixa_pendencia(tmp_path):
    """Desmarcar o que já foi publicado NÃO pode só esquecer: acervo público
    continuaria mostrando o que saiu do ar."""
    w = _producao(tmp_path, "p", ["capa.png"])
    assert nuvem.aprovar(w) == "aprovado"
    nuvem.marcar_publicado(w)
    assert nuvem.situacao(w) == "publicado"
    assert nuvem.aprovar(w, False) == "remover"
    assert nuvem.a_remover(tmp_path) == ["p"]
    nuvem.marcar_removido(w)
    assert nuvem.situacao(w) == "local"


def test_so_o_aprovado_entra_na_lista(tmp_path):
    _producao(tmp_path, "sim", ["capa.png"])
    _producao(tmp_path, "nao", ["capa.png"])
    nuvem.aprovar(tmp_path / "sim")
    assert nuvem.pendentes(tmp_path) == ["sim"]


def test_manifesto_nao_leva_o_video_da_analise(tmp_path, monkeypatch):
    """`fonte.mp4` é vídeo de terceiros baixado do YouTube: re-hospedar é
    redistribuição. A análise vale pelo texto."""
    monkeypatch.setattr(publicahf.painel, "coletar", lambda raiz: {
        "musicavideo": [{"slug": "p", "capa": "musicavideo/p/capa.png?v=1", "doc": "x"}],
        "analisevideo": [{"slug": "a", "video": "analisevideo/a/fonte.mp4",
                          "doc": "texto da análise", "url": "https://youtu.be/abc123"}]})
    man = publicahf.manifesto(tmp_path, "Conta/repo", ["p"])
    assert man["analisevideo"][0]["video"] is None
    assert man["analisevideo"][0]["doc"] == "texto da análise"
    assert man["musicavideo"][0]["capa"].startswith("https://huggingface.co/")


def test_manifesto_ignora_quem_nao_esta_publicado(tmp_path, monkeypatch):
    monkeypatch.setattr(publicahf.painel, "coletar", lambda raiz: {
        "musicavideo": [{"slug": "p"}, {"slug": "outro"}], "analisevideo": []})
    man = publicahf.manifesto(tmp_path, "Conta/repo", ["p"])
    assert [x["slug"] for x in man["musicavideo"]] == ["p"]


# --- o elo que faltava: publicar termina no push -----------------------------

def _repo_app(tmp_path):
    """Um `musicavideo-pub` de mentira, com origin em outro repo local."""
    import subprocess
    remoto = tmp_path / "remoto.git"
    subprocess.run(["git", "init", "--bare", "-q", str(remoto)], check=True)
    app = tmp_path / "app"
    (app / "data").mkdir(parents=True)
    (app / "package.json").write_text("{}")
    g = lambda *a: subprocess.run(["git", "-C", str(app), *a], check=True,
                                  capture_output=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(app)], check=True)
    g("config", "user.name", "t"), g("config", "user.email", "t@t")
    g("add", "-A"), g("commit", "-qm", "base")
    g("remote", "add", "origin", str(remoto)), g("push", "-q", "-u", "origin", "main")
    return app, remoto


def _man(n=2):
    return {"musicavideo": [{"slug": f"p{i}"} for i in range(n)], "analisevideo": []}


def test_manifesto_novo_vira_commit_e_chega_no_origin(tmp_path):
    """Sem o push, o `publica-hf` subia gigabytes para o HF e a vitrine
    continuava desenhando o manifesto anterior."""
    import subprocess
    app, remoto = _repo_app(tmp_path)
    alvo = publicahf.gravar_no_app(_man(), app=app, log=lambda *a: None)
    assert publicahf.subir_app(alvo, _man(), log=lambda *a: None) is True
    r = subprocess.run(["git", "-C", str(remoto), "show", "main:data/manifest.json"],
                       capture_output=True, text=True)
    assert json.loads(r.stdout)["musicavideo"] == [{"slug": "p0"}, {"slug": "p1"}]


def test_manifesto_igual_nao_vira_commit_vazio(tmp_path):
    """Rodar duas vezes não polui o histórico da vitrine."""
    app, _ = _repo_app(tmp_path)
    alvo = publicahf.gravar_no_app(_man(), app=app, log=lambda *a: None)
    publicahf.subir_app(alvo, _man(), log=lambda *a: None)
    publicahf.gravar_no_app(_man(), app=app, log=lambda *a: None)
    assert publicahf.subir_app(alvo, _man(), log=lambda *a: None) is False


def test_app_sem_git_nao_explode(tmp_path):
    """O manifesto foi escrito; não ter repo é aviso, não falha."""
    app = tmp_path / "solto"
    (app / "data").mkdir(parents=True)
    (app / "package.json").write_text("{}")
    alvo = publicahf.gravar_no_app(_man(), app=app, log=lambda *a: None)
    ditos = []
    assert publicahf.subir_app(alvo, _man(), log=ditos.append) is False
    assert any("não é repo git" in d for d in ditos)


# --- o que precisa subir não é tudo o que está aprovado ----------------------

def _aprovada(base, slug, publicado_em=None):
    w = _producao(base, slug, ["capa.png", "clipe-1.mp4"])
    nuvem.aprovar(w)
    if publicado_em:
        nuvem.marcar_publicado(w, publicado_em)
    return w


def test_aprovado_que_nunca_subiu_entra(tmp_path):
    _aprovada(tmp_path, "novo")
    assert publicahf.a_subir(tmp_path) == ["novo"]


def test_publicado_e_intocado_fica_de_fora(tmp_path):
    """Era daqui que vinham os 4,13 GB relidos a cada passada."""
    _aprovada(tmp_path, "velho", publicado_em="2099-01-01T00:00:00-03:00")
    assert publicahf.a_subir(tmp_path) == []


def test_arquivo_final_mais_novo_faz_voltar_a_fila(tmp_path):
    """Refazer o clipe de uma produção já publicada tem de reenviar."""
    import datetime as dt
    import os
    quando = "2099-01-01T00:00:00-03:00"
    w = _aprovada(tmp_path, "refeito", publicado_em=quando)
    assert publicahf.a_subir(tmp_path) == []          # de fora enquanto intocado
    depois = dt.datetime.fromisoformat(quando).timestamp() + 60
    os.utime(w / "clipe-1.mp4", (depois, depois))
    assert publicahf.a_subir(tmp_path) == ["refeito"]


def test_estado_json_nao_conta_como_mudanca(tmp_path):
    """`marcar_publicado` reescreve o `estado.json` DEPOIS de carimbar a hora.
    Se ele entrasse na conta, toda produção pareceria mudada para sempre."""
    _aprovada(tmp_path, "p", publicado_em="2099-01-01T00:00:00-03:00")
    from src.estado import carregar_estado, salvar_estado
    w = tmp_path / "p"
    salvar_estado(w, carregar_estado(w))          # toca só o estado.json
    assert publicahf.a_subir(tmp_path) == []


def test_carimbo_ilegivel_sobe_em_vez_de_adivinhar(tmp_path):
    _aprovada(tmp_path, "p", publicado_em="sei la")
    assert publicahf.a_subir(tmp_path) == ["p"]


def test_numero_vem_do_estado_e_nao_do_indice(tmp_path):
    """O `index.jsonl` só é reescrito por quem mexe em estado ou por um
    `reindex`. Uma renumeração feita direto no `estado.json` ficava invisível —
    foi assim que a vitrine passou dias mostrando `MVD-013` enquanto o disco já
    dizia `MVD#113`."""
    import json as J
    from src import painel
    from src.estado import carregar_estado, salvar_estado
    base = tmp_path / "musicavideo"
    w = _producao(base, "p", ["capa.png", "clipe-1.mp4", "faixa-1.mp3"])
    est = carregar_estado(w); est["mvd"] = "MVD#113"; salvar_estado(w, est)
    (base / "index.jsonl").write_text(
        J.dumps({"slug": "p", "mvd": "MVD-013", "titulo": "t"}) + "\n", encoding="utf-8")
    achado = painel.coletar(tmp_path)["musicavideo"]
    assert [x["mvd"] for x in achado] == ["MVD#113"]


# --- o botão que sobe de verdade --------------------------------------------

def test_subida_sem_trava_diz_que_comecou(tmp_path, monkeypatch):
    """O botão dizia 'subir para a nuvem' e só marcava: sem o cron (retirado na
    v1.3.0) o card ficava em `aprovado` para sempre."""
    from src import subida
    monkeypatch.setattr(subida, "TRAVA", tmp_path / "trava")
    chamadas = []
    class FakeP:
        pid = 4242
    monkeypatch.setattr(subida.subprocess, "Popen", lambda *a, **k: (chamadas.append(a) or FakeP()))
    assert subida.iniciar("p", outdir=tmp_path, log=tmp_path / "log") == "subindo:p"
    assert "publica-hf" in chamadas[0][0] and "p" in chamadas[0][0]


def test_uma_subida_por_vez(tmp_path, monkeypatch):
    """Dois uploads de gigabytes concorrendo só multiplicam banda e confusão."""
    from src import subida
    monkeypatch.setattr(subida, "TRAVA", tmp_path / "trava")
    monkeypatch.setattr(subida, "_pid_vivo", lambda pid: True)
    (tmp_path / "trava").write_text("999:outra\n")
    assert subida.iniciar("p", outdir=tmp_path, log=tmp_path / "log") == "ja-subindo:outra"


def test_trava_de_processo_morto_nao_prende_o_painel(tmp_path, monkeypatch):
    """kill -9 ou queda da máquina deixariam a trava para trás."""
    from src import subida
    monkeypatch.setattr(subida, "TRAVA", tmp_path / "trava")
    monkeypatch.setattr(subida, "_pid_vivo", lambda pid: False)
    (tmp_path / "trava").write_text("999:morta\n")
    assert subida.em_andamento() is None


def test_zumbi_nao_conta_como_subindo(tmp_path, monkeypatch):
    """O painel é o pai e não colhe o filho: terminado, ele vira zumbi e o
    `os.kill(pid, 0)` responde que está vivo. O selo `subindo…` ficaria pulsando
    para sempre numa subida que já acabou — foi o que aconteceu com o MVD#124."""
    import subprocess as sp
    import sys as _sys
    import time
    from pathlib import Path as _P
    from src import subida
    monkeypatch.setattr(subida, "TRAVA", tmp_path / "trava")
    filho = sp.Popen([_sys.executable, "-c", "pass"])    # de propósito: NÃO colhido
    (tmp_path / "trava").write_text(f"{filho.pid}:p\n")
    st = _P(f"/proc/{filho.pid}/status")
    for _ in range(60):                                  # espera virar zumbi
        if st.exists() and "Z" in st.read_text().split("State:")[1][:4]:
            break
        time.sleep(0.05)
    assert subida.em_andamento() is None


def test_fila_de_aprovados_se_esvazia_sozinha(tmp_path, monkeypatch):
    """`aprovado` não pode ser um beco: sem cron, ficaria esperando alguém rodar
    o comando à mão — a reclamação que originou a subida pelo painel."""
    from src import subida
    monkeypatch.setattr(subida, "TRAVA", tmp_path / "trava")
    monkeypatch.setattr(subida, "em_andamento", lambda: None)
    comecou = []
    monkeypatch.setattr(subida, "iniciar", lambda slug, **k: comecou.append(slug))
    base = tmp_path / "acervo"
    quieto = _producao(base, "a-quieto", ["capa.png"])
    subir = _producao(base, "b-subir", ["capa.png"])
    nuvem.aprovar(subir)
    nuvem.marcar_publicado(_producao(base, "c-ja-foi", ["capa.png"]))
    assert subida.proxima(base) == "b-subir"
    assert comecou == ["b-subir"] and quieto.name not in comecou


def test_nada_comeca_enquanto_algo_sobe(tmp_path, monkeypatch):
    from src import subida
    monkeypatch.setattr(subida, "em_andamento", lambda: "outra")
    base = tmp_path / "acervo"
    nuvem.aprovar(_producao(base, "p", ["capa.png"]))
    assert subida.proxima(base) is None


def test_painel_chama_a_fila_na_pasta_certa(tmp_path, monkeypatch):
    """Passar `base / "musicavideo"` (com `base` já sendo o acervo) aponta para
    pasta que não existe — e o guard de OSError engolia o erro em silêncio."""
    from src import painel, subida
    vistos = []
    monkeypatch.setattr(subida, "proxima", lambda outdir, **k: vistos.append(outdir))
    monkeypatch.setattr(subida, "em_andamento", lambda: None)
    base = tmp_path / "musicavideo"
    _producao(base, "p", ["capa.png"])
    painel.coletar(tmp_path)
    assert vistos == [base] and vistos[0].is_dir()


# --------------------------------------------------- aprovação POR FAIXA (v2.1)
#
# O Suno entrega duas músicas por pedido, e elas são músicas diferentes. Aprovar
# a produção inteira obrigava a levar as duas para a vitrine — ou nenhuma.


def test_aprovar_uma_faixa_nao_leva_a_outra(tmp_path):
    w = _producao(tmp_path, "p", ["capa.png", "faixa-1.mp3", "clipe-1.mp4",
                                  "faixa-2.mp3", "clipe-2.mp4"])
    nuvem.aprovar(w, faixa="1")
    assert nuvem.situacao_faixa(w, "1") == "aprovado"
    assert nuvem.situacao_faixa(w, "2") == "local"
    nomes = {f.name for f in publicahf.arquivos_a_subir(w)}
    assert "faixa-1.mp3" in nomes and "clipe-1.mp4" in nomes
    assert "faixa-2.mp3" not in nomes and "clipe-2.mp4" not in nomes
    assert "capa.png" in nomes            # a capa da produção é de todas


def test_faixa_aprovada_depois_da_publicacao_ainda_sobe(tmp_path):
    """O buraco do modelo antigo: `publicado_em` era da PRODUÇÃO, e o filtro de
    reenvio olhava mtime. A faixa 2 nasceu antes daquele carimbo, então
    aprová-la depois não mudava nada no disco — e ela nunca subia."""
    w = _producao(tmp_path, "p", ["capa.png", "faixa-1.mp3", "clipe-1.mp4",
                                  "faixa-2.mp3", "clipe-2.mp4"])
    nuvem.aprovar(w, faixa="1")
    nuvem.marcar_publicado(w, faixa="1")
    assert publicahf.a_subir(tmp_path) == []
    nuvem.aprovar(w, faixa="2")
    assert publicahf.a_subir(tmp_path) == ["p"]
    nomes = {f.name for f in publicahf.arquivos_a_subir(w)}
    assert "clipe-2.mp4" in nomes
    assert "clipe-1.mp4" not in nomes     # essa já está lá e não mudou


def test_estado_antigo_vale_como_todas_as_faixas_aprovadas(tmp_path):
    """Acervo já marcado antes desta versão não pode desaparecer da vitrine."""
    w = _producao(tmp_path, "p", ["faixa-1.mp3", "faixa-2.mp3"])
    nuvem.aprovar(w)                       # gesto antigo, sem faixa
    assert nuvem.situacao_faixa(w, "1") == "aprovado"
    assert nuvem.situacao_faixa(w, "2") == "aprovado"
    assert nuvem.pendentes(tmp_path) == ["p"]


def test_desmarcar_faixa_publicada_pede_remocao_so_dela(tmp_path):
    w = _producao(tmp_path, "p", ["faixa-1.mp3", "clipe-1.mp4",
                                  "faixa-2.mp3", "clipe-2.mp4"])
    nuvem.aprovar(w)
    nuvem.marcar_publicado(w)
    nuvem.aprovar(w, False, faixa="2")
    assert nuvem.situacao_faixa(w, "2") == "remover"
    assert nuvem.situacao_faixa(w, "1") == "publicado"
    assert nuvem.faixas_a_remover(w) == ["2"]
    assert nuvem.a_remover(tmp_path) == []       # a pasta fica: a faixa 1 está lá
    nuvem.aprovar(w, False, faixa="1")
    assert nuvem.a_remover(tmp_path) == ["p"]    # sem nenhuma faixa, sai a pasta


def test_manifesto_so_mostra_a_faixa_publicada(tmp_path, monkeypatch):
    w = _producao(tmp_path, "p", ["faixa-1.mp3", "clipe-1.mp4",
                                  "faixa-2.mp3", "clipe-2.mp4"])
    nuvem.aprovar(w, faixa="1")
    nuvem.marcar_publicado(w, faixa="1")
    monkeypatch.setattr(publicahf.painel, "coletar", lambda raiz: {
        "musicavideo": [{"slug": "p", "titulo": "P",
                         "faixas": [{"n": "1", "url": "musicavideo/p/faixa-1.mp3"},
                                    {"n": "2", "url": "musicavideo/p/faixa-2.mp3"}],
                         "versoes": [{"n": "1", "clipe": "musicavideo/p/clipe-1.mp4"},
                                     {"n": "2", "clipe": "musicavideo/p/clipe-2.mp4"}]}],
        "analisevideo": []})
    man = publicahf.manifesto(tmp_path, "Conta/repo", ["p"])
    item = man["musicavideo"][0]
    assert [f["n"] for f in item["faixas"]] == ["1"]
    assert [v["n"] for v in item["versoes"]] == ["1"]


def test_slug_nomeado_reenvia_mas_nao_inventa_faixa(tmp_path):
    """`publica-hf <slug>` ignora o "já subiu e não mudou" — é o que o botão do
    painel usa. O que ele NÃO pode ignorar é a escolha: com a faixa 2 fora, o
    alvo nomeado mandava a pasta inteira e as duas músicas apareciam na
    vitrine."""
    w = _producao(tmp_path, "p", ["capa.png", "faixa-1.mp3", "clipe-1.mp4",
                                  "faixa-2.mp3", "clipe-2.mp4"])
    nuvem.aprovar(w, faixa="1")
    nuvem.marcar_publicado(w, faixa="1")
    nomes = {f.name for f in publicahf.arquivos_a_subir(w, forcar=True)}
    assert "faixa-1.mp3" in nomes and "clipe-1.mp4" in nomes   # reenvia a dela
    assert "faixa-2.mp3" not in nomes and "clipe-2.mp4" not in nomes

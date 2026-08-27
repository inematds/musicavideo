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

import json
import pytest
from pathlib import Path
from src.planner import gerar_plano, aprovar_parte
from src.executor import faz
from src.estado import carregar_estado
from providers.base import Resultado, ProviderError


class ProvFake:
    nome = "kie"

    def __init__(self, ok=True):
        self.ok = ok

    def disponivel(self):
        return True, ""

    def estimar_custo(self, modelo, params):
        return 0.08

    def gerar(self, modelo, params, workdir):
        if not self.ok:
            raise ProviderError("boom")
        a = workdir / "faixa.mp3"
        a.write_bytes(b"x")
        return Resultado(a, 0.08, {"kie_task_id": "T1"})


def _reg_fake(prov):
    return {m: {"provider": prov, "modelo": {"id": m.split(":")[1], "params": {},
                "custo": {"base_usd": 0.08, "por": "geracao"}, "capacidade": "musica"}}
            for m in ("kie:suno-v4.5", "agnes:agnes-image-2.1-flash", "agnes:agnes-video-v2.0")}


@pytest.fixture
def slug(outdir, plano_ok):
    gerar_plano("x", "teste-rock", {}, outdir, chamar_llm=lambda p: json.dumps(plano_ok))
    return "teste-rock"


def test_faz_musica_para_no_portao_de_revisao(outdir, slug):
    """Com portão ligado (padrão), a faixa espera você ouvir antes de virar pronto."""
    aprovar_parte(outdir, slug, "musica")
    rc = faz(outdir, slug, ["musica"], sim=True, reg=_reg_fake(ProvFake()))
    assert rc == 0
    e = carregar_estado(outdir / slug)
    assert e["partes"]["musica"]["estado"] == "revisao"
    assert e["partes"]["musica"]["artefato"] == "faixa.mp3"
    assert e["custo_total_usd"]["gasto"] == 0.08     # o custo conta na geração
    idx = json.loads((outdir / "index.jsonl").read_text().splitlines()[0])
    assert idx["estados"]["musica"] == "revisao"


def test_sem_revisao_vai_direto_pra_pronto(outdir, slug):
    aprovar_parte(outdir, slug, "musica")
    rc = faz(outdir, slug, ["musica"], sim=True, sem_revisao=True, reg=_reg_fake(ProvFake()))
    assert rc == 0
    assert carregar_estado(outdir / slug)["partes"]["musica"]["estado"] == "pronto"


def test_faz_parte_nao_aprovada_erra_uso(outdir, slug):
    assert faz(outdir, slug, ["musica"], sim=True, reg=_reg_fake(ProvFake())) == 1


def test_erro_de_provider_nao_derruba_e_exit_2(outdir, slug):
    aprovar_parte(outdir, slug, "musica")
    rc = faz(outdir, slug, ["musica"], sim=True, reg=_reg_fake(ProvFake(ok=False)))
    assert rc == 2
    e = carregar_estado(outdir / slug)
    assert e["partes"]["musica"]["estado"] == "erro"
    assert e["partes"]["musica"]["erro"]["msg"] == "boom"


def test_teto_pula_parte_exit_3(outdir, slug):
    aprovar_parte(outdir, slug, "musica")
    w = outdir / slug
    e = carregar_estado(w)
    e["teto_usd"] = 0.01
    from src.estado import salvar_estado
    salvar_estado(w, e)
    rc = faz(outdir, slug, ["musica"], sim=True, reg=_reg_fake(ProvFake()))
    assert rc == 3
    assert carregar_estado(w)["partes"]["musica"]["estado"] == "aprovado"


class ProvDuasFaixas(ProvFake):
    """O Suno entrega DUAS: as duas ficam no disco, pagas no mesmo custo."""

    def gerar(self, modelo, params, workdir):
        a = workdir / "faixa-1.mp3"
        a.write_bytes(b"x")
        (workdir / "faixa-2.mp3").write_bytes(b"y")
        return Resultado(a, 0.08, {"kie_task_id": "T1"})


def test_recibo_declara_a_segunda_faixa(outdir, slug, capsys):
    """A faixa-2 existia e nunca era ouvida — o recibo só declarava a escolhida.

    O bot entrega o que o recibo declara (MVD#96, 2026-08-22): sem a linha
    `musica_alt:`, a segunda variação fica no disco, paga, e ninguém sabe.
    """
    aprovar_parte(outdir, slug, "musica")
    faz(outdir, slug, ["musica"], sim=True, sem_revisao=True, reg=_reg_fake(ProvDuasFaixas()))
    linhas = capsys.readouterr().out.splitlines()
    assert f"musica: {outdir / slug / 'faixa-1.mp3'}" in linhas
    assert f"musica_alt: {outdir / slug / 'faixa-2.mp3'}" in linhas


def test_uma_faixa_so_nao_inventa_alternativa(outdir, slug, capsys):
    aprovar_parte(outdir, slug, "musica")
    faz(outdir, slug, ["musica"], sim=True, sem_revisao=True, reg=_reg_fake(ProvFake()))
    saida = capsys.readouterr().out
    assert "musica_alt:" not in saida


def test_reprova_o_que_ja_esta_pronto(outdir, slug):
    """O portão de verdade é o chat, e lá a parte já está `pronto`.

    O bot roda com `--sem-revisao --aprovar`, então quando o dono vê o material
    ele não está mais em `revisao`. Sem a transição (pronto, reprova) o comando
    morria com TransicaoInvalida — o estado não previa revisão DEPOIS.
    """
    from src.executor import cmd_reprova
    aprovar_parte(outdir, slug, "musica")
    faz(outdir, slug, ["musica"], sim=True, sem_revisao=True, reg=_reg_fake(ProvFake()))
    assert carregar_estado(outdir / slug)["partes"]["musica"]["estado"] == "pronto"
    assert cmd_reprova([slug, "musica"]) == 0
    assert carregar_estado(outdir / slug)["partes"]["musica"]["estado"] == "aprovado"


def test_escolher_a_outra_faixa_depois_de_pronto(outdir, slug):
    """`aprova <slug> musica --faixa 2` com a parte já pronta.

    As duas faixas ganham o MESMO vídeo em `montar_todas` — escolher é reapontar
    `clipe.mp4`, sem re-render e sem custo. Só que o estado não previa aprovar
    algo que já estava pronto, e o comando morria em TransicaoInvalida.
    """
    from src.executor import cmd_aprova
    aprovar_parte(outdir, slug, "musica")
    faz(outdir, slug, ["musica"], sim=True, sem_revisao=True, reg=_reg_fake(ProvDuasFaixas()))
    assert cmd_aprova([slug, "musica", "--faixa", "2"]) == 0
    e = carregar_estado(outdir / slug)
    assert e["partes"]["musica"]["artefato"] == "faixa-2.mp3"
    assert e["partes"]["musica"]["estado"] == "pronto"


# --- capa sem tipografia alucinada (2026-08-25) ------------------------------

def test_prompt_de_capa_perde_o_pedido_de_album_cover():
    """'album cover' pede LETRA ao modelo, e o título é nosso — composto por
    cima. No flux não há negativo para desfazer isso."""
    from src.executor import prompt_sem_tipografia
    saida = prompt_sem_tipografia("album cover, wide landscape at dusk, film grain")
    assert "album cover" not in saida.lower()
    assert saida.startswith("wide landscape at dusk")
    assert "clean unmarked surfaces" in saida


def test_pedido_de_limpeza_nao_duplica():
    from src.executor import prompt_sem_tipografia
    uma = prompt_sem_tipografia("poster art, a lone boat")
    assert prompt_sem_tipografia(uma) == uma


def test_prompt_sem_tipografia_aguenta_vazio():
    from src.executor import prompt_sem_tipografia
    assert "clean unmarked surfaces" in prompt_sem_tipografia("")


def test_clausula_que_pede_espaco_para_titulo_some():
    """'space for bold title at the bottom' fazia o flux desenhar um título
    em negrito na base — garatuja, no lugar exato do título de verdade."""
    from src.executor import prompt_sem_tipografia
    saida = prompt_sem_tipografia(
        "a lone boat on ice, space for bold title at the bottom, film grain")
    assert "title" not in saida.lower()
    assert "a lone boat on ice" in saida and "film grain" in saida


def test_a_instrucao_de_limpeza_nao_nomeia_letra():
    """O modelo desenha o que lê, inclusive dentro de uma negação."""
    from src.executor import prompt_sem_tipografia
    saida = prompt_sem_tipografia("a barn at dusk").lower()
    for palavra in ("text", "letter", "typograph", "writing", "word"):
        assert palavra not in saida


def test_parte_ja_pronta_sai_com_recibo_e_zero(tmp_path, capsys, monkeypatch):
    """MVD#157: com --faixa-pronta a musica nasce `pronto`, e a fase `musica`
    do bot dispara `faz <slug> musica` do mesmo jeito. A recusa saia SEM
    recibo, o portao nao achava `musica: <arquivo>` e o fluxo morria com a
    faixa ja no disco."""
    import json
    from src.executor import _recibo
    from pathlib import Path
    w = tmp_path / "s"
    w.mkdir()
    (w / "faixa-1.mp3").write_bytes(b"a")
    (w / "faixa-2.mp3").write_bytes(b"b")
    estado = {"partes": {"musica": {"estado": "pronto", "artefato": "faixa-1.mp3"},
                         "capa": {"estado": "planejado", "artefato": None},
                         "clipe": {"estado": "planejado", "artefato": None}}}
    assert _recibo("s", estado, w) == 0
    saida = capsys.readouterr().out
    assert "slug: s" in saida
    assert "musica: " in saida and "faixa-1.mp3" in saida
    assert "musica_alt: " in saida and "faixa-2.mp3" in saida
    assert "capa:" not in saida       # parte nao pronta nao entra no recibo

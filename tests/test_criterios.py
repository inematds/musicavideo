"""Os critérios de sucesso do spec §11 que faltavam prova, e os fixes da crítica."""
import json
import pytest
from pathlib import Path

from src.planner import gerar_plano, aprovar_parte
from src.executor import faz
from src.estado import carregar_estado, salvar_estado
from providers.base import Resultado, ProviderError


class ProvOK:
    nome = "agnes"

    def __init__(self, arquivo):
        self.arquivo = arquivo

    def disponivel(self):
        return True, ""

    def estimar_custo(self, modelo, params):
        return 0.0

    def gerar(self, modelo, params, workdir):
        a = Path(workdir) / self.arquivo
        a.write_bytes(b"x")
        return Resultado(a, 0.0, {})


class ProvSemChave:
    nome = "kie"

    def disponivel(self):
        return False, "kie: indisponível — KIE_API_KEY não encontrada em openpcbotv2/.env nem wifi/.env"

    def estimar_custo(self, modelo, params):
        return 0.08

    def gerar(self, modelo, params, workdir):
        raise AssertionError("não deveria chamar gerar de provider indisponível")


class ProvExplode:
    """Adapter mal-comportado: levanta o que NÃO é ProviderError."""
    nome = "kie"

    def disponivel(self):
        return True, ""

    def estimar_custo(self, modelo, params):
        return 0.08

    def gerar(self, modelo, params, workdir):
        raise KeyError("audioUrl")


def _reg(musica, capa, clipe):
    def ent(prov, cap):
        return {"provider": prov, "modelo": {"id": "m", "params": {},
                "custo": {"base_usd": 0.0, "por": "geracao"}, "capacidade": cap}}
    return {"kie:suno-v4.5": ent(musica, "musica"),
            "agnes:agnes-image-2.1-flash": ent(capa, "imagem"),
            "agnes:agnes-video-v2.0": ent(clipe, "video")}


@pytest.fixture
def slug(outdir, plano_ok):
    gerar_plano("x", "teste-rock", {}, outdir, chamar_llm=lambda p: json.dumps(plano_ok))
    return "teste-rock"


# ---- critério 4: chave derrubada → parte erro, AS OUTRAS ENTREGUES, exit 2

def test_parte_sem_chave_erra_e_as_outras_seguem(outdir, slug):
    for p in ("musica", "capa", "clipe"):
        aprovar_parte(outdir, slug, p)
    rc = faz(outdir, slug, ["musica", "capa", "clipe"], sim=True, sem_revisao=True,
             reg=_reg(ProvSemChave(), ProvOK("capa.png"), ProvOK("clipe.mp4")))
    assert rc == 2
    e = carregar_estado(outdir / slug)
    assert e["partes"]["musica"]["estado"] == "erro"
    assert "KIE_API_KEY" in e["partes"]["musica"]["erro"]["msg"]
    assert e["partes"]["capa"]["estado"] == "pronto"
    assert e["partes"]["clipe"]["estado"] == "pronto"
    assert (outdir / slug / "capa.png").exists() and (outdir / slug / "clipe.mp4").exists()


def test_adapter_que_levanta_erro_nao_ProviderError_nao_derruba(outdir, slug):
    for p in ("musica", "capa", "clipe"):
        aprovar_parte(outdir, slug, p)
    rc = faz(outdir, slug, ["musica", "capa", "clipe"], sim=True, sem_revisao=True,
             reg=_reg(ProvExplode(), ProvOK("capa.png"), ProvOK("clipe.mp4")))
    assert rc == 2
    e = carregar_estado(outdir / slug)
    assert e["partes"]["musica"]["estado"] == "erro"
    assert "KeyError" in e["partes"]["musica"]["erro"]["msg"]
    assert e["partes"]["capa"]["estado"] == "pronto"


# ---- critério 5: retomar depois, sem dizer as partes

def test_faz_sem_parte_exige_a_musica_primeiro(outdir, slug):
    """Só a capa aprovada e música ainda no plano: o faz automático recusa e explica."""
    aprovar_parte(outdir, slug, "capa")
    rc = faz(outdir, slug, None, sim=True,
             reg=_reg(ProvSemChave(), ProvOK("capa.png"), ProvOK("clipe.mp4")))
    assert rc == 1
    e = carregar_estado(outdir / slug)
    assert e["partes"]["capa"]["estado"] == "aprovado"      # nada foi gerado


def test_parte_explicita_ignora_a_ordem(outdir, slug):
    """Pedir a capa de propósito gera a capa, mesmo sem música."""
    aprovar_parte(outdir, slug, "capa")
    rc = faz(outdir, slug, ["capa"], sim=True, sem_revisao=True,
             reg=_reg(ProvSemChave(), ProvOK("capa.png"), ProvOK("clipe.mp4")))
    assert rc == 0
    assert carregar_estado(outdir / slug)["partes"]["capa"]["estado"] == "pronto"


def test_faz_automatico_faz_a_musica_primeiro(outdir, slug):
    """As três aprovadas: só a música roda, capa e clipe esperam a faixa."""
    for p in ("musica", "capa", "clipe"):
        aprovar_parte(outdir, slug, p)
    rc = faz(outdir, slug, None, sim=True, sem_revisao=True,
             reg=_reg(ProvOK("faixa-1.mp3"), ProvOK("capa.png"), ProvOK("clipe.mp4")))
    assert rc == 0
    e = carregar_estado(outdir / slug)
    assert e["partes"]["musica"]["estado"] == "pronto"
    assert e["partes"]["capa"]["estado"] == "aprovado"      # ainda não rodou
    assert e["partes"]["clipe"]["estado"] == "aprovado"


def test_faz_sem_nada_aprovado_erra_uso(outdir, slug):
    assert faz(outdir, slug, None, sim=True,
               reg=_reg(ProvSemChave(), ProvOK("capa.png"), ProvOK("clipe.mp4"))) == 1


# ---- critério 8: chave de API nunca aparece em arquivo, estado ou index

def test_chave_nunca_vaza_pros_arquivos(outdir, slug, monkeypatch, capsys):
    import providers.kie as kie_mod
    SEGREDO = "sk-chave-secreta-do-usuario-123"
    monkeypatch.setattr(kie_mod, "ler_env_chave", lambda n: SEGREDO)
    monkeypatch.setattr(kie_mod, "http_json", lambda url, metodo="GET", corpo=None,
                        headers=None, **kw:
                        {"data": {"taskId": "T1"}} if url.endswith("/generate")
                        else {"data": {"status": "SUCCESS", "response": {"sunoData": [
                            {"audioUrl": "http://x/f.mp3", "duration": 100}]}}})
    monkeypatch.setattr(kie_mod, "baixar",
                        lambda url, destino, **kw: (destino.write_bytes(b"mp3"), destino)[-1])
    decl = json.loads((Path(__file__).resolve().parents[1] / "providers/kie.models.json").read_text())
    aprovar_parte(outdir, slug, "musica")
    rc = faz(outdir, slug, ["musica"], sim=True, sem_revisao=True,
             reg={"kie:suno-v4.5": {"provider": kie_mod.criar(decl),
                                    "modelo": decl["modelos"][0]},
                  "agnes:agnes-image-2.1-flash": {"provider": ProvOK("capa.png"),
                                                  "modelo": decl["modelos"][0]},
                  "agnes:agnes-video-v2.0": {"provider": ProvOK("clipe.mp4"),
                                             "modelo": decl["modelos"][0]}})
    assert rc == 0
    saida = capsys.readouterr()
    assert SEGREDO not in saida.out + saida.err
    for arq in list((outdir / slug).rglob("*")) + [outdir / "index.jsonl"]:
        if arq.is_file() and arq.suffix in (".json", ".md", ".jsonl", ".txt"):
            assert SEGREDO not in arq.read_text(encoding="utf-8", errors="ignore"), arq


# ---- fixes da crítica

def test_forca_nao_destroi_parte_pronta(outdir, slug, plano_ok):
    aprovar_parte(outdir, slug, "musica")
    faz(outdir, slug, ["musica"], sim=True, sem_revisao=True,
        reg=_reg(ProvOK("faixa.mp3"), ProvOK("capa.png"), ProvOK("clipe.mp4")))
    with pytest.raises(ValueError, match="pronta"):
        gerar_plano("x", slug, {"forca": True}, outdir,
                    chamar_llm=lambda p: json.dumps(plano_ok))


def test_motor_override_persiste_no_plano(outdir, slug):
    aprovar_parte(outdir, slug, "clipe")
    faz(outdir, slug, ["clipe"], sim=True, sem_revisao=True,
        motor_override={"clipe": "kling:kling-v2_5"},
        reg={**_reg(ProvOK("faixa.mp3"), ProvOK("capa.png"), ProvOK("clipe.mp4")),
             "kling:kling-v2_5": {"provider": ProvOK("clipe.mp4"),
                                 "modelo": {"id": "kling-2.5", "params": {},
                                            "custo": {"base_usd": 0.0, "por": "geracao"}}}})
    plano = json.loads((outdir / slug / "plano.json").read_text(encoding="utf-8"))
    assert plano["clipe"]["motor"] == "kling:kling-v2_5"


def test_motor_inexistente_no_faz_nao_da_stacktrace(outdir, slug, capsys):
    aprovar_parte(outdir, slug, "clipe")
    rc = faz(outdir, slug, ["clipe"], sim=True, motor_override={"clipe": "foo:bar"},
             reg=_reg(ProvOK("faixa.mp3"), ProvOK("capa.png"), ProvOK("clipe.mp4")))
    assert rc == 1
    assert "foo" in capsys.readouterr().out


def test_letra_rascunho_forca_origem_e_diff(outdir, plano_ok, tmp_path):
    arq = tmp_path / "rascunho.txt"
    arq.write_text("[Verse 1]\nmeu rascunho torto\n", encoding="utf-8")
    plano_ok["musica"]["letra"] = {"origem": "gerada", "texto": "[Verse 1]\nversao acabada\n",
                                   "texto_original": None, "idioma": "pt-BR"}
    p = gerar_plano("x", "s-rasc", {"letra": str(arq)}, outdir,
                    chamar_llm=lambda pr: json.dumps(plano_ok))
    assert p["musica"]["letra"]["origem"] == "rascunho_usuario"
    assert p["musica"]["letra"]["texto_original"] == arq.read_text(encoding="utf-8")
    md = (outdir / "s-rasc" / "PLANO.md").read_text(encoding="utf-8")
    assert "Diff do seu rascunho" in md

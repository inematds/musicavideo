import json
import pytest
from pathlib import Path
from src.planner import derivar_slug, gerar_plano, render_plano_md


def _fake_llm(plano_ok):
    def f(prompt: str) -> str:
        return "aqui está o plano:\n```json\n" + json.dumps(plano_ok) + "\n```"
    return f


def test_derivar_slug(outdir):
    s = derivar_slug("Música de VIRADA, rock feminino!!", outdir)
    assert s == "musica-de-virada-rock-feminino"
    (outdir / s).mkdir()
    assert derivar_slug("Música de VIRADA, rock feminino!!", outdir) == s + "-2"


def test_gerar_plano_grava_tudo(outdir, plano_ok):
    p = gerar_plano("rock feminino de virada", "teste-rock", {}, outdir,
                    chamar_llm=_fake_llm(plano_ok))
    w = outdir / "teste-rock"
    assert (w / "plano.json").exists() and (w / "PLANO.md").exists()
    assert (w / "estado.json").exists()
    assert json.loads((outdir / "index.jsonl").read_text().splitlines()[0])["slug"] == "teste-rock"
    assert p["capa"]["motor"] == "agnes:agnes-image-2.1-flash"


def test_plano_invalido_faz_retry_e_erra(outdir, plano_ok):
    plano_ok["capa"]["prompt_imagem"] = "retrato em contraluz âmbar"
    with pytest.raises(ValueError, match="INGLÊS"):
        gerar_plano("x", "s2", {}, outdir, chamar_llm=_fake_llm(plano_ok))


def test_letra_final_e_lei(outdir, plano_ok, tmp_path):
    arq = tmp_path / "letra.txt"
    arq.write_text("[Verse 1]\nminha letra imutável\n", encoding="utf-8")
    p = gerar_plano("balada", "s3", {"letra": str(arq), "letra_final": True},
                    outdir, chamar_llm=_fake_llm(plano_ok))
    assert p["musica"]["letra"]["origem"] == "final_usuario"
    assert p["musica"]["letra"]["texto"] == arq.read_text(encoding="utf-8")


# Até 2026-08-21 não havia como pedir outro idioma: pt-BR era chumbado no
# `setdefault` e repetido em inglês no prompt de estilo. Quem quisesse música em
# inglês só podia escrever isso no texto livre e torcer.
def test_idioma_pedido_manda(outdir, plano_ok):
    p = gerar_plano("x", "s-idioma", {"idioma": "en-US"}, outdir,
                    chamar_llm=_fake_llm(plano_ok))
    assert p["musica"]["letra"]["idioma"] == "en-US"


def test_sem_idioma_continua_pt_br(outdir, plano_ok):
    p = gerar_plano("x", "s-default", {}, outdir, chamar_llm=_fake_llm(plano_ok))
    assert p["musica"]["letra"]["idioma"] == "pt-BR"


# Metade garantida não garante nada: quem CANTA é o provedor, e ele só lê o
# `prompt_estilo`. O campo `letra.idioma` já era chumbado; a frase do estilo era
# só instrução no prompt, e o modelo podia ignorá-la em silêncio.
def test_idioma_pedido_entra_no_prompt_estilo(outdir, plano_ok):
    p = gerar_plano("x", "s-estilo-idioma", {"idioma": "en-US"}, outdir,
                    chamar_llm=_fake_llm(plano_ok))
    assert p["musica"]["estilo"]["prompt_estilo"].endswith("Lyrics in en-US")


def test_idioma_pedido_apaga_a_declaracao_do_modelo(outdir, plano_ok):
    """Duas declarações no mesmo prompt é o que produz portunhol acidental."""
    import copy
    pl = copy.deepcopy(plano_ok)
    pl["musica"]["estilo"]["prompt_estilo"] = (
        "rustic folk, acoustic guitar. language = portuguese or spanish or mix like portunhol")
    p = gerar_plano("x", "s-troca-idioma", {"idioma": "en-US"}, outdir,
                    chamar_llm=_fake_llm(pl))
    estilo = p["musica"]["estilo"]["prompt_estilo"]
    assert estilo == "rustic folk, acoustic guitar. Lyrics in en-US"
    assert "portunhol" not in estilo


def test_idioma_com_acento_nao_quebra_a_validacao_en(outdir, plano_ok):
    """`prompt_estilo` com acento é recusado (`campos_prompt_en`) — e o idioma
    entra dentro dele. `português` tem que virar `portugues` na frase."""
    p = gerar_plano("x", "s-idioma-acento", {"idioma": "português"}, outdir,
                    chamar_llm=_fake_llm(plano_ok))
    assert p["musica"]["estilo"]["prompt_estilo"].endswith("Lyrics in portugues")
    assert p["musica"]["letra"]["idioma"] == "português"   # o rótulo fica como pedido


def test_sem_idioma_nao_mexe_no_prompt_estilo(outdir, plano_ok):
    antes = plano_ok["musica"]["estilo"]["prompt_estilo"]
    p = gerar_plano("x", "s-estilo-intacto", {}, outdir, chamar_llm=_fake_llm(plano_ok))
    assert p["musica"]["estilo"]["prompt_estilo"] == antes


# O idioma pedido vence até com letra do usuário: a letra é dele, o rótulo do
# idioma tem que ser o que ele pediu — é ele que vai para o prompt do Suno.
def test_idioma_pedido_vence_com_letra_do_usuario(outdir, plano_ok, tmp_path):
    arq = tmp_path / "letra.txt"
    arq.write_text("[Verse 1]\nmy own lyrics\n", encoding="utf-8")
    p = gerar_plano("x", "s-idioma-letra",
                    {"idioma": "en-US", "letra": str(arq)}, outdir,
                    chamar_llm=_fake_llm(plano_ok))
    assert p["musica"]["letra"]["idioma"] == "en-US"


# O planejador tem que RECEBER o pedido, senão escreve a letra em português e
# termina o prompt de estilo com "Lyrics in Brazilian Portuguese".
def test_contexto_leva_o_idioma_ao_planejador(outdir):
    from src.planner import montar_contexto
    ctx = montar_contexto("uma música", {"idioma": "en-US"}, outdir)
    assert "IDIOMA DA LETRA: en-US" in ctx
    assert "Lyrics in en-US" in ctx


# Portão, não aviso. Em 2026-08-21, com a Agnes fora do ar no meio de um clipe,
# um `--motor clipe=kling:...` "óbvio" queimou 105 créditos da conta do dono
# antes de alguém perceber. Trocar para provedor que gasta é decisão dele.
# `--flag=valor` e `--flag valor` são a mesma coisa. Antes só a segunda
# funcionava: `--idioma=en-US` sobrava nos argumentos livres e virava parte da
# SOLICITAÇÃO — pedido de idioma virando letra de música, em silêncio.
def test_flag_com_igual_e_com_espaco_sao_iguais():
    import shlex
    from src.planner import _parse_opts
    com_igual = _parse_opts(shlex.split('balada --idioma=en-US --estilo=anthem-pop-rock'))
    com_espaco = _parse_opts(shlex.split('balada --idioma en-US --estilo anthem-pop-rock'))
    assert com_igual == com_espaco
    assert com_igual == (['balada'], {'idioma': 'en-US', 'estilo': 'anthem-pop-rock'})


# O `--motor` tem `=` no PRÓPRIO valor (`parte=provedor:modelo`): a divisão é no
# primeiro `=`, senão a forma com igual comeria a parte.
def test_motor_com_igual_nao_perde_a_parte():
    import shlex
    from src.planner import _parse_opts
    _, opts = _parse_opts(shlex.split('x --motor=clipe=kling:kling-v2_5'))
    assert opts['motor'] == {'clipe': 'kling:kling-v2_5'}


# MÚSICA PRONTA: o usuário traz a faixa e o pipeline faz só capa e clipe. Sem
# isto, a parte PAGA (~US$ 0,08) era obrigatória mesmo quando ela já existia.
def test_faixa_pronta_nasce_pronta_e_ancora_a_duracao(outdir, plano_ok, tmp_path, monkeypatch):
    from src.estado import carregar_estado
    faixa = tmp_path / "minha.mp3"
    faixa.write_bytes(b"audio")
    # 10s: a duração REAL da fixture, para a validação de cobertura (o clipe
    # tem que cobrir a música) continuar valendo — é ela que o `--faixa-pronta`
    # passa a ancorar no arquivo em vez de num palpite de 180s.
    monkeypatch.setattr("src.planner.duracao_de", lambda a: 10)

    p = gerar_plano("uma música minha", "s-pronta", {"faixa_pronta": str(faixa)},
                    outdir, chamar_llm=_fake_llm(plano_ok))
    assert p["musica"]["params"]["duracao_s"] == 10
    e = carregar_estado(outdir / "s-pronta")
    assert e["partes"]["musica"]["estado"] == "pronto"
    assert e["partes"]["musica"]["artefato"] == "faixa-1.mp3"
    assert e["partes"]["musica"]["custo_real_usd"] == 0.0
    # O arquivo é COPIADO para dentro do slug — o original do usuário fica onde
    # está, e o pacote/montagem não precisam saber de onde ele veio.
    assert (outdir / "s-pronta" / "faixa-1.mp3").exists()
    assert faixa.exists()


def test_faixa_pronta_inexistente_erra_claro(outdir, plano_ok):
    import pytest as _p
    with _p.raises(ValueError, match="não encontrada"):
        gerar_plano("x", "s-sem-faixa", {"faixa_pronta": "/nao/existe.mp3"},
                    outdir, chamar_llm=_fake_llm(plano_ok))


def test_contexto_avisa_que_a_musica_ja_existe(outdir, monkeypatch):
    from src.planner import montar_contexto
    monkeypatch.setattr("src.planner.duracao_de", lambda a: 200)
    ctx = montar_contexto("x", {"faixa_pronta": "/tmp/a.mp3"}, outdir)
    assert "MÚSICA JÁ EXISTE" in ctx
    assert "200s" in ctx


def test_motor_pago_exige_autorizacao():
    from src.planner import exigir_autorizacao_de_motor
    import pytest as _p
    for motor in ("kling:kling-v2_5", "fal:kling-v3-turbo", "kie:suno-v4.5"):
        with _p.raises(ValueError, match="sem autorização"):
            exigir_autorizacao_de_motor({"motor": {"clipe": motor}})


def test_motor_pago_passa_com_autorizacao():
    from src.planner import exigir_autorizacao_de_motor
    exigir_autorizacao_de_motor({"motor": {"clipe": "kling:kling-v2_5"},
                                 "autorizo_pago": True})


# Os DEFAULTS do plano não são afetados: a música nasce em kie e isso é sabido.
# O portão é sobre TROCAR de motor na linha de comando.
def test_motor_gratis_e_plano_sem_motor_passam(outdir, plano_ok):
    from src.planner import exigir_autorizacao_de_motor
    exigir_autorizacao_de_motor({})
    exigir_autorizacao_de_motor({"motor": {"capa": "inemaimg:flux2-klein"}})
    exigir_autorizacao_de_motor({"motor": {"clipe": "agnes:agnes-video-v2.0"}})
    p = gerar_plano("x", "s-default-kie", {}, outdir, chamar_llm=_fake_llm(plano_ok))
    assert p["musica"]["motor"] == "kie:suno-v4.5"


def test_motor_override(outdir, plano_ok):
    p = gerar_plano("x", "s4", {"motor": {"clipe": "kling:kling-v2_5"}},
                    outdir, chamar_llm=_fake_llm(plano_ok))
    assert p["clipe"]["motor"] == "kling:kling-v2_5"


def test_slug_existente_sem_forca_erra(outdir, plano_ok):
    gerar_plano("x", "s5", {}, outdir, chamar_llm=_fake_llm(plano_ok))
    with pytest.raises(ValueError, match="--forca"):
        gerar_plano("x", "s5", {}, outdir, chamar_llm=_fake_llm(plano_ok))


def test_render_md_mostra_indisponivel(plano_ok):
    md = render_plano_md(plano_ok, {"kie": (False, "kie: indisponível — KIE_API_KEY não encontrada")})
    assert "indisponível" in md and "KIE_API_KEY" in md


# O PLANO.md tem que sair mesmo quando `musica.estrutura` vem como lista de
# dicts. O esquema só exige lista, e o planejador é livre para detalhar a seção
# com tempos — foi o que o Fable devolveu no MVD#87 (2026-08-21), e o
# `' · '.join` estourou TypeError DEPOIS de gravar o plano.json: trabalho caro
# feito, fase falhada na formatação, duas tentativas queimadas.
def test_render_md_aceita_estrutura_detalhada(plano_ok):
    plano = dict(plano_ok)
    plano["musica"] = dict(plano_ok["musica"])
    plano["musica"]["estrutura"] = [
        {"secao": "intro", "inicio_s": 0, "duracao_s": 15},
        {"secao": "verso1", "inicio_s": 15, "duracao_s": 25},
    ]
    md = render_plano_md(plano, {})
    assert "intro (15s)" in md and "verso1 (25s)" in md


def test_render_md_continua_aceitando_estrutura_simples(plano_ok):
    md = render_plano_md(plano_ok, {})
    assert "intro · verso 1" in md


def test_clipe_mais_curto_que_a_musica_e_rejeitado(outdir, plano_ok):
    """Clipe que não cobre a faixa vira vídeo em loop — não é um clipe."""
    from src.planner import cobertura_do_clipe
    plano_ok["musica"]["params"]["duracao_s"] = 180      # 3 min de música...
    assert cobertura_do_clipe(plano_ok)                   # ...com 10s de decupagem
    with pytest.raises(ValueError, match="decupe a música inteira"):
        gerar_plano("x", "s-curto", {}, outdir, chamar_llm=lambda p: json.dumps(plano_ok))


def test_decupagem_que_cobre_a_musica_passa(plano_ok):
    from src.planner import cobertura_do_clipe
    plano_ok["musica"]["params"]["duracao_s"] = 10
    assert cobertura_do_clipe(plano_ok) == []


def test_contexto_pede_a_musica_inteira(outdir):
    from src.planner import montar_contexto
    ctx = montar_contexto("rock", {"duracao_s": 180}, outdir)
    assert "36 shots" in ctx and "cobrir a música INTEIRA" in ctx


def test_contexto_injeta_referencias_do_analisevideo(outdir, tmp_path, monkeypatch):
    """O planejamento visual deve se apoiar em vídeo medido, não só nos templates."""
    import json as _json
    from src.planner import montar_contexto
    b = tmp_path / "av"
    b.mkdir()
    (b / "index.jsonl").write_text(_json.dumps({
        "slug": "war-drums", "titulo": "War drums", "tipo": "clipe musical",
        "look": "épico sombrio", "paleta": ["#C0873F"], "movimentos": ["whip-pan"],
        "ritmo": "acelerado", "cortes_por_minuto": 42.0, "bpm": 120,
        "mood": "épico", "tags": ["rock", "épico"], "referencias": ["Vikings"]}) + "\n",
        encoding="utf-8")
    monkeypatch.setenv("MUSICAVIDEO_ANALISEVIDEO", str(b))
    ctx = montar_contexto("clipe de rock épico", {"estilo": "anthem rock"}, outdir)
    assert "REFERÊNCIAS VISUAIS MEDIDAS" in ctx
    assert "whip-pan" in ctx and "#C0873F" in ctx


def test_contexto_sem_banco_de_referencias_nao_quebra(outdir, tmp_path, monkeypatch):
    from src.planner import montar_contexto
    monkeypatch.setenv("MUSICAVIDEO_ANALISEVIDEO", str(tmp_path / "vazio"))
    ctx = montar_contexto("rock", {}, outdir)
    assert "REFERÊNCIAS VISUAIS MEDIDAS" not in ctx and "SOLICITAÇÃO" in ctx


def test_contexto_pede_o_plano_b_de_cada_shot(outdir):
    from src.planner import montar_contexto
    ctx = montar_contexto("rock", {}, outdir)
    assert "prompt_alt" in ctx and "PLANO B" in ctx


def test_parse_opts_le_versao_e_tagline():
    """Flag com VALOR que o parser não conhece vira argumento LIVRE em silêncio —
    e no `arte` o valor caía na posição do título: `--versao 1` renomeava a
    música para "1". Mesmo defeito que o `--idioma=en-US` teve em 2026-08-21."""
    from src.planner import _parse_opts
    livres, opts = _parse_opts(["slug", "--versao", "2", "--tagline", "o mar não espera"])
    assert livres == ["slug"]
    assert opts["versao"] == "2"
    assert opts["tagline"] == "o mar não espera"
    assert _parse_opts(["slug", "--versao=2"])[1]["versao"] == "2"


# --- ritmo do clipe (2026-08-23) ---------------------------------------------

def test_ritmo_auto_e_o_default_e_manda_o_planejador_decidir():
    from src.planner import _instrucao_ritmo, _ritmo, media_shot_s
    assert _ritmo({}) == "auto"
    txt = _instrucao_ritmo({})
    assert "você decide" in txt and "REFERÊNCIAS MEDIDAS" in txt
    assert media_shot_s({}) == 5          # auto dimensiona pelo padrão


def test_ritmo_dinamico_pede_mais_shots_que_o_calmo():
    from src.planner import _n_shots_alvo
    calmo = _n_shots_alvo({"duracao_s": 180, "ritmo": "calmo"})
    padrao = _n_shots_alvo({"duracao_s": 180, "ritmo": "padrao"})
    dinamico = _n_shots_alvo({"duracao_s": 180, "ritmo": "dinamico"})
    assert calmo < padrao < dinamico     # mais cortes = mais shots = mais horas
    assert dinamico == 60 and calmo == 22


def test_ritmo_variado_nao_muda_o_numero_de_shots():
    """É o ponto dele: ritmo sem pagar hora de fila."""
    from src.planner import _n_shots_alvo
    assert _n_shots_alvo({"duracao_s": 180, "ritmo": "variado"}) == \
           _n_shots_alvo({"duracao_s": 180, "ritmo": "padrao"})


def test_ritmo_invalido_cai_no_auto_sem_quebrar():
    from src.planner import _ritmo
    assert _ritmo({"ritmo": "furioso"}) == "auto"


def test_todo_ritmo_proibe_duracao_parelha():
    from src.planner import _instrucao_ritmo, RITMOS
    for nome in RITMOS:
        assert "NÃO é parelha" in _instrucao_ritmo({"ritmo": nome})


def test_flag_ritmo_e_lida():
    from src.planner import _parse_opts
    assert _parse_opts(["--ritmo", "dinamico"])[1]["ritmo"] == "dinamico"
    assert _parse_opts(["--ritmo=variado"])[1]["ritmo"] == "variado"


def test_contexto_proibe_descrever_a_boca_cantando(tmp_path):
    """O gerador não ouve a faixa: boca aberta vira careta parada, e boca em
    movimento vira mímica que não bate com som nenhum (MVD 'Stay')."""
    from src.planner import montar_contexto
    ctx = montar_contexto("balada sobre recomeço", {}, tmp_path)
    assert "NUNCA descreva a boca" in ctx
    assert "'singing'" in ctx and "'belting'" in ctx
    assert "garganta" in ctx and "olhos fechados" in ctx


def test_contexto_manda_cortar_o_close_sem_nomear_a_pessoa(tmp_path):
    """Nomear a dona do pé faz o modelo desenhar a criança inteira e errar o
    tronco (MVD 'Levanta a Poeira')."""
    from src.planner import montar_contexto
    ctx = montar_contexto("forró sobre festa de rua", {}, tmp_path)
    assert "CLOSE DE PARTE DO CORPO" in ctx
    assert "NUNCA nomeie a pessoa" in ctx


def test_regra_do_canto_e_escopada_ao_clipe(tmp_path):
    """A regra existe para o CLIPE; solta, ela vazava para a capa e saíam
    retratos em série com queixo erguido e olhos fechados."""
    from src.planner import montar_contexto
    ctx = montar_contexto("balada pop", {}, tmp_path)
    assert "vale SÓ para clipe.decupagem[].prompt" in ctx
    assert "NUNCA para capa.prompt_imagem" in ctx


def test_capa_manda_variar_o_olhar(tmp_path):
    from src.planner import montar_contexto
    ctx = montar_contexto("balada pop", {}, tmp_path)
    assert "CAPA — o olhar VARIA" in ctx
    for proibido in ("chin raised", "chin lifted", "head tilted back", "eyes closed"):
        assert proibido in ctx          # citados como o que NÃO repetir
    assert "capa SEM pessoa nenhuma" in ctx


def test_chamar_fable_timeout_vira_runtime_error(monkeypatch):
    """MVD#132: o `claude -p` pendurou 900 s e o `TimeoutExpired` subiu como
    traceback — `cmd_plano` só pega ValueError/RuntimeError, então o job morria
    com "saiu com código 1" sem dizer o motivo. Tem que virar RuntimeError."""
    import subprocess

    import src.planner as pl

    def estoura(*a, **k):
        raise subprocess.TimeoutExpired("claude", 900)

    monkeypatch.setattr(subprocess, "run", estoura)
    with pytest.raises(RuntimeError, match="900 s"):
        pl.chamar_fable("qualquer prompt")

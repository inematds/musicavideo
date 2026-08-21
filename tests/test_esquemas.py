from src.esquemas import validar_plano, validar_estado, campos_prompt_en


def test_plano_valido_sem_erros(plano_ok):
    assert validar_plano(plano_ok) == []


def test_campo_desconhecido_e_erro(plano_ok):
    plano_ok["extra"] = 1
    assert any("extra" in e for e in validar_plano(plano_ok))


def test_campo_obrigatorio_faltando(plano_ok):
    del plano_ok["musica"]["letra"]
    assert any("letra" in e for e in validar_plano(plano_ok))


def test_motor_malformado(plano_ok):
    plano_ok["capa"]["motor"] = "semdoispontos"
    assert any("motor" in e for e in validar_plano(plano_ok))


def test_letra_final_exige_texto(plano_ok):
    plano_ok["musica"]["letra"]["origem"] = "final_usuario"
    plano_ok["musica"]["letra"]["texto"] = ""
    assert any("final_usuario" in e for e in validar_plano(plano_ok))


def test_prompt_em_portugues_e_rejeitado(plano_ok):
    plano_ok["capa"]["prompt_imagem"] = "capa de álbum, retrato de mulher, iluminação âmbar"
    erros = campos_prompt_en(plano_ok)
    assert any("prompt_imagem" in e for e in erros)


def test_conceito_em_pt_e_permitido(plano_ok):
    assert campos_prompt_en(plano_ok) == []


# O MVD#89 (2026-08-21): o prompt_estilo terminava com "Wardruna meets anthem
# rock". O plano validou, o portão abriu, a fase entrou na fila — e o Suno
# recusou na hora de gerar. Erro que só aparece onde custa é o pior tipo.
def test_artista_no_prompt_de_estilo_e_rejeitado(plano_ok):
    plano_ok["musica"]["estilo"]["prompt_estilo"] = (
        "Nordic folk anthem rock, 118 BPM, D minor, Wardruna meets anthem rock."
    )
    erros = campos_prompt_en(plano_ok)
    assert any("Wardruna" in e for e in erros)


def test_comparacao_sem_nome_tambem_e_rejeitada(plano_ok):
    plano_ok["capa"]["prompt_imagem"] = "album cover, in the style of a famous painter"
    assert any("prompt_imagem" in e for e in campos_prompt_en(plano_ok))


# E o conserto não pode virar um novo bug: descrição por característica passa.
def test_descricao_por_caracteristica_passa(plano_ok):
    plano_ok["musica"]["estilo"]["prompt_estilo"] = (
        "Nordic ritual folk anthem, tagelharpa drone, bone flute, throat-singing "
        "choir, war drums, male tenor with grit. Lyrics in Brazilian Portuguese."
    )
    assert campos_prompt_en(plano_ok) == []


def test_estado_valido():
    e = {"schema_version": "1", "slug": "x", "atualizado_em": "2026-08-20T14:00:00-03:00",
         "fase": "plano", "telegram": False, "teto_usd": None,
         "partes": {p: {"estado": "planejado", "aprovado_em": None, "ajustes": 0,
                        "tentativas": 0, "custo_estimado_usd": 0.0, "custo_real_usd": 0.0,
                        "artefato": None, "erro": None, "meta": {}}
                    for p in ("musica", "capa", "clipe")},
         "custo_total_usd": {"estimado": 0.0, "gasto": 0.0}, "historico": []}
    assert validar_estado(e) == []
    e["partes"]["musica"]["estado"] = "voando"
    assert validar_estado(e) != []


def test_campo_de_lista_como_string_e_erro(plano_ok):
    plano_ok["musica"]["estilo"]["mood"] = "determinada, vitoriosa"
    assert any("mood" in e and "lista" in e for e in validar_plano(plano_ok))
    plano_ok["musica"]["estilo"]["mood"] = ["determinada"]
    plano_ok["capa"]["paleta"] = "#E8A13C"
    assert any("paleta" in e for e in validar_plano(plano_ok))


def test_prompt_alt_e_opcional_mas_validado_como_EN(plano_ok):
    assert validar_plano(plano_ok) == []                      # sem alt: válido
    plano_ok["clipe"]["decupagem"][0]["prompt_alt"] = "empty workshop at dawn, no people"
    assert validar_plano(plano_ok) == []                      # com alt: válido
    plano_ok["clipe"]["decupagem"][0]["prompt_alt"] = "oficina vazia, luz âmbar"
    assert any("prompt_alt" in e for e in campos_prompt_en(plano_ok))

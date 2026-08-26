"""O pacote de canal: o destino não deve refazer título, descrição nem capa."""
import json

from PIL import Image

from src.arte import compor_capa_yt, YT_LARGURA, YT_ALTURA, YT_TETO_BYTES
from src.entrega import montar_publicacao, tags_de


def _plano(**extra):
    p = {
        "schema_version": "1", "slug": "faixa-teste", "criado_em": "2026-08-22",
        "solicitacao": "uma música", "pesquisa": False, "estilo_ref": "lo-fi-noturno",
        "titulo": "Chuva de Verão",
        "musica": {"motor": "suno:v4", "params": {}, "estilo": {
            "genero": "MPB", "bpm": 92, "tom": "Am",
            "mood": ["melancólico", "quente", "íntimo", "noturno", "sobra"],
            "instrumentacao": ["violão", "rhodes", "bateria", "sobra"],
            "voz": {}, "prompt_estilo": "x"},
            "estrutura": [], "letra": {"origem": "gerada", "texto": "a", "idioma": "pt"}},
        "capa": {"motor": "agnes:i", "params": {}, "template": "paisagem-simbolica",
                 "conceito": "c", "prompt_imagem": "p", "prompt_negativo": "n",
                 "paleta": ["#8ecae6"]},
        "clipe": {"motor": "agnes:v", "params": {}, "template": "narrativo",
                  "sincronia": "s", "decupagem": []},
    }
    p.update(extra)
    return p


def _slug(tmp_path, plano, com_clipe=True, com_crua=True):
    w = tmp_path / plano["slug"]
    (w / "raw").mkdir(parents=True)
    (w / "plano.json").write_text(json.dumps(plano), encoding="utf-8")
    if com_clipe:
        (w / "clipe.mp4").write_bytes(b"mp4")
    if com_crua:
        Image.new("RGB", (1024, 1024), (30, 40, 60)).save(w / "raw" / "capa-crua.png")
    return w


def test_tags_saem_do_plano_sem_modelo():
    t = tags_de(_plano())
    assert t[0] == "mpb"
    assert "melancolico" in t and "violao" in t      # sem acento, minúsculas
    assert "lo fi noturno" in t
    assert len(t) == len(set(t)) <= 15


def test_pacote_tem_tudo_que_o_destino_precisa(tmp_path):
    _slug(tmp_path, _plano(publicacao={"descricao": "Uma canção sobre a chuva."}))
    pasta = montar_publicacao(tmp_path, "faixa-teste")
    assert pasta and pasta.name == "publicacao"
    m = json.loads((pasta / "manifest.json").read_text(encoding="utf-8"))
    clip = m["clips"][0]
    assert clip["filename"] == "faixa-teste.mp4"
    assert clip["title"] == "Chuva de Verão"
    assert clip["description"] == "Uma canção sobre a chuva."
    assert clip["tags"] and clip["thumbnail"] == "capa-yt.jpg"
    assert (pasta / clip["filename"]).exists()
    assert (pasta / clip["thumbnail"]).exists()
    # agendamento e visibilidade são decisão do canal, não da peça
    assert "privacy" not in m and "publish_at" not in m


def test_sem_descricao_nao_sai_pacote(tmp_path):
    """Melhor não entregar do que entregar pedindo pro destino inventar."""
    _slug(tmp_path, _plano())
    assert montar_publicacao(tmp_path, "faixa-teste") is None


def test_sem_clipe_nao_sai_pacote(tmp_path):
    _slug(tmp_path, _plano(publicacao={"descricao": "x"}), com_clipe=False)
    assert montar_publicacao(tmp_path, "faixa-teste") is None


def test_sem_capa_crua_o_pacote_ainda_sai(tmp_path):
    """Vídeo + título + descrição já valem a entrega; a capa é o que falta."""
    _slug(tmp_path, _plano(publicacao={"descricao": "x"}), com_crua=False)
    pasta = montar_publicacao(tmp_path, "faixa-teste")
    m = json.loads((pasta / "manifest.json").read_text(encoding="utf-8"))
    assert "thumbnail" not in m["clips"][0]


def test_remontar_nao_deixa_lixo(tmp_path):
    _slug(tmp_path, _plano(publicacao={"descricao": "x"}))
    p1 = montar_publicacao(tmp_path, "faixa-teste")
    (p1 / "sobra.txt").write_text("velho")
    p2 = montar_publicacao(tmp_path, "faixa-teste")
    assert not (p2 / "sobra.txt").exists()
    assert not (tmp_path / "faixa-teste" / ".publicacao-tmp").exists()


def test_capa_yt_e_16x9_e_cabe_no_teto(tmp_path):
    crua = tmp_path / "crua.png"
    Image.new("RGB", (1024, 1024), (200, 30, 60)).save(crua)
    destino = tmp_path / "capa-yt.jpg"
    compor_capa_yt(crua, "Chuva de Verão", ["#ffffff"], "paisagem-simbolica", destino)
    assert Image.open(destino).size == (YT_LARGURA, YT_ALTURA)
    assert destino.stat().st_size <= YT_TETO_BYTES
    assert not destino.with_suffix(".base.png").exists()


# --- duas faixas = dois vídeos no pacote (2026-08-26) ------------------------

def test_pacote_leva_as_duas_faixas_como_dois_videos(tmp_path):
    """O Suno entrega duas MÚSICAS, não duas versões — cada uma merece sua
    publicação, com título e capa próprios."""
    w = _slug(tmp_path, _plano(publicacao={"descricao": "Uma canção sobre a chuva."}))
    for n in (1, 2):
        (w / f"faixa-{n}.mp3").write_bytes(b"m")
        (w / f"clipe-{n}.mp4").write_bytes(b"v" * 20)
    pasta = montar_publicacao(tmp_path, "faixa-teste")
    m = json.loads((pasta / "manifest.json").read_text(encoding="utf-8"))
    assert len(m["clips"]) == 2
    assert [c["filename"] for c in m["clips"]] == ["faixa-teste-1.mp4", "faixa-teste-2.mp4"]
    assert [c["title"] for c in m["clips"]] == ["Chuva de Verão (faixa 1)",
                                                "Chuva de Verão (faixa 2)"]
    assert [c["thumbnail"] for c in m["clips"]] == ["capa-yt-1.jpg", "capa-yt-2.jpg"]
    for c in m["clips"]:
        assert (pasta / c["filename"]).exists() and (pasta / c["thumbnail"]).exists()
    assert all(c["description"] for c in m["clips"])


def test_uma_faixa_so_continua_com_um_video_e_sem_sufixo(tmp_path):
    w = _slug(tmp_path, _plano(publicacao={"descricao": "Uma canção."}))
    (w / "faixa-1.mp3").write_bytes(b"m")
    pasta = montar_publicacao(tmp_path, "faixa-teste")
    m = json.loads((pasta / "manifest.json").read_text(encoding="utf-8"))
    assert len(m["clips"]) == 1
    assert m["clips"][0]["filename"] == "faixa-teste.mp4"
    assert m["clips"][0]["title"] == "Chuva de Verão"      # sem "(faixa 1)"
    assert m["clips"][0]["thumbnail"] == "capa-yt.jpg"

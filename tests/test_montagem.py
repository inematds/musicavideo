"""A montagem é o que transforma 3 arquivos soltos num clipe. Usa ffmpeg de verdade
(sintético, sem rede): é barato e é justamente o que os mocks deixaram passar."""
import subprocess
import pytest
from pathlib import Path

from src.montagem import montar, _ffprobe_duracao, MontagemError


def _video_mudo(alvo: Path, segundos: float):
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c=black:s=320x240:d={segundos}",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", str(alvo)],
                   capture_output=True, check=True)


def _audio(alvo: Path, segundos: float):
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"sine=frequency=440:duration={segundos}",
                    "-c:a", "libmp3lame", str(alvo)], capture_output=True, check=True)


def test_clipe_recebe_o_audio_da_faixa(tmp_path):
    v, a, alvo = tmp_path / "v.mp4", tmp_path / "f.mp3", tmp_path / "clipe.mp4"
    _video_mudo(v, 4)
    _audio(a, 10)
    meta = montar(v, a, alvo, fade_s=1.0)
    assert alvo.exists()
    streams = subprocess.run(["ffprobe", "-v", "quiet", "-show_entries", "stream=codec_type",
                              "-of", "csv=p=0", str(alvo)], capture_output=True, text=True).stdout
    assert "audio" in streams and "video" in streams   # o clipe TEM som
    assert meta["duracao_final_s"] == pytest.approx(4, abs=0.6)   # cortou no vídeo


def test_cobrir_musica_repete_o_video_ate_a_faixa_acabar(tmp_path):
    v, a, alvo = tmp_path / "v.mp4", tmp_path / "f.mp3", tmp_path / "clipe.mp4"
    _video_mudo(v, 2)
    _audio(a, 8)
    meta = montar(v, a, alvo, fade_s=1.0, cobrir_musica=True)
    assert meta["video_em_loop"] is True
    assert meta["duracao_final_s"] == pytest.approx(8, abs=0.6)   # cobre a música toda


def test_video_mais_longo_que_a_musica_mantem_o_video(tmp_path):
    v, a, alvo = tmp_path / "v.mp4", tmp_path / "f.mp3", tmp_path / "clipe.mp4"
    _video_mudo(v, 6)
    _audio(a, 2)
    meta = montar(v, a, alvo, fade_s=0.5)
    assert meta["video_em_loop"] is False
    assert meta["duracao_final_s"] == pytest.approx(6, abs=0.6)


def test_arquivo_invalido_da_erro_legivel(tmp_path):
    ruim = tmp_path / "nao-e-video.mp4"
    ruim.write_bytes(b"lixo")
    a = tmp_path / "f.mp3"
    _audio(a, 2)
    with pytest.raises(MontagemError):
        montar(ruim, a, tmp_path / "x.mp4")


def test_montagem_acha_a_faixa_que_voce_escolheu(tmp_path):
    """O Suno entrega faixa-1 e faixa-2; a montagem usa a APROVADA, não um nome fixo."""
    from src.executor import faixa_aprovada
    from src.estado import novo_estado, transicao
    (tmp_path / "faixa-1.mp3").write_bytes(b"a")
    (tmp_path / "faixa-2.mp3").write_bytes(b"b")
    e = novo_estado("s")
    transicao(e, "musica", "ok")
    transicao(e, "musica", "faz")
    transicao(e, "musica", "revisar", artefato="faixa-2.mp3", custo_real=0.08)
    transicao(e, "musica", "aprova")
    assert faixa_aprovada(tmp_path, e).name == "faixa-2.mp3"


def test_faixa_de_slug_antigo_ainda_e_encontrada(tmp_path):
    from src.executor import faixa_aprovada
    (tmp_path / "faixa.mp3").write_bytes(b"a")
    assert faixa_aprovada(tmp_path, None).name == "faixa.mp3"


def test_sem_faixa_nenhuma_devolve_none(tmp_path):
    from src.executor import faixa_aprovada
    assert faixa_aprovada(tmp_path, None) is None


# --------------------------------------------------- uma versão do clipe por faixa

def test_monta_uma_versao_por_faixa_e_aponta_pra_aprovada(tmp_path):
    """O Suno entrega duas faixas: o mesmo vídeo vira duas versões, e `clipe.mp4`
    é a da faixa aprovada — sem re-render, sem custo."""
    from src.montagem import montar_todas
    _video_mudo(tmp_path / "bruto.mp4", 4)
    _audio(tmp_path / "faixa-1.mp3", 6)
    _audio(tmp_path / "faixa-2.mp3", 10)
    meta = montar_todas(tmp_path, tmp_path / "bruto.mp4", cobrir_musica=True,
                        aprovada="faixa-2.mp3")
    assert meta["versoes"] == {"faixa-1.mp3": "clipe-1.mp4", "faixa-2.mp3": "clipe-2.mp4"}
    assert (tmp_path / "clipe-1.mp4").exists() and (tmp_path / "clipe-2.mp4").exists()
    # cada faixa tem a sua duração: são passadas de ffmpeg diferentes, não cópia
    assert _ffprobe_duracao(tmp_path / "clipe-1.mp4") == pytest.approx(6, abs=0.5)
    assert _ffprobe_duracao(tmp_path / "clipe-2.mp4") == pytest.approx(10, abs=0.5)
    assert meta["faixa_principal"] == "faixa-2.mp3"
    assert _ffprobe_duracao(tmp_path / "clipe.mp4") == pytest.approx(10, abs=0.5)


def test_faixa_unica_do_first_success_nao_e_erro(tmp_path):
    """Status FIRST_SUCCESS entrega só a faixa 1 — sai um clipe, sem estourar."""
    from src.montagem import montar_todas
    _video_mudo(tmp_path / "bruto.mp4", 3)
    _audio(tmp_path / "faixa-1.mp3", 5)
    meta = montar_todas(tmp_path, tmp_path / "bruto.mp4")
    assert meta["versoes"] == {"faixa-1.mp3": "clipe-1.mp4"}
    assert meta["principal"] == "clipe.mp4" and (tmp_path / "clipe.mp4").exists()


def test_slug_antigo_com_faixa_mp3_continua_saindo_em_clipe_mp4(tmp_path):
    from src.montagem import montar_todas
    _video_mudo(tmp_path / "bruto.mp4", 3)
    _audio(tmp_path / "faixa.mp3", 4)
    meta = montar_todas(tmp_path, tmp_path / "bruto.mp4")
    assert meta["versoes"] == {"faixa.mp3": "clipe.mp4"}
    assert not list(tmp_path.glob("clipe-*.mp4"))


def test_trocar_a_faixa_aprovada_reaponta_sem_novo_render(tmp_path):
    from src.montagem import montar_todas, apontar_clipe
    _video_mudo(tmp_path / "bruto.mp4", 4)
    _audio(tmp_path / "faixa-1.mp3", 6)
    _audio(tmp_path / "faixa-2.mp3", 10)
    montar_todas(tmp_path, tmp_path / "bruto.mp4", cobrir_musica=True, aprovada="faixa-1.mp3")
    antes = (tmp_path / "clipe-2.mp4").stat().st_mtime_ns
    apontar_clipe(tmp_path, tmp_path / "clipe-2.mp4")
    assert (tmp_path / "clipe-2.mp4").stat().st_mtime_ns == antes      # não re-renderizou
    assert _ffprobe_duracao(tmp_path / "clipe.mp4") == pytest.approx(10, abs=0.5)


def test_sem_faixa_nenhuma_estoura_montagem_error(tmp_path):
    from src.montagem import montar_todas
    _video_mudo(tmp_path / "bruto.mp4", 2)
    with pytest.raises(MontagemError):
        montar_todas(tmp_path, tmp_path / "bruto.mp4")


# --- recorte: ritmo sem gerar nada (2026-08-23) -------------------------------

def test_recorte_preserva_a_soma():
    """Encurtar refrão e esticar verso não pode encurtar o clipe — ele cobre a
    música, e a cobertura é o que separa clipe de vídeo em loop."""
    from src.recorte import duracoes_alvo
    secoes = ["intro"] * 3 + ["verso 1"] * 6 + ["refrão 1"] * 5 + ["ponte"] * 4
    orig = [5.0] * len(secoes)
    alvos = duracoes_alvo(secoes, orig)
    assert abs(sum(alvos) - sum(orig)) < 0.5
    assert min(alvos) >= 1.5


def test_refrao_fica_mais_curto_que_verso():
    from src.recorte import duracoes_alvo
    alvos = duracoes_alvo(["refrão 1", "verso 1"], [5.0, 5.0])
    assert alvos[0] < alvos[1]


def test_slowmo_tem_teto():
    """Esticar demais trava aos olhos — o alvo nunca passa de 1,6x o original."""
    from src.recorte import duracoes_alvo, LENTO_MAX
    alvos = duracoes_alvo(["verso"] * 2 + ["refrão"] * 8, [5.0] * 10)
    assert max(alvos) <= 5.0 * LENTO_MAX + 0.01


def test_expandir_fatia_antes_de_espelhar():
    """Metade de um plano é material NOVO; espelhar é o último recurso."""
    from pathlib import Path as P
    from src.recorte import expandir_sequencia
    shots = [P(f"shot-{i}.mp4") for i in range(4)]
    seq = expandir_sequencia(shots, ["refrão"] * 4, 8)
    assert len(seq) == 8
    assert not any(espelho for _, _, espelho, _ in seq)     # deu pra fatiar tudo
    assert all(fatia == (0, 2) or fatia == (1, 2) for _, fatia, _, _ in seq)


def test_expandir_nao_mexe_se_ja_tem_planos_bastante():
    from pathlib import Path as P
    from src.recorte import expandir_sequencia
    shots = [P("a.mp4"), P("b.mp4")]
    assert len(expandir_sequencia(shots, ["verso", "verso"], 2)) == 2

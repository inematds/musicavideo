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

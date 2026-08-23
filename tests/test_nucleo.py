"""O núcleo é MEDIDO, não opinado — então dá para testar com onda sintética."""
import math
import struct
import subprocess
import wave

import pytest

from src.nucleo import NucleoError, nucleo_de, rms_por_segundo


def _wav(path, blocos, taxa=8000):
    """Um wav onde cada bloco é (duração_s, amplitude 0..1)."""
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(taxa)
        for dur, amp in blocos:
            quadros = b"".join(
                struct.pack("<h", int(amp * 30000 * math.sin(2 * math.pi * 220 * i / taxa)))
                for i in range(int(dur * taxa)))
            w.writeframes(quadros)
    return path


@pytest.fixture(autouse=True)
def _precisa_de_ffmpeg():
    if subprocess.run(["which", "ffmpeg"], capture_output=True).returncode != 0:
        pytest.skip("ffmpeg ausente")


def test_acha_o_trecho_forte_no_meio(tmp_path):
    f = _wav(tmp_path / "a.wav", [(20, 0.1), (14, 1.0), (20, 0.1)])
    n = nucleo_de(f)
    assert 18 <= n["inicio_s"] <= 22          # entra junto com a parte alta
    assert n["fim_s"] - n["inicio_s"] == 12


def test_prefere_o_salto_e_nao_so_o_volume(tmp_path):
    """Dois trechos altos iguais: ganha o que SOBE depois de um vale — é a
    diferença entre 'o mais alto' e 'o momento em que a música vira'."""
    f = _wav(tmp_path / "b.wav", [(14, 0.9), (20, 0.05), (14, 0.9), (10, 0.05)])
    assert nucleo_de(f)["inicio_s"] > 20


def test_faixa_curta_demais_e_erro_claro(tmp_path):
    f = _wav(tmp_path / "c.wav", [(5, 0.5)])
    with pytest.raises(NucleoError, match="curta demais"):
        nucleo_de(f)


def test_curva_tem_um_valor_por_segundo(tmp_path):
    f = _wav(tmp_path / "d.wav", [(30, 0.5)])
    assert len(rms_por_segundo(f)) == 30


def test_arquivo_que_nao_e_audio(tmp_path):
    ruim = tmp_path / "e.mp3"
    ruim.write_text("isso não é áudio", encoding="utf-8")
    with pytest.raises(NucleoError):
        nucleo_de(ruim)

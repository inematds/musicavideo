import subprocess
import pytest
from pathlib import Path

from src.revisao import (folha_de_contato, descartar_shots, parse_numeros,
                         o_que_revisar, shots_de, RevisaoError)
from src.estado import novo_estado, transicao


def _shot(alvo: Path, cor: str, segundos: float = 2):
    alvo.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi",
                    "-i", f"color=c={cor}:s=320x176:d={segundos}",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", str(alvo)],
                   capture_output=True, check=True)


def test_folha_de_contato_junta_todos_os_shots(tmp_path):
    for i, cor in enumerate(["red", "green", "blue", "yellow", "white", "gray", "orange"], 1):
        _shot(tmp_path / "raw" / f"shot-{i:02d}.mp4", cor)
    folha = folha_de_contato(tmp_path)
    assert folha.exists() and folha.stat().st_size > 1000
    larg = subprocess.run(["ffprobe", "-v", "quiet", "-show_entries", "stream=width,height",
                           "-of", "csv=p=0", str(folha)], capture_output=True, text=True).stdout
    assert larg.strip()                       # é uma imagem de verdade
    assert not (tmp_path / "revisao" / "_frames").exists()   # limpou os temporários


def test_folha_sem_shots_erra_legivel(tmp_path):
    with pytest.raises(RevisaoError, match="nenhum shot"):
        folha_de_contato(tmp_path)


def test_descartar_apaga_so_os_reprovados(tmp_path):
    for i in (1, 2, 3):
        _shot(tmp_path / "raw" / f"shot-{i:02d}.mp4", "red")
    assert descartar_shots(tmp_path, [2]) == [2]
    assert [p.name for p in shots_de(tmp_path)] == ["shot-01.mp4", "shot-03.mp4"]


def test_parse_aceita_lista_e_intervalo():
    assert parse_numeros("4,17,23") == [4, 17, 23]
    assert parse_numeros("4-7,12") == [4, 5, 6, 7, 12]
    assert parse_numeros(" 3 , 3 ") == [3]


def test_o_que_revisar_lista_so_o_que_esta_no_portao(tmp_path):
    e = novo_estado("s")
    transicao(e, "musica", "ok")
    transicao(e, "musica", "faz")
    transicao(e, "musica", "revisar", artefato="faixa-1.mp3", custo_real=0.08)
    (tmp_path / "faixa-1.mp3").write_bytes(b"a")
    (tmp_path / "faixa-2.mp3").write_bytes(b"b")
    itens = o_que_revisar(tmp_path, e)
    assert len(itens) == 1 and itens[0]["parte"] == "musica"
    assert itens[0]["opcoes"] == ["faixa-1.mp3", "faixa-2.mp3"]   # as 2 faixas do Suno

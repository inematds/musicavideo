from pathlib import Path
import pytest
from src.registry import carregar_registry, resolver_motor, disponibilidade, validar_params
from providers.base import ler_env_chave, Resultado, Provider


def test_registry_tem_os_5_provedores_e_defaults():
    reg = carregar_registry()
    for motor in ("kie:suno-v4.5", "agnes:agnes-image-2.1-flash", "agnes:agnes-video-v2.0",
                  "inemaimg:flux2-klein", "kling:kling-v2_5", "fal:kling-v3-turbo"):
        assert motor in reg, motor


def test_resolver_motor_inexistente_erra_legivel():
    reg = carregar_registry()
    with pytest.raises(KeyError, match="nao-existe"):
        resolver_motor(reg, "nao-existe:modelo")


def test_disponibilidade_sem_chave_da_motivo(monkeypatch):
    monkeypatch.setenv("MUSICAVIDEO_ENV_DIRS", "/nonexistent-a:/nonexistent-b")
    reg = carregar_registry()
    ok, motivo = disponibilidade(reg)["kie"]
    assert ok is False and "KIE_API_KEY" in motivo and ".env" in motivo


def test_validar_params_rejeita_chave_desconhecida():
    reg = carregar_registry()
    _, modelo = resolver_motor(reg, "kie:suno-v4.5")
    assert validar_params(modelo, {"duracao_s": 180}) == []
    assert validar_params(modelo, {"xyz": 1}) != []


def test_ler_env_chave_nunca_retorna_de_env_nao_autorizado(monkeypatch, tmp_path):
    d = tmp_path / "a"
    d.mkdir()
    (d / ".env").write_text("MINHA_CHAVE=segredo\n")
    monkeypatch.setenv("MUSICAVIDEO_ENV_DIRS", str(d))
    assert ler_env_chave(["MINHA_CHAVE"]) == "segredo"
    assert ler_env_chave(["OUTRA"]) is None

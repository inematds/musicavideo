"""Contrato do adapter + utilitários compartilhados (stdlib only)."""
import json
import os
import time
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from pathlib import Path

ENV_DIRS_DEFAULT = [Path.home() / "projetos/openpcbotv2", Path.home() / "projetos/wifi"]


class ProviderError(Exception):
    pass


@dataclass
class Resultado:
    arquivo: Path
    custo_real: float
    meta: dict = field(default_factory=dict)


class Provider:
    nome: str = "?"

    def disponivel(self) -> tuple[bool, str]:
        raise NotImplementedError

    def estimar_custo(self, modelo: str, params: dict) -> float:
        raise NotImplementedError

    def gerar(self, modelo: str, params: dict, workdir: Path) -> Resultado:
        raise NotImplementedError


def _env_dirs() -> list[Path]:
    env = os.environ.get("MUSICAVIDEO_ENV_DIRS")
    if env:
        return [Path(p) for p in env.split(":")]
    return ENV_DIRS_DEFAULT


def ler_env_chave(nomes: list[str]) -> str | None:
    """Lê a 1ª chave encontrada nos .env autorizados. NUNCA logar o valor."""
    for d in _env_dirs():
        arq = d / ".env"
        if not arq.exists():
            continue
        for linha in arq.read_text(encoding="utf-8", errors="ignore").splitlines():
            linha = linha.strip()
            if "=" not in linha or linha.startswith("#"):
                continue
            k, _, v = linha.partition("=")
            if k.strip() in nomes and v.strip():
                return v.strip().strip('"').strip("'")
    return None


def motivo_indisponivel(nomes: list[str]) -> str:
    return f"{'/'.join(nomes)} não encontrada em openpcbotv2/.env nem wifi/.env"


def http_json(url: str, metodo: str = "GET", corpo: dict | None = None,
              headers: dict | None = None, tentativas: int = 4, timeout: int = 120) -> dict:
    dados = json.dumps(corpo).encode() if corpo is not None else None
    h = {"Content-Type": "application/json", **(headers or {})}
    for i in range(tentativas):
        try:
            req = urllib.request.Request(url, data=dados, headers=h, method=metodo)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            if e.code in (429, 502, 503) and i < tentativas - 1:
                time.sleep(2 ** (i + 1))
                continue
            raise ProviderError(f"HTTP {e.code} em {url}: {e.read().decode()[:300]}") from e
        except urllib.error.URLError as e:
            if i < tentativas - 1:
                time.sleep(2 ** (i + 1))
                continue
            raise ProviderError(f"rede indisponível em {url}: {e.reason}") from e
    raise ProviderError(f"esgotou tentativas em {url}")


UA = "Mozilla/5.0 (X11; Linux x86_64) musicavideo/1.0"


def baixar(url: str, destino: Path, timeout: int = 300) -> Path:
    """Baixa NA HORA (URLs de provedores expiram).

    O User-Agent não é enfeite: o CDN do Suno (tempfile.aiquickdraw.com)
    responde 403 ao UA padrão do urllib.
    """
    destino.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        destino.write_bytes(r.read())
    return destino


def gravar_raw(workdir: Path, nome: str, payload: dict) -> None:
    raw = workdir / "raw"
    raw.mkdir(exist_ok=True, parents=True)
    alvo, n = raw / f"{nome}.json", 2
    while alvo.exists():
        alvo = raw / f"{nome}-v{n}.json"
        n += 1
    alvo.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

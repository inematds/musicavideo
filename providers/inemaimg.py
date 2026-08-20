from pathlib import Path
from providers.base import Provider, Resultado, ProviderError, http_json

BASE_URL = "http://localhost:8000"


class Inemaimg(Provider):
    """Servidor local (DGX) de imagem — sem chave; disponibilidade = servidor no ar."""
    nome = "inemaimg"

    def __init__(self, decl):
        self.decl = decl

    def disponivel(self):
        try:
            http_json(f"{BASE_URL}/health", tentativas=1, timeout=3)
            return True, ""
        except Exception:
            return False, (f"{self.nome}: indisponível — servidor local não responde "
                           f"em localhost:8000")

    def estimar_custo(self, modelo, params):
        m = next(x for x in self.decl["modelos"] if x["id"] == modelo)
        c = m["custo"]
        if c["por"] == "segundo":
            return round(c["base_usd"] * float(params.get("duracao_shot_s", 5)), 4)
        return c["base_usd"]

    def gerar(self, modelo, params, workdir: Path) -> Resultado:
        raise ProviderError(f"{self.nome}: gerar() ainda não implementado")


def criar(decl):
    return Inemaimg(decl)

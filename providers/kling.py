from pathlib import Path
from providers.base import Provider, Resultado, ProviderError, ler_env_chave, motivo_indisponivel


class Kling(Provider):
    nome = "kling"

    def __init__(self, decl):
        self.decl = decl

    def disponivel(self):
        if ler_env_chave(self.decl["env_keys"]) is None:
            return False, f"{self.nome}: indisponível — {motivo_indisponivel(self.decl['env_keys'])}"
        return True, ""

    def estimar_custo(self, modelo, params):
        m = next(x for x in self.decl["modelos"] if x["id"] == modelo)
        c = m["custo"]
        if c["por"] == "segundo":
            return round(c["base_usd"] * float(params.get("duracao_shot_s", 5)), 4)
        return c["base_usd"]

    def gerar(self, modelo, params, workdir: Path) -> Resultado:
        raise ProviderError(f"{self.nome}: gerar() ainda não implementado")


def criar(decl):
    return Kling(decl)

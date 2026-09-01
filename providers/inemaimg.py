"""inemaimg — servidor local de imagem (flux2-klein no DGX). Sem chave, custo zero."""
import base64
from pathlib import Path

from providers.base import (Provider, Resultado, ProviderError, http_json, gravar_raw,
                            adaptar_prompt, regras_de_prompt)

BASE_URL = "http://localhost:8000"


class Inemaimg(Provider):
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
        largura, _, altura = (params.get("tamanho") or "1024x1024").partition("x")
        corpo = {"model": modelo,
                 "prompt": adaptar_prompt(regras_de_prompt(self.decl, modelo), params["prompt"]),
                 "negative_prompt": params.get("prompt_negativo", ""),
                 "width": int(largura), "height": int(altura)}
        resp = http_json(f"{BASE_URL}/generate", "POST", corpo, timeout=600)
        b64 = resp.get("image") or resp.get("image_base64") or ""
        if not b64:
            raise ProviderError(f"inemaimg: resposta sem imagem base64: {str(resp)[:300]}")
        gravar_raw(workdir, "inemaimg-capa", {"request": corpo, "response_keys": list(resp)})
        alvo = workdir / "capa.png"
        alvo.write_bytes(base64.b64decode(b64))
        return Resultado(alvo, 0.0, {"size": f"{largura}x{altura}"})


def criar(decl):
    return Inemaimg(decl)

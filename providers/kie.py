"""Música: Suno via api.kie.ai. O POST /generate já gasta — taskId vai pro raw/ antes do poll."""
import time
from pathlib import Path

from providers.base import (Provider, Resultado, ProviderError, ler_env_chave,
                            motivo_indisponivel, http_json, baixar, gravar_raw)

KIE_BASE = "https://api.kie.ai/api/v1"
TIMEOUT_POLL_S = 15 * 60


class Kie(Provider):
    nome = "kie"

    def __init__(self, decl):
        self.decl = decl

    def _headers(self):
        return {"Authorization": f"Bearer {ler_env_chave(self.decl['env_keys'])}"}

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
        m = next(x for x in self.decl["modelos"] if x["id"] == modelo)
        corpo = {"prompt": params["letra"],
                 "style": params["estilo"][:m["params"]["estilo_prompt_max_chars"]],
                 "title": params["titulo"], "customMode": True,
                 "instrumental": bool(params.get("instrumental", False)),
                 "model": m["api_model"], "negativeTags": params.get("negative_tags", "")}
        resp = http_json(f"{KIE_BASE}/generate", "POST", corpo, self._headers())
        task = (resp.get("data") or {}).get("taskId")
        if not task:
            raise ProviderError(f"kie: POST /generate sem taskId: {str(resp)[:300]}")
        gravar_raw(workdir, "kie-generate",
                   {"taskId": task, "request_sem_chave": corpo, "response": resp})
        inicio = time.time()
        faixas = []
        while True:
            if time.time() - inicio > TIMEOUT_POLL_S:
                raise ProviderError(f"kie: timeout de polling (15 min) taskId={task}")
            r = http_json(f"{KIE_BASE}/generate/record-info?taskId={task}",
                          headers=self._headers())
            d = r.get("data") or {}
            st = d.get("status", "")
            faixas = (d.get("response") or {}).get("sunoData") or []
            if faixas and (st in ("SUCCESS", "FIRST_SUCCESS") or st == ""):
                gravar_raw(workdir, "kie-record-info", r)
                break
            if "FAIL" in st or "ERROR" in st:
                raise ProviderError(f"kie: geração falhou: {d.get('errorMessage', st)}")
            time.sleep(15)
        alvo = baixar(faixas[0]["audioUrl"], workdir / "faixa.mp3")   # URL do Suno EXPIRA
        return Resultado(alvo, m["custo"]["base_usd"],
                         {"kie_task_id": task, "duracao_s": faixas[0].get("duration"),
                          "faixas_geradas": len(faixas)})


def criar(decl):
    return Kie(decl)

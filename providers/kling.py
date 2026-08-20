"""Clipe via Kling (kie /jobs). Alternativa paga ao Agnes.
# NÃO testado contra API real nesta rodada (2026-08-20) — só contrato/mock."""
import json
import time
from pathlib import Path

from providers.base import (Provider, Resultado, ProviderError, ler_env_chave,
                            motivo_indisponivel, http_json, baixar, gravar_raw)
from providers.agnes import concat_ffmpeg

KIE_BASE = "https://api.kie.ai/api/v1"
TIMEOUT_POLL_S = 15 * 60


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
        m = next(x for x in self.decl["modelos"] if x["id"] == modelo)
        h = {"Authorization": f"Bearer {ler_env_chave(self.decl['env_keys'])}"}
        shots_arq, custo = [], 0.0
        inicio = time.time()
        for shot in params["decupagem"]:
            corpo = {"model": m["api_model"],
                     "input": {"prompt": shot["prompt"],
                               "duration": int(shot["duracao_s"]),
                               "aspect_ratio": "16:9"}}
            resp = http_json(f"{KIE_BASE}/jobs/createTask", "POST", corpo, h)
            task = (resp.get("data") or {}).get("taskId")
            if not task:
                raise ProviderError(f"kling: createTask sem taskId: {str(resp)[:300]}")
            gravar_raw(workdir, f"kling-shot-{shot['n']:02d}",
                       {"request": corpo, "response": resp})
            while True:
                if time.time() - inicio > TIMEOUT_POLL_S:
                    raise ProviderError(f"kling: timeout de polling (15 min) taskId={task}")
                r = http_json(f"{KIE_BASE}/jobs/recordInfo?taskId={task}", headers=h)
                d = r.get("data") or {}
                if d.get("state") == "success":
                    urls = json.loads(d.get("resultJson") or "{}").get("resultUrls") or []
                    if not urls:
                        raise ProviderError(f"kling: success sem resultUrls taskId={task}")
                    shots_arq.append(baixar(urls[0],
                                            workdir / "raw" / f"shot-{shot['n']:02d}.mp4"))
                    break
                if d.get("state") in ("fail", "failed", "error"):
                    raise ProviderError(f"kling: shot {shot['n']} falhou: "
                                        f"{d.get('failMsg', d.get('state'))}")
                time.sleep(10)
            custo += self.estimar_custo(modelo, {"duracao_shot_s": shot["duracao_s"]})
        alvo = concat_ffmpeg(shots_arq, workdir / "clipe.mp4")
        return Resultado(alvo, round(custo, 4), {"shots": len(shots_arq)})


def criar(decl):
    return Kling(decl)

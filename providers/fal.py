"""Clipe via fal.ai (fila). Alternativa paga ao Agnes.
# NÃO testado contra API real nesta rodada (2026-08-20) — só contrato/mock."""
import time
from pathlib import Path

from providers.base import (Provider, Resultado, ProviderError, ler_env_chave,
                            motivo_indisponivel, http_json, baixar, gravar_raw)
from providers.agnes import concat_ffmpeg

TIMEOUT_POLL_S = 15 * 60


class Fal(Provider):
    nome = "fal"

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
        h = {"Authorization": f"Key {ler_env_chave(self.decl['env_keys'])}"}
        shots_arq, custo = [], 0.0
        inicio = time.time()
        for shot in params["decupagem"]:
            corpo = {"prompt": shot["prompt"], "duration": str(int(shot["duracao_s"]))}
            resp = http_json(f"https://queue.fal.run/{m['api_path']}", "POST", corpo, h)
            st_url, resp_url = resp.get("status_url"), resp.get("response_url")
            if not (st_url and resp_url):
                raise ProviderError(f"fal: enqueue sem status_url: {str(resp)[:300]}")
            gravar_raw(workdir, f"fal-shot-{shot['n']:02d}",
                       {"request": corpo, "response": resp})
            while True:
                if time.time() - inicio > TIMEOUT_POLL_S:
                    raise ProviderError(f"fal: timeout de polling (15 min) no shot {shot['n']}")
                st = http_json(st_url, headers=h)
                if st.get("status") == "COMPLETED":
                    r = http_json(resp_url, headers=h)
                    url = (r.get("video") or {}).get("url")
                    if not url:
                        raise ProviderError(f"fal: resposta sem video.url: {str(r)[:300]}")
                    shots_arq.append(baixar(url,
                                            workdir / "raw" / f"shot-{shot['n']:02d}.mp4"))
                    break
                if st.get("status") in ("FAILED", "ERROR"):
                    raise ProviderError(f"fal: shot {shot['n']} falhou: "
                                        f"{st.get('error', st.get('status'))}")
                time.sleep(10)
            custo += self.estimar_custo(modelo, {"duracao_shot_s": shot["duracao_s"]})
        alvo = concat_ffmpeg(shots_arq, workdir / "clipe.mp4")
        return Resultado(alvo, round(custo, 4), {"shots": len(shots_arq)})


def criar(decl):
    return Fal(decl)

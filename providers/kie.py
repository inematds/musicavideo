"""Música: Suno via api.kie.ai. O POST /generate já gasta — taskId vai pro raw/ antes do poll."""
import json
import os
import time
from pathlib import Path

from providers.base import (Provider, Resultado, ProviderError, ler_env_chave,
                            motivo_indisponivel, http_json, baixar, gravar_raw)

KIE_BASE = "https://api.kie.ai/api/v1"
TIMEOUT_POLL_S = 15 * 60
# A API devolve 422 "Please enter callBackUrl" sem este campo, embora o doc o
# marque como opcional. Não temos endpoint público: mandamos um placeholder e
# lemos o resultado por polling (mesmo caminho que o musicaclone usa).
CALLBACK_PLACEHOLDER = "https://example.com/kie-callback"


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

    def _task_reaproveitavel(self, workdir: Path):
        """Retry depois de falha PÓS-geração (download, rede) não deve pagar de
        novo: se a task anterior ainda entrega áudio, reusa o taskId."""
        raws = sorted((workdir / "raw").glob("kie-generate*.json"),
                      key=lambda f: f.stat().st_mtime, reverse=True)
        for arq in raws:
            try:
                task = json.loads(arq.read_text(encoding="utf-8")).get("taskId")
                if not task:
                    continue
                r = http_json(f"{KIE_BASE}/generate/record-info?taskId={task}",
                              headers=self._headers())
                d = r.get("data") or {}
                pronta = [f for f in ((d.get("response") or {}).get("sunoData") or [])
                          if (f.get("audioUrl") or "").startswith("http")]
                if pronta and d.get("status") in ("SUCCESS", "FIRST_SUCCESS"):
                    return task
            except Exception:
                continue
        return None

    def gerar(self, modelo, params, workdir: Path) -> Resultado:
        m = next(x for x in self.decl["modelos"] if x["id"] == modelo)
        if params.get("retry"):
            task = self._task_reaproveitavel(workdir)
            if task:
                print(f"kie: reaproveitando a geração já paga (taskId={task})")
                return self._colher(task, m, workdir, ja_pago=True)
        corpo = {"prompt": params["letra"],
                 "style": params["estilo"][:m["params"]["estilo_prompt_max_chars"]],
                 "title": params["titulo"], "customMode": True,
                 "instrumental": bool(params.get("instrumental", False)),
                 "model": m["api_model"], "negativeTags": params.get("negative_tags", ""),
                 "callBackUrl": os.environ.get("MUSICA_CALLBACK", CALLBACK_PLACEHOLDER)}
        resp = http_json(f"{KIE_BASE}/generate", "POST", corpo, self._headers())
        task = (resp.get("data") or {}).get("taskId")
        if not task:
            raise ProviderError(f"kie: POST /generate sem taskId: {str(resp)[:300]}")
        gravar_raw(workdir, "kie-generate",
                   {"taskId": task, "request_sem_chave": corpo, "response": resp})
        return self._colher(task, m, workdir)

    def _colher(self, task: str, m: dict, workdir: Path, ja_pago: bool = False) -> Resultado:
        inicio = time.time()
        faixas = []
        while True:
            if time.time() - inicio > TIMEOUT_POLL_S:
                raise ProviderError(f"kie: timeout de polling (15 min) taskId={task}")
            r = http_json(f"{KIE_BASE}/generate/record-info?taskId={task}",
                          headers=self._headers())
            d = r.get("data") or {}
            st = d.get("status", "")
            todas = (d.get("response") or {}).get("sunoData") or []
            # FIRST_SUCCESS = só uma faixa ficou pronta; as outras ainda vêm com
            # audioUrl vazio. Só serve a que já tem áudio de verdade.
            faixas = [f for f in todas if (f.get("audioUrl") or "").startswith("http")]
            if faixas and st in ("SUCCESS", "FIRST_SUCCESS"):
                gravar_raw(workdir, "kie-record-info", r)
                break
            if "FAIL" in st or "ERROR" in st:
                raise ProviderError(f"kie: geração falhou: {d.get('errorMessage', st)}")
            time.sleep(15)
        # a geração traz 2 faixas pelo mesmo preço — baixa as duas, você escolhe
        baixadas, duracoes = [], []
        for i, f in enumerate(faixas[:2], 1):
            baixadas.append(baixar(f["audioUrl"], workdir / f"faixa-{i}.mp3"))  # URL EXPIRA
            duracoes.append(f.get("duration"))
        return Resultado(baixadas[0], 0.0 if ja_pago else m["custo"]["base_usd"],
                         {"kie_task_id": task, "duracao_s": duracoes[0],
                          "faixas_geradas": len(baixadas), "status_final": st,
                          "opcoes": [p.name for p in baixadas], "duracoes_s": duracoes})


def criar(decl):
    return Kie(decl)

"""Clipe pelo Kling OFICIAL — CLI `kling` autenticado por OAuth, sem intermediário.

Diferente de todos os outros adapters: não é HTTP com chave, é subprocesso.
Quatro fatos medidos que moram aqui:

1. **Todo job é cobrado.** A própria ferramenta instrui a não re-submeter
   sozinho. Falhou, falhou: a mensagem sobe e quem decide é a pessoa. Por isso
   a cascata de substituição do Agnes NÃO se aplica aqui — só o `prompt_alt`,
   que é uma decisão sua tomada no plano.
2. **O CLI trunca stdout em 64 KB quando é pipe.** Toda captura passa por
   arquivo temporário.
3. **Cobra em CRÉDITOS do plano**, sem taxa publicada para dólar: o custo é
   medido pelo delta de `kling account` e reportado em créditos. O valor em
   dólar fica 0.0 — explicitamente desconhecido, nunca inventado.
4. **As URLs de resultado expiram em 24 h** — baixar na hora.
"""
import json
import os
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

from providers.base import (Provider, Resultado, ProviderError, baixar, gravar_raw,
                            adaptar_prompt, regras_de_prompt)
from providers.agnes import concat_ffmpeg

POLL_S = 10
TIMEOUT_JOB_S = 30 * 60
CREDENCIAIS = Path.home() / ".kling" / ".credentials"


def _kling_json(args: list[str], timeout: int = 900) -> dict:
    """Roda o CLI capturando por ARQUIVO — pipe corta em 64 KB (fato medido)."""
    tmp = Path(tempfile.gettempdir()) / f"kling-{uuid.uuid4().hex}.json"
    try:
        with open(tmp, "w") as saida:
            r = subprocess.run(["kling", *args], stdout=saida,
                               stderr=subprocess.PIPE, text=True, timeout=timeout)
        texto = tmp.read_text(encoding="utf-8", errors="ignore")
    except FileNotFoundError:
        raise ProviderError("kling: CLI não encontrado — `npm i -g @klingai/cli-global`")
    except subprocess.TimeoutExpired:
        raise ProviderError(f"kling: CLI travou (>{timeout}s) em {args[0]}")
    finally:
        tmp.unlink(missing_ok=True)
    i = texto.find("{")
    if i < 0:
        raise ProviderError(f"kling: saída sem JSON em {args[0]}: "
                            f"{(texto or r.stderr)[:300]}")
    try:
        return json.loads(texto[i:])
    except json.JSONDecodeError as e:
        raise ProviderError(f"kling: JSON inválido em {args[0]}: {e}")


def creditos() -> float | None:
    try:
        b = _kling_json(["account"], timeout=90).get("body") or {}
        v = b.get("availableRemainCredits")
        return float(v) if v is not None else None
    except ProviderError:
        return None


def _resolucao_kling(valor) -> str:
    """`1312x736` (vocabulário da Agnes) → `720p`. O kling só aceita 720p/1080p.

    O plano guarda os params do motor que estava escolhido quando ele foi feito.
    Trocar de motor no `faz --motor` troca o provedor, não o plano — e o
    adaptador é justamente quem traduz. Sem isto, `--motor clipe=kling:...` num
    plano nascido na Agnes morria com "Invalid value '1312x736' for argument
    'resolution'" (2026-08-21, ao contornar uma queda da Agnes no meio do
    MVD#89, com 8 dos 43 shots já prontos).

    Corte em 1080 de altura: acima disso é 1080p, o resto é 720p — e a altura é
    o que o rótulo nomeia.
    """
    texto = str(valor or "").strip().lower()
    if texto in ("720p", "1080p"):
        return texto
    if "x" in texto:
        try:
            altura = int(texto.split("x")[1])
        except (IndexError, ValueError):
            return "720p"
        return "1080p" if altura >= 1080 else "720p"
    return "1080p" if texto == "" else "720p"


DURACOES_KLING = (5, 10)     # o gerador só aceita estes dois; o resto é corte nosso


def duracao_gerada(pedida: float) -> int:
    """Quanto PEDIR ao Kling para um plano de `pedida` segundos.

    O gerador só entrega 5s ou 10s. Um plano de 3s vem de uma geração de 5s
    cortada; um de 12s, de uma geração de 10s esticada. Mandar o número cru
    (era o que acontecia até 2026-08-25) faz o Kling recusar o job — e com
    ritmo variável no plano, quase todo shot vira número que ele não aceita.
    """
    for d in DURACOES_KLING:
        if pedida <= d:
            return d
    return DURACOES_KLING[-1]


def ajustar_duracao(arq: Path, alvo_s: float) -> Path:
    """Encaixa o plano gerado na duração do PLANO: corta o miolo ou estica.

    O corte é de graça e não some com o plano; esticar é slowmo, com o mesmo
    teto de 1,6x que o recorte usa (além disso o olho vê travando).
    """
    from src.recorte import LENTO_MAX, RecorteError, _refazer_shot, duracao
    try:
        atual = duracao(arq)
        if abs(atual - alvo_s) < 0.25:
            return arq
        alvo_s = min(alvo_s, atual * LENTO_MAX)
        tmp = arq.with_suffix(".ajustado.mp4")
        _refazer_shot(arq, tmp, atual, alvo_s)
        tmp.replace(arq)
    except (RecorteError, OSError) as e:
        # o plano gerado vale mais que o encaixe: o clipe segue com a duração
        # que veio, e a montagem acomoda.
        print(f"kling: shot ficou com a duração do gerador ({e})")
    return arq


class Kling(Provider):
    nome = "kling"

    def __init__(self, decl):
        self.decl = decl

    def disponivel(self):
        if subprocess.run(["which", "kling"], capture_output=True).returncode != 0:
            return False, ("kling: indisponível — CLI oficial não instalado "
                           "(`npm i -g @klingai/cli-global`)")
        if not CREDENCIAIS.exists() and creditos() is None:
            return False, "kling: indisponível — não autenticado (`kling login`)"
        return True, ""

    def estimar_custo(self, modelo, params):
        """Cobra em créditos do plano, não em dólar. Sem taxa publicada, o custo
        em dólar é 0.0 e o consumo real aparece medido em créditos no meta."""
        return 0.0

    def _um_shot(self, modelo: str, shot: dict, params: dict, workdir: Path) -> tuple[Path, float | None]:
        m = next(x for x in self.decl["modelos"] if x["id"] == modelo)
        aceitos = m.get("params", {})
        flags = []
        for nome, valor in (("duration", duracao_gerada(float(shot.get("duracao_s", 5)))),
                            ("aspect_ratio", params.get("aspect_ratio", "16:9")),
                            ("resolution", _resolucao_kling(params.get("resolucao")))):
            if nome in aceitos:
                flags += [f"--{nome}", str(valor)]
        antes = creditos()
        texto = adaptar_prompt(regras_de_prompt(self.decl, modelo), shot["prompt"])
        resp = _kling_json(["text_to_video", "--model", m["api_model"], *flags, texto])
        if resp.get("ok") is False:
            raise ProviderError(f"kling recusou: {json.dumps(resp.get('body', resp))[:300]}")
        corpo = resp.get("body") or resp
        gid = (corpo.get("generation_id") or corpo.get("generationId")
               or (corpo.get("data") or {}).get("generation_id"))
        if not gid:
            raise ProviderError(f"kling: sem generation_id: {json.dumps(corpo)[:300]}")
        gravar_raw(workdir, f"kling-shot-{shot['n']:02d}",
                   {"model": m["api_model"], "flags": flags, "generation_id": gid,
                    "creditos_antes": antes})
        inicio = time.time()
        while time.time() - inicio < TIMEOUT_JOB_S:
            time.sleep(POLL_S)
            try:
                b = _kling_json(["query_tasks", str(gid)], timeout=120).get("body") or {}
            except ProviderError:
                continue          # consulta que falha não mata a tarefa lá no Kling
            tarefa = (b.get("tasks") or [b.get("task") or b])[0] if isinstance(b.get("tasks"), list) else (b.get("task") or b)
            urls = [w.get("url") or (w.get("resource") or {}).get("resource")
                    for w in (tarefa.get("works") or b.get("works") or [])]
            urls = [u for u in urls if u]
            if urls:
                arq = baixar(urls[0], workdir / "raw" / f"shot-{shot['n']:02d}.mp4")
                ajustar_duracao(arq, float(shot.get("duracao_s", 5)))
                depois = creditos()
                gasto = round(antes - depois, 2) if (antes is not None and depois is not None) else None
                return arq, gasto
            if str(tarefa.get("status") or tarefa.get("state") or "").lower() in ("failed", "error"):
                raise ProviderError(f"kling: shot {shot['n']} falhou: {json.dumps(tarefa)[:250]}")
        raise ProviderError(f"kling: tempo esgotado (30 min) no shot {shot['n']} — "
                            f"a tarefa pode concluir no site")

    def gerar(self, modelo, params, workdir: Path) -> Resultado:
        shots_arq, creditos_gastos, com_alt = [], 0.0, []
        for i, shot in enumerate(params["decupagem"]):
            pronto = workdir / "raw" / f"shot-{shot['n']:02d}.mp4"
            if pronto.exists() and pronto.stat().st_size > 10_000:
                shots_arq.append(pronto)
                continue
            try:
                arq, gasto = self._um_shot(modelo, shot, params, workdir)
            except ProviderError as e:
                # sem retry automático: cada job é cobrado. Só o plano B, que
                # você aprovou, tem direito a uma segunda submissão.
                if shot.get("prompt_alt") and ("recusou" in str(e) or "falhou" in str(e)):
                    print(f"kling: shot {shot['n']} recusado — tentando o prompt_alt")
                    alt = dict(shot, prompt=shot["prompt_alt"])
                    arq, gasto = self._um_shot(modelo, alt, params, workdir)
                    com_alt.append(shot["n"])
                else:
                    raise
            shots_arq.append(arq)
            if gasto:
                creditos_gastos += gasto
                print(f"kling: shot {shot['n']} pronto ({gasto:g} créditos)")
        alvo = concat_ffmpeg(shots_arq, workdir / "clipe.mp4")
        return Resultado(alvo, 0.0, {"shots": len(shots_arq), "shots_com_alt": com_alt,
                                     "creditos_kling": round(creditos_gastos, 2),
                                     "modelo": modelo})


def criar(decl):
    return Kling(decl)

"""Agnes AI — imagem E vídeo a custo ZERO (default de capa e clipe).

Fatos que importam:
- prompt DEVE ser em inglês (a API filtra português legítimo com 400);
- imagem: `size` sempre em PIXELS ("1024x1024"), nunca ratio;
- vídeo: `num_frames` segue 8n+1 com teto 441; rate limit real de 5 req/min;
- a resposta do vídeo MENTE o tamanho — conferir o arquivo com ffprobe;
- URLs de saída são temporárias: baixar na hora.
"""
import subprocess
import time
from pathlib import Path

from providers.base import (Provider, Resultado, ProviderError, ler_env_chave,
                            motivo_indisponivel, http_json, baixar, gravar_raw)

AGNES_BASE = "https://apihub.agnes-ai.com"
FPS = 24
MAX_FRAMES = 441
TIMEOUT_POLL_S = 15 * 60


def num_frames_para(duracao_s: float, fps: int = FPS) -> int:
    """Regra 8n+1, teto 441 (18,4s @24fps)."""
    alvo = min(int(round(duracao_s * fps)), MAX_FRAMES)
    n = max(1, round((alvo - 1) / 8))
    return min(8 * n + 1, MAX_FRAMES)


def concat_ffmpeg(shots: list, alvo: Path) -> Path:
    lista = alvo.parent / "raw" / "concat.txt"
    lista.parent.mkdir(exist_ok=True, parents=True)
    lista.write_text("".join(f"file '{s}'\n" for s in shots), encoding="utf-8")
    r = subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lista),
                        "-c", "copy", str(alvo)], capture_output=True, text=True)
    if r.returncode != 0:
        raise ProviderError(f"ffmpeg concat falhou: {r.stderr[-300:]}")
    return alvo


class Agnes(Provider):
    nome = "agnes"

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
        if modelo == "agnes-image-2.1-flash":
            return self._gerar_imagem(params, workdir)
        if modelo == "agnes-video-v2.0":
            return self._gerar_video(params, workdir)
        raise ProviderError(f"agnes: modelo desconhecido {modelo}")

    def _gerar_imagem(self, params, workdir: Path) -> Resultado:
        corpo = {"model": "agnes-image-2.1-flash",
                 "prompt": params["prompt"],                    # EN já validado no plano
                 "size": params.get("tamanho", "1024x1024")}    # PIXELS, nunca ratio
        resp = http_json(f"{AGNES_BASE}/v1/images/generations", "POST", corpo, self._headers())
        gravar_raw(workdir, "agnes-capa", {"request": corpo, "response": resp})
        dados = resp.get("data") or []
        if not dados or not dados[0].get("url"):
            raise ProviderError(f"agnes: resposta sem url de imagem: {str(resp)[:300]}")
        alvo = baixar(dados[0]["url"], workdir / "capa.png")    # URL temporária: baixar já
        return Resultado(alvo, 0.0, {"size": corpo["size"]})

    def _gerar_video(self, params, workdir: Path) -> Resultado:
        w, h = (params.get("resolucao") or "1312x736").split("x")
        shots_arq, video_ids, barrados = [], [], []
        for i, shot in enumerate(params["decupagem"]):
            pronto = workdir / "raw" / f"shot-{shot['n']:02d}.mp4"
            if pronto.exists() and pronto.stat().st_size > 10_000:
                shots_arq.append(pronto)   # já gerado numa corrida anterior: não refaz
                continue
            inicio_shot = time.time()   # timeout é POR shot, não do clipe inteiro
            if i > 0:
                time.sleep(12)                       # rate limit real: 5 req/min
            corpo = {"model": "agnes-video-v2.0", "prompt": shot["prompt"],
                     "num_frames": num_frames_para(shot["duracao_s"]),
                     "frame_rate": FPS, "width": int(w), "height": int(h)}
            try:
                resp = http_json(f"{AGNES_BASE}/v1/videos", "POST", corpo, self._headers())
            except ProviderError as e:
                # filtro de conteúdo barra UM shot — não é motivo pra perder o clipe
                if "content_policy" in str(e) or "HTTP 400" in str(e):
                    barrados.append(shot["n"])
                    print(f"agnes: shot {shot['n']} barrado pelo filtro de conteúdo — pulando")
                    continue
                raise
            vid = resp.get("video_id") or resp.get("task_id") or resp.get("id")
            if not vid:
                raise ProviderError(f"agnes: POST /videos sem id: {str(resp)[:300]}")
            video_ids.append(vid)
            gravar_raw(workdir, f"agnes-shot-{shot['n']:02d}",
                       {"request": corpo, "response": resp})
            while True:
                if time.time() - inicio_shot > TIMEOUT_POLL_S:
                    raise ProviderError(f"agnes: timeout de polling (15 min) no shot {shot['n']}")
                st = http_json(f"{AGNES_BASE}/agnesapi?video_id={vid}", headers=self._headers())
                if st.get("status") == "completed":
                    url = st.get("video_url") or st.get("url")
                    arq = baixar(url, workdir / "raw" / f"shot-{shot['n']:02d}.mp4")
                    shots_arq.append(arq)
                    break
                if st.get("status") == "failed":
                    barrados.append(shot["n"])
                    print(f"agnes: shot {shot['n']} falhou ({st.get('error', '')}) — pulando")
                    break
                time.sleep(10)
        total = len(params["decupagem"])
        if len(shots_arq) < total * 0.8:
            raise ProviderError(
                f"agnes: só {len(shots_arq)} de {total} shots saíram "
                f"(barrados: {barrados}) — pouco pra montar um clipe")
        if barrados:
            print(f"agnes: clipe montado sem os shots {barrados} "
                  f"({len(shots_arq)}/{total} entraram)")
        shots_arq.sort(key=lambda p: p.name)
        alvo = concat_ffmpeg(shots_arq, workdir / "clipe.mp4")
        try:   # a resposta MENTE o size — medir o arquivo real
            probe = subprocess.run(["ffprobe", "-v", "quiet", "-show_entries",
                                    "stream=width,height", "-of", "csv=p=0", str(alvo)],
                                   capture_output=True, text=True).stdout.strip()
        except FileNotFoundError:
            probe = "ffprobe ausente"
        return Resultado(alvo, 0.0, {"shots": len(shots_arq), "video_ids": video_ids,
                                     "shots_barrados": barrados, "size_real": probe})


def criar(decl):
    return Agnes(decl)

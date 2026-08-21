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


def _barrou(e: Exception) -> bool:
    """Filtro de conteúdo (ou 400 equivalente) — não é falha de infraestrutura."""
    t = str(e)
    return "content_policy" in t or "HTTP 400" in t or "failed" in t


def _vizinho_da_secao(decupagem: list, shot: dict, feitos: dict):
    """Um shot JÁ pronto da mesma seção — o mais próximo em número."""
    candidatos = [s["n"] for s in decupagem
                  if s.get("secao") == shot.get("secao") and s["n"] in feitos]
    if not candidatos:
        return None
    return feitos[min(candidatos, key=lambda n: abs(n - shot["n"]))]


def variacao_de(origem: Path, alvo: Path) -> Path:
    """Espelha o vizinho pra não parecer repetição pura. Preserva a duração."""
    r = subprocess.run(["ffmpeg", "-y", "-i", str(origem), "-vf", "hflip",
                        "-c:a", "copy", str(alvo)], capture_output=True, text=True)
    if r.returncode != 0 or not alvo.exists():
        raise ProviderError(f"ffmpeg falhou ao preencher shot: {r.stderr[-200:]}")
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

    def _um_shot(self, prompt: str, shot: dict, w: str, h: str, workdir: Path,
                 sufixo: str = "") -> Path:
        """Gera UM shot. Levanta ProviderError se barrar ou falhar."""
        corpo = {"model": "agnes-video-v2.0", "prompt": prompt,
                 "num_frames": num_frames_para(shot["duracao_s"]),
                 "frame_rate": FPS, "width": int(w), "height": int(h)}
        resp = http_json(f"{AGNES_BASE}/v1/videos", "POST", corpo, self._headers())
        vid = resp.get("video_id") or resp.get("task_id") or resp.get("id")
        if not vid:
            raise ProviderError(f"agnes: POST /videos sem id: {str(resp)[:300]}")
        gravar_raw(workdir, f"agnes-shot-{shot['n']:02d}{sufixo}",
                   {"request": corpo, "response": resp})
        inicio = time.time()
        while True:
            if time.time() - inicio > TIMEOUT_POLL_S:
                raise ProviderError(f"agnes: timeout de polling (15 min) no shot {shot['n']}")
            # 404 NO POLL NÃO É FALHA — é a task ainda não visível no endpoint de
            # status. O POST já devolveu o id; o backend só registra a task com
            # algum atraso, e nesse intervalo o status responde
            # `404 task not found`.
            #
            # Custou o MVD#89 (2026-08-21): o shot 9 foi abortado por esse 404
            # em duas tentativas seguidas, e o diagnóstico virou "a Agnes está
            # fora do ar" — quando as duas tasks tinham COMPLETADO em 73s. O
            # vídeo foi gerado e jogado fora, e a conclusão errada levou a uma
            # troca de motor que gastou crédito de outro provedor.
            #
            # Só antes do primeiro `completed`: task que some DEPOIS de ter
            # aparecido é outra história, e aí o timeout de 15 min fecha.
            try:
                st = http_json(f"{AGNES_BASE}/agnesapi?video_id={vid}", headers=self._headers())
            except ProviderError as e:
                if "404" in str(e):
                    time.sleep(10)
                    continue
                raise
            if st.get("status") == "completed":
                url = st.get("video_url") or st.get("url")
                return baixar(url, workdir / "raw" / f"shot-{shot['n']:02d}.mp4")
            if st.get("status") == "failed":
                raise ProviderError(f"agnes: shot {shot['n']} failed: {st.get('error', '')}")
            time.sleep(10)

    def _gerar_video(self, params, workdir: Path) -> Resultado:
        """Cascata por shot: prompt → prompt_alt → reescrita → vizinho da seção.

        A duração total é sagrada: é ela que mantém imagem e música alinhadas.
        Perder variedade num shot é aceitável; encurtar o clipe desloca TUDO
        que vem depois."""
        w, h = (params.get("resolucao") or "1312x736").split("x")
        reescrever = params.get("reescrever")      # injetado pelo executor (Fable)
        decupagem = params["decupagem"]
        feitos: dict[int, Path] = {}
        barrados, com_alt, reescritos, preenchidos = [], [], [], []

        for i, shot in enumerate(decupagem):
            n = shot["n"]
            pronto = workdir / "raw" / f"shot-{n:02d}.mp4"
            if pronto.exists() and pronto.stat().st_size > 10_000:
                feitos[n] = pronto            # de corrida anterior: não refaz
                continue
            if i > 0:
                time.sleep(12)                # rate limit real: 5 req/min

            tentativas = [("prompt", shot["prompt"])]
            if shot.get("prompt_alt"):
                tentativas.append(("alt", shot["prompt_alt"]))

            erro_final = None
            for origem, prompt in tentativas:
                try:
                    feitos[n] = self._um_shot(prompt, shot, w, h, workdir,
                                              "" if origem == "prompt" else f"-{origem}")
                    if origem == "alt":
                        com_alt.append(n)
                        print(f"agnes: shot {n} barrado — entrou pelo prompt_alt")
                    break
                except ProviderError as e:
                    if not _barrou(e):
                        raise
                    erro_final = e
            if n in feitos:
                continue

            if reescrever:                    # rede de segurança: Fable reescreve na hora
                try:
                    novo_prompt = reescrever(shot, str(erro_final))
                    if novo_prompt:
                        time.sleep(12)
                        feitos[n] = self._um_shot(novo_prompt, shot, w, h, workdir, "-reescrito")
                        reescritos.append(n)
                        print(f"agnes: shot {n} entrou com prompt reescrito na hora")
                        continue
                except ProviderError as e:
                    if not _barrou(e):
                        raise
                    erro_final = e
                except Exception as e:        # reescritor quebrado não derruba o clipe
                    print(f"agnes: reescrita do shot {n} falhou ({e})")

            vizinho = _vizinho_da_secao(decupagem, shot, feitos)
            if vizinho is not None:           # preserva a DURAÇÃO, que é o que importa
                variacao_de(vizinho, workdir / "raw" / f"shot-{n:02d}.mp4")
                feitos[n] = workdir / "raw" / f"shot-{n:02d}.mp4"
                preenchidos.append(n)
                print(f"agnes: shot {n} preenchido com variação de um vizinho da mesma seção")
                continue

            barrados.append(n)
            print(f"agnes: shot {n} BARRADO e sem substituto — o clipe encurta "
                  f"{shot['duracao_s']}s e a sincronia desloca daqui pra frente")

        shots_arq = [feitos[s["n"]] for s in decupagem if s["n"] in feitos]
        total = len(decupagem)
        if len(shots_arq) < total * 0.8:
            raise ProviderError(
                f"agnes: só {len(shots_arq)} de {total} shots saíram "
                f"(barrados: {barrados}) — pouco pra montar um clipe")
        if barrados:
            print(f"agnes: clipe montado sem os shots {barrados} "
                  f"({len(shots_arq)}/{total} entraram)")
        alvo = concat_ffmpeg(shots_arq, workdir / "clipe.mp4")
        try:   # a resposta MENTE o size — medir o arquivo real
            probe = subprocess.run(["ffprobe", "-v", "quiet", "-show_entries",
                                    "stream=width,height", "-of", "csv=p=0", str(alvo)],
                                   capture_output=True, text=True).stdout.strip()
        except FileNotFoundError:
            probe = "ffprobe ausente"
        return Resultado(alvo, 0.0, {"shots": len(shots_arq), "shots_barrados": barrados,
                                     "shots_com_alt": com_alt, "shots_reescritos": reescritos,
                                     "shots_preenchidos": preenchidos, "size_real": probe})


def criar(decl):
    return Agnes(decl)

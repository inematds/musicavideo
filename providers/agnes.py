"""Agnes AI — imagem E vídeo a custo ZERO (default de capa e clipe).

Fatos que importam:
- prompt DEVE ser em inglês (a API filtra português legítimo com 400);
- imagem: `size` sempre em PIXELS ("1024x1024"), nunca ratio;
- vídeo: `num_frames` segue 8n+1 com teto POR RESOLUÇÃO (720p=481 → 20,0s
  @24fps; 480p=961; 1080p=241) e rate limit real de 6 req/min — os três
  medidos em 2026-08-31 contra a API, ver `videos-agnes/README.md`;
- a resposta do vídeo MENTE o tamanho — conferir o arquivo com ffprobe;
- URLs de saída são temporárias: baixar na hora;
- **404 no poll não é falha**: o POST devolve o id na hora, mas o endpoint de
  status registra a task com atraso e responde `404 task not found` no
  intervalo. Abortar aí joga fora vídeo que ficou pronto (MVD#89, 2026-08-21);
- **503 `video_queue_full` no POST não é falha**: é o provedor dizendo "retry
  later". Espera-se 60s dentro do mesmo teto do polling (MVD#91);
- **`resolucao` pode vir como RÓTULO** (`1080p`) em vez de pixels: é o
  vocabulário de outro provedor chegando pelo plano. Traduzir é papel do
  adaptador — `1080p".split("x")` estourou o clipe do MVD#90 com 47 shots
  planejados e a música já paga.

ONDE ESTÁ O RESTO DO CONHECIMENTO desta API, que não cabe aqui:
- `~/projetos/videos-agnes/pipeline.py` — o irmão que roda esta API há mais
  tempo, e de onde vieram o teto de polling (45 min) e a espera de 70s no 429.
  Ele tolera QUALQUER erro no poll; nós toleramos 404 e 429 e deixamos o resto
  abortar, para não esconder chave errada atrás de 45 minutos de espera.
- `~/projetos/bench-studio-br/docs/RELATORIO-integracao-modelos.md` — medições
  de ponta a ponta (o vídeo de 3,4s levou 71s de parede e 4 polls).
"""
import calendar
import re
import subprocess
import time
from pathlib import Path

from providers.base import (Provider, Resultado, ProviderError, ler_env_chave,
                            motivo_indisponivel, http_json, baixar, gravar_raw)

AGNES_BASE = "https://apihub.agnes-ai.com"
FPS = 24
# Teto de frames POR RESOLUÇÃO, medido 2026-08-31 (a própria API devolve a
# tabela no erro 400): 480p=961, 720p=481, 1080p=241 — a proporção não altera.
# `PADRAO_WH` é 720p, daí o default 481. Era 441, número que não existe na API:
# custava ~1,7s de teto por shot.
MAX_FRAMES_POR_ALTURA = ((1000, 241), (700, 481), (0, 961))
MAX_FRAMES = 481

# A FAMÍLIA 2.5 TEM OUTRO CONTRATO DE REQUEST — não é o v2.0 com outro nome.
# Medido 2026-09-01 contra a API (o v2.0 continua exatamente como estava):
#   v2.0  : num_frames (8n+1) + frame_rate + width/height
#   2.5-* : mode ("text" | "keyframe") + seconds STRING em [4,12] + n
#           + size ("720P") + aspect_ratio ("16:9"); `frame_rate` responde
#           `not an allowed request field` e `width` responde `is a forbidden
#           field`. Mandar o corpo do v2.0 dá 400 — que o `_barrou` lê como
#           filtro de conteúdo, e o shot cai na cascata como se tivesse sido
#           censurado. Foi o que aconteceu na primeira tentativa de re-render.
# `mode:"keyframe"` exige first_frame e/ou last_frame (não usamos: aqui é t2v).
SEGUNDOS_MIN_25, SEGUNDOS_MAX_25 = 4, 12


def url_status(modelo: str, vid: str) -> str:
    """O POLL da 2.5 é OUTRO ENDPOINT — e o do v2.0 responde `404 task not
    found` para uma task 2.5, que o código lê como "ainda não registrada" e
    espera o timeout inteiro. Custou 45 min de polling num vídeo que já estava
    pronto em 49 s (2026-09-01)."""
    if familia_25(modelo):
        return f"{AGNES_BASE}/v1/videos/{vid}"
    return f"{AGNES_BASE}/agnesapi?video_id={vid}"


def url_do_video(st: dict) -> str | None:
    """v2.0: `video_url`/`url` na raiz. 2.5: dentro de `metadata.url`."""
    return (st.get("video_url") or st.get("url")
            or (st.get("metadata") or {}).get("url")
            or (st.get("data") or [{}])[0].get("url"))


def familia_25(modelo: str) -> bool:
    return "2.5" in modelo


def segundos_25(duracao_s: float) -> str:
    """A 2.5 só aceita 4..12 s inteiros, como STRING."""
    return str(int(min(max(round(duracao_s), SEGUNDOS_MIN_25), SEGUNDOS_MAX_25)))


def _tamanho_25(altura: int) -> str:
    return "1080P" if altura > 1000 else ("480P" if altura <= 500 else "720P")


def _proporcao_25(w: int, h: int) -> str:
    from fractions import Fraction
    conhecidas = {(16, 9): "16:9", (9, 16): "9:16", (1, 1): "1:1",
                  (4, 3): "4:3", (3, 4): "3:4"}
    alvo = w / h
    return min(conhecidas.items(), key=lambda kv: abs(kv[0][0] / kv[0][1] - alvo))[1]


def corpo_video(modelo: str, prompt: str, duracao_s: float, w: int, h: int) -> dict:
    """O corpo certo para CADA família — ver o bloco acima."""
    if familia_25(modelo):
        return {"model": modelo, "prompt": prompt, "mode": "text",
                "seconds": segundos_25(duracao_s), "n": 1,
                "size": _tamanho_25(h), "aspect_ratio": _proporcao_25(w, h)}
    return {"model": modelo, "prompt": prompt,
            "num_frames": num_frames_para(duracao_s, altura=h),
            "frame_rate": FPS, "width": w, "height": h}
# 45 min, e o número não é chute: é o `ESPERA_VIDEO` do `videos-agnes`
# (`pipeline.py`), projeto irmão que roda esta mesma API há mais tempo. Lá o
# comentário registra o porquê — "30min deixava job lento virar buraco no
# filme". Aqui era 15 min, escolhido sem essa evidência.
TIMEOUT_POLL_S = 45 * 60
TETO_ESPERA_COTA_S = 8 * 3600   # cota diária: até 8h de espera, nunca indefinido
_COTA_RE = re.compile(r"(\d{4}-\d{2}-\d{2})[ T](\d{2}):(\d{2})")


# Rótulo de resolução → PIXELS, que é o vocabulário desta API (`width`/`height`).
#
# O plano guarda o que o planejador escreveu, e ele às vezes escreve `1080p` —
# rótulo do kling, não da Agnes. Um `"1080p".split("x")` devolve um item só e
# estoura `ValueError: not enough values to unpack`, DEPOIS de a música estar
# pronta e paga: foi o MVD#90 (2026-08-21), com 47 shots planejados e nenhum
# gerado.
#
# É o espelho exato do `_resolucao_kling` (que traduz WxH → rótulo). Cada
# provedor tem seu vocabulário, e traduzir é papel do adaptador — não do plano,
# que nasce antes de se saber qual motor vai rodar.
PADRAO_WH = ("1312", "736")
_ROTULOS = {"720p": ("1280", "720"), "1080p": ("1920", "1080"), "480p": ("854", "480")}


def _resolucao_agnes(valor) -> tuple[str, str]:
    texto = str(valor or "").strip().lower()
    if texto in _ROTULOS:
        return _ROTULOS[texto]
    if "x" in texto:
        w, _, h = texto.partition("x")
        if w.isdigit() and h.isdigit():
            return (w, h)
    return PADRAO_WH


def max_frames_para(altura: int) -> int:
    """Teto de frames da resolução usada (a API valida por altura de saída)."""
    for minimo, teto in MAX_FRAMES_POR_ALTURA:
        if altura > minimo:
            return teto
    return MAX_FRAMES


def num_frames_para(duracao_s: float, fps: int = FPS, altura: int = 736) -> int:
    """Regra 8n+1, teto conforme a resolução (720p = 481 = 20,0s @24fps)."""
    teto = max_frames_para(altura)
    alvo = min(int(round(duracao_s * fps)), teto)
    n = max(1, round((alvo - 1) / 8))
    return min(8 * n + 1, teto)


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


def _cota_diaria(e: Exception) -> bool:
    """`429 Daily API usage limit reached` — cota do dia, não falha."""
    txt = str(e).lower()
    return "429" in txt and ("daily" in txt or "usage limit" in txt or "quota" in txt)


def segundos_ate_reset(msg: str, agora: float | None = None) -> float:
    """Quanto falta até o horário que o PRÓPRIO erro informa (em UTC).

    A mensagem traz `Please try again after **2026-08-26 00:00 UTC**`. Ler o
    horário dela é melhor que chutar: a espera é a resposta do provedor, não um
    palpite nosso. Sem horário legível, cai numa hora — tempo de a cota virar
    sem prender a fila de render a noite inteira.
    """
    agora = time.time() if agora is None else agora
    m = _COTA_RE.search(msg or "")
    if not m:
        return 3600.0
    data, hora, minuto = m.group(1), int(m.group(2)), int(m.group(3))
    ano, mes, dia = (int(x) for x in data.split("-"))
    alvo = calendar.timegm((ano, mes, dia, hora, minuto, 0, 0, 0, 0))
    return max(60.0, min(alvo - agora + 60, TETO_ESPERA_COTA_S))


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

    # CONTAS EM CASCATA. A cota é DIÁRIA e por conta: quando a primeira estoura,
    # a segunda (`inemaccbottime`) ainda tem o dia inteiro. Trocar de conta
    # custa zero e devolve o render na hora — dormir até o reset é o último
    # recurso, não o primeiro.
    def _chaves(self) -> list[str]:
        nomes = list(self.decl.get("env_keys") or [])
        return [n for n in nomes if ler_env_chave([n])]

    def _headers(self):
        chaves = self._chaves()
        i = min(getattr(self, "_conta", 0), max(0, len(chaves) - 1))
        nome = chaves[i] if chaves else (self.decl.get("env_keys") or ["AGNES_API_KEY"])[0]
        return {"Authorization": f"Bearer {ler_env_chave([nome])}"}

    def _proxima_conta(self) -> bool:
        """Vira para a próxima conta com chave. False = não há reserva."""
        atual = getattr(self, "_conta", 0)
        if atual + 1 >= len(self._chaves()):
            return False
        self._conta = atual + 1
        print(f"agnes: trocando para a conta reserva "
              f"({self._chaves()[self._conta]}) — a cota da anterior estourou", flush=True)
        return True

    def disponivel(self):
        if not self._chaves():
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
        if modelo.startswith("agnes-video-"):
            return self._gerar_video(params, workdir, modelo)
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
                 sufixo: str = "", modelo: str = "agnes-video-v2.0") -> Path:
        """Gera UM shot. Levanta ProviderError se barrar ou falhar.

        `modelo` vem do plano/`--motor`: o corpo hardcodava `agnes-video-v2.0` e
        um pedido de re-render em 2.5-flash renderizaria em v2.0 em silêncio."""
        corpo = corpo_video(modelo, prompt, shot["duracao_s"], int(w), int(h))
        # FILA CHEIA NÃO É FALHA. O POST responde
        # `503 video_queue_full: video queue is full, please retry later` quando
        # a fila da Agnes lota — e o `http_json` até repete, mas na exponencial
        # curta (2s, 4s, 8s), que devolve para dentro da mesma lotação. Abortar
        # ali derrubou o clipe do MVD#91 com a música já pronta e paga.
        #
        # Esperar é o certo porque o provedor DIZ "retry later": a espera é a
        # resposta dele, não um palpite nosso. O teto é o mesmo do polling, e
        # dentro dele são poucas tentativas longas em vez de muitas curtas.
        resp = None
        limite = time.time() + TIMEOUT_POLL_S
        while resp is None:
            try:
                resp = http_json(f"{AGNES_BASE}/v1/videos", "POST", corpo, self._headers())
            except ProviderError as e:
                # COTA DIÁRIA TAMBÉM NÃO É FALHA — e essa custa mais caro que a
                # fila cheia: o erro derrubava a produção inteira e ela ficava
                # marcada `erro`, parada a noite toda, mesmo depois de a cota
                # virar (MVD "Levanta o Céu", 2026-08-25). O reset vem escrito
                # na mensagem; dormir até lá é a resposta do provedor.
                if _cota_diaria(e):
                    if self._proxima_conta():
                        continue          # a reserva tem o dia inteiro: sem espera
                    espera = segundos_ate_reset(str(e))
                    print(f"agnes: COTA DIÁRIA estourada no shot {shot['n']} — "
                          f"dormindo {espera / 3600:.1f}h até o reset informado pela API",
                          flush=True)
                    time.sleep(espera)
                    limite = time.time() + TIMEOUT_POLL_S    # o relógio da fila recomeça
                    continue
                cheia = "503" in str(e) or "queue_full" in str(e) or "queue is full" in str(e)
                if not cheia or time.time() > limite:
                    raise
                print(f"agnes: fila cheia no shot {shot['n']} — esperando 60s", flush=True)
                time.sleep(60)
        vid = resp.get("video_id") or resp.get("task_id") or resp.get("id")
        if not vid:
            raise ProviderError(f"agnes: POST /videos sem id: {str(resp)[:300]}")
        gravar_raw(workdir, f"agnes-shot-{shot['n']:02d}{sufixo}",
                   {"request": corpo, "response": resp})
        inicio = time.time()
        while True:
            if time.time() - inicio > TIMEOUT_POLL_S:
                raise ProviderError(f"agnes: timeout de polling ({TIMEOUT_POLL_S // 60} min) no shot {shot['n']}")
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
            #
            # E 429 é rate limit (6 req/min, real): espera LONGA, não a
            # exponencial curta do `http_json` (2s, 4s, 8s — que devolve para
            # dentro da mesma janela e leva outro 429). O `videos-agnes` dorme
            # 70s aqui, e é o número que sobreviveu ao uso.
            try:
                st = http_json(url_status(modelo, vid), headers=self._headers())
            except ProviderError as e:
                if "404" in str(e):
                    time.sleep(10)
                    continue
                if "429" in str(e):
                    time.sleep(70)
                    continue
                raise
            if str(st.get("status", "")).lower() in ("completed", "succeeded", "success", "done"):
                url = url_do_video(st)
                if not url:
                    raise ProviderError(
                        f"agnes: shot {shot['n']} completou sem url: {str(st)[:200]}")
                return baixar(url, workdir / "raw" / f"shot-{shot['n']:02d}.mp4")
            if st.get("status") == "failed":
                raise ProviderError(f"agnes: shot {shot['n']} failed: {st.get('error', '')}")
            time.sleep(10)

    def _gerar_video(self, params, workdir: Path,
                     modelo: str = "agnes-video-v2.0") -> Resultado:
        """Cascata por shot: prompt → prompt_alt → reescrita → vizinho da seção.

        A duração total é sagrada: é ela que mantém imagem e música alinhadas.
        Perder variedade num shot é aceitável; encurtar o clipe desloca TUDO
        que vem depois."""
        w, h = _resolucao_agnes(params.get("resolucao"))
        reescrever = params.get("reescrever")      # injetado pelo executor (Fable)
        decupagem = params["decupagem"]
        feitos: dict[int, Path] = {}
        barrados, com_alt, reescritos, preenchidos = [], [], [], []

        # PROGRESSO em linha declarada: `progresso: 23/47`. É o contrato que o bot
        # lê do log para mostrar no /status — sem ele, uma fase de uma hora
        # aparece como "▶️ rodando" do começo ao fim, e não dá para saber se ela
        # avançou 2 ou 40 shots (pedido do dono em 2026-08-22). Uma linha por
        # shot concluído, sempre com o total.
        total = len(decupagem)

        def _progresso() -> None:
            # "quantos já foram" E "quantos faltam": o segundo é o que decide se
            # vale retomar, e obrigar quem lê a subtrair de cabeça no celular é
            # pedir demais.
            falta = total - len(feitos)
            print(f"progresso: {len(feitos)}/{total} · faltam {falta}", flush=True)

        for i, shot in enumerate(decupagem):
            n = shot["n"]
            pronto = workdir / "raw" / f"shot-{n:02d}.mp4"
            if pronto.exists() and pronto.stat().st_size > 10_000:
                feitos[n] = pronto            # de corrida anterior: não refaz
                _progresso()
                continue
            if i > 0:
                time.sleep(12)                # rate limit real: 6 req/min

            tentativas = [("prompt", shot["prompt"])]
            if shot.get("prompt_alt"):
                tentativas.append(("alt", shot["prompt_alt"]))

            erro_final = None
            for origem, prompt in tentativas:
                try:
                    feitos[n] = self._um_shot(prompt, shot, w, h, workdir,
                                              "" if origem == "prompt" else f"-{origem}",
                                              modelo=modelo)
                    if origem == "alt":
                        com_alt.append(n)
                        print(f"agnes: shot {n} barrado — entrou pelo prompt_alt")
                    break
                except ProviderError as e:
                    if not _barrou(e):
                        raise
                    erro_final = e
            if n in feitos:
                _progresso()
                continue

            if reescrever:                    # rede de segurança: Fable reescreve na hora
                try:
                    novo_prompt = reescrever(shot, str(erro_final))
                    if novo_prompt:
                        time.sleep(12)
                        feitos[n] = self._um_shot(novo_prompt, shot, w, h, workdir, "-reescrito",
                                                  modelo=modelo)
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

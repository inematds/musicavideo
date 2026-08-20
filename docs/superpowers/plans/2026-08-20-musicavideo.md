# Plano de Implementação — musicavideo

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** CLI `musicavideo` que transforma uma solicitação em texto livre em MÚSICA + CAPA + CLIPE, em fases com portão de aprovação por parte (`plano`→`ver`/`ajusta`/`ok`→`faz`→entrega), banco em `~/projetos/output/musicavideo/<slug>/`, provedores plugáveis com custo estimado antes de gastar.

**Architecture:** molde `analisevideo` (`.sh` fino roteando pra `python3 src/main.py`, banco por slug + `index.jsonl`, SKILL.md, guia GitHub Pages) + padrão de provedores do `bench-studio-br` (adapter `providers/<nome>.py` + `<nome>.models.json` declarativo, registry mesclado, indisponível-com-motivo). `estado.json` é a fonte de verdade (máquina de estados por parte); `plano.json` é o contrato fechado entre planejador (Fable via `claude -p`) e executor (providers).

**Tech Stack:** python3 (stdlib apenas: `urllib`, `json`, `dataclasses`, `pathlib`, `subprocess`, `difflib`) + bash + `pytest` para testes + `ffmpeg`/`ffprobe` para concat/verificação de vídeo. Zero dependências pip em runtime.

**Spec:** `/home/nmaldaner/projetos/musicavideo/docs/superpowers/specs/2026-08-20-musicavideo-design.md`

## Decisões pós-spec (vencem o spec onde conflitarem)

1. **Agnes é o motor DEFAULT de capa E clipe** (`agnes:agnes-image-2.1-flash` e `agnes:agnes-video-v2.0`) — custo US$ 0, sem crédito, roda em qualquer VPS. Todo exemplo de `plano.json`/`index.jsonl` deste plano usa esses defaults (os exemplos do spec §8.1/§8.5 com inemaimg/kling estão superados como default; os provedores continuam registrados como alternativas).
2. **Música: `kie:suno-v4.5`** — único provedor pago exercitado nesta rodada.
3. **`kling`, `fal`: adapters implementados e registrados, mas NÃO testados contra API real** — testes só de contrato/mock (HTTP inteiramente monkeypatchado, zero rede).
4. **Telegram: implementado, desligado por default** — só envia com `--telegram`.
5. **Pesquisa web: opt-in `--pesquisa`**, default desligado.
6. **Prompts de provedor SEMPRE em INGLÊS** (Agnes filtra PT legítimo com HTTP 400). Material criativo (`conceito`, `descricao`, letra, mood) pode ser PT; os campos `musica.estilo.prompt_estilo`, `capa.prompt_imagem`, `capa.prompt_negativo` e `clipe.decupagem[].prompt` são EN e VALIDADOS (rejeita caractere acentuado nesses campos).

## Global Constraints (valem para TODA tarefa)

- **python3 + bash, stdlib only.** HTTP via `urllib.request`, nunca `requests`. Único binário externo: `ffmpeg`/`ffprobe`.
- **Chaves de API lidas em runtime de `~/projetos/openpcbotv2/.env` e `~/projetos/wifi/.env` (nesta ordem), NUNCA impressas, logadas, copiadas pro repo ou pra saída.** Fatos medidos: `AGNES_API_KEY` está em `openpcbotv2/.env`; `KIE_API_KEY` em `wifi/.env`; `FAL_KEY` em `wifi/.env`. Nenhum outro `.env` é autorizado (não usar `agnes-nei/.env`).
- **Saída sempre em `~/projetos/output/musicavideo/<slug>/`** (`OUT_DIR = Path.home()/"projetos/output/musicavideo"`, sobrescritível por env `MUSICAVIDEO_OUT` só para testes).
- **Provedor sem chave/servidor = indisponível COM MOTIVO legível**, nunca exceção na hora de gerar; `faz` de parte indisponível marca a parte `erro` e as outras seguem (exit 2).
- **Nada de UI web, nada de lote, nada de pós-edição de vídeo** além do concat simples via ffmpeg.
- **Todo JSON tem `schema_version: "1"`; campo desconhecido = erro de validação.**
- **Escrita de `estado.json`/`index.jsonl` sempre atômica** (tmp + `os.replace`).
- **Commits neste repo com author E committer `inematds <inematds@gmail.com>`** (config local do repo, Task 1).
- **Testes com `pytest`, rodados como `python3 -m pytest tests/ -x -q` da raiz do repo.** Testes nunca chamam API real (exceto a Task 18, o e2e autorizado).
- Custo estimado impresso ANTES de qualquer chamada de API em todo `faz` (confirmação interativa; `--sim` pula).

## File Structure

```
musicavideo/
├── musicavideo.sh              # roteador fino bash: valida $1, resolve raiz, exec python3 src/main.py "$@"
├── SKILL.md                    # interface pro bot/skill (comandos, exemplos, saída)
├── .env.example                # documenta KIE_API_KEY, AGNES_API_KEY, FAL_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID (sem valores)
├── README.md                   # visão geral + quickstart
├── guia/index.html             # landing+guia GitHub Pages (INEMA dark âmbar)
├── src/
│   ├── main.py                 # argparse + dispatch dos subcomandos; exit codes 0/1/2/3
│   ├── esquemas.py             # validação fechada de plano.json/estado.json + validação EN dos prompts
│   ├── estado.py               # máquina de estados, escrita atômica, normalização de `gerando` interrompido
│   ├── indexer.py              # index.jsonl: gravar_linha, lista, busca, reindex
│   ├── planner.py              # plano/ver/ajusta/ok: contexto → Fable (claude -p) → plano.json + PLANO.md + diff
│   ├── registry.py             # merge dos providers/*.models.json + disponibilidade
│   ├── custo.py                # estimativa por parte + relatório estimado vs gasto
│   ├── executor.py             # faz: valida, estima, confirma, roda provider, marca estado, teto
│   ├── entrega.py              # PACOTE.md + envio Telegram opcional
│   └── pesquisa.py             # fase 0 opt-in: pesquisa web → pesquisa.md
├── providers/
│   ├── base.py                 # Provider, Resultado, ProviderError, ler_env_chave, http_json (urllib+retry)
│   ├── kie.py + kie.models.json           # música Suno via api.kie.ai (POST /generate, poll record-info)
│   ├── agnes.py + agnes.models.json       # capa (images/generations) E clipe (POST /videos, keyframes) — DEFAULT
│   ├── inemaimg.py + inemaimg.models.json # capa alternativa (flux2-klein local, localhost:8000)
│   ├── kling.py + kling.models.json       # clipe alternativo via kie /jobs/createTask (mock-only nesta rodada)
│   └── fal.py + fal.models.json           # clipe alternativo via queue.fal.run (mock-only nesta rodada)
├── data/
│   ├── estilos.json            # semeado das análises Gemini reais (Task 15)
│   ├── templates-capa.json     # 4 composições (spec §8.4, verbatim)
│   └── templates-clipe.json    # 4 decupagens (spec §8.4, verbatim)
├── tests/
│   ├── conftest.py             # fixture outdir tmp (MUSICAVIDEO_OUT), fixture plano válido
│   ├── fixtures/estilos.json   # mini-estilos p/ testes do planner (o real vem na Task 15)
│   ├── test_esquemas.py  test_estado.py  test_indexer.py
│   ├── test_planner.py   test_registry.py  test_custo.py
│   ├── test_kie.py  test_agnes.py  test_inemaimg.py  test_kling_fal.py
│   ├── test_executor.py  test_entrega.py  test_main.py
└── docs/superpowers/{specs,plans}/...
```

---

### Task 1: Esqueleto do repo + git + roteador bash + dispatch

**Files:** Create `/home/nmaldaner/projetos/musicavideo/musicavideo.sh`, `/home/nmaldaner/projetos/musicavideo/src/main.py`, `/home/nmaldaner/projetos/musicavideo/tests/conftest.py`, `/home/nmaldaner/projetos/musicavideo/tests/test_main.py`, `/home/nmaldaner/projetos/musicavideo/.gitignore`
**Interfaces:** Produces: `src/main.py` com `main(argv: list[str]) -> int` e dict `COMANDOS`; `conftest.py` com fixture `outdir` (tmp, seta `MUSICAVIDEO_OUT`); convenção `OUT_DIR` via `MUSICAVIDEO_OUT`.

- [ ] **Step 1: git init + autoria local**
  ```bash
  cd /home/nmaldaner/projetos/musicavideo
  git init
  git config user.name "inematds"
  git config user.email "inematds@gmail.com"
  printf '__pycache__/\n*.pyc\n.pytest_cache/\n' > .gitignore
  ```
- [ ] **Step 2: Escrever o teste que falha** — `tests/conftest.py` e `tests/test_main.py`:
  ```python
  # tests/conftest.py
  import os, pytest
  from pathlib import Path

  @pytest.fixture
  def outdir(tmp_path, monkeypatch):
      d = tmp_path / "out"
      d.mkdir()
      monkeypatch.setenv("MUSICAVIDEO_OUT", str(d))
      return d
  ```
  ```python
  # tests/test_main.py
  import subprocess, sys
  from pathlib import Path
  RAIZ = Path(__file__).resolve().parents[1]

  def test_main_sem_args_exit_1():
      r = subprocess.run([sys.executable, str(RAIZ / "src/main.py")],
                         capture_output=True, text=True)
      assert r.returncode == 1
      assert "uso:" in (r.stdout + r.stderr).lower()

  def test_main_comando_desconhecido_exit_1():
      r = subprocess.run([sys.executable, str(RAIZ / "src/main.py"), "xyzzy"],
                         capture_output=True, text=True)
      assert r.returncode == 1

  def test_sh_roteia_pro_python():
      r = subprocess.run(["bash", str(RAIZ / "musicavideo.sh")],
                         capture_output=True, text=True)
      assert r.returncode == 1
      assert "uso:" in (r.stdout + r.stderr).lower()
  ```
- [ ] **Step 3: Rodar e ver falhar:** `cd /home/nmaldaner/projetos/musicavideo && python3 -m pytest tests/ -x -q` — falha com `FileNotFoundError`/`No such file` para `src/main.py`.
- [ ] **Step 4: Implementação mínima:**
  ```bash
  # musicavideo.sh
  #!/usr/bin/env bash
  # roteador fino: zero lógica além de resolver a raiz e delegar.
  set -euo pipefail
  RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  exec python3 "$RAIZ/src/main.py" "$@"
  ```
  ```python
  # src/main.py
  """Dispatch dos subcomandos do musicavideo. Exit codes: 0 ok; 1 uso/validação;
  2 parte terminou em erro; 3 teto estourado."""
  import os, sys
  from pathlib import Path

  def out_dir() -> Path:
      return Path(os.environ.get("MUSICAVIDEO_OUT",
                  str(Path.home() / "projetos/output/musicavideo")))

  USO = """uso: musicavideo <comando> ...
    plano "<solicitação>" [slug] [--pesquisa] [--estilo X] [--letra arq [--letra-final]] [--motor parte=prov:modelo] [--forca]
    ver <slug> [musica|capa|clipe]
    ajusta <slug> <parte> "<instrução>" [--refaz]
    ok <slug> <parte>
    faz <slug> [parte] [--sim] [--telegram] [--motor parte=prov:modelo]
    tudo "<solicitação>" [--teto N] [demais flags de plano] [--sim] [--telegram]
    custo <slug> | lista [N] | busca "<termo>" | reindex"""

  COMANDOS = {}   # nome -> callable(argv) -> int; preenchido pelas próximas tasks

  def main(argv: list[str]) -> int:
      if not argv or argv[0] in ("-h", "--help"):
          print(USO); return 1
      cmd = argv[0]
      fn = COMANDOS.get(cmd)
      if fn is None:
          print(f"comando desconhecido: {cmd}\n{USO}", file=sys.stderr); return 1
      return fn(argv[1:])

  if __name__ == "__main__":
      sys.exit(main(sys.argv[1:]))
  ```
  `chmod +x musicavideo.sh`
- [ ] **Step 5: Rodar e ver passar:** `python3 -m pytest tests/ -x -q`
- [ ] **Step 6: Commit:** `git add -A && git commit -m "esqueleto: roteador bash fino + dispatch python + pytest"`

---

### Task 2: `src/esquemas.py` — validação fechada + prompts em inglês

**Files:** Create `src/esquemas.py`, `tests/test_esquemas.py`, `tests/conftest.py` (adicionar fixture `plano_ok`)
**Interfaces:** Produces: `validar_plano(plano: dict) -> list[str]` (lista de erros, vazia = válido), `validar_estado(estado: dict) -> list[str]`, `campos_prompt_en(plano: dict) -> list[str]` (erros de prompt não-EN). Consumido por planner (Task 7) e executor (Task 9).

- [ ] **Step 1: Fixture `plano_ok` no conftest** (defaults pós-spec — agnes na capa e no clipe):
  ```python
  # acrescentar em tests/conftest.py
  @pytest.fixture
  def plano_ok():
      return {
        "schema_version": "1", "slug": "teste-rock", "criado_em": "2026-08-20T14:00:00-03:00",
        "solicitacao": "rock feminino de virada", "pesquisa": False,
        "estilo_ref": None, "titulo": "Agora Eu Cobro",
        "musica": {
          "motor": "kie:suno-v4.5",
          "params": {"duracao_s": 180, "instrumental": False},
          "estilo": {"genero": "Female Anthem Rock", "bpm": 120, "tom": "E menor",
            "mood": ["determinada", "vitoriosa"],
            "instrumentacao": ["electric guitar", "bass", "drums"],
            "voz": {"tipo": "feminina", "registro": "médio-agudo",
                    "entrega": "belting com grit", "harmonias": "backing nos refrões"},
            "prompt_estilo": "Female anthem rock, 120 bpm, E minor, powerful female belting vocals, driving guitars"},
          "estrutura": ["intro", "verso 1", "refrão", "verso 2", "refrão", "ponte", "refrão final"],
          "letra": {"origem": "gerada", "texto": "[Verse 1]\nConstrui no silencio...",
                    "texto_original": None, "idioma": "pt-BR"}
        },
        "capa": {
          "motor": "agnes:agnes-image-2.1-flash",
          "params": {"tamanho": "1024x1024"},
          "template": "retrato-centralizado",
          "conceito": "Mulher de perfil em contraluz âmbar, punho fechado",
          "prompt_imagem": "album cover, three-quarter portrait of a determined woman in amber backlight, closed fist, cinematic, space for bold title, 1:1",
          "prompt_negativo": "text, watermark, logo, front-facing symmetric pose",
          "paleta": ["#E8A13C", "#1A1A2E"]
        },
        "clipe": {
          "motor": "agnes:agnes-video-v2.0",
          "params": {"resolucao": "1312x736", "duracao_shot_s": 5},
          "template": "narrativo",
          "sincronia": "um shot por seção da música",
          "decupagem": [
            {"n": 1, "secao": "intro", "duracao_s": 5, "camera": "dolly-in lento",
             "descricao": "oficina escura ao amanhecer, ferramentas na bancada",
             "prompt": "slow dolly-in, dark workshop at dawn, tools on a bench, warm amber light, cinematic, 5s"},
            {"n": 2, "secao": "refrão", "duracao_s": 5, "camera": "orbit",
             "descricao": "mulher ergue a cabeça sob luz forte",
             "prompt": "slow orbit around a woman raising her head under strong stage light, amber and teal, cinematic, 5s"}
          ]
        }
      }
  ```
- [ ] **Step 2: Escrever o teste que falha:**
  ```python
  # tests/test_esquemas.py
  from src.esquemas import validar_plano, validar_estado, campos_prompt_en

  def test_plano_valido_sem_erros(plano_ok):
      assert validar_plano(plano_ok) == []

  def test_campo_desconhecido_e_erro(plano_ok):
      plano_ok["extra"] = 1
      assert any("extra" in e for e in validar_plano(plano_ok))

  def test_campo_obrigatorio_faltando(plano_ok):
      del plano_ok["musica"]["letra"]
      assert any("letra" in e for e in validar_plano(plano_ok))

  def test_motor_malformado(plano_ok):
      plano_ok["capa"]["motor"] = "semdoispontos"
      assert any("motor" in e for e in validar_plano(plano_ok))

  def test_letra_final_exige_texto(plano_ok):
      plano_ok["musica"]["letra"]["origem"] = "final_usuario"
      plano_ok["musica"]["letra"]["texto"] = ""
      assert any("final_usuario" in e for e in validar_plano(plano_ok))

  def test_prompt_em_portugues_e_rejeitado(plano_ok):
      plano_ok["capa"]["prompt_imagem"] = "capa de álbum, retrato de mulher, iluminação âmbar"
      erros = campos_prompt_en(plano_ok)
      assert any("prompt_imagem" in e for e in erros)

  def test_conceito_em_pt_e_permitido(plano_ok):
      assert campos_prompt_en(plano_ok) == []  # fixture já tem conceito/descricao em PT

  def test_estado_valido():
      # nesta task validamos um dict literal (src.estado só existe na Task 3):
      e = {"schema_version": "1", "slug": "x", "atualizado_em": "2026-08-20T14:00:00-03:00",
           "fase": "plano", "telegram": False, "teto_usd": None,
           "partes": {p: {"estado": "planejado", "aprovado_em": None, "ajustes": 0,
                          "tentativas": 0, "custo_estimado_usd": 0.0, "custo_real_usd": 0.0,
                          "artefato": None, "erro": None, "meta": {}}
                      for p in ("musica", "capa", "clipe")},
           "custo_total_usd": {"estimado": 0.0, "gasto": 0.0}, "historico": []}
      assert validar_estado(e) == []
      e["partes"]["musica"]["estado"] = "voando"
      assert validar_estado(e) != []
  ```
- [ ] **Step 3: Rodar e ver falhar:** `python3 -m pytest tests/test_esquemas.py -x -q` — `ModuleNotFoundError: src.esquemas`.
- [ ] **Step 4: Implementação mínima:**
  ```python
  # src/esquemas.py
  """Validação FECHADA dos contratos (spec §8): campo desconhecido é erro."""
  import re

  _ESTADOS = {"planejado", "aprovado", "gerando", "pronto", "erro"}
  _PARTES = ("musica", "capa", "clipe")
  _ACENTOS = re.compile(r"[áàâãéêíóôõúüçÁÀÂÃÉÊÍÓÔÕÚÜÇ]")

  def _chaves(d: dict, obrig: set, opc: set, ctx: str, erros: list):
      for k in d:
          if k not in obrig | opc:
              erros.append(f"{ctx}: campo desconhecido '{k}'")
      for k in obrig:
          if k not in d:
              erros.append(f"{ctx}: campo obrigatório '{k}' ausente")

  def _motor_ok(m, ctx, erros):
      if not (isinstance(m, str) and re.fullmatch(r"[a-z0-9_-]+:[A-Za-z0-9._/-]+", m)):
          erros.append(f"{ctx}: motor inválido '{m}' (esperado provider:modelo)")

  def validar_plano(plano: dict) -> list[str]:
      erros: list[str] = []
      _chaves(plano, {"schema_version", "slug", "criado_em", "solicitacao", "pesquisa",
                      "estilo_ref", "titulo", "musica", "capa", "clipe"}, set(), "plano", erros)
      if plano.get("schema_version") != "1":
          erros.append("plano: schema_version deve ser \"1\"")
      m = plano.get("musica", {})
      _chaves(m, {"motor", "params", "estilo", "estrutura", "letra"}, set(), "musica", erros)
      if "motor" in m: _motor_ok(m["motor"], "musica", erros)
      est = m.get("estilo", {})
      _chaves(est, {"genero", "bpm", "tom", "mood", "instrumentacao", "voz", "prompt_estilo"},
              set(), "musica.estilo", erros)
      le = m.get("letra", {})
      _chaves(le, {"origem", "texto", "texto_original", "idioma"}, set(), "musica.letra", erros)
      if le.get("origem") not in (None, "gerada", "rascunho_usuario", "final_usuario"):
          erros.append(f"musica.letra: origem inválida '{le.get('origem')}'")
      if le.get("origem") == "final_usuario" and not le.get("texto"):
          erros.append("musica.letra: origem final_usuario exige texto não vazio")
      c = plano.get("capa", {})
      _chaves(c, {"motor", "params", "template", "conceito", "prompt_imagem",
                  "prompt_negativo", "paleta"}, set(), "capa", erros)
      if "motor" in c: _motor_ok(c["motor"], "capa", erros)
      v = plano.get("clipe", {})
      _chaves(v, {"motor", "params", "template", "sincronia", "decupagem"}, set(), "clipe", erros)
      if "motor" in v: _motor_ok(v["motor"], "clipe", erros)
      for i, shot in enumerate(v.get("decupagem", []) or []):
          _chaves(shot, {"n", "secao", "duracao_s", "camera", "descricao", "prompt"},
                  set(), f"clipe.decupagem[{i}]", erros)
      return erros

  def campos_prompt_en(plano: dict) -> list[str]:
      """Prompts que vão pro provedor DEVEM ser EN (Agnes 400 em PT legítimo)."""
      erros = []
      alvos = [("musica.estilo.prompt_estilo", plano["musica"]["estilo"].get("prompt_estilo", "")),
               ("capa.prompt_imagem", plano["capa"].get("prompt_imagem", "")),
               ("capa.prompt_negativo", plano["capa"].get("prompt_negativo", ""))]
      for i, s in enumerate(plano["clipe"].get("decupagem", []) or []):
          alvos.append((f"clipe.decupagem[{i}].prompt", s.get("prompt", "")))
      for nome, txt in alvos:
          if _ACENTOS.search(txt or ""):
              erros.append(f"{nome}: prompt de provedor deve ser em INGLÊS (achei acento)")
      return erros

  def validar_estado(estado: dict) -> list[str]:
      erros: list[str] = []
      _chaves(estado, {"schema_version", "slug", "atualizado_em", "fase", "telegram",
                       "teto_usd", "partes", "custo_total_usd", "historico"}, set(), "estado", erros)
      if estado.get("fase") not in ("plano", "execucao", "entregue"):
          erros.append(f"estado: fase inválida '{estado.get('fase')}'")
      for p in _PARTES:
          d = estado.get("partes", {}).get(p)
          if d is None:
              erros.append(f"estado: parte '{p}' ausente"); continue
          _chaves(d, {"estado", "aprovado_em", "ajustes", "tentativas", "custo_estimado_usd",
                      "custo_real_usd", "artefato", "erro", "meta"}, set(), f"estado.{p}", erros)
          if d.get("estado") not in _ESTADOS:
              erros.append(f"estado.{p}: estado inválido '{d.get('estado')}'")
      return erros
  ```
- [ ] **Step 5: Rodar e ver passar:** `python3 -m pytest tests/test_esquemas.py -x -q`
- [ ] **Step 6: Commit:** `git add -A && git commit -m "esquemas: validação fechada de plano/estado + prompts de provedor em EN"`

---

### Task 3: `src/estado.py` — máquina de estados + escrita atômica

**Files:** Create `src/estado.py`, `tests/test_estado.py`
**Interfaces:** Consumes: `validar_estado` (Task 2). Produces: `novo_estado(slug: str) -> dict`; `carregar_estado(workdir: Path) -> dict` (normaliza `gerando` interrompido → `erro` motivo `"interrompido"`); `salvar_estado(workdir: Path, estado: dict) -> None` (atômico, atualiza `atualizado_em`); `transicao(estado: dict, parte: str, evento: str, **kw) -> None` (eventos: `ok`, `ajusta`, `faz`, `pronto`, `erro`, `refaz`; levanta `TransicaoInvalida`); `registrar(estado, evento, **detalhe)` (append no `historico`); classe `TransicaoInvalida(ValueError)`. Usado por planner (7-8), executor (9), entrega (13).

- [ ] **Step 1: Escrever o teste que falha:**
  ```python
  # tests/test_estado.py
  import json, pytest
  from pathlib import Path
  from src.estado import (novo_estado, carregar_estado, salvar_estado,
                          transicao, TransicaoInvalida)
  from src.esquemas import validar_estado

  def test_novo_estado_valida(outdir):
      e = novo_estado("meu-slug")
      assert validar_estado(e) == []
      assert all(e["partes"][p]["estado"] == "planejado" for p in ("musica", "capa", "clipe"))

  def test_fluxo_feliz():
      e = novo_estado("s")
      transicao(e, "musica", "ok")
      assert e["partes"]["musica"]["estado"] == "aprovado"
      assert e["partes"]["musica"]["aprovado_em"] is not None
      transicao(e, "musica", "faz")
      assert e["partes"]["musica"]["estado"] == "gerando"
      transicao(e, "musica", "pronto", artefato="faixa.mp3", custo_real=0.08)
      assert e["partes"]["musica"]["estado"] == "pronto"
      assert e["partes"]["musica"]["artefato"] == "faixa.mp3"

  def test_transicoes_invalidas():
      e = novo_estado("s")
      with pytest.raises(TransicaoInvalida):
          transicao(e, "musica", "faz")          # planejado não pode faz
      transicao(e, "musica", "ok")
      transicao(e, "musica", "faz")
      transicao(e, "musica", "pronto", artefato="faixa.mp3", custo_real=0)
      with pytest.raises(TransicaoInvalida):
          transicao(e, "musica", "ajusta")       # pronto exige refaz

  def test_erro_permite_retry_e_ajusta():
      e = novo_estado("s")
      transicao(e, "capa", "ok"); transicao(e, "capa", "faz")
      transicao(e, "capa", "erro", motor="agnes:agnes-image-2.1-flash", msg="503")
      assert e["partes"]["capa"]["erro"]["msg"] == "503"
      transicao(e, "capa", "faz")                # retry direto de erro
      assert e["partes"]["capa"]["estado"] == "gerando"
      transicao(e, "capa", "erro", motor="m", msg="x")
      transicao(e, "capa", "ajusta")             # erro → planejado
      assert e["partes"]["capa"]["estado"] == "planejado"

  def test_refaz_de_pronto():
      e = novo_estado("s")
      transicao(e, "clipe", "ok"); transicao(e, "clipe", "faz")
      transicao(e, "clipe", "pronto", artefato="clipe.mp4", custo_real=0)
      transicao(e, "clipe", "refaz")
      assert e["partes"]["clipe"]["estado"] == "planejado"

  def test_persistencia_atomica_e_interrompido(outdir):
      w = outdir / "s"; w.mkdir()
      e = novo_estado("s")
      transicao(e, "musica", "ok"); transicao(e, "musica", "faz")  # gerando
      salvar_estado(w, e)
      assert not list(w.glob("*.tmp"))
      e2 = carregar_estado(w)   # simula crash durante gerando
      assert e2["partes"]["musica"]["estado"] == "erro"
      assert e2["partes"]["musica"]["erro"]["msg"] == "interrompido"
  ```
- [ ] **Step 2: Rodar e ver falhar:** `python3 -m pytest tests/test_estado.py -x -q` — `ModuleNotFoundError: src.estado`.
- [ ] **Step 3: Implementação mínima:**
  ```python
  # src/estado.py
  """estado.json: fonte de verdade. Máquina: planejado→(ok)→aprovado→(faz)→gerando→pronto|erro;
  erro→(faz retry)|(ajusta→planejado); pronto→(refaz→planejado)."""
  import json, os
  from datetime import datetime, timezone, timedelta
  from pathlib import Path

  TZ = timezone(timedelta(hours=-3))
  PARTES = ("musica", "capa", "clipe")

  class TransicaoInvalida(ValueError):
      pass

  def _agora() -> str:
      return datetime.now(TZ).isoformat(timespec="seconds")

  def novo_estado(slug: str) -> dict:
      return {"schema_version": "1", "slug": slug, "atualizado_em": _agora(),
              "fase": "plano", "telegram": False, "teto_usd": None,
              "partes": {p: {"estado": "planejado", "aprovado_em": None, "ajustes": 0,
                             "tentativas": 0, "custo_estimado_usd": 0.0, "custo_real_usd": 0.0,
                             "artefato": None, "erro": None, "meta": {}} for p in PARTES},
              "custo_total_usd": {"estimado": 0.0, "gasto": 0.0},
              "historico": [{"quando": _agora(), "evento": "plano", "detalhe": "criado"}]}

  _TRANSICOES = {  # (estado_atual, evento) -> novo_estado
      ("planejado", "ok"): "aprovado",
      ("planejado", "ajusta"): "planejado",
      ("aprovado", "ajusta"): "planejado",
      ("aprovado", "faz"): "gerando",
      ("gerando", "pronto"): "pronto",
      ("gerando", "erro"): "erro",
      ("erro", "faz"): "gerando",
      ("erro", "ajusta"): "planejado",
      ("pronto", "refaz"): "planejado",
  }

  def transicao(estado: dict, parte: str, evento: str, **kw) -> None:
      p = estado["partes"][parte]
      novo = _TRANSICOES.get((p["estado"], evento))
      if novo is None:
          raise TransicaoInvalida(
              f"{parte}: '{evento}' não vale no estado '{p['estado']}' "
              f"(transições: {sorted(set(e for s, e in _TRANSICOES if s == p['estado']))})")
      p["estado"] = novo
      if evento == "ok":
          p["aprovado_em"] = _agora()
      elif evento == "ajusta":
          p["ajustes"] += 1; p["aprovado_em"] = None; p["erro"] = None
      elif evento == "faz":
          p["tentativas"] += 1; p["erro"] = None
      elif evento == "pronto":
          p["artefato"] = kw["artefato"]; p["erro"] = None
          p["custo_real_usd"] += float(kw.get("custo_real", 0.0))
          estado["custo_total_usd"]["gasto"] = round(
              sum(x["custo_real_usd"] for x in estado["partes"].values()), 4)
          if "meta" in kw: p["meta"] = kw["meta"]
      elif evento == "erro":
          p["erro"] = {"quando": _agora(), "motor": kw.get("motor", ""), "msg": kw.get("msg", "")}
      elif evento == "refaz":
          p["aprovado_em"] = None; p["artefato"] = None
      registrar(estado, evento, parte=parte)

  def registrar(estado: dict, evento: str, **detalhe) -> None:
      estado["historico"].append({"quando": _agora(), "evento": evento, **detalhe})

  def salvar_estado(workdir: Path, estado: dict) -> None:
      estado["atualizado_em"] = _agora()
      alvo = workdir / "estado.json"
      tmp = workdir / "estado.json.tmp"
      tmp.write_text(json.dumps(estado, ensure_ascii=False, indent=2), encoding="utf-8")
      os.replace(tmp, alvo)

  def carregar_estado(workdir: Path) -> dict:
      estado = json.loads((workdir / "estado.json").read_text(encoding="utf-8"))
      for parte, p in estado["partes"].items():
          if p["estado"] == "gerando":   # crash/ctrl-c anterior
              p["estado"] = "erro"
              p["erro"] = {"quando": _agora(), "motor": "", "msg": "interrompido"}
              registrar(estado, "erro", parte=parte, detalhe="gerando interrompido")
      return estado
  ```
- [ ] **Step 4: Rodar e ver passar:** `python3 -m pytest tests/test_estado.py -x -q`
- [ ] **Step 5: Commit:** `git add -A && git commit -m "estado: máquina de estados por parte + escrita atômica + interrompido→erro"`

---

### Task 4: `src/indexer.py` — index.jsonl (lista/busca/reindex)

**Files:** Create `src/indexer.py`, `tests/test_indexer.py`; Modify `src/main.py` (registrar `lista`, `busca`, `reindex` em `COMANDOS`)
**Interfaces:** Consumes: `out_dir()` (Task 1), `carregar_estado` (Task 3). Produces: `linha_de(plano: dict, estado: dict) -> dict`; `gravar_linha(outdir: Path, linha: dict) -> None` (substitui a linha do slug, atômico); `lista(outdir: Path, n: int = 10) -> list[dict]`; `busca(outdir: Path, termo: str) -> list[dict]`; `reindex(outdir: Path) -> int` (nº de linhas reconstruídas); `contexto_acervo(outdir: Path, solicitacao: str, n: int = 5) -> list[dict]` (últimas N + matches — insumo do planner Task 7).

- [ ] **Step 1: Escrever o teste que falha:**
  ```python
  # tests/test_indexer.py
  import json
  from src.indexer import linha_de, gravar_linha, lista, busca, reindex, contexto_acervo
  from src.estado import novo_estado

  def _linha(plano_ok):
      return linha_de(plano_ok, novo_estado(plano_ok["slug"]))

  def test_linha_tem_campos_do_contrato(plano_ok):
      l = _linha(plano_ok)
      assert l["slug"] == "teste-rock"
      assert l["motores"]["capa"] == "agnes:agnes-image-2.1-flash"
      assert l["estados"] == {"musica": "planejado", "capa": "planejado", "clipe": "planejado"}
      assert l["custo_gasto_usd"] == 0.0

  def test_gravar_substitui_linha_do_slug(outdir, plano_ok):
      l = _linha(plano_ok)
      gravar_linha(outdir, l)
      l["estados"]["musica"] = "pronto"
      gravar_linha(outdir, l)
      linhas = (outdir / "index.jsonl").read_text().strip().splitlines()
      assert len(linhas) == 1
      assert json.loads(linhas[0])["estados"]["musica"] == "pronto"

  def test_lista_e_busca(outdir, plano_ok):
      gravar_linha(outdir, _linha(plano_ok))
      assert lista(outdir, 5)[0]["slug"] == "teste-rock"
      assert busca(outdir, "ROCK")           # case-insensitive
      assert busca(outdir, "inexistente-xyz") == []

  def test_reindex_reconstroi(outdir, plano_ok):
      w = outdir / plano_ok["slug"]; w.mkdir()
      (w / "plano.json").write_text(json.dumps(plano_ok), encoding="utf-8")
      from src.estado import salvar_estado
      salvar_estado(w, novo_estado(plano_ok["slug"]))
      assert reindex(outdir) == 1
      assert lista(outdir)[0]["slug"] == plano_ok["slug"]

  def test_contexto_acervo(outdir, plano_ok):
      gravar_linha(outdir, _linha(plano_ok))
      ctx = contexto_acervo(outdir, "quero um rock de virada")
      assert any(l["slug"] == "teste-rock" for l in ctx)
  ```
- [ ] **Step 2: Rodar e ver falhar:** `python3 -m pytest tests/test_indexer.py -x -q` — `ModuleNotFoundError: src.indexer`.
- [ ] **Step 3: Implementação mínima:**
  ```python
  # src/indexer.py
  """index.jsonl: 1 linha por slug, reescrita por todo comando que muda estado."""
  import json, os
  from pathlib import Path

  def linha_de(plano: dict, estado: dict) -> dict:
      return {"slug": plano["slug"], "titulo": plano["titulo"],
              "criado_em": plano["criado_em"], "solicitacao": plano["solicitacao"],
              "estilo_ref": plano["estilo_ref"],
              "genero": plano["musica"]["estilo"]["genero"],
              "bpm": plano["musica"]["estilo"]["bpm"],
              "tom": plano["musica"]["estilo"]["tom"],
              "motores": {p: plano[p]["motor"] for p in ("musica", "capa", "clipe")},
              "estados": {p: estado["partes"][p]["estado"] for p in ("musica", "capa", "clipe")},
              "custo_gasto_usd": estado["custo_total_usd"]["gasto"],
              "tags": plano["musica"]["estilo"]["mood"]}

  def _ler(outdir: Path) -> list[dict]:
      arq = outdir / "index.jsonl"
      if not arq.exists(): return []
      return [json.loads(l) for l in arq.read_text(encoding="utf-8").splitlines() if l.strip()]

  def _escrever(outdir: Path, linhas: list[dict]) -> None:
      tmp = outdir / "index.jsonl.tmp"
      tmp.write_text("".join(json.dumps(l, ensure_ascii=False) + "\n" for l in linhas),
                     encoding="utf-8")
      os.replace(tmp, outdir / "index.jsonl")

  def gravar_linha(outdir: Path, linha: dict) -> None:
      linhas = [l for l in _ler(outdir) if l["slug"] != linha["slug"]]
      linhas.append(linha)
      _escrever(outdir, linhas)

  def lista(outdir: Path, n: int = 10) -> list[dict]:
      return list(reversed(_ler(outdir)))[:n]

  def busca(outdir: Path, termo: str) -> list[dict]:
      t = termo.lower()
      def bate(l):
          campos = [l["slug"], l["titulo"], l["solicitacao"], str(l["genero"])] + list(l["tags"])
          return any(t in str(c).lower() for c in campos)
      return [l for l in _ler(outdir) if bate(l)]

  def reindex(outdir: Path) -> int:
      from src.estado import carregar_estado
      linhas = []
      for w in sorted(p for p in outdir.iterdir() if p.is_dir()):
          pj, ej = w / "plano.json", w / "estado.json"
          if pj.exists() and ej.exists():
              linhas.append(linha_de(json.loads(pj.read_text(encoding="utf-8")),
                                     carregar_estado(w)))
      _escrever(outdir, linhas)
      return len(linhas)

  def contexto_acervo(outdir: Path, solicitacao: str, n: int = 5) -> list[dict]:
      recentes = lista(outdir, n)
      matches = [l for tok in solicitacao.lower().split() if len(tok) > 3
                 for l in busca(outdir, tok)]
      vistos, saida = set(), []
      for l in recentes + matches:
          if l["slug"] not in vistos:
              vistos.add(l["slug"]); saida.append(l)
      return saida
  ```
  Em `src/main.py`, registrar os três comandos (padrão que as próximas tasks repetem):
  ```python
  # src/main.py — acrescentar após COMANDOS = {}
  def _cmd_lista(args):
      from src.indexer import lista
      for l in lista(out_dir(), int(args[0]) if args else 10):
          print(f"{l['slug']:40s} {l['estados']}  US${l['custo_gasto_usd']}")
      return 0

  def _cmd_busca(args):
      if not args: print("uso: busca \"<termo>\"", file=sys.stderr); return 1
      from src.indexer import busca
      for l in busca(out_dir(), args[0]):
          print(f"{l['slug']:40s} {l['titulo']}")
      return 0

  def _cmd_reindex(args):
      from src.indexer import reindex
      print(f"reindexadas: {reindex(out_dir())} linhas"); return 0

  COMANDOS.update({"lista": _cmd_lista, "busca": _cmd_busca, "reindex": _cmd_reindex})
  ```
  (Para `from src...` funcionar com `python3 src/main.py`, adicionar no topo do `main.py`: `sys.path.insert(0, str(Path(__file__).resolve().parents[1]))`.)
- [ ] **Step 4: Rodar e ver passar:** `python3 -m pytest tests/ -x -q`
- [ ] **Step 5: Commit:** `git add -A && git commit -m "indexer: index.jsonl com lista/busca/reindex + contexto do acervo"`

---

### Task 5: Templates de capa e clipe + fixture de estilos

**Files:** Create `data/templates-capa.json`, `data/templates-clipe.json` (conteúdo VERBATIM do spec §8.4 — copiar os dois blocos JSON inteiros de lá, removendo comentários `//`), `tests/fixtures/estilos.json`, `tests/test_dados.py`
**Interfaces:** Produces: arquivos de dados carregáveis; `tests/fixtures/estilos.json` com 1 estilo mínimo para o planner (o real vem na Task 15).

- [ ] **Step 1: Escrever o teste que falha:**
  ```python
  # tests/test_dados.py
  import json
  from pathlib import Path
  RAIZ = Path(__file__).resolve().parents[1]

  def test_templates_capa():
      d = json.loads((RAIZ / "data/templates-capa.json").read_text(encoding="utf-8"))
      assert d["schema_version"] == "1"
      ids = {t["id"] for t in d["templates"]}
      assert ids == {"tipografia-dominante", "retrato-centralizado",
                     "paisagem-simbolica", "minimal-abstrato"}
      for t in d["templates"]:
          assert set(t) == {"id", "nome", "descricao", "composicao",
                            "quando_usar", "prompt_base", "negativo_base"}

  def test_templates_clipe():
      d = json.loads((RAIZ / "data/templates-clipe.json").read_text(encoding="utf-8"))
      ids = {t["id"] for t in d["templates"]}
      assert ids == {"performance", "narrativo", "lyric-video", "abstrato-loop"}
      for t in d["templates"]:
          assert set(t) == {"id", "nome", "descricao", "estrutura_shots",
                            "sincronia", "quando_usar"}

  def test_fixture_estilos():
      d = json.loads((RAIZ / "tests/fixtures/estilos.json").read_text(encoding="utf-8"))
      assert d["schema_version"] == "1" and len(d["estilos"]) >= 1
  ```
- [ ] **Step 2: Rodar e ver falhar:** `python3 -m pytest tests/test_dados.py -x -q` — `FileNotFoundError`.
- [ ] **Step 3: Implementação mínima:** copiar os JSON do spec §8.4 (sem os comentários `//`) para os dois arquivos de `data/`, e criar a fixture:
  ```json
  // tests/fixtures/estilos.json (sem este comentário no arquivo real)
  {"schema_version": "1", "estilos": [
    {"id": "female-anthem-rock", "nome": "Female Anthem Rock",
     "genero": ["anthem rock", "pop rock"], "bpm": null, "tom": null,
     "mood": ["determinada", "vitoriosa"],
     "instrumentacao": ["electric guitars", "bass", "drums"],
     "voz": {"presenca": "lead", "tipos": [
        {"genero": "feminina", "registro": "médio-agudo", "entrega": "belting com grit"}]},
     "estrutura_tipica": ["intro", "verso", "refrão", "verso", "refrão", "ponte", "refrão final"],
     "producao": "guitarras amplas, bateria forte, voz na frente",
     "prompt_suno_curto": "Female anthem rock, powerful female belting vocals, driving guitars, big drums, triumphant mood.",
     "prompt_suno_longo": "Female anthem rock. Powerful female lead with belting and light grit, driving distorted guitars, punchy live drums, anthemic gang-vocal chorus, triumphant build from quiet verse to explosive final chorus.",
     "referencias": ["fire-rock-fem-a.mp3"], "fonte": "acervo suno",
     "tags": ["rock", "feminino", "virada"]}
  ]}
  ```
- [ ] **Step 4: Rodar e ver passar:** `python3 -m pytest tests/test_dados.py -x -q`
- [ ] **Step 5: Commit:** `git add -A && git commit -m "data: templates de capa e clipe (spec §8.4) + fixture de estilos p/ testes"`

---

### Task 6: `providers/base.py` + `src/registry.py`

**Files:** Create `providers/__init__.py` (vazio), `providers/base.py`, `src/registry.py`, `tests/test_registry.py`, e os 5 `providers/*.models.json` (conteúdo abaixo)
**Interfaces:** Produces (contrato usado por TODAS as tasks de provider e pelo executor):
- `providers/base.py`: `class ProviderError(Exception)`; `@dataclass Resultado(arquivo: Path, custo_real: float, meta: dict)`; `class Provider` com `nome: str`, `disponivel(self) -> tuple[bool, str]`, `estimar_custo(self, modelo: str, params: dict) -> float`, `gerar(self, modelo: str, params: dict, workdir: Path) -> Resultado`; `ler_env_chave(nomes: list[str]) -> str | None` (varre `~/projetos/openpcbotv2/.env` depois `~/projetos/wifi/.env`, parse `CHAVE=valor`, nunca imprime valor); `http_json(url, metodo="GET", corpo=None, headers=None, tentativas=4, timeout=120) -> dict` (urllib + backoff 2/4/8s em 503/429); `gravar_raw(workdir: Path, nome: str, payload: dict) -> None` (em `workdir/raw/`, com sufixo `-vN` se colidir).
- `src/registry.py`: `carregar_registry() -> dict` → `{"kie:suno-v4.5": {"provider": <Provider>, "modelo": <dict do models.json>}}`; `resolver_motor(reg, motor: str) -> tuple[Provider, dict]` (KeyError legível se não existe); `disponibilidade(reg) -> dict[str, tuple[bool, str]]` (por provider); `validar_params(modelo: dict, params: dict) -> list[str]` (só chaves declaradas).

- [ ] **Step 1: Escrever os 5 models.json** (fatos medidos — não inventar):
  ```json
  // providers/kie.models.json
  {"provider": "kie", "env_keys": ["KIE_API_KEY"], "modelos": [
    {"id": "suno-v4.5", "api_model": "V4_5", "capacidade": "musica",
     "custo": {"base_usd": 0.08, "por": "geracao"},
     "params": {"duracao_s": {"default": 180, "max": 240},
                "instrumental": {"default": false},
                "estilo_prompt_max_chars": 1000}}]}
  ```
  ```json
  // providers/agnes.models.json
  {"provider": "agnes", "env_keys": ["AGNES_API_KEY"], "modelos": [
    {"id": "agnes-image-2.1-flash", "capacidade": "imagem",
     "custo": {"base_usd": 0.0, "por": "geracao"},
     "params": {"tamanho": {"default": "1024x1024"}}},
    {"id": "agnes-video-v2.0", "capacidade": "video",
     "custo": {"base_usd": 0.0, "por": "segundo"},
     "params": {"resolucao": {"default": "1312x736"},
                "duracao_shot_s": {"default": 5, "max": 18}}}]}
  ```
  ```json
  // providers/inemaimg.models.json
  {"provider": "inemaimg", "env_keys": [], "modelos": [
    {"id": "flux2-klein", "capacidade": "imagem",
     "custo": {"base_usd": 0.0, "por": "geracao"},
     "params": {"tamanho": {"default": "1024x1024"}}}]}
  ```
  ```json
  // providers/kling.models.json  (via kie /jobs/createTask — NÃO testado nesta rodada)
  {"provider": "kling", "env_keys": ["KIE_API_KEY"], "modelos": [
    {"id": "kling-2.5", "api_model": "kling/v2-5-turbo-text-to-video-pro",
     "capacidade": "video",
     "custo": {"base_usd": 0.056, "por": "segundo"},
     "params": {"resolucao": {"default": "720p"}, "duracao_shot_s": {"default": 5, "max": 10}}}]}
  ```
  (0.056/s = US$ 0,28 por shot de 5s, preço medido do grupo kling-2-x no KIE-MODELOS.md do bench-studio-br.)
  ```json
  // providers/fal.models.json  (NÃO testado nesta rodada)
  {"provider": "fal", "env_keys": ["FAL_KEY"], "modelos": [
    {"id": "kling-video-v2.5-turbo-pro", "capacidade": "video",
     "api_path": "fal-ai/kling-video/v2.5-turbo/pro/text-to-video",
     "custo": {"base_usd": 0.07, "por": "segundo"},
     "params": {"resolucao": {"default": "720p"}, "duracao_shot_s": {"default": 5, "max": 10}}}]}
  ```
- [ ] **Step 2: Escrever o teste que falha:**
  ```python
  # tests/test_registry.py
  from pathlib import Path
  import pytest
  from src.registry import carregar_registry, resolver_motor, disponibilidade, validar_params
  from providers.base import ler_env_chave, Resultado, Provider

  def test_registry_tem_os_5_provedores_e_defaults():
      reg = carregar_registry()
      for motor in ("kie:suno-v4.5", "agnes:agnes-image-2.1-flash", "agnes:agnes-video-v2.0",
                    "inemaimg:flux2-klein", "kling:kling-2.5", "fal:kling-video-v2.5-turbo-pro"):
          assert motor in reg, motor

  def test_resolver_motor_inexistente_erra_legivel():
      reg = carregar_registry()
      with pytest.raises(KeyError, match="nao-existe"):
          resolver_motor(reg, "nao-existe:modelo")

  def test_disponibilidade_sem_chave_da_motivo(monkeypatch):
      # aponta os .env autorizados pra um lugar vazio
      monkeypatch.setenv("MUSICAVIDEO_ENV_DIRS", "/nonexistent-a:/nonexistent-b")
      reg = carregar_registry()
      ok, motivo = disponibilidade(reg)["kie"]
      assert ok is False and "KIE_API_KEY" in motivo and ".env" in motivo

  def test_validar_params_rejeita_chave_desconhecida():
      reg = carregar_registry()
      _, modelo = resolver_motor(reg, "kie:suno-v4.5")
      assert validar_params(modelo, {"duracao_s": 180}) == []
      assert validar_params(modelo, {"xyz": 1}) != []

  def test_ler_env_chave_nunca_retorna_de_env_nao_autorizado(monkeypatch, tmp_path):
      d = tmp_path / "a"; d.mkdir()
      (d / ".env").write_text("MINHA_CHAVE=segredo\n")
      monkeypatch.setenv("MUSICAVIDEO_ENV_DIRS", str(d))
      assert ler_env_chave(["MINHA_CHAVE"]) == "segredo"
      assert ler_env_chave(["OUTRA"]) is None
  ```
- [ ] **Step 3: Rodar e ver falhar:** `python3 -m pytest tests/test_registry.py -x -q` — `ModuleNotFoundError`.
- [ ] **Step 4: Implementação mínima:**
  ```python
  # providers/base.py
  """Contrato do adapter + utilitários compartilhados (stdlib only)."""
  import json, os, time, urllib.request, urllib.error
  from dataclasses import dataclass, field
  from pathlib import Path

  ENV_DIRS_DEFAULT = [Path.home() / "projetos/openpcbotv2", Path.home() / "projetos/wifi"]

  class ProviderError(Exception):
      pass

  @dataclass
  class Resultado:
      arquivo: Path
      custo_real: float
      meta: dict = field(default_factory=dict)

  class Provider:
      nome: str = "?"
      def disponivel(self) -> tuple[bool, str]: raise NotImplementedError
      def estimar_custo(self, modelo: str, params: dict) -> float: raise NotImplementedError
      def gerar(self, modelo: str, params: dict, workdir: Path) -> Resultado: raise NotImplementedError

  def _env_dirs() -> list[Path]:
      env = os.environ.get("MUSICAVIDEO_ENV_DIRS")
      if env: return [Path(p) for p in env.split(":")]
      return ENV_DIRS_DEFAULT

  def ler_env_chave(nomes: list[str]) -> str | None:
      """Lê a 1ª chave encontrada nos .env autorizados. NUNCA logar o valor."""
      for d in _env_dirs():
          arq = d / ".env"
          if not arq.exists(): continue
          for linha in arq.read_text(encoding="utf-8", errors="ignore").splitlines():
              linha = linha.strip()
              if "=" not in linha or linha.startswith("#"): continue
              k, _, v = linha.partition("=")
              if k.strip() in nomes and v.strip():
                  return v.strip().strip('"').strip("'")
      return None

  def motivo_indisponivel(nomes: list[str]) -> str:
      return (f"{'/'.join(nomes)} não encontrada em "
              "openpcbotv2/.env nem wifi/.env")

  def http_json(url: str, metodo: str = "GET", corpo: dict | None = None,
                headers: dict | None = None, tentativas: int = 4, timeout: int = 120) -> dict:
      dados = json.dumps(corpo).encode() if corpo is not None else None
      h = {"Content-Type": "application/json", **(headers or {})}
      for i in range(tentativas):
          try:
              req = urllib.request.Request(url, data=dados, headers=h, method=metodo)
              with urllib.request.urlopen(req, timeout=timeout) as r:
                  return json.loads(r.read().decode())
          except urllib.error.HTTPError as e:
              if e.code in (429, 502, 503) and i < tentativas - 1:
                  time.sleep(2 ** (i + 1)); continue
              raise ProviderError(f"HTTP {e.code} em {url}: {e.read().decode()[:300]}") from e
          except urllib.error.URLError as e:
              if i < tentativas - 1: time.sleep(2 ** (i + 1)); continue
              raise ProviderError(f"rede indisponível em {url}: {e.reason}") from e
      raise ProviderError(f"esgotou tentativas em {url}")

  def baixar(url: str, destino: Path, timeout: int = 300) -> Path:
      """Baixa NA HORA (URLs de provedores expiram)."""
      destino.parent.mkdir(parents=True, exist_ok=True)
      with urllib.request.urlopen(url, timeout=timeout) as r:
          destino.write_bytes(r.read())
      return destino

  def gravar_raw(workdir: Path, nome: str, payload: dict) -> None:
      raw = workdir / "raw"; raw.mkdir(exist_ok=True)
      alvo, n = raw / f"{nome}.json", 2
      while alvo.exists():
          alvo = raw / f"{nome}-v{n}.json"; n += 1
      alvo.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
  ```
  ```python
  # src/registry.py
  """Mescla providers/*.models.json num registry único; indisponível-com-motivo."""
  import importlib, json
  from pathlib import Path

  PROVIDERS_DIR = Path(__file__).resolve().parents[1] / "providers"

  def carregar_registry() -> dict:
      reg = {}
      for mj in sorted(PROVIDERS_DIR.glob("*.models.json")):
          decl = json.loads(mj.read_text(encoding="utf-8"))
          mod = importlib.import_module(f"providers.{decl['provider']}")
          prov = mod.criar(decl)   # cada providers/<nome>.py expõe criar(decl) -> Provider
          for m in decl["modelos"]:
              reg[f"{decl['provider']}:{m['id']}"] = {"provider": prov, "modelo": m}
      return reg

  def resolver_motor(reg: dict, motor: str):
      if motor not in reg:
          prov = motor.split(":")[0]
          raise KeyError(f"motor '{motor}' não existe no registry (provider '{prov}'; "
                         f"disponíveis: {sorted(reg)})")
      e = reg[motor]
      return e["provider"], e["modelo"]

  def disponibilidade(reg: dict) -> dict:
      vistos = {}
      for e in reg.values():
          p = e["provider"]
          if p.nome not in vistos:
              vistos[p.nome] = p.disponivel()
      return vistos

  def validar_params(modelo: dict, params: dict) -> list[str]:
      declarados = set(modelo.get("params", {}))
      return [f"param desconhecido '{k}' pro modelo {modelo['id']}"
              for k in params if k not in declarados]
  ```
  Para o registry importar sem os adapters prontos, criar nesta task **stubs mínimos** `providers/kie.py`, `providers/agnes.py`, `providers/inemaimg.py`, `providers/kling.py`, `providers/fal.py`, todos com o mesmo esqueleto (as Tasks 9-12 substituem `gerar`):
  ```python
  # providers/kie.py (stub desta task; mesmo shape nos outros 4, mudando nome/env_keys)
  from pathlib import Path
  from providers.base import Provider, Resultado, ProviderError, ler_env_chave, motivo_indisponivel

  class Kie(Provider):
      nome = "kie"
      def __init__(self, decl): self.decl = decl
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

  def criar(decl): return Kie(decl)
  ```
  (`inemaimg` difere: `disponivel()` faz `GET http://localhost:8000/health` com timeout 3s via `http_json`; sem servidor → `(False, "inemaimg: indisponível — servidor local não responde em localhost:8000")`.)
- [ ] **Step 5: Rodar e ver passar:** `python3 -m pytest tests/ -x -q`
- [ ] **Step 6: Commit:** `git add -A && git commit -m "providers: contrato base + registry declarativo + 5 provedores registrados (indisponível-com-motivo)"`

---

### Task 7: `src/planner.py` — `plano` + `ver`

**Files:** Create `src/planner.py`, `tests/test_planner.py`; Modify `src/main.py` (comandos `plano`, `ver`)
**Interfaces:** Consumes: `validar_plano`/`campos_prompt_en` (T2), `novo_estado`/`salvar_estado` (T3), `linha_de`/`gravar_linha`/`contexto_acervo` (T4), `carregar_registry`/`disponibilidade`/`resolver_motor`/`validar_params` (T6). Produces:
- `derivar_slug(solicitacao: str, outdir: Path) -> str` (kebab, ≤40, sufixo -2/-3 se colidir)
- `montar_contexto(solicitacao, opts: dict, outdir: Path) -> str` (prompt pro Fable: solicitação + estilos.json + templates + acervo + pesquisa.md se houver + REGRAS: JSON puro no schema §8.1, prompts de provedor em EN, letra conforme origem)
- `chamar_fable(prompt: str) -> str` (subprocess `claude -p <prompt> --model fable`, captura stdout; `RuntimeError` legível se o binário faltar)
- `gerar_plano(solicitacao: str, slug: str | None, opts: dict, outdir: Path, chamar_llm=chamar_fable) -> dict` — monta contexto, chama LLM, extrai o primeiro bloco JSON, aplica `--motor`/`--estilo`/`--letra`, força defaults de motor se o LLM omitir (`kie:suno-v4.5`, `agnes:agnes-image-2.1-flash`, `agnes:agnes-video-v2.0`), valida (schema + EN + params + motor no registry, com **1 retry**: reenvia ao LLM com os erros; persistindo, `ValueError`), grava `plano.json` + `PLANO.md` + `estado.json` + linha do index, avisa disponibilidade
- `render_plano_md(plano: dict, disponibilidade: dict) -> str`
- `cmd_plano(args) -> int`, `cmd_ver(args) -> int`
`chamar_llm` é injetável — testes usam um fake, nunca o `claude` real.

- [ ] **Step 1: Escrever o teste que falha:**
  ```python
  # tests/test_planner.py
  import json, pytest
  from pathlib import Path
  from src.planner import derivar_slug, gerar_plano, render_plano_md

  def _fake_llm(plano_ok):
      def f(prompt: str) -> str:
          return "aqui está o plano:\n```json\n" + json.dumps(plano_ok) + "\n```"
      return f

  def test_derivar_slug(outdir):
      s = derivar_slug("Música de VIRADA, rock feminino!!", outdir)
      assert s == "musica-de-virada-rock-feminino"
      (outdir / s).mkdir()
      assert derivar_slug("Música de VIRADA, rock feminino!!", outdir) == s + "-2"

  def test_gerar_plano_grava_tudo(outdir, plano_ok):
      p = gerar_plano("rock feminino de virada", "teste-rock", {}, outdir,
                      chamar_llm=_fake_llm(plano_ok))
      w = outdir / "teste-rock"
      assert (w / "plano.json").exists() and (w / "PLANO.md").exists()
      assert (w / "estado.json").exists()
      assert json.loads((outdir / "index.jsonl").read_text().splitlines()[0])["slug"] == "teste-rock"
      assert p["capa"]["motor"] == "agnes:agnes-image-2.1-flash"

  def test_plano_invalido_faz_retry_e_erra(outdir, plano_ok):
      plano_ok["capa"]["prompt_imagem"] = "retrato em contraluz âmbar"  # PT → inválido
      with pytest.raises(ValueError, match="INGLÊS"):
          gerar_plano("x", "s2", {}, outdir, chamar_llm=_fake_llm(plano_ok))

  def test_letra_final_e_lei(outdir, plano_ok, tmp_path):
      arq = tmp_path / "letra.txt"
      arq.write_text("[Verse 1]\nminha letra imutável\n", encoding="utf-8")
      p = gerar_plano("balada", "s3", {"letra": str(arq), "letra_final": True},
                      outdir, chamar_llm=_fake_llm(plano_ok))
      assert p["musica"]["letra"]["origem"] == "final_usuario"
      assert p["musica"]["letra"]["texto"] == arq.read_text(encoding="utf-8")

  def test_motor_override(outdir, plano_ok):
      p = gerar_plano("x", "s4", {"motor": {"clipe": "kling:kling-2.5"}},
                      outdir, chamar_llm=_fake_llm(plano_ok))
      assert p["clipe"]["motor"] == "kling:kling-2.5"

  def test_slug_existente_sem_forca_erra(outdir, plano_ok):
      gerar_plano("x", "s5", {}, outdir, chamar_llm=_fake_llm(plano_ok))
      with pytest.raises(ValueError, match="--forca"):
          gerar_plano("x", "s5", {}, outdir, chamar_llm=_fake_llm(plano_ok))

  def test_render_md_mostra_indisponivel(plano_ok):
      md = render_plano_md(plano_ok, {"kie": (False, "kie: indisponível — KIE_API_KEY não encontrada")})
      assert "indisponível" in md and "KIE_API_KEY" in md
  ```
- [ ] **Step 2: Rodar e ver falhar:** `python3 -m pytest tests/test_planner.py -x -q` — `ModuleNotFoundError: src.planner`.
- [ ] **Step 3: Implementação mínima** (pontos não-óbvios; o resto é encadeamento das interfaces já definidas):
  ```python
  # src/planner.py — núcleo
  import json, re, subprocess, unicodedata
  from pathlib import Path
  from src.esquemas import validar_plano, campos_prompt_en
  from src.estado import novo_estado, salvar_estado, _agora
  from src.indexer import linha_de, gravar_linha, contexto_acervo
  from src.registry import carregar_registry, disponibilidade, resolver_motor, validar_params

  RAIZ = Path(__file__).resolve().parents[1]
  MOTORES_DEFAULT = {"musica": "kie:suno-v4.5",
                     "capa": "agnes:agnes-image-2.1-flash",
                     "clipe": "agnes:agnes-video-v2.0"}

  def derivar_slug(solicitacao: str, outdir: Path) -> str:
      s = unicodedata.normalize("NFKD", solicitacao).encode("ascii", "ignore").decode()
      s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:40].rstrip("-")
      base, n = s, 2
      while (outdir / s).exists():
          s = f"{base}-{n}"; n += 1
      return s

  def chamar_fable(prompt: str) -> str:
      try:
          r = subprocess.run(["claude", "-p", prompt, "--model", "fable"],
                             capture_output=True, text=True, timeout=600)
      except FileNotFoundError:
          raise RuntimeError("binário 'claude' não encontrado — o planner precisa do Claude Code no PATH")
      if r.returncode != 0:
          raise RuntimeError(f"claude -p falhou: {r.stderr[:300]}")
      return r.stdout

  def _extrair_json(texto: str) -> dict:
      m = re.search(r"\{.*\}", texto, re.S)
      if not m: raise ValueError("resposta do planejador não contém JSON")
      return json.loads(m.group(0))

  def montar_contexto(solicitacao: str, opts: dict, outdir: Path) -> str:
      estilos = (RAIZ / "data/estilos.json")
      if not estilos.exists(): estilos = RAIZ / "tests/fixtures/estilos.json"
      partes = [
        "Você é o planejador do musicavideo. Responda APENAS um JSON no schema plano.json v1 "
        "(schema_version, slug, criado_em, solicitacao, pesquisa, estilo_ref, titulo, musica, capa, clipe).",
        "REGRA: os campos musica.estilo.prompt_estilo, capa.prompt_imagem, capa.prompt_negativo e "
        "clipe.decupagem[].prompt DEVEM ser em INGLÊS (a API Agnes bloqueia português). "
        "conceito/descricao/letra/mood podem ser em português.",
        "Motores default: " + json.dumps(MOTORES_DEFAULT),
        f"SOLICITAÇÃO: {solicitacao}",
        "ESTILOS: " + estilos.read_text(encoding="utf-8"),
        "TEMPLATES CAPA: " + (RAIZ / "data/templates-capa.json").read_text(encoding="utf-8"),
        "TEMPLATES CLIPE: " + (RAIZ / "data/templates-clipe.json").read_text(encoding="utf-8"),
        "ACERVO: " + json.dumps(contexto_acervo(outdir, solicitacao), ensure_ascii=False),
      ]
      if opts.get("estilo"): partes.append(f"ESTILO PEDIDO: {opts['estilo']}")
      if opts.get("pesquisa_md"): partes.append("PESQUISA:\n" + opts["pesquisa_md"])
      if opts.get("letra"):
          modo = "FINAL (copiar VERBATIM em musica.letra.texto, origem final_usuario)" \
                 if opts.get("letra_final") else \
                 "RASCUNHO (terminar/ajustar; origem rascunho_usuario; guardar original em texto_original)"
          partes.append(f"LETRA {modo}:\n" + Path(opts["letra"]).read_text(encoding="utf-8"))
      partes.append("Antes de responder, faça um passe de autocrítica: coerência letra↔estrutura↔decupagem, "
                    "prompts completos e em inglês, params válidos. Responda só o JSON final.")
      return "\n\n".join(partes)

  def _validar_tudo(plano: dict, reg: dict) -> list[str]:
      erros = validar_plano(plano) + campos_prompt_en(plano)
      for parte in ("musica", "capa", "clipe"):
          motor = plano.get(parte, {}).get("motor", "")
          try:
              _, modelo = resolver_motor(reg, motor)
              erros += validar_params(modelo, plano[parte].get("params", {}))
          except KeyError as e:
              erros.append(str(e))
      return erros

  def gerar_plano(solicitacao, slug, opts, outdir, chamar_llm=chamar_fable) -> dict:
      outdir.mkdir(parents=True, exist_ok=True)
      slug = slug or derivar_slug(solicitacao, outdir)
      w = outdir / slug
      if w.exists() and not opts.get("forca"):
          raise ValueError(f"slug '{slug}' já existe — use --forca para replanejar")
      reg = carregar_registry()
      prompt = montar_contexto(solicitacao, opts, outdir)
      plano = _extrair_json(chamar_llm(prompt))
      # imposições determinísticas (não confiar no LLM pra isso):
      plano.update({"schema_version": "1", "slug": slug, "criado_em": _agora(),
                    "solicitacao": solicitacao, "pesquisa": bool(opts.get("pesquisa_md")),
                    })
      for parte, motor in MOTORES_DEFAULT.items():
          plano[parte].setdefault("motor", motor)
      for parte, motor in (opts.get("motor") or {}).items():
          plano[parte]["motor"] = motor
      if opts.get("letra") and opts.get("letra_final"):
          plano["musica"]["letra"] = {"origem": "final_usuario",
              "texto": Path(opts["letra"]).read_text(encoding="utf-8"),
              "texto_original": None, "idioma": plano["musica"]["letra"].get("idioma", "pt-BR")}
      erros = _validar_tudo(plano, reg)
      if erros:  # 1 retry com os erros de volta pro LLM
          plano2 = _extrair_json(chamar_llm(prompt + "\n\nSEU JSON ANTERIOR TINHA ERROS, corrija:\n- "
                                            + "\n- ".join(erros) + "\n\nJSON anterior:\n" + json.dumps(plano, ensure_ascii=False)))
          for k in ("schema_version", "slug", "criado_em", "solicitacao", "pesquisa"):
              plano2[k] = plano[k]
          if opts.get("letra") and opts.get("letra_final"):
              plano2["musica"]["letra"] = plano["musica"]["letra"]
          plano = plano2
          erros = _validar_tudo(plano, reg)
          if erros:
              raise ValueError("plano inválido após retry:\n- " + "\n- ".join(erros))
      w.mkdir(parents=True, exist_ok=True)
      (w / "plano.json").write_text(json.dumps(plano, ensure_ascii=False, indent=2), encoding="utf-8")
      disp = disponibilidade(reg)
      (w / "PLANO.md").write_text(render_plano_md(plano, disp), encoding="utf-8")
      estado = novo_estado(slug)
      salvar_estado(w, estado)
      gravar_linha(outdir, linha_de(plano, estado))
      return plano
  ```
  `render_plano_md` gera markdown com título, solicitação, seção por parte (motor, params, estilo/letra ou conceito/prompt ou decupagem em tabela) e um bloco "Disponibilidade dos provedores" listando `(ok/indisponível — motivo)`. Diff da letra rascunho (`texto_original` vs `texto`) via `difflib.unified_diff`. `cmd_plano` parseia flags (`--pesquisa` chama `src.pesquisa` quando existir — até a Task 14, flag aceita e ignorada com aviso), `cmd_ver` imprime `PLANO.md` inteiro ou a seção da parte. Registrar em `COMANDOS`.
- [ ] **Step 4: Rodar e ver passar:** `python3 -m pytest tests/ -x -q`
- [ ] **Step 5: Commit:** `git add -A && git commit -m "planner: plano+ver — Fable via claude -p injetável, validação com retry, defaults agnes/kie"`

---

### Task 8: `ajusta` + `ok` (portão completo)

**Files:** Modify `src/planner.py` (adicionar `ajustar_parte`, `aprovar_parte`, `cmd_ajusta`, `cmd_ok`), `src/main.py`; Create `tests/test_ajusta_ok.py`
**Interfaces:** Consumes: tudo da Task 7 + `transicao`/`carregar_estado`/`salvar_estado` (T3). Produces:
- `ajustar_parte(outdir: Path, slug: str, parte: str, instrucao: str, refaz: bool = False, chamar_llm=chamar_fable) -> str` — retorna o diff unificado impresso; reescreve SÓ `plano[parte]` (LLM recebe o plano atual + instrução + regra de imutabilidade da letra final), valida a seção, aplica `transicao(estado, parte, "refaz")` se estava `pronto` (exigindo `refaz=True`, e movendo o artefato antigo pra `raw/<artefato>-vN`) senão `transicao(..., "ajusta")`, regrava plano/PLANO.md/estado/index.
- `aprovar_parte(outdir: Path, slug: str, parte: str) -> None` — `transicao(..., "ok")` + persistências.

- [ ] **Step 1: Escrever o teste que falha:**
  ```python
  # tests/test_ajusta_ok.py
  import json, pytest
  from src.planner import gerar_plano, ajustar_parte, aprovar_parte
  from src.estado import carregar_estado, TransicaoInvalida

  def _fake_llm(plano): 
      return lambda prompt: json.dumps(plano)

  def _fake_ajuste(secao):  # LLM do ajusta devolve só a seção nova
      return lambda prompt: json.dumps(secao)

  @pytest.fixture
  def slug_pronto(outdir, plano_ok):
      gerar_plano("rock feminino", "teste-rock", {}, outdir, chamar_llm=_fake_llm(plano_ok))
      return "teste-rock"

  def test_ok_abre_portao(outdir, slug_pronto):
      aprovar_parte(outdir, slug_pronto, "musica")
      e = carregar_estado(outdir / slug_pronto)
      assert e["partes"]["musica"]["estado"] == "aprovado"

  def test_ajusta_reescreve_so_a_parte_e_mostra_diff(outdir, slug_pronto, plano_ok):
      nova = dict(plano_ok["capa"], conceito="Novo conceito de capa")
      diff = ajustar_parte(outdir, slug_pronto, "capa", "muda o conceito",
                           chamar_llm=_fake_ajuste(nova))
      assert "Novo conceito" in diff
      plano = json.loads((outdir / slug_pronto / "plano.json").read_text())
      assert plano["capa"]["conceito"] == "Novo conceito de capa"
      assert plano["musica"] == plano_ok["musica"]   # intocada

  def test_ajusta_derruba_aprovacao(outdir, slug_pronto, plano_ok):
      aprovar_parte(outdir, slug_pronto, "capa")
      ajustar_parte(outdir, slug_pronto, "capa", "x",
                    chamar_llm=_fake_ajuste(plano_ok["capa"] | {"conceito": "outro"}))
      e = carregar_estado(outdir / slug_pronto)
      assert e["partes"]["capa"]["estado"] == "planejado"
      assert e["partes"]["capa"]["ajustes"] == 1

  def test_ajusta_recusa_mudar_letra_final(outdir, plano_ok):
      plano_ok["musica"]["letra"] = {"origem": "final_usuario", "texto": "IMUTÁVEL",
                                     "texto_original": None, "idioma": "pt-BR"}
      gerar_plano("x", "s-lei", {}, outdir, chamar_llm=_fake_llm(plano_ok))
      mexida = json.loads(json.dumps(plano_ok["musica"]))
      mexida["letra"]["texto"] = "TROCADA"
      with pytest.raises(ValueError, match="final_usuario"):
          ajustar_parte(outdir, "s-lei", "musica", "troca a letra",
                        chamar_llm=_fake_ajuste(mexida))

  def test_ok_duas_vezes_erra(outdir, slug_pronto):
      aprovar_parte(outdir, slug_pronto, "musica")
      with pytest.raises(TransicaoInvalida):
          aprovar_parte(outdir, slug_pronto, "musica")
  ```
- [ ] **Step 2: Rodar e ver falhar:** `python3 -m pytest tests/test_ajusta_ok.py -x -q` — `ImportError: ajustar_parte`.
- [ ] **Step 3: Implementação mínima:**
  ```python
  # src/planner.py — acrescentar
  import difflib
  from src.estado import carregar_estado, salvar_estado, transicao

  def aprovar_parte(outdir: Path, slug: str, parte: str) -> None:
      w = outdir / slug
      plano = json.loads((w / "plano.json").read_text(encoding="utf-8"))
      estado = carregar_estado(w)
      transicao(estado, parte, "ok")
      salvar_estado(w, estado)
      gravar_linha(outdir, linha_de(plano, estado))

  def ajustar_parte(outdir: Path, slug: str, parte: str, instrucao: str,
                    refaz: bool = False, chamar_llm=chamar_fable) -> str:
      w = outdir / slug
      plano = json.loads((w / "plano.json").read_text(encoding="utf-8"))
      estado = carregar_estado(w)
      antiga = plano[parte]
      letra_lei = (parte == "musica"
                   and antiga.get("letra", {}).get("origem") == "final_usuario")
      prompt = ("Plano atual:\n" + json.dumps(plano, ensure_ascii=False)
                + f"\n\nReescreva APENAS a seção '{parte}' seguindo: {instrucao}. "
                  "Prompts de provedor em INGLÊS. Responda só o JSON da seção."
                + ("\nREGRA: musica.letra é IMUTÁVEL (final_usuario) — copie verbatim."
                   if letra_lei else ""))
      nova = _extrair_json(chamar_llm(prompt))
      if letra_lei and nova.get("letra", {}).get("texto") != antiga["letra"]["texto"]:
          raise ValueError("musica.letra é final_usuario — o ajusta não pode alterá-la")
      candidato = dict(plano); candidato[parte] = nova
      erros = _validar_tudo(candidato, carregar_registry())
      if erros:
          raise ValueError("ajuste inválido:\n- " + "\n- ".join(erros))
      # estado: pronto exige --refaz (artefato antigo vai pra raw/ com -vN)
      if estado["partes"][parte]["estado"] == "pronto":
          if not refaz:
              raise ValueError(f"{parte} está pronto — use --refaz para replanejar")
          art = estado["partes"][parte]["artefato"]
          if art and (w / art).exists():
              raw = w / "raw"; raw.mkdir(exist_ok=True)
              n = 1
              while (raw / f"{art}-v{n}").exists(): n += 1
              (w / art).rename(raw / f"{art}-v{n}")
          transicao(estado, parte, "refaz")
      transicao(estado, parte, "ajusta")
      plano[parte] = nova
      (w / "plano.json").write_text(json.dumps(plano, ensure_ascii=False, indent=2),
                                    encoding="utf-8")
      disp = disponibilidade(carregar_registry())
      (w / "PLANO.md").write_text(render_plano_md(plano, disp), encoding="utf-8")
      salvar_estado(w, estado)
      gravar_linha(outdir, linha_de(plano, estado))
      diff = "\n".join(difflib.unified_diff(
          json.dumps(antiga, ensure_ascii=False, indent=2).splitlines(),
          json.dumps(nova, ensure_ascii=False, indent=2).splitlines(),
          fromfile=f"{parte} (antes)", tofile=f"{parte} (depois)", lineterm=""))
      print(diff)
      return diff
  ```
  `cmd_ajusta`/`cmd_ok` em `main.py` traduzem `TransicaoInvalida`/`ValueError` em mensagem legível + exit 1 e registram-se em `COMANDOS`.
- [ ] **Step 4: Rodar e ver passar:** `python3 -m pytest tests/ -x -q`
- [ ] **Step 5: Commit:** `git add -A && git commit -m "planner: ajusta (diff por parte, letra final imutável, --refaz) + ok"`

---

### Task 9: `src/custo.py` + `providers/kie.py` real + `src/executor.py` + `faz musica`

**Files:** Modify `providers/kie.py`; Create `src/custo.py`, `src/executor.py`, `tests/test_custo.py`, `tests/test_kie.py`, `tests/test_executor.py`; Modify `src/main.py` (comandos `faz`, `custo`)
**Interfaces:** Consumes: T3, T4, T6, plano/estado das T7-8. Produces:
- `src/custo.py`: `estimar_partes(plano: dict, reg: dict, partes: list[str]) -> dict[str, float]` (usa `Provider.estimar_custo`; pro clipe soma `duracao_s` da decupagem quando `por == "segundo"`); `relatorio(estado: dict) -> str` (tabela estimado vs gasto por parte).
- `src/executor.py`: `faz(outdir: Path, slug: str, partes: list[str] | None, sim: bool = False, telegram: bool = False, motor_override: dict | None = None, reg=None) -> int` — carrega plano+estado; sem `partes` = todas em `aprovado`/`erro`; imprime estimativa e pede confirmação (a menos de `sim`); por parte: valida motor disponível (senão `transicao erro` com o motivo, segue), respeita `teto_usd` (estimativa + gasto > teto → pula, imprime motivo, exit 3 no fim), `transicao faz` + salvar (persistir `gerando` ANTES de chamar API), `provider.gerar(...)` com timeout de polling 15 min dentro do adapter, `transicao pronto|erro`, salvar estado + index a cada parte. Exit: 0 tudo ok; 2 alguma parte em erro; 3 teto.
- `providers/kie.py::Kie.gerar` real (Suno via api.kie.ai).

- [ ] **Step 1: Escrever os testes que falham:**
  ```python
  # tests/test_custo.py
  from src.custo import estimar_partes, relatorio
  from src.registry import carregar_registry
  from src.estado import novo_estado

  def test_estimativa_por_parte(plano_ok):
      est = estimar_partes(plano_ok, carregar_registry(), ["musica", "capa", "clipe"])
      assert est["musica"] == 0.08
      assert est["capa"] == 0.0            # agnes
      assert est["clipe"] == 0.0           # agnes: 0/segundo
      plano_ok["clipe"]["motor"] = "kling:kling-2.5"
      est2 = estimar_partes(plano_ok, carregar_registry(), ["clipe"])
      assert est2["clipe"] == round(0.056 * 10, 4)   # 2 shots de 5s

  def test_relatorio_mostra_estimado_vs_gasto():
      e = novo_estado("s")
      e["partes"]["musica"]["custo_estimado_usd"] = 0.08
      e["partes"]["musica"]["custo_real_usd"] = 0.08
      r = relatorio(e)
      assert "musica" in r and "0.08" in r
  ```
  ```python
  # tests/test_kie.py — mock HTTP total, zero rede
  import json, pytest
  from pathlib import Path
  import providers.kie as kie_mod
  from providers.base import ProviderError

  DECL = json.loads((Path(__file__).resolve().parents[1] / "providers/kie.models.json").read_text())

  def test_gerar_posta_polla_e_baixa(tmp_path, monkeypatch, plano_ok):
      chamadas = []
      def fake_http(url, metodo="GET", corpo=None, headers=None, **kw):
          chamadas.append((metodo, url, corpo))
          if url.endswith("/generate"):
              assert corpo["customMode"] is True
              assert corpo["model"] == "V4_5"          # api_model, não o id
              assert corpo["style"] == plano_ok["musica"]["estilo"]["prompt_estilo"]
              assert corpo["prompt"] == plano_ok["musica"]["letra"]["texto"]
              return {"data": {"taskId": "T1"}}
          return {"data": {"status": "SUCCESS", "response": {"sunoData": [
                  {"audioUrl": "http://x/faixa.mp3", "duration": 178}]}}}
      baixados = []
      monkeypatch.setattr(kie_mod, "http_json", fake_http)
      monkeypatch.setattr(kie_mod, "baixar",
          lambda url, destino, **kw: (baixados.append(url), destino.write_bytes(b"mp3"), destino)[-1])
      monkeypatch.setattr(kie_mod, "ler_env_chave", lambda nomes: "chave-fake")
      prov = kie_mod.criar(DECL)
      r = prov.gerar("suno-v4.5", {"titulo": plano_ok["titulo"],
                                   "letra": plano_ok["musica"]["letra"]["texto"],
                                   "estilo": plano_ok["musica"]["estilo"]["prompt_estilo"],
                                   "instrumental": False}, tmp_path)
      assert r.arquivo == tmp_path / "faixa.mp3" and r.arquivo.exists()
      assert r.custo_real == 0.08
      assert r.meta["kie_task_id"] == "T1"
      # taskId gravado em raw/ ANTES do poll (dinheiro já foi no POST):
      raws = list((tmp_path / "raw").glob("*.json"))
      assert any("T1" in p.read_text() for p in raws)

  def test_falha_da_api_vira_provider_error(tmp_path, monkeypatch):
      monkeypatch.setattr(kie_mod, "ler_env_chave", lambda n: "k")
      monkeypatch.setattr(kie_mod, "http_json",
          lambda *a, **k: (_ for _ in ()).throw(ProviderError("HTTP 500")))
      with pytest.raises(ProviderError):
          kie_mod.criar(DECL).gerar("suno-v4.5", {"titulo": "t", "letra": "l",
                                                  "estilo": "s", "instrumental": False}, tmp_path)
  ```
  ```python
  # tests/test_executor.py
  import json, pytest
  from pathlib import Path
  from src.planner import gerar_plano, aprovar_parte
  from src.executor import faz
  from src.estado import carregar_estado
  from providers.base import Resultado, ProviderError

  class ProvFake:
      nome = "kie"
      def __init__(self, ok=True): self.ok = ok
      def disponivel(self): return True, ""
      def estimar_custo(self, modelo, params): return 0.08
      def gerar(self, modelo, params, workdir):
          if not self.ok: raise ProviderError("boom")
          a = workdir / "faixa.mp3"; a.write_bytes(b"x")
          return Resultado(a, 0.08, {"kie_task_id": "T1"})

  def _reg_fake(prov):
      return {m: {"provider": prov, "modelo": {"id": m.split(":")[1], "params": {},
                  "custo": {"base_usd": 0.08, "por": "geracao"}, "capacidade": "musica"}}
              for m in ("kie:suno-v4.5", "agnes:agnes-image-2.1-flash", "agnes:agnes-video-v2.0")}

  @pytest.fixture
  def slug(outdir, plano_ok):
      gerar_plano("x", "teste-rock", {},
                  outdir, chamar_llm=lambda p: json.dumps(plano_ok))
      return "teste-rock"

  def test_faz_musica_aprovada(outdir, slug):
      aprovar_parte(outdir, slug, "musica")
      rc = faz(outdir, slug, ["musica"], sim=True, reg=_reg_fake(ProvFake()))
      assert rc == 0
      e = carregar_estado(outdir / slug)
      assert e["partes"]["musica"]["estado"] == "pronto"
      assert e["partes"]["musica"]["artefato"] == "faixa.mp3"
      assert e["custo_total_usd"]["gasto"] == 0.08
      idx = json.loads((outdir / "index.jsonl").read_text().splitlines()[0])
      assert idx["estados"]["musica"] == "pronto"

  def test_faz_parte_nao_aprovada_erra_uso(outdir, slug):
      assert faz(outdir, slug, ["musica"], sim=True, reg=_reg_fake(ProvFake())) == 1

  def test_erro_de_provider_nao_derruba_e_exit_2(outdir, slug):
      aprovar_parte(outdir, slug, "musica")
      rc = faz(outdir, slug, ["musica"], sim=True, reg=_reg_fake(ProvFake(ok=False)))
      assert rc == 2
      e = carregar_estado(outdir / slug)
      assert e["partes"]["musica"]["estado"] == "erro"
      assert e["partes"]["musica"]["erro"]["msg"] == "boom"

  def test_teto_pula_parte_exit_3(outdir, slug):
      aprovar_parte(outdir, slug, "musica")
      w = outdir / slug
      e = carregar_estado(w); e["teto_usd"] = 0.01
      from src.estado import salvar_estado; salvar_estado(w, e)
      rc = faz(outdir, slug, ["musica"], sim=True, reg=_reg_fake(ProvFake()))
      assert rc == 3
      assert carregar_estado(w)["partes"]["musica"]["estado"] == "aprovado"
  ```
- [ ] **Step 2: Rodar e ver falhar:** `python3 -m pytest tests/test_custo.py tests/test_kie.py tests/test_executor.py -x -q`
- [ ] **Step 3: Implementação mínima:**
  ```python
  # providers/kie.py — substituir gerar() do stub (resto do stub fica)
  import time
  from providers.base import http_json, baixar, gravar_raw  # + já importados no stub

  KIE_BASE = "https://api.kie.ai/api/v1"

  def _headers(self):
      return {"Authorization": f"Bearer {ler_env_chave(self.decl['env_keys'])}"}

  def gerar(self, modelo, params, workdir):
      m = next(x for x in self.decl["modelos"] if x["id"] == modelo)
      corpo = {"prompt": params["letra"], "style": params["estilo"][:m["params"]["estilo_prompt_max_chars"]],
               "title": params["titulo"], "customMode": True,
               "instrumental": bool(params.get("instrumental", False)),
               "model": m["api_model"], "negativeTags": params.get("negative_tags", "")}
      resp = http_json(f"{KIE_BASE}/generate", "POST", corpo, self._headers())
      task = (resp.get("data") or {}).get("taskId")
      if not task:
          raise ProviderError(f"kie: POST /generate sem taskId: {str(resp)[:300]}")
      gravar_raw(workdir, "kie-generate", {"taskId": task, "request_sem_chave": corpo, "response": resp})
      inicio = time.time()
      while True:
          if time.time() - inicio > 15 * 60:
              raise ProviderError(f"kie: timeout de polling (15 min) taskId={task}")
          r = http_json(f"{KIE_BASE}/generate/record-info?taskId={task}", headers=self._headers())
          d = r.get("data") or {}
          st = d.get("status", "")
          if st in ("SUCCESS", "FIRST_SUCCESS") or (d.get("response") or {}).get("sunoData"):
              faixas = (d.get("response") or {}).get("sunoData") or []
              if faixas: 
                  gravar_raw(workdir, "kie-record-info", r)
                  break
          if "FAIL" in st or "ERROR" in st:
              raise ProviderError(f"kie: geração falhou: {d.get('errorMessage', st)}")
          time.sleep(15)
      alvo = baixar(faixas[0]["audioUrl"], workdir / "faixa.mp3")   # URL do Suno EXPIRA: baixar já
      return Resultado(alvo, m["custo"]["base_usd"],
                       {"kie_task_id": task, "duracao_s": faixas[0].get("duration"),
                        "faixas_geradas": len(faixas)})
  ```
  ```python
  # src/executor.py — núcleo
  import json
  from pathlib import Path
  from src.estado import carregar_estado, salvar_estado, transicao, TransicaoInvalida
  from src.indexer import linha_de, gravar_linha
  from src.registry import carregar_registry, resolver_motor
  from src.custo import estimar_partes
  from providers.base import ProviderError

  ARTEFATOS = {"musica": "faixa.mp3", "capa": "capa.png", "clipe": "clipe.mp4"}

  def _params_de(plano: dict, parte: str) -> dict:
      p = dict(plano[parte].get("params", {}))
      if parte == "musica":
          p.update({"titulo": plano["titulo"], "letra": plano["musica"]["letra"]["texto"],
                    "estilo": plano["musica"]["estilo"]["prompt_estilo"],
                    "instrumental": plano["musica"]["params"].get("instrumental", False)})
      elif parte == "capa":
          p.update({"prompt": plano["capa"]["prompt_imagem"],
                    "prompt_negativo": plano["capa"]["prompt_negativo"]})
      elif parte == "clipe":
          p["decupagem"] = plano["clipe"]["decupagem"]
      return p

  def faz(outdir, slug, partes=None, sim=False, telegram=False,
          motor_override=None, reg=None) -> int:
      w = outdir / slug
      plano = json.loads((w / "plano.json").read_text(encoding="utf-8"))
      estado = carregar_estado(w)
      if telegram: estado["telegram"] = True
      for parte, motor in (motor_override or {}).items():
          plano[parte]["motor"] = motor
      reg = reg or carregar_registry()
      if partes is None:
          partes = [p for p in ("musica", "capa", "clipe")
                    if estado["partes"][p]["estado"] in ("aprovado", "erro")]
          if not partes:
              print("nada aprovado pra fazer — use `ok <slug> <parte>` antes"); return 1
      for p in partes:
          if estado["partes"][p]["estado"] not in ("aprovado", "erro"):
              print(f"{p}: estado '{estado['partes'][p]['estado']}' não permite faz "
                    f"(precisa aprovado ou erro)"); return 1
      est = estimar_partes(plano, reg, partes)
      print("custo estimado:")
      for p in partes: print(f"  {p:8s} US$ {est[p]:.4f}  ({plano[p]['motor']})")
      print(f"  total    US$ {sum(est.values()):.4f}")
      if not sim and input("confirmar? [s/N] ").strip().lower() != "s":
          print("cancelado"); return 0
      houve_erro = houve_teto = False
      for p in partes:
          prov, modelo = resolver_motor(reg, plano[p]["motor"])
          ok, motivo = prov.disponivel()
          if not ok:
              transicao(estado, p, "faz"); transicao(estado, p, "erro",
                        motor=plano[p]["motor"], msg=motivo)
              salvar_estado(w, estado); gravar_linha(outdir, linha_de(plano, estado))
              print(f"{p}: erro — {motivo}"); houve_erro = True; continue
          teto = estado.get("teto_usd")
          if teto is not None and estado["custo_total_usd"]["gasto"] + est[p] > teto:
              print(f"{p}: pulada — estouraria o teto de US$ {teto} "
                    f"(gasto {estado['custo_total_usd']['gasto']} + est {est[p]}). "
                    f"Retomar: musicavideo faz {slug} {p}")
              houve_teto = True; continue
          estado["partes"][p]["custo_estimado_usd"] = est[p]
          estado["custo_total_usd"]["estimado"] = round(sum(
              x["custo_estimado_usd"] for x in estado["partes"].values()), 4)
          transicao(estado, p, "faz"); salvar_estado(w, estado)   # gerando persistido ANTES da API
          try:
              r = prov.gerar(modelo["id"], _params_de(plano, p), w)
              transicao(estado, p, "pronto", artefato=r.arquivo.name,
                        custo_real=r.custo_real, meta=r.meta)
              print(f"{p}: pronto → {r.arquivo.name} (US$ {r.custo_real:.4f})")
          except ProviderError as e:
              transicao(estado, p, "erro", motor=plano[p]["motor"], msg=str(e))
              print(f"{p}: erro — {e}"); houve_erro = True
          salvar_estado(w, estado); gravar_linha(outdir, linha_de(plano, estado))
      if all(x["estado"] == "pronto" for x in estado["partes"].values()):
          from src.entrega import entregar   # Task 13; até lá, try/except ImportError
          try: entregar(outdir, slug)
          except ImportError: pass
      return 3 if houve_teto else (2 if houve_erro else 0)
  ```
  (Até a Task 13, o bloco de entrega fica protegido por `try/except ImportError`.)
  `src/custo.py`: `estimar_partes` resolve motor e chama `prov.estimar_custo(modelo["id"], params)`; pro clipe, quando `custo.por == "segundo"`, params ganham `duracao_shot_s = sum(s["duracao_s"] for s in decupagem)` antes; `relatorio` formata tabela do estado. Registrar `cmd_faz` (parse `--sim/--telegram/--motor`) e `cmd_custo` em `COMANDOS`.
- [ ] **Step 4: Rodar e ver passar:** `python3 -m pytest tests/ -x -q`
- [ ] **Step 5: Commit:** `git add -A && git commit -m "executor+custo+kie: faz musica ponta a ponta (mock), custo estimado antes, teto, exit 0/1/2/3"`

---

### Task 10: Capa — `providers/agnes.py` (imagem) + `providers/inemaimg.py`

**Files:** Modify `providers/agnes.py`, `providers/inemaimg.py`; Create `tests/test_agnes.py`, `tests/test_inemaimg.py`
**Interfaces:** Consumes: base.py (T6), executor `_params_de` capa (T9: `{"tamanho", "prompt", "prompt_negativo"}`). Produces: `Agnes.gerar("agnes-image-2.1-flash", params, workdir) -> Resultado(arquivo=workdir/"capa.png", custo_real=0.0, meta)`; `Inemaimg.gerar("flux2-klein", ...) -> Resultado` idem. Fatos medidos do Agnes imagem: endpoint `POST https://apihub.agnes-ai.com/v1/images/generations`, corpo `{"model", "prompt", "size": "1024x1024"}` (size SEMPRE em pixels), prompt EN obrigatório, ~34% de 503 (o retry do `http_json` já cobre), URL de saída temporária (baixar na hora).

- [ ] **Step 1: Escrever o teste que falha:**
  ```python
  # tests/test_agnes.py
  import json
  from pathlib import Path
  import providers.agnes as agnes_mod

  DECL = json.loads((Path(__file__).resolve().parents[1] / "providers/agnes.models.json").read_text())

  def test_capa_posta_size_em_pixels_e_baixa(tmp_path, monkeypatch):
      def fake_http(url, metodo="GET", corpo=None, headers=None, **kw):
          assert url.endswith("/v1/images/generations")
          assert corpo["model"] == "agnes-image-2.1-flash"
          assert corpo["size"] == "1024x1024"        # pixels, nunca ratio
          assert "album cover" in corpo["prompt"]
          return {"data": [{"url": "http://tmp/img.png"}]}
      monkeypatch.setattr(agnes_mod, "http_json", fake_http)
      monkeypatch.setattr(agnes_mod, "baixar",
          lambda url, destino, **kw: (destino.write_bytes(b"png"), destino)[-1])
      monkeypatch.setattr(agnes_mod, "ler_env_chave", lambda n: "k")
      r = agnes_mod.criar(DECL).gerar("agnes-image-2.1-flash",
          {"tamanho": "1024x1024", "prompt": "album cover, portrait", "prompt_negativo": "text"},
          tmp_path)
      assert r.arquivo == tmp_path / "capa.png" and r.custo_real == 0.0

  def test_custo_agnes_e_zero():
      prov = agnes_mod.criar(DECL)
      assert prov.estimar_custo("agnes-image-2.1-flash", {}) == 0.0
      assert prov.estimar_custo("agnes-video-v2.0", {"duracao_shot_s": 10}) == 0.0
  ```
  ```python
  # tests/test_inemaimg.py
  import json
  from pathlib import Path
  import providers.inemaimg as im

  DECL = json.loads((Path(__file__).resolve().parents[1] / "providers/inemaimg.models.json").read_text())

  def test_disponivel_sem_servidor_da_motivo(monkeypatch):
      from providers.base import ProviderError
      monkeypatch.setattr(im, "http_json",
          lambda *a, **k: (_ for _ in ()).throw(ProviderError("rede")))
      ok, motivo = im.criar(DECL).disponivel()
      assert ok is False and "localhost:8000" in motivo

  def test_gerar_decodifica_base64(tmp_path, monkeypatch):
      import base64
      monkeypatch.setattr(im, "http_json", lambda url, metodo="GET", corpo=None, **k:
          {"image": base64.b64encode(b"png-bytes").decode()} if url.endswith("/generate")
          else {"status": "ok"})
      r = im.criar(DECL).gerar("flux2-klein",
          {"tamanho": "1024x1024", "prompt": "album cover", "prompt_negativo": ""}, tmp_path)
      assert (tmp_path / "capa.png").read_bytes() == b"png-bytes"
  ```
- [ ] **Step 2: Rodar e ver falhar:** `python3 -m pytest tests/test_agnes.py tests/test_inemaimg.py -x -q`
- [ ] **Step 3: Implementação mínima:**
  ```python
  # providers/agnes.py — gerar() de imagem (o de vídeo vem na Task 11)
  AGNES_BASE = "https://apihub.agnes-ai.com"

  def _headers(self):
      return {"Authorization": f"Bearer {ler_env_chave(self.decl['env_keys'])}"}

  def gerar(self, modelo, params, workdir):
      if modelo == "agnes-image-2.1-flash":
          return self._gerar_imagem(params, workdir)
      if modelo == "agnes-video-v2.0":
          return self._gerar_video(params, workdir)   # Task 11
      raise ProviderError(f"agnes: modelo desconhecido {modelo}")

  def _gerar_imagem(self, params, workdir):
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
  ```
  `providers/inemaimg.py`: `disponivel()` = `http_json("http://localhost:8000/health", timeout=3, tentativas=1)` em try/except → `(False, "inemaimg: indisponível — servidor local não responde em localhost:8000")`; `gerar` = `POST http://localhost:8000/generate` com `{"prompt", "negative_prompt", "width", "height"}` (split do `tamanho`), decodifica o campo base64 da resposta pra `capa.png`, custo 0.
- [ ] **Step 4: Rodar e ver passar:** `python3 -m pytest tests/ -x -q`
- [ ] **Step 5: Commit:** `git add -A && git commit -m "capa: agnes imagem (default, size em pixels, EN) + inemaimg local como alternativa"`

---

### Task 11: Clipe — `providers/agnes.py` (vídeo) + concat ffmpeg

**Files:** Modify `providers/agnes.py`; Create `tests/test_agnes_video.py`
**Interfaces:** Consumes: base.py; params do executor (T9): `{"resolucao": "1312x736", "duracao_shot_s": 5, "decupagem": [...]}`. Produces: `Agnes._gerar_video(params, workdir) -> Resultado(arquivo=workdir/"clipe.mp4", custo_real=0.0, meta={"shots": N, "video_ids": [...]})`. Fatos medidos: `POST {AGNES_BASE}/v1/videos` com `{"model": "agnes-video-v2.0", "prompt": <EN>, "num_frames", "frame_rate": 24, "width", "height"}`; poll `GET {AGNES_BASE}/agnesapi?video_id=<ID>` (`queued`→`in_progress`→`completed`|`failed`); `num_frames` segue regra **8n+1, ≤441** (5s@24fps=120→**121**); rate limit real **5 req/min** → throttle ≥12s entre submissões; a resposta MENTE o tamanho → conferir com `ffprobe` o arquivo, não o JSON.

- [ ] **Step 1: Escrever o teste que falha:**
  ```python
  # tests/test_agnes_video.py
  import json
  from pathlib import Path
  import providers.agnes as agnes_mod

  DECL = json.loads((Path(__file__).resolve().parents[1] / "providers/agnes.models.json").read_text())

  def test_num_frames_regra_8n1():
      from providers.agnes import num_frames_para
      assert num_frames_para(5, 24) == 121    # 120 → próximo 8n+1
      assert num_frames_para(3.4, 24) == 81
      assert num_frames_para(30, 24) == 441   # teto 18,4s

  def test_gerar_video_shots_poll_concat(tmp_path, monkeypatch):
      posts, polls = [], []
      def fake_http(url, metodo="GET", corpo=None, headers=None, **kw):
          if metodo == "POST":
              posts.append(corpo)
              assert corpo["model"] == "agnes-video-v2.0"
              assert corpo["num_frames"] == 121 and corpo["frame_rate"] == 24
              return {"video_id": f"V{len(posts)}"}
          polls.append(url)
          return {"status": "completed", "video_url": "http://tmp/shot.mp4"}
      monkeypatch.setattr(agnes_mod, "http_json", fake_http)
      monkeypatch.setattr(agnes_mod, "baixar",
          lambda url, destino, **kw: (destino.write_bytes(b"mp4"), destino)[-1])
      monkeypatch.setattr(agnes_mod, "ler_env_chave", lambda n: "k")
      monkeypatch.setattr(agnes_mod.time, "sleep", lambda s: None)   # sem throttle no teste
      monkeypatch.setattr(agnes_mod, "concat_ffmpeg",
          lambda shots, alvo: (alvo.write_bytes(b"final"), alvo)[-1])
      decup = [{"n": 1, "secao": "intro", "duracao_s": 5, "camera": "dolly",
                "descricao": "x", "prompt": "slow dolly-in, workshop at dawn, 5s"},
               {"n": 2, "secao": "refrão", "duracao_s": 5, "camera": "orbit",
                "descricao": "y", "prompt": "orbit around woman, stage light, 5s"}]
      r = agnes_mod.criar(DECL).gerar("agnes-video-v2.0",
          {"resolucao": "1312x736", "duracao_shot_s": 5, "decupagem": decup}, tmp_path)
      assert len(posts) == 2
      assert r.arquivo == tmp_path / "clipe.mp4"
      assert r.meta["shots"] == 2 and r.meta["video_ids"] == ["V1", "V2"]

  def test_shot_failed_vira_provider_error(tmp_path, monkeypatch):
      import pytest
      from providers.base import ProviderError
      monkeypatch.setattr(agnes_mod, "ler_env_chave", lambda n: "k")
      monkeypatch.setattr(agnes_mod.time, "sleep", lambda s: None)
      monkeypatch.setattr(agnes_mod, "http_json", lambda url, metodo="GET", **k:
          {"video_id": "V1"} if metodo == "POST" else {"status": "failed", "error": "nsfw"})
      with pytest.raises(ProviderError, match="failed"):
          agnes_mod.criar(DECL).gerar("agnes-video-v2.0",
              {"resolucao": "1312x736", "decupagem": [
                  {"n": 1, "secao": "i", "duracao_s": 5, "camera": "c",
                   "descricao": "d", "prompt": "p"}]}, tmp_path)
  ```
- [ ] **Step 2: Rodar e ver falhar:** `python3 -m pytest tests/test_agnes_video.py -x -q` — `ImportError: num_frames_para`.
- [ ] **Step 3: Implementação mínima:**
  ```python
  # providers/agnes.py — acrescentar
  import subprocess, time

  def num_frames_para(duracao_s: float, fps: int = 24) -> int:
      """Regra 8n+1, teto 441 (18,4s @24fps)."""
      alvo = min(int(round(duracao_s * fps)), 441)
      n = max(1, round((alvo - 1) / 8))
      return min(8 * n + 1, 441)

  def concat_ffmpeg(shots: list, alvo) -> "Path":
      lista = alvo.parent / "raw" / "concat.txt"
      lista.parent.mkdir(exist_ok=True)
      lista.write_text("".join(f"file '{s}'\n" for s in shots), encoding="utf-8")
      r = subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lista),
                          "-c", "copy", str(alvo)], capture_output=True, text=True)
      if r.returncode != 0:
          raise ProviderError(f"ffmpeg concat falhou: {r.stderr[-300:]}")
      return alvo

  def _gerar_video(self, params, workdir):
      w, h = (params.get("resolucao") or "1312x736").split("x")
      shots_arq, video_ids = [], []
      inicio_geral = time.time()
      for i, shot in enumerate(params["decupagem"]):
          if i > 0: time.sleep(12)                       # rate limit real: 5 req/min
          corpo = {"model": "agnes-video-v2.0", "prompt": shot["prompt"],
                   "num_frames": num_frames_para(shot["duracao_s"]),
                   "frame_rate": 24, "width": int(w), "height": int(h)}
          resp = http_json(f"{AGNES_BASE}/v1/videos", "POST", corpo, self._headers())
          vid = resp.get("video_id") or resp.get("task_id") or resp.get("id")
          if not vid: raise ProviderError(f"agnes: POST /videos sem id: {str(resp)[:300]}")
          video_ids.append(vid)
          gravar_raw(workdir, f"agnes-shot-{shot['n']:02d}", {"request": corpo, "response": resp})
          while True:
              if time.time() - inicio_geral > 15 * 60:
                  raise ProviderError(f"agnes: timeout de polling (15 min) no shot {shot['n']}")
              st = http_json(f"{AGNES_BASE}/agnesapi?video_id={vid}", headers=self._headers())
              if st.get("status") == "completed":
                  url = st.get("video_url") or st.get("url")
                  arq = baixar(url, workdir / "raw" / f"shot-{shot['n']:02d}.mp4")
                  shots_arq.append(arq); break
              if st.get("status") == "failed":
                  raise ProviderError(f"agnes: shot {shot['n']} failed: {st.get('error', '')}")
              time.sleep(10)
      alvo = concat_ffmpeg(shots_arq, workdir / "clipe.mp4")
      # a resposta MENTE o size — medir o arquivo real:
      try:
          probe = subprocess.run(["ffprobe", "-v", "quiet", "-show_entries",
                                  "stream=width,height", "-of", "csv=p=0", str(alvo)],
                                 capture_output=True, text=True).stdout.strip()
      except FileNotFoundError:
          probe = "ffprobe ausente"
      return Resultado(alvo, 0.0, {"shots": len(shots_arq), "video_ids": video_ids,
                                   "size_real": probe})
  ```
- [ ] **Step 4: Rodar e ver passar:** `python3 -m pytest tests/ -x -q`
- [ ] **Step 5: Commit:** `git add -A && git commit -m "clipe: agnes vídeo (8n+1, throttle 5req/min, poll, ffprobe) + concat ffmpeg"`

---

### Task 12: `providers/kling.py` + `providers/fal.py` (contrato/mock, NÃO testados contra API real)

**Files:** Modify `providers/kling.py`, `providers/fal.py`; Create `tests/test_kling_fal.py`
**Interfaces:** Consumes: base.py; mesmos params de clipe da T11. Produces: `Kling.gerar` (kie `POST /api/v1/jobs/createTask` com `{"model": "kling/v2-5-turbo-text-to-video-pro", "input": {"prompt", "duration", "aspect_ratio"}}` por shot, poll `GET /api/v1/jobs/recordInfo?taskId=`, download + `concat_ffmpeg` importado de `providers.agnes`); `Fal.gerar` (fal queue: `POST https://queue.fal.run/<api_path>` header `Authorization: Key <FAL_KEY>`, poll `status_url`/`response_url` da resposta). **Testes 100% mock — decisão 3: o usuário testa esses adapters contra API real depois, junto.** Cabeçalho de ambos os arquivos leva o comentário `# NÃO testado contra API real nesta rodada (2026-08-20) — só contrato/mock.`

- [ ] **Step 1: Escrever o teste que falha:**
  ```python
  # tests/test_kling_fal.py — contrato apenas; NUNCA chamar rede real
  import json
  from pathlib import Path
  import providers.kling as kling_mod
  import providers.fal as fal_mod

  RAIZ = Path(__file__).resolve().parents[1]
  DECL_K = json.loads((RAIZ / "providers/kling.models.json").read_text())
  DECL_F = json.loads((RAIZ / "providers/fal.models.json").read_text())
  DECUP = [{"n": 1, "secao": "i", "duracao_s": 5, "camera": "c", "descricao": "d",
            "prompt": "orbit shot, 5s"}]

  def test_kling_custo_por_segundo():
      assert kling_mod.criar(DECL_K).estimar_custo(
          "kling-2.5", {"duracao_shot_s": 10}) == 0.56

  def test_kling_contrato_createtask(tmp_path, monkeypatch):
      def fake_http(url, metodo="GET", corpo=None, headers=None, **kw):
          if "createTask" in url:
              assert corpo["model"] == "kling/v2-5-turbo-text-to-video-pro"
              assert corpo["input"]["prompt"] == "orbit shot, 5s"
              return {"data": {"taskId": "K1"}}
          return {"data": {"state": "success",
                           "resultJson": json.dumps({"resultUrls": ["http://x/s.mp4"]})}}
      monkeypatch.setattr(kling_mod, "http_json", fake_http)
      monkeypatch.setattr(kling_mod, "baixar",
          lambda url, destino, **kw: (destino.write_bytes(b"v"), destino)[-1])
      monkeypatch.setattr(kling_mod, "ler_env_chave", lambda n: "k")
      monkeypatch.setattr(kling_mod, "concat_ffmpeg",
          lambda shots, alvo: (alvo.write_bytes(b"f"), alvo)[-1])
      monkeypatch.setattr(kling_mod.time, "sleep", lambda s: None)
      r = kling_mod.criar(DECL_K).gerar("kling-2.5",
          {"resolucao": "720p", "decupagem": DECUP}, tmp_path)
      assert r.arquivo.name == "clipe.mp4" and r.custo_real == 0.28

  def test_fal_contrato_queue(tmp_path, monkeypatch):
      def fake_http(url, metodo="GET", corpo=None, headers=None, **kw):
          if metodo == "POST":
              assert "queue.fal.run" in url and headers["Authorization"].startswith("Key ")
              return {"status_url": "http://q/st", "response_url": "http://q/resp"}
          if url == "http://q/st": return {"status": "COMPLETED"}
          return {"video": {"url": "http://x/s.mp4"}}
      monkeypatch.setattr(fal_mod, "http_json", fake_http)
      monkeypatch.setattr(fal_mod, "baixar",
          lambda url, destino, **kw: (destino.write_bytes(b"v"), destino)[-1])
      monkeypatch.setattr(fal_mod, "ler_env_chave", lambda n: "k")
      monkeypatch.setattr(fal_mod, "concat_ffmpeg",
          lambda shots, alvo: (alvo.write_bytes(b"f"), alvo)[-1])
      monkeypatch.setattr(fal_mod.time, "sleep", lambda s: None)
      r = fal_mod.criar(DECL_F).gerar("kling-video-v2.5-turbo-pro",
          {"resolucao": "720p", "decupagem": DECUP}, tmp_path)
      assert r.arquivo.name == "clipe.mp4"
  ```
- [ ] **Step 2: Rodar e ver falhar:** `python3 -m pytest tests/test_kling_fal.py -x -q`
- [ ] **Step 3: Implementação mínima:**
  ```python
  # providers/kling.py — substituir gerar() do stub
  # NÃO testado contra API real nesta rodada (2026-08-20) — só contrato/mock.
  import json, time
  from providers.base import (Provider, Resultado, ProviderError,
                              ler_env_chave, motivo_indisponivel, http_json, baixar, gravar_raw)
  from providers.agnes import concat_ffmpeg

  KIE_BASE = "https://api.kie.ai/api/v1"

  def gerar(self, modelo, params, workdir):
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
          gravar_raw(workdir, f"kling-shot-{shot['n']:02d}", {"request": corpo, "response": resp})
          while True:
              if time.time() - inicio > 15 * 60:
                  raise ProviderError(f"kling: timeout de polling (15 min) taskId={task}")
              r = http_json(f"{KIE_BASE}/jobs/recordInfo?taskId={task}", headers=h)
              d = r.get("data") or {}
              if d.get("state") == "success":
                  urls = json.loads(d.get("resultJson") or "{}").get("resultUrls") or []
                  if not urls:
                      raise ProviderError(f"kling: success sem resultUrls taskId={task}")
                  shots_arq.append(baixar(urls[0], workdir / "raw" / f"shot-{shot['n']:02d}.mp4"))
                  break
              if d.get("state") in ("fail", "failed", "error"):
                  raise ProviderError(f"kling: shot {shot['n']} falhou: {d.get('failMsg', d.get('state'))}")
              time.sleep(10)
          custo += self.estimar_custo(modelo, {"duracao_shot_s": shot["duracao_s"]})
      alvo = concat_ffmpeg(shots_arq, workdir / "clipe.mp4")
      return Resultado(alvo, round(custo, 4), {"shots": len(shots_arq)})
  ```
  ```python
  # providers/fal.py — substituir gerar() do stub
  # NÃO testado contra API real nesta rodada (2026-08-20) — só contrato/mock.
  import time
  from providers.base import (Provider, Resultado, ProviderError,
                              ler_env_chave, motivo_indisponivel, http_json, baixar, gravar_raw)
  from providers.agnes import concat_ffmpeg

  def gerar(self, modelo, params, workdir):
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
          gravar_raw(workdir, f"fal-shot-{shot['n']:02d}", {"request": corpo, "response": resp})
          while True:
              if time.time() - inicio > 15 * 60:
                  raise ProviderError(f"fal: timeout de polling (15 min) no shot {shot['n']}")
              st = http_json(st_url, headers=h)
              if st.get("status") == "COMPLETED":
                  r = http_json(resp_url, headers=h)
                  url = (r.get("video") or {}).get("url")
                  if not url:
                      raise ProviderError(f"fal: resposta sem video.url: {str(r)[:300]}")
                  shots_arq.append(baixar(url, workdir / "raw" / f"shot-{shot['n']:02d}.mp4"))
                  break
              if st.get("status") in ("FAILED", "ERROR"):
                  raise ProviderError(f"fal: shot {shot['n']} falhou: {st.get('error', st.get('status'))}")
              time.sleep(10)
          custo += self.estimar_custo(modelo, {"duracao_shot_s": shot["duracao_s"]})
      alvo = concat_ffmpeg(shots_arq, workdir / "clipe.mp4")
      return Resultado(alvo, round(custo, 4), {"shots": len(shots_arq)})
  ```
  `estimar_custo` de vídeo em ambos (já no stub da T6): `base_usd * duracao_shot_s` — o executor injeta a soma da decupagem quando `custo.por == "segundo"`.
- [ ] **Step 4: Rodar e ver passar:** `python3 -m pytest tests/ -x -q`
- [ ] **Step 5: Commit:** `git add -A && git commit -m "kling+fal: adapters de clipe por contrato (mock-only nesta rodada, teste real fica pro usuário)"`

---

### Task 13: `tudo --teto` + `src/entrega.py` (PACOTE.md + Telegram opt-in)

**Files:** Create `src/entrega.py`, `tests/test_entrega.py`, `tests/test_tudo.py`; Modify `src/main.py` (comando `tudo`), `src/executor.py` (remover o try/except ImportError da entrega)
**Interfaces:** Consumes: T7 (`gerar_plano`), T8 (`aprovar_parte`), T9 (`faz`), T3/T4. Produces:
- `src/entrega.py`: `gerar_pacote(outdir: Path, slug: str) -> Path` — escreve `PACOTE.md` (título, solicitação, tabela parte/estado/artefato/custo, o que falta se parcial, caminho da pasta); `enviar_telegram(workdir: Path, estado: dict, plano: dict, http=None) -> None` — só age se `estado["telegram"]` for True E `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID` via `ler_env_chave`; envia faixa (sendAudio), capa (sendPhoto), clipe (sendVideo) via `https://api.telegram.org/bot<token>/...` multipart (urllib); ausência de token = aviso, nunca erro; `entregar(outdir: Path, slug: str) -> Path` = pacote + telegram-se-ligado + `estado["fase"]="entregue"` quando as 3 prontas + index.
- `src/main.py::cmd_tudo(args) -> int`: `gerar_plano` → auto-`aprovar_parte` nas 3 → grava `teto_usd` no estado (se `--teto`) → `faz(..., partes=None, sim=<--sim>, telegram=<--telegram>)` → propaga exit do faz.

- [ ] **Step 1: Escrever o teste que falha:**
  ```python
  # tests/test_entrega.py
  import json
  from src.planner import gerar_plano
  from src.estado import carregar_estado, salvar_estado, transicao
  from src.entrega import gerar_pacote, entregar, enviar_telegram

  def _preparar(outdir, plano_ok, prontas=("musica", "capa", "clipe")):
      gerar_plano("x", "teste-rock", {}, outdir, chamar_llm=lambda p: json.dumps(plano_ok))
      w = outdir / "teste-rock"
      e = carregar_estado(w)
      art = {"musica": "faixa.mp3", "capa": "capa.png", "clipe": "clipe.mp4"}
      for p in prontas:
          transicao(e, p, "ok"); transicao(e, p, "faz")
          (w / art[p]).write_bytes(b"x")
          transicao(e, p, "pronto", artefato=art[p], custo_real=0.05)
      salvar_estado(w, e)
      return w

  def test_pacote_completo(outdir, plano_ok):
      w = _preparar(outdir, plano_ok)
      pac = gerar_pacote(outdir, "teste-rock")
      md = pac.read_text(encoding="utf-8")
      assert "faixa.mp3" in md and "capa.png" in md and "clipe.mp4" in md

  def test_pacote_parcial_lista_o_que_falta(outdir, plano_ok):
      _preparar(outdir, plano_ok, prontas=("musica",))
      md = gerar_pacote(outdir, "teste-rock").read_text(encoding="utf-8")
      assert "falta" in md.lower() and "clipe" in md.lower()

  def test_entregar_marca_fase_entregue(outdir, plano_ok):
      _preparar(outdir, plano_ok)
      entregar(outdir, "teste-rock")
      assert carregar_estado(outdir / "teste-rock")["fase"] == "entregue"

  def test_telegram_desligado_nao_envia(outdir, plano_ok, monkeypatch):
      w = _preparar(outdir, plano_ok)
      chamadas = []
      import src.entrega as ent
      monkeypatch.setattr(ent, "_post_multipart", lambda *a, **k: chamadas.append(a))
      e = carregar_estado(w)          # telegram False por default (decisão 4)
      plano = json.loads((w / "plano.json").read_text())
      enviar_telegram(w, e, plano)
      assert chamadas == []
      e["telegram"] = True
      monkeypatch.setattr(ent, "ler_env_chave",
          lambda n: "tok" if "TOKEN" in n[0] else "123")
      enviar_telegram(w, e, plano)
      assert len(chamadas) == 3       # audio, foto, vídeo
  ```
  ```python
  # tests/test_tudo.py
  import json, sys
  from src.main import COMANDOS
  from src.estado import carregar_estado

  def test_tudo_respeita_teto(outdir, plano_ok, monkeypatch):
      import src.planner as pl
      monkeypatch.setattr(pl, "chamar_fable", lambda prompt: json.dumps(plano_ok))
      class ProvCaro:
          nome = "kie"
          def disponivel(self): return True, ""
          def estimar_custo(self, m, p): return 5.0
          def gerar(self, m, p, w): raise AssertionError("não deveria gerar")
      import src.executor as ex
      monkeypatch.setattr(ex, "carregar_registry", lambda: {
          m: {"provider": ProvCaro(), "modelo": {"id": m.split(":")[1], "params": {},
              "custo": {"base_usd": 5.0, "por": "geracao"}}}
          for m in ("kie:suno-v4.5", "agnes:agnes-image-2.1-flash", "agnes:agnes-video-v2.0")})
      rc = COMANDOS["tudo"](["rock de virada", "--teto", "1", "--sim"])
      assert rc == 3
      slug = json.loads((outdir / "index.jsonl").read_text().splitlines()[0])["slug"]
      e = carregar_estado(outdir / slug)
      assert all(p["estado"] == "aprovado" for p in e["partes"].values())
  ```
- [ ] **Step 2: Rodar e ver falhar:** `python3 -m pytest tests/test_entrega.py tests/test_tudo.py -x -q`
- [ ] **Step 3: Implementação mínima:** `gerar_pacote` monta o markdown da tabela lendo plano+estado (linha "falta: <partes>" quando parcial); `entregar` chama pacote + telegram-se-ligado, grava `fase="entregue"` quando as 3 prontas e regrava o index. Núcleo do multipart e do `tudo`:
  ```python
  # src/entrega.py — envio Telegram (multipart manual, stdlib)
  import json, uuid, urllib.request
  from pathlib import Path
  from providers.base import ler_env_chave

  def _post_multipart(url: str, campos: dict, arquivo_campo: str, arquivo: Path) -> dict:
      b = uuid.uuid4().hex
      corpo = b""
      for k, v in campos.items():
          corpo += (f"--{b}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n").encode()
      corpo += (f"--{b}\r\nContent-Disposition: form-data; name=\"{arquivo_campo}\"; "
                f"filename=\"{arquivo.name}\"\r\nContent-Type: application/octet-stream\r\n\r\n").encode()
      corpo += arquivo.read_bytes() + f"\r\n--{b}--\r\n".encode()
      req = urllib.request.Request(url, data=corpo,
          headers={"Content-Type": f"multipart/form-data; boundary={b}"}, method="POST")
      with urllib.request.urlopen(req, timeout=300) as r:
          return json.loads(r.read().decode())

  def enviar_telegram(workdir: Path, estado: dict, plano: dict, http=None) -> None:
      if not estado.get("telegram"):
          return                                   # decisão 4: desligado por default
      token = ler_env_chave(["TELEGRAM_BOT_TOKEN"])
      chat = ler_env_chave(["TELEGRAM_CHAT_ID", "ALLOWED_CHAT_ID"])
      if not (token and chat):
          print("telegram: token/chat_id não encontrados nos .env autorizados — pulando envio")
          return
      base = f"https://api.telegram.org/bot{token}"
      envios = [("faixa.mp3", "sendAudio", "audio"), ("capa.png", "sendPhoto", "photo"),
                ("clipe.mp4", "sendVideo", "video")]
      for nome, metodo, campo in envios:
          arq = workdir / nome
          if arq.exists():
              _post_multipart(f"{base}/{metodo}",
                              {"chat_id": chat, "caption": plano["titulo"]}, campo, arq)
  ```
  ```python
  # src/main.py — cmd_tudo (reusa planner/executor, nada duplicado)
  def _cmd_tudo(args):
      import src.planner as pl
      from src.executor import faz
      from src.estado import carregar_estado, salvar_estado
      if not args: print("uso: tudo \"<solicitação>\" [--teto N] ...", file=sys.stderr); return 1
      solicitacao, resto = args[0], args[1:]
      teto = sim = telegram = None
      opts = {}
      i = 0
      while i < len(resto):
          a = resto[i]
          if a == "--teto": teto = float(resto[i + 1]); i += 2
          elif a == "--sim": sim = True; i += 1
          elif a == "--telegram": telegram = True; i += 1
          elif a == "--estilo": opts["estilo"] = resto[i + 1]; i += 2
          elif a == "--letra": opts["letra"] = resto[i + 1]; i += 2
          elif a == "--letra-final": opts["letra_final"] = True; i += 1
          elif a == "--pesquisa": opts["pesquisa"] = True; i += 1
          else: print(f"flag desconhecida: {a}", file=sys.stderr); return 1
      if opts.get("pesquisa"):
          from src.pesquisa import pesquisar   # Task 14; até lá o parse aceita e avisa
      plano = pl.gerar_plano(solicitacao, None, opts, out_dir())
      slug = plano["slug"]
      for parte in ("musica", "capa", "clipe"):
          pl.aprovar_parte(out_dir(), slug, parte)
      if teto is not None:
          w = out_dir() / slug
          e = carregar_estado(w); e["teto_usd"] = teto; salvar_estado(w, e)
      return faz(out_dir(), slug, None, sim=bool(sim), telegram=bool(telegram))

  COMANDOS["tudo"] = _cmd_tudo
  ```
  Remover o `try/except ImportError` do executor.
- [ ] **Step 4: Rodar e ver passar:** `python3 -m pytest tests/ -x -q`
- [ ] **Step 5: Commit:** `git add -A && git commit -m "tudo+entrega: PACOTE.md (completo/parcial), teto no tudo, telegram opt-in --telegram"`

---

### Task 14: `src/pesquisa.py` + SKILL.md + .env.example + README

**Files:** Create `src/pesquisa.py`, `SKILL.md`, `.env.example`, `README.md`, `tests/test_pesquisa.py`; Modify `src/planner.py::cmd_plano` (ligar `--pesquisa` de verdade)
**Interfaces:** Consumes: `chamar_fable` (T7). Produces: `pesquisar(solicitacao: str, workdir: Path, chamar_llm=chamar_fable) -> Path` — usa o próprio `claude -p` com WebSearch habilitado (`claude -p "<pedido de pesquisa>" --allowedTools WebSearch`) para produzir um resumo de referências (artistas, sonoridades, tendências) e grava `pesquisa.md`; o `cmd_plano` com `--pesquisa` roda isso ANTES e injeta o texto em `opts["pesquisa_md"]`. Default DESLIGADO (decisão 5).

- [ ] **Step 1: Escrever o teste que falha:**
  ```python
  # tests/test_pesquisa.py
  from src.pesquisa import pesquisar

  def test_pesquisa_grava_md(tmp_path):
      p = pesquisar("rock feminino de virada", tmp_path,
                    chamar_llm=lambda prompt: "## Referências\n- Paramore\n")
      assert p == tmp_path / "pesquisa.md"
      assert "Paramore" in p.read_text(encoding="utf-8")

  def test_plano_sem_pesquisa_nao_cria_md(outdir, plano_ok, monkeypatch):
      import json
      import src.planner as pl
      pl.gerar_plano("x", "s-sem", {}, outdir, chamar_llm=lambda p: json.dumps(plano_ok))
      assert not (outdir / "s-sem" / "pesquisa.md").exists()
  ```
- [ ] **Step 2: Rodar e ver falhar:** `python3 -m pytest tests/test_pesquisa.py -x -q`
- [ ] **Step 3: Implementação mínima:** `pesquisa.py` (10 linhas: prompt de pesquisa + gravar md); `.env.example` documentando `KIE_API_KEY` (música Suno — mora em `~/projetos/wifi/.env`), `AGNES_API_KEY` (capa/clipe default — `~/projetos/openpcbotv2/.env`), `FAL_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, com o aviso "valores reais são lidos EM RUNTIME dos .env autorizados; NUNCA copiar valores pra este repo"; `SKILL.md` com os 10 comandos, fases, exemplos e o mapa de saída; `README.md` com quickstart + defaults (agnes grátis, kie pago).
- [ ] **Step 4: Rodar e ver passar:** `python3 -m pytest tests/ -x -q`
- [ ] **Step 5: Commit:** `git add -A && git commit -m "pesquisa opt-in (--pesquisa) + SKILL.md + .env.example + README"`

---

### Task 15: Semear `data/estilos.json` com as análises Gemini REAIS

**Files:** Create `data/estilos.json`; Modify `tests/test_dados.py` (adicionar teste do arquivo real)
**Interfaces:** Consumes: schema §8.3. Fontes lidas de verdade: `/home/nmaldaner/projetos/output/musical/analises/*.md` (6 análises) + acervo `/home/nmaldaner/projetos/output/musical/musicas/` (28 mp3 + 1 wav). **Dados reais, não inventados.** As 3 análises do reel do Facebook são passes sobre a MESMA faixa — a v2 corrige o BPM (103, não 125/118... a 118/F Major é uma segunda leitura utilizável como receita própria); não semear como 3 estilos idênticos conflitantes.

- [ ] **Step 1: Escrever o teste que falha:**
  ```python
  # acrescentar em tests/test_dados.py
  def test_estilos_reais_semeados():
      d = json.loads((RAIZ / "data/estilos.json").read_text(encoding="utf-8"))
      ids = {e["id"] for e in d["estilos"]}
      assert {"uplifting-ambient-electronic", "corporate-tech-electro-pop",
              "uplifting-progressive-trance", "anthem-pop-rock",
              "female-anthem-rock"} <= ids
      ea = next(e for e in d["estilos"] if e["id"] == "uplifting-ambient-electronic")
      assert ea["bpm"] == 103 and ea["tom"] == "C maior"
      assert len(ea["prompt_suno_curto"]) <= 260
      assert len(ea["prompt_suno_longo"]) <= 1000
      tr = next(e for e in d["estilos"] if e["id"] == "uplifting-progressive-trance")
      assert tr["bpm"] == 132 and tr["voz"]["presenca"] == "instrumental"
      ap = next(e for e in d["estilos"] if e["id"] == "anthem-pop-rock")
      assert ap["bpm"] is None      # a análise de voz não mediu BPM — não inventar
      for e in d["estilos"]:
          assert e["fonte"]
  ```
- [ ] **Step 2: Rodar e ver falhar:** `python3 -m pytest tests/test_dados.py -x -q`
- [ ] **Step 3: Implementação mínima** — escrever `data/estilos.json` com estas 5 entradas (dados extraídos das análises reais):
  1. **`uplifting-ambient-electronic`** — bpm **103**, tom **C maior**, gênero `["uplifting ambient electronic", "modern corporate instrumental", "chill tech"]`, mood `["inspirador", "otimista", "tecnológico", "etéreo"]`, instrumentação `["minimalist electronic drums", "clean warm synth bass", "wide atmospheric pads", "bright synth lead"]`, voz `{"presenca": "vocal chops", "tipos": [{"genero": "feminina", "registro": "agudo", "entrega": "ooh/aah etéreo com reverb e pitch-shift"}, {"genero": "masculina", "registro": "médio-grave", "entrega": "chops rítmicos filtrados, quase percussão vocal"}]}`, produção `"mix limpo, sidechain sutil, top end arejado, pads em estéreo largo"`, `prompt_suno_curto` e `prompt_suno_longo` **verbatim** dos campos "Versão Curta (200 chars)" e "Versão Longa (1000 chars)" de `analise-vozes-musica-fbvideo-gemini-v2.md`, referências `["reel-fb-vocal.mp3", "reel-fb-instrumental.mp3"]`, fonte `"output/musical/analises/analise-vozes-musica-fbvideo-gemini-v2.md (corrige o BPM de analise-musica-voz-fbvideo-gemini.md)"`, tags `["reel", "tech", "corporativo", "motivacional"]`.
  2. **`corporate-tech-electro-pop`** — bpm **118**, tom **F maior** (progressão Fmaj7-Bbmaj7-Cmaj7-Dm7), gênero `["corporate tech electro pop", "ambient house", "modern synthwave"]`, instrumentação `["warm synth pad", "plucked bell-like arpeggiator (hook principal)", "soft pulsating synth bass", "four-on-the-floor kick", "reverbed clap", "closed hi-hats + shakers", "synth stabs"]`, voz `{"presenca": "instrumental", "tipos": []}`, estrutura `["intro pad+arpejo", "main theme com bateria e bass", "variação sutil", "fade out"]`, produção `"-14 a -16 LUFS, estéreo amplo nos pads, sem drops dramáticos"`, `prompt_suno_longo` = o prompt inteiro da seção 5 de `analise-musica-fbvideo-gemini.md` (começa em "Corporate Tech Electro Pop, uplifting and positive, 118 BPM, F Major..."), `prompt_suno_curto` = `"Corporate Tech Electro Pop, uplifting, 118 BPM, F Major, plucked synth arpeggio hook, warm pads, soft four-on-the-floor drums, pulsating bass, clean bright modern mix."`, fonte `"output/musical/analises/analise-musica-fbvideo-gemini.md"`, tags `["corporativo", "tech", "instrumental", "arpejo"]`.
  3. **`uplifting-progressive-trance`** — bpm **132**, tom null, gênero `["uplifting progressive trance", "tech house", "melodic techno"]`, mood `["alta energia", "futurista", "otimista", "propulsor"]`, instrumentação `["four-on-the-floor kick", "open/closed hi-hats em semicolcheias", "electronic clap nos contratempos", "deep continuous synth bass", "bright arpeggiated synth lead", "ethereal sustained pads"]`, voz `{"presenca": "instrumental", "tipos": []}`, produção `"reverb nos synths/pads, delay no arpeggio, sidechain pumping sutil"`, `prompt_suno_curto`/`prompt_suno_longo` = os prompts "Prompt Suno" e "Prompt Upload&Cover" **verbatim** de `analise-musica-tiktok-gemini.md`, referências `["tiktok-audio.mp3", "Paul van Dyk", "Eric Prydz", "Deadmau5"]`, fonte `"output/musical/analises/analise-musica-tiktok-gemini.md"`, tags `["trance", "edm", "instrumental", "energia"]`.
  4. **`anthem-pop-rock`** — bpm **null**, tom null (a análise mediu só as vozes), gênero `["anthem pop rock"]`, voz `{"presenca": "lead", "tipos": [{"genero": "masculina", "registro": "tenor G3-B4, belting em peito→misto", "entrega": "brilhante, metálico, levemente raspy, vibrato médio controlado"}, {"genero": "feminina", "registro": "mezzo-soprano C4-G5, mista→cabeça", "entrega": "límpida, etérea, harmonias tight de hino nos refrões"}]}`, mood `["hino", "contagiante", "potente"]`, referências `["Counting Stars (OneRepublic) — faixa identificada na análise"]`, `prompt_suno_curto` = `"Anthem pop rock, energetic male tenor lead with belting and light rasp, ethereal female mezzo backing harmonies on choruses, driving hymn-like energy."`, `prompt_suno_longo` = versão expandida com os dados de registro/extensão/técnica acima (escrever em EN), fonte `"output/musical/analises/analise-voz-profunda-gemini.md"`, tags `["hino", "rock", "dueto"]`.
  5. **`female-anthem-rock`** — do acervo Suno (sem análise Gemini: bpm null, tom null — **não inventar números**), voz lead feminina belting, referências `["fire-rock-fem-a.mp3", "fire-rock-fem-b.mp3", "shatter-gates-a.mp3", "born-for-this-a.mp3"]`, fonte `"acervo output/musical/musicas/ (faixas Suno geradas, variantes A/B)"`, prompts curto/longo como na fixture da Task 5, tags `["rock", "feminino", "virada", "empoderamento"]`.
  Mais entradas de acervo opcionais (`throne-rock-masc`, `tears`, `wewerehere`, `suno-digital-sky`, `suno-horizons` chops, `suno-builders`) podem ser adicionadas no mesmo padrão referências-sem-números; o teste só exige as 5 acima.
- [ ] **Step 4: Rodar e ver passar:** `python3 -m pytest tests/ -x -q`
- [ ] **Step 5: Commit:** `git add -A && git commit -m "data: estilos.json semeado das 6 análises Gemini reais + acervo Suno (28 faixas)"`

---

### Task 16: Guia GitHub Pages (`guia/index.html`)

**Files:** Create `guia/index.html` (+ `guia/assets/` se a skill gerar)
**Interfaces:** Consumes: README/SKILL.md como fonte de conteúdo. Produces: página única landing+guia, self-contained, padrão INEMA dark âmbar, como `~/projetos/analisevideo/guia/index.html`.

- [ ] **Step 1:** Invocar a skill `projetos-landing-guia` para o projeto `musicavideo` (ela gera o `guia/index.html` no padrão; conteúdo: o que é, fases plano→ok→faz, comandos, custo/portões, provedores com Agnes grátis como default, exemplos).
- [ ] **Step 2: Verificar:** `python3 -c "html=open('guia/index.html').read(); assert 'musicavideo' in html and len(html) > 5000"` e abrir localmente (`xdg-open guia/index.html`) conferindo dark âmbar + seções de comandos.
- [ ] **Step 3: Commit:** `git add guia && git commit -m "guia: landing+guia GitHub Pages (INEMA dark âmbar)"`

---

### Task 17: Repo remoto + push (conta inematds)

**Files:** — (operação git/gh)
**Interfaces:** Consumes: repo local com todos os commits. Produces: `github.com/inematds/musicavideo` com branch main publicada; GitHub Pages da raiz (guia acessível em `https://inematds.github.io/musicavideo/guia/`).

- [ ] **Step 1: Conferir autoria:** `git config user.email` deve ser `inematds@gmail.com`; `git log --format='%an %ae %cn %ce' | sort -u` só pode mostrar inematds.
- [ ] **Step 2: Criar remoto e push:**
  ```bash
  cd /home/nmaldaner/projetos/musicavideo
  gh repo create inematds/musicavideo --public --source=. --remote=origin
  git push -u origin main
  ```
  (Se o push HTTPS falhar por escopo workflow — não é o caso, não há `.github/workflows/` — o contorno padrão é push via SSH; NUNCA `gh auth refresh -s workflow`.)
- [ ] **Step 3: Habilitar Pages (branch main, raiz):** `gh api -X POST repos/inematds/musicavideo/pages -f 'source[branch]=main' -f 'source[path]=/' || gh api -X PUT repos/inematds/musicavideo/pages -f 'source[branch]=main' -f 'source[path]=/'`
- [ ] **Step 4: Verificar:** `git ls-remote origin main` responde; após alguns minutos `curl -sI https://inematds.github.io/musicavideo/guia/ | head -1` retorna 200 (se demorar, registrar e seguir — Pages propaga sozinho).

---

### Task 18: Teste de ponta a ponta REAL (Agnes grátis + Kie autorizado 1x)

**Files:** — (execução real; saída em `~/projetos/output/musicavideo/<slug>/`)
**Interfaces:** Consumes: o CLI completo. **Autorização: UMA geração no kie (US$ ~0,08); Agnes é US$ 0.** Solicitação combinada: *"uma música de virada, rock feminino, sobre quem constrói em silêncio e agora cobra"*.

- [ ] **Step 1: Plano (zero crédito):**
  ```bash
  cd /home/nmaldaner/projetos/musicavideo
  ./musicavideo.sh plano "uma música de virada, rock feminino, sobre quem constrói em silêncio e agora cobra" virada-rock-feminino
  ./musicavideo.sh ver virada-rock-feminino
  ```
  Conferir no PLANO.md: motor musica `kie:suno-v4.5`, capa `agnes:agnes-image-2.1-flash`, clipe `agnes:agnes-video-v2.0`; prompts de provedor em EN; letra em PT coerente com "constrói em silêncio e agora cobra"; decupagem curta (≤6 shots — se o Fable gerar mais, `ajusta clipe "no máximo 6 shots"` antes de aprovar, pra corrida no rate limit do Agnes não se arrastar); estilo_ref apontando pra `female-anthem-rock`.
- [ ] **Step 2: Aprovar e executar (gasta: só a música):**
  ```bash
  ./musicavideo.sh ok virada-rock-feminino musica
  ./musicavideo.sh ok virada-rock-feminino capa
  ./musicavideo.sh ok virada-rock-feminino clipe
  ./musicavideo.sh faz virada-rock-feminino    # confirmar o custo mostrado (~US$0,08 total)
  ```
- [ ] **Step 3: Verificar critérios (spec §11):**
  ```bash
  S=~/projetos/output/musicavideo/virada-rock-feminino
  ls -la "$S"/faixa.mp3 "$S"/capa.png "$S"/clipe.mp4 "$S"/PACOTE.md
  ffprobe -v quiet -show_format "$S"/clipe.mp4 | grep duration
  ./musicavideo.sh custo virada-rock-feminino
  ./musicavideo.sh busca "rock"
  grep -RiE "sk-|Bearer [A-Za-z0-9]" "$S" && echo "VAZOU CHAVE" || echo "sem chave em saída"
  ```
  Aceite: os 4 arquivos existem; `custo` mostra estimado vs gasto (musica ~0.08, capa/clipe 0.00); `busca` acha o slug; nenhum valor de chave em nenhum arquivo de saída; ouvir a faixa e ver capa/clipe (relatar ao usuário o que saiu torto — deriva de identidade do Agnes é limitação conhecida, não bug).
- [ ] **Step 4: Commit final de eventual ajuste + push:** `git add -A && git commit -m "e2e: teste real virada-rock-feminino (agnes capa/clipe + kie musica)" --allow-empty && git push`

---

## Self-review (feito na escrita deste plano)

- **Cobertura do spec:** §2 forma/layout → T1, T14, T16; §3 fases → T7 (1), T9 (2), T13 (3), T14 (0); §4 entrada/letra → T7-T8; §5 comandos+exit codes+`--motor`+`--forca` → T1, T4, T7-T9, T13; §6 máquina+interrompido+`--refaz` → T3, T8; §7 providers/indisponível-com-motivo → T6, T9-T12; §8 esquemas → T2, T4, T5, T15; §9 Fable planeja (com autocrítica no prompt e retry de validação) / executor não recria criativo → T7, T9; §10 erros/custo/teto/timeout 15min/chaves → T6, T9, T11, T13; §11 critérios → T18; §13 fatias → ordem das tasks (estilos.json movido pro fim por decisão explícita do usuário, com fixture na T5 pra não travar o planner).
- **Placeholders:** nenhum TBD/TODO; todo teste tem código; kling/fal têm contrato completo e a restrição "mock-only" é decisão do usuário, não pendência.
- **Consistência de assinaturas:** `Resultado(arquivo, custo_real, meta)` (T6) é o que kie/agnes/inemaimg/kling/fal retornam (T9-T12) e o executor consome (T9); `transicao(estado, parte, evento, **kw)` (T3) usada em T8/T9/T13; `gerar_plano(solicitacao, slug, opts, outdir, chamar_llm)` (T7) usada em T8/T13/T18; `estimar_partes(plano, reg, partes)` (T9) usada em T9/T13; `concat_ffmpeg(shots, alvo)` (T11) reusada em T12.

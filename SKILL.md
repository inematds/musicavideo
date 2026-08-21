---
name: musicavideo
description: Solicitação em texto livre vira MÚSICA + CAPA + CLIPE, em fases, com portão de aprovação por parte (ou sem portão nenhum). Planeja com o Fable (grátis), executa com provedores plugáveis (Agnes de graça na capa e no clipe, Kie/Suno pago na música), mostra o custo antes de gastar. Use quando o usuário pedir "faz uma música sobre X", "quero uma música com capa e clipe", "planeja uma música", ou mandar uma letra pra virar faixa.
---

# musicavideo — da solicitação ao pacote (música + capa + clipe)

`bash /home/nmaldaner/projetos/musicavideo/musicavideo.sh <subcomando>`

**Princípio:** planejar é barato, executar é caro. A fase de plano não gasta
nada e é onde a qualidade se decide. Só o `faz` gasta — e sempre mostra o custo
estimado antes.

## Comandos

```bash
S=/home/nmaldaner/projetos/musicavideo/musicavideo.sh

# COM PORTÃO (o caminho normal)
bash $S plano "<solicitação>" [slug] [--estilo X] [--letra arq [--letra-final]] [--pesquisa]
bash $S ver    <slug> [musica|capa|clipe]     # lê o plano
bash $S ajusta <slug> <parte> "<instrução>"   # replaneja só a parte, mostra diff
bash $S ok     <slug> <parte>                 # aprova (abre o portão)
bash $S faz    <slug> [parte] [--sim]         # executa o aprovado (GASTA)
bash $S monta  <slug> [--completo]           # casa o clipe com CADA faixa (grátis)
bash $S aprova <slug> musica --faixa 2       # troca a faixa: reaponta o clipe.mp4

# SEM PORTÃO
bash $S tudo "<solicitação>" [--teto 2] [--sim] [--telegram]

# consulta
bash $S custo <slug>        # estimado vs gasto, por parte
bash $S lista [N]           # últimos slugs
bash $S busca "<termo>"     # acervo (slug, título, solicitação, gênero, tags)
bash $S painel [--porta N] [--lan]   # painel no navegador (:5400): acervo do
                                     # musicavideo + as análises do analisevideo
```

## Fases

| # | fase | gatilho | produz | custo |
|---|---|---|---|---|
| 0 | pesquisa | `--pesquisa` (**opt-in**) | `pesquisa.md` | tempo |
| 1 | plano | `plano` / `tudo` | `plano.json` + `PLANO.md` | **zero** |
| 2 | execução | `faz` (por parte) | `faixa-N.mp3` / `capa.png` / `clipe-N.mp4` | **gasta** |
| 3 | entrega | automática com as 3 prontas | `PACOTE.md` (+ Telegram se `--telegram`) | zero |

Cada parte tem portão próprio e vive sua própria máquina de estados:
`planejado → (ok) → aprovado → (faz) → gerando → pronto | erro`.
`erro` aceita `faz` de novo (retry) ou `ajusta`. `pronto` só volta com
`ajusta --refaz` (o artefato antigo vai pra `raw/` com sufixo `-vN`).

## Entrada

Solicitação em texto livre. Opcionais:
- `--estilo X` — estilo/gênero (livre ou id do `data/estilos.json`)
- `--letra arq` — letra **rascunho**: o planejador termina/ajusta e o `PLANO.md`
  mostra o **diff** do que mudou
- `--letra arq --letra-final` — a letra é **lei**: vai verbatim pro plano e
  nem o `ajusta` pode mexer nela

## Motores (plugáveis, nunca chumbados)

| parte | default | custo | alternativas |
|---|---|---|---|
| música | `kie:suno-v4.5` | ~US$ 0,08 | — |
| capa | `agnes:agnes-image-2.1-flash` | **US$ 0** | `inemaimg:flux2-klein` (local) |
| clipe | `agnes:agnes-video-v2.0` | **US$ 0** | `kling:kling-2.5`, `fal:kling-video-v2.5-turbo-pro` |

Trocar: `--motor clipe=kling:kling-2.5` em `plano`, `ajusta` ou `faz`.
Provedor sem chave aparece **indisponível com o motivo** — nunca stacktrace.
Adicionar provedor = criar `providers/<nome>.py` + `<nome>.models.json`.

## Saída

`~/projetos/output/musicavideo/<slug>/`: `plano.json`, `PLANO.md`, `estado.json`,
`faixa.mp3`, `capa.png`, `clipe.mp4`, `PACOTE.md`, `raw/` (respostas cruas).
Index geral em `~/projetos/output/musicavideo/index.jsonl` — uma linha por slug,
reescrita a cada mudança de estado; é o que `lista` e `busca` leem.

## Fluxo no bot

1. Briefing de 1 linha ("planejando a música, já te mostro").
2. `plano "<solicitação>"` — mandar o `PLANO.md` no Telegram e **esperar o ok**.
3. Ajuste pedido? `ajusta <slug> <parte> "<o que o usuário disse>"` e remostrar.
4. Ok? `ok <slug> <parte>` e então `faz <slug> <parte> --sim`.
5. `faz` é tarefa longa (poll de API): avisar nos checkpoints.
6. No fim, mandar o `PACOTE.md` + os arquivos.

## Detalhes que importam

- **Prompts de provedor são em inglês** (`prompt_estilo`, `prompt_imagem`,
  `prompt_negativo`, `decupagem[].prompt`) — a Agnes bloqueia português. O
  material criativo (conceito, descrição, letra, mood) continua em PT. O
  validador recusa o plano se um prompt de provedor vier com acento.
- **Exit codes:** `0` ok · `1` uso/validação · `2` alguma parte em erro (as
  outras seguiram) · `3` teto estourado.
- `tudo --teto N` para antes de estourar: as partes que couberam ficam prontas,
  o resto continua `aprovado` e retoma com `faz <slug>`.
- Chaves vêm de `~/projetos/openpcbotv2/.env` ou `~/projetos/wifi/.env`, lidas em
  runtime, nunca copiadas nem impressas.
- Interrupção durante `gerando` (crash/ctrl-c) vira `erro: interrompido` no
  próximo comando — é só rodar `faz` de novo.

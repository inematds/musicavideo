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

bash $S pacote <slug>       # gera o PACOTE.md sob demanda (a entrega do fluxo)

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
- `--idioma X` — idioma da letra (default `pt-BR`). Vai para a letra E para o
  prompt do Suno, que são dois lugares e precisam concordar
- `--faixa-pronta <arq>` — a MÚSICA já existe. A faixa é copiada para dentro do
  slug e nasce `pronto` (custo zero), a duração real do arquivo ancora a
  decupagem do clipe, e o planejador é avisado para descrever a música como ela
  é em vez de inventar estrutura e letra. Sobra o trabalho de US$ 0: capa e clipe
- `--bruto` — a solicitação vem com as flags DENTRO dela, num argumento só
  (é como o bot chama; ver "Fluxo no bot")
- `--letra arq` — letra **rascunho**: o planejador termina/ajusta e o `PLANO.md`
  mostra o **diff** do que mudou
- `--letra arq --letra-final` — a letra é **lei**: vai verbatim pro plano e
  nem o `ajusta` pode mexer nela

## Motores (plugáveis, nunca chumbados)

| parte | default | custo | alternativas |
|---|---|---|---|
| música | `kie:suno-v4.5` | ~US$ 0,08 | — |
| capa | `agnes:agnes-image-2.1-flash` | **US$ 0** | `inemaimg:flux2-klein` (local) |
| clipe | `agnes:agnes-video-v2.0` | **US$ 0** | `kling:kling-v2_5`, `fal:kling-v3-turbo` |

Trocar: `--motor clipe=fal:kling-v3-turbo` em `plano`, `ajusta` ou `faz`.

**`kie`, `kling` e `fal` consomem crédito ou dinheiro do dono da conta**, então
trocar para um deles exige `--autorizo-pago` no mesmo comando. É portão, não
aviso: em 2026-08-21, com a Agnes parecendo fora do ar, um `--motor` "óbvio"
queimou 105 créditos antes de alguém perceber. Os defaults do plano não mudam —
a música nasce em `kie:suno-v4.5`, que é sabido e custa ~US$ 0,08.
Provedor sem chave aparece **indisponível com o motivo** — nunca stacktrace.
Adicionar provedor = criar `providers/<nome>.py` + `<nome>.models.json`.

## Saída

`~/projetos/output/musicavideo/<slug>/`: `plano.json`, `PLANO.md`, `estado.json`,
`faixa.mp3`, `capa.png`, `clipe.mp4`, `PACOTE.md`, `raw/` (respostas cruas).
Index geral em `~/projetos/output/musicavideo/index.jsonl` — uma linha por slug,
reescrita a cada mudança de estado; é o que `lista` e `busca` leem.

## Fluxo no bot (inemaccbot) — SEM agente desde 2026-08-21

O `flow.json` deste repo declara o COMANDO de cada fase, e quem executa é o bot
(tarefa `cli.rodar`). Não há agente lendo prompt para digitar linha de comando —
as quatro fases eram assim até 2026-08-21, e as quatro falharam na primeira
execução real (binário inventado, contrato de saída quebrado, render destacado
morto pelo job, portão duplo).

| fase | comando |
|---|---|
| `plano` | `plano {{input}} --bruto` |
| `musica` | `faz {{anterior:slug}} musica --sim --sem-revisao --aprovar` |
| `capa-clipe` | `faz {{anterior:slug}} --sim --sem-revisao --aprovar` (destacado, poll de 60s) |
| `entrega` | `pacote {{anterior:slug}}` |

Três coisas fazem isso funcionar, e todas são deste repo:

- **`--bruto`**: o texto do chat chega INTEIRO num argumento só, e quem
  interpreta as flags (`--estilo`, `--idioma`, `--letra`) é este CLI. O bot não
  conhece o vocabulário do domínio, e aspar tudo é o que impede texto de virar
  comando.
- **O RECIBO em `campo: valor`** nas últimas linhas de `plano`, `faz` e
  `pacote` (`slug:`, `titulo:`, `plano:`, `musica:`, `capa:`, `clipe:`,
  `pacote:`). É o que o portão do bot mostra no chat e o que a fase seguinte lê
  em `{{anterior:slug}}` — o slug é derivado do texto e desambiguado com `-2`, e
  o bot nunca o conhece.
- **`--aprovar` e `--sem-revisao`**: o portão humano é o do BOT, no chat. Sem
  eles a parte fica em `revisao` esperando alguém que está do outro lado, e o
  fluxo trava com a faixa já paga.

O que o portão manda no chat, declarado em `portao.mostrar`: o `PLANO.md`
(inline), a faixa e a capa (arquivo), e o clipe (link publicado — mp4 de música
passa dos 50 MB que o Telegram aceita).

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

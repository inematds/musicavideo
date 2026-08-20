# Como o musicavideo funciona por dentro

Este documento responde cinco perguntas: **quais são as fases**, **onde dá pra
atuar e refazer**, **como a busca funciona**, **como o planejamento decide**, e
**como música e clipe são montados** — e em cima de quê.

---

## 1. As fases, e onde você entra

| # | fase | comando | gasta? | dá pra refazer? |
|---|------|---------|--------|-----------------|
| 0 | pesquisa | `plano ... --pesquisa` | não | sim, replanejando |
| 1 | plano | `plano "<frase>"` | **não** | sim, quantas vezes quiser |
| — | revisão | `ver` / `ajusta` | não | é o lugar de mexer |
| — | portão | `ok <slug> <parte>` | não | destrava a execução |
| 2 | execução | `faz <slug> [parte]` | **sim** (só a música) | sim, com `--refaz` |
| 2.2 | **revisão do artefato** | `revisa` / `aprova` / `reprova` | não | sim, sempre |
| 2.5 | montagem | automática, ou `monta <slug>` | não | sim, sempre |
| 3 | entrega | automática | não | — |

**A fase onde você deve atuar é a 1.** Enquanto nada foi gerado, mexer é grátis
e ilimitado. Depois da fase 2, refazer custa (na música) ou custa tempo (no
clipe: ~3 min por shot).

Cada parte — música, capa, clipe — anda na sua própria máquina de estados:

```
planejado ──ok──▶ aprovado ──faz──▶ gerando ──▶ revisao ──aprova──▶ pronto
    ▲                │                  │           │
    │              ajusta               ▼        reprova
    └──── ajusta ────┘                erro          │
                                        └───────────┴──▶ aprovado (regera)

pronto ──ajusta --refaz──▶ planejado   (o artefato antigo vai pra raw/ com -vN)
```

**Dois portões, não um.** O primeiro aprova o *plano* (`ok`); o segundo aprova o
*artefato gerado* (`aprova`). Nada vira `pronto` sem você olhar — `--sem-revisao`
desliga o segundo, e o `tudo` já roda sem ele.

### O portão de artefato

```bash
musicavideo revisa  <slug> [parte]          # o que está esperando você
musicavideo aprova  <slug> musica --faixa 2 # o Suno gera 2 faixas: escolha
musicavideo reprova <slug> clipe 4,17,23    # descarta só esses shots
musicavideo aprova  <slug> capa
```

- **Música** — as **duas** faixas da geração são baixadas (`faixa-1.mp3`,
  `faixa-2.mp3`) e você escolhe. Reprovar as duas custa nova geração.
- **Clipe** — sai uma **folha de contato** (`revisao/contato-clipe.jpg`): grade
  com um frame de cada shot, numerada. Você reprova pelos números; só esses são
  apagados e regerados no próximo `faz` — o resto é reaproveitado do disco.
- **Capa** — reprovar regenera (custo zero no Agnes).

### A música é o portão-mestre

`faz <slug>` sem dizer a parte gera **só a música** e para. Capa e clipe só
entram depois que a faixa for aprovada — a duração real dela é que ancora o
clipe, e ninguém quer 2 h de vídeo gerado para uma faixa que vai ser rejeitada.
Pedir uma parte explicitamente (`faz <slug> capa`) ignora a ordem: você mandou.

Tudo isso vive no `estado.json` do slug, que é a fonte de verdade. Pode parar
depois do `ok capa` e voltar três dias depois: `faz <slug>` retoma de onde parou.

---

## 2. Como refazer uma música

Depende do estado em que ela está.

**Ainda não gerou** (`planejado` ou `aprovado`) — é só ajustar:

```bash
musicavideo ajusta <slug> musica "mais lenta, voz masculina, refrão mais curto"
musicavideo ok  <slug> musica
musicavideo faz <slug> musica
```

**Já gerou** (`pronto`) — precisa do `--refaz`, que é a trava contra apagar o
que você já pagou:

```bash
musicavideo ajusta <slug> musica "troca o refrão" --refaz
musicavideo ok  <slug> musica
musicavideo faz <slug> musica      # nova geração, ~US$ 0,08
```

A faixa antiga **não se perde**: vai pra `raw/faixa.mp3-v1`.

**Quer a mesma letra com outra interpretação?** Não use `ajusta` — apague só a
faixa e refaça. O Suno nunca gera igual duas vezes.

**Refazer o projeto inteiro:** `plano "<frase>" <slug> --forca`. É **recusado**
se alguma parte estiver `pronto` (protege o custo já gasto) — nesse caso, use
outro slug ou vá de `--refaz` parte por parte.

Duas regras que valem sempre:

- **`ajusta` derruba a aprovação.** Mexeu, tem que dar `ok` de novo.
- **As partes são independentes.** Refazer a música não toca capa nem clipe.

---

## 3. A busca e o acervo

Tudo vive em `~/projetos/output/musicavideo/index.jsonl` — **uma linha por
música**, reescrita a cada mudança de estado (nunca fica defasada).

```bash
musicavideo lista 10        # as 10 últimas
musicavideo busca "rock"    # case-insensitive
```

A busca casa em **slug, título, solicitação original, gênero e tags** (as tags
hoje vêm do `mood` do plano). **Não** procura dentro da letra — limitação
conhecida.

Cada linha guarda: slug, título, data, a frase que você pediu, estilo de
referência, gênero/BPM/tom, os motores usados, o estado das três partes e o
custo gasto.

O detalhe que importa: **esse índice também alimenta o planejador.** Ao
planejar, ele recebe as últimas 5 músicas mais as que casam com palavras da sua
solicitação. O sistema fica mais informado sobre o seu gosto a cada uso.

Se o índice quebrar, `musicavideo reindex` reconstrói a partir das pastas.

---

## 4. Como o planejamento funciona

O Fable recebe um pacote e devolve **um JSON só**, com as três partes decididas
juntas — é isso que faz música, capa e clipe conversarem.

O que entra no pacote:

1. **Sua solicitação**, verbatim
2. **`data/estilos.json`** — estilos medidos das análises do Gemini: BPM, tom,
   instrumentação, caracterização de voz e prompts de Suno prontos (curto e longo)
3. **`data/templates-capa.json`** — 4 composições: tipografia dominante, retrato
   centralizado, paisagem simbólica, minimal abstrato
4. **`data/templates-clipe.json`** — 4 decupagens: performance, narrativo,
   lyric-video, abstrato/loop
5. **Seu acervo** (do `index.jsonl`)
6. **Referências visuais medidas** — as análises do `analisevideo` que casam com a
   música: paleta em hex, look, movimentos de câmera, cortes por minuto, BPM e os
   movimentos notáveis com timecode. Vêm de vídeos reais que você mandou analisar
   (`~/projetos/output/analisevideo/`), e o planejador é instruído a copiar a
   **linguagem** visual, não o conteúdo. Sem banco, o bloco simplesmente não entra.
7. **`pesquisa.md`**, se você usou `--pesquisa`
8. **As regras:** prompts de provedor em inglês, o clipe cobre a música inteira,
   schema fechado

Antes de responder, o planejador faz um passe de autocrítica (coerência
letra ↔ estrutura ↔ decupagem, prompts completos, params válidos).

### O que o código NÃO confia ao modelo

Impõe por cima, sempre: slug, data, solicitação, motores (e o `--motor`), e o
status da letra. Se você mandou `--letra-final`, a letra é copiada byte a byte
e nem o `ajusta` consegue alterá-la.

### Validação, com 1 retry automático

- schema fechado — campo a mais é erro
- prompts de provedor sem acento (a Agnes bloqueia português)
- `params` existentes no `models.json` do motor
- motor existente no registry
- **cobertura do clipe ≥ 90% da duração da música**

Deu erro, o plano volta pro Fable com a lista de erros. Falhou de novo, para e
mostra o motivo — não grava plano inválido.

---

## 5. Como a música é montada

O plano decide **três coisas separadas**, que viram três campos do Suno:

| campo do plano | vai pra | exemplo |
|---|---|---|
| `musica.estilo.prompt_estilo` (EN, ≤1000 chars) | campo **Style** | *"Female anthem rock, 120 BPM, E minor. Powerful female lead, restrained almost spoken in the verses, exploding into belting with grit on the choruses..."* |
| `musica.letra.texto` (PT, com `[Intro]`, `[Refrão]`) | campo **Prompt** | a letra inteira, marcada por seção |
| `musica.params` | flags | duração, instrumental ou não |

O adapter manda `POST /generate` no Kie com `customMode: true`, grava o
`taskId` **antes de qualquer outra coisa** (o dinheiro sai nesse instante) e
entra em polling. Uma geração traz 2 faixas; ele baixa a primeira que tenha
áudio de verdade.

**Em cima de quê:** o `estilo` e a `estrutura` saem do `estilos.json` — não são
invenção livre. A letra é escrita **para** aquela estrutura, e a estrutura guia
a decupagem do clipe.

---

## 6. Como o clipe é montado

Quatro etapas.

**1. Decupagem (no plano).** O Fable pega a `estrutura` da música, a **letra** e
um dos 4 templates, e escreve N shots de 5 s cobrindo a faixa inteira. Cada shot
tem seção, câmera, descrição em português e **prompt próprio em inglês**. Num
clipe de 3 minutos isso dá ~37 shots — com mais peso nos refrões.

**2. Geração (Agnes).** Um POST por shot, throttle de 12 s (limite real de 5
req/min). `num_frames` segue a regra 8n+1, teto 441 (5 s = 121 frames). Shot
barrado pelo filtro de conteúdo é **pulado e listado**; shot já baixado é
**reaproveitado** numa retomada.

**3. Concatenação.** `ffmpeg concat -c copy`, sem reencode — todos os shots saem
1280×704.

**4. Montagem.** Troca o áudio ambiente dos shots pela `faixa.mp3`, com
fade-out. Se o vídeo ficar mais curto que a música, `--completo` repete o vídeo
em loop; o certo é a decupagem cobrir tudo — e a validação agora obriga isso.

**Em cima de quê:** a base é **a letra e a estrutura da música**, não imagem
bonita solta — mais as referências visuais medidas do `analisevideo`, que dão
paleta, movimento de câmera e ritmo de corte que funcionaram em vídeos reais. O shot da virada cai onde entra o primeiro refrão; o último fecha
no outro. A sincronia é declarada no plano — por exemplo: *"1 shot por seção;
virada no primeiro refrão; cortes no beat a 120 BPM"*.

---

## 7. Resumo de uma linha

**Planejar é barato, executar é caro.** Por isso o plano é o produto: ele decide
música, capa e clipe juntos, olhando um banco de estilos medido de material
real — e você aprova parte por parte antes de qualquer centavo sair.

---

## 8. Ideias anotadas (não implementadas)

- **Banco de referências público.** Hoje `data/estilos.json` mora no repo e as
  análises visuais moram só no disco local (`~/projetos/output/analisevideo/`).
  A ideia é publicá-las como repositório versionado ou base de dados consultável,
  para que outras máquinas e outros projetos usem sem reanalisar tudo do zero.
  `src/referencias.py` já isola a leitura num único ponto (`_banco()` /
  `_ler_index()`), então trocar a fonte não toca o planejador. Ao publicar,
  revisar o que vai junto: só a análise derivada, nunca mídia de terceiros.
- **Busca dentro da letra** — hoje `busca` cobre slug, título, solicitação,
  gênero e tags, mas não o texto da letra.
- **Tags próprias no índice** — hoje as tags são o `mood` do plano.

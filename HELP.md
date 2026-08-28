/musicavideo — uma frase vira música + capa + clipe, planejados juntos.

Uso: /musicavideo balada pop sobre recomeço
     /musicavideo <descrição> [--idioma en-US] [--estilo <id>] [--letra <arq>]
     (todos os parâmetros: /musicavideo help campos)

Fases (cada uma para e espera /aprovar, menos a última):
  1. plano    (fila texto)  → PLANO.md no chat · NÃO gasta nada
  2. musica   (fila io)     → a faixa, como arquivo · ÚNICA parte paga (~US$ 0,08)
  3. capa     (fila io)     → a capa, como arquivo · US$ 0 · sai em segundos
  4. clipe    (fila render) → o clipe, como link · US$ 0 · leva de 30 min a horas
  5. entrega  (fila io)     → PACOTE.md

A capa tem portão PRÓPRIO desde 2026-08-22: ela é o frame 0 no feed e sai em
segundos — esperar o clipe para revisá-la era revisar tarde.

Em cada portão o material chega no chat e o fluxo PARA. Você tem duas saídas:
`/aprovar MVD#N` segue, e as palavras da tabela RESPONDER AO PORTÃO corrigem —
o bot lista as da fase junto com o material. Reprovar devolve a fase para a
fila e o portão REABRE com o material novo, quantas vezes for preciso.

Acompanhar: /status MVD#N · /aprovar MVD#N · /refazer MVD#N · /cancelar MVD#N

## CONSULTAS

Perguntas de leitura, direto no chat — não entram na fila e não gastam nada:

| comando | o que responde |
|---|---|
| `/musicavideo lista` | os últimos 10 slugs, com estado de cada parte e custo |
| `/musicavideo busca <termo>` | procura no acervo (slug, título, solicitação, gênero, tags) |
| `/musicavideo estilos` | os estilos disponíveis, por id |
| `/musicavideo custo <slug>` | estimado vs gasto, por parte |
| `/musicavideo curto <slug>` | recorta o Short 9:16 do núcleo da faixa (não gasta) |

## PADROES

Os valores que valem quando você não diz nada:

| o quê | padrão | onde muda |
|---|---|---|
| canal de entrega | **lives10** (`~/projetos/yt-pub-lives10/imports/videos`) | `alvos.unico.canal` no `flow.json` |
| público | `unico` — o fluxo tem UM só | `alvos` no `flow.json` |
| portão | **liga** em `plano`, `musica` e `capa-clipe` | campo `sem-portao` na hora, ou `pausa_apos` no `flow.json` |
| motor da música | `kie:suno-v4.5` (~US$ 0,08, traz 2 faixas) | `--motor musica=...` |
| motor da capa | `agnes:agnes-image-2.1-flash` (**US$ 0**) | `--motor capa=inemaimg:flux2-klein` |
| motor do clipe | `agnes:agnes-video-v2.0` (**US$ 0**) | `--motor clipe=kling:kling-v2_5` ou `fal:kling-v3-turbo` |
| ritmo do clipe | **auto** — o planejador decide pelo bpm/gênero e pelas referências medidas | `--ritmo calmo\|padrao\|variado\|dinamico` |
| pesquisa prévia | **desligada** (opt-in) | `--pesquisa` |
| letra | o planejador escreve | `--letra <arq>`, e `--letra-final` para ela virar lei |
| idioma da letra | **pt-BR** | `--idioma en-US` |
| pasta de saída | `~/projetos/output/musicavideo/<slug>/` | `MUSICAVIDEO_OUT` |
| slug | derivado da solicitação, com `-2`, `-3` se repetir | 2º argumento do `plano` |

O plano é sempre de graça: quem gasta é só a fase `musica`, e o custo estimado
aparece antes.

## RITMO

Quantos cortes por minuto o clipe tem. **Você não precisa escolher:** o default
é `auto` — o planejador decide pelo bpm, pelo gênero e pelas REFERÊNCIAS
MEDIDAS do `analisevideo` (o acervo mostra 22-35 cortes/min nos clipes que
performaram, 11-15 nos médios), e escreve em `clipe.sincronia` qual ritmo
escolheu e por quê. Isso aparece no `PLANO.md`, antes de qualquer gasto.

A flag existe para você DISCORDAR dele, ou para segurar o relógio:

| `--ritmo` | média por plano | ~180s de música | o que é |
|---|---|---|---|
| `auto` (default) | o planejador decide | — | ancorado no que foi medido, não no gosto |
| `calmo` | ~8s | ~22 shots · ~2h30 | balada, ambiente, plano longo |
| `padrao` | 5s | ~36 shots · ~4h | o de sempre |
| `variado` | 5s de MÉDIA | ~36 shots · ~4h | **ritmo sem pagar hora**: 2-3s no refrão pagos com 8-10s no verso |
| `dinamico` | ~3s | ~60 shots · ~6-7h | 20-30 cortes/min, o regime dos virais do acervo |

**As horas são o custo real, não o dólar.** Na Agnes o clipe é US$ 0 em qualquer
ritmo; o que muda é a fila (5 requisições/min). Em motor pago por segundo o
dólar também não muda com o ritmo — a metragem total continua sendo a duração
da música, só o número de chamadas cresce.

Vale para qualquer ritmo, e não se desliga: **a duração nunca é parelha entre os
shots** — refrão pica, verso respira, intro segura o plano. Piso de 1,5s (abaixo
disso o gerador não entrega plano legível) e teto de 18s (limite duro da Agnes).
O reajuste que roda quando a faixa fica pronta **preserva essa variação** em vez
de reescrever tudo igual.

Sem flag nenhuma, dá para mexer depois: `ajusta <slug> clipe "deixa o refrão
mais picado"`.

## NUCLEO (o trecho de 12s) e o SHORT

Assim que a faixa aprovada existe, o pipeline **mede** — não opina — qual é o
trecho de 12 segundos mais forte dela: energia (RMS) segundo a segundo pela
onda, com bônus para o trecho que SOBE depois de um vale (é o que separa "o mais
alto" de "o momento em que a música vira"). Sai no log e em `nucleo.json`:

```
núcleo da faixa: 151-163s (energia 95% do pico) — é daí que sai o Short
```

Serve a duas coisas:

- **onde investir o clipe:** o reajuste da decupagem manda pôr ali o melhor
  plano e o ritmo mais picado;
- **o Short:** `musicavideo curto <slug>` recorta esses 12s em 9:16 (1080x1920)
  **do clipe que já existe** — é corte, não render: segundos e US$ 0. Discordou
  da medição? `--inicio N` manda o segundo na mão.

Limite honesto: energia acerta refrão e drop, que é o caso comum, e erra em
música que constrói por letra ou por silêncio. É sugestão, não ordem.

## RECORTE (ritmo em clipe que já existe)

`musicavideo recorta <slug> [--ritmo variado|dinamico|calmo]`

O caro no clipe é GERAR os planos (fila de 5/min, horas). O corte não custa
nada. Então um clipe já pronto e parelho pode ganhar ritmo **sem a segunda
geração**: encurta no refrão, estica no verso, e a soma continua cobrindo a
música. Medido no MVD gaúcho: **19 segundos**, contra as ~4h de gerar de novo.

| | |
|---|---|
| encurtar | corte no miolo do plano (onde o movimento já engrenou) |
| esticar | slowmo até 1,6x — além disso o olho vê travando |
| faltam planos (`dinamico`) | **fabricados do próprio material**: um plano de 5s vira dois de 2,5s (metades = material real), e só em último caso entra o espelhado, longe do original |

O clipe velho fica intacto: o novo sai em `<slug>-<ritmo>/`, com as faixas e a
capa, para comparar lado a lado.

## PAINEL

`musicavideo painel [--lan] [--porta N]` sobe o acervo no navegador.

Desde 2026-08-23 ele mostra **tudo que existe no disco**, não só o que está no
`index.jsonl`: qualquer pasta com clipe entra, inclusive as derivadas de
`recorta` (`<slug>-variado`, `<slug>-dinamico`), com selo do ritmo, o slug de
origem e o **tamanho em disco** — que é o número que importa, porque cada
recorte são centenas de MB.

**A música toca no card.** Nos cards do musicavideo há um player da faixa
aprovada, e nos da análise o vídeo local quando existe — ouvir/ver não exige
abrir nada. Clicar no player NÃO abre o modal (senão arrastar a barra abriria a
janela por cima); clicar em qualquer outro ponto do card abre como antes. Nas
análises há também **"assistir no canal ↗"**, que leva ao vídeo original.

Cada card tem **"mandar para a lixeira"**: não apaga, MOVE para
`output/musicavideo/.lixo/`. Engano tem volta, e esvaziar a lixeira é decisão
de terminal (`rm -rf`), nunca de clique — ainda mais com `--lan`, onde a página
está aberta pra rede.

## O QUE O BOT RECEBE

Quando a entrega roda com `--telegram`, o bot recebe, nesta ordem:

1. **as DUAS faixas** — `faixa-1.mp3` e `faixa-2.mp3`, com legenda
   `<título> — 1|2` (a aprovada marcada `✓ aprovada`) **e o estilo embaixo**.
   Elas são músicas diferentes, não versões: mandar só a aprovada tirava de
   você justamente o que se decide de ouvido;
2. a **capa**, com `<título>` e o **estilo**;
3. o **clipe**, com **só o título**;
4. **o fecho** — a capa outra vez, com `<título>` e o **link do clipe**.

O fecho existe porque é a mensagem que fica valendo no chat: quem rolar a
conversa depois acha a peça por ela, sem caçar o vídeo no meio dos áudios. O
link sai de `MUSICAVIDEO_LINK_BASE` (ex.: `http://192.168.2.99:5400/musicavideo`,
o painel, que serve o arquivo e deixa arrastar a barra); sem a variável vai o
caminho absoluto — caminho certo é melhor que link inventado.

A regra da legenda: enquanto a decisão é sobre o SOM (mp3 + capa), vai título
**e estilo** — gênero · bpm · tom · mood, como `nordic folk anthem rock · 118
bpm · sombrio, épico`. Com o vídeo final a peça já se explica, e a legenda é só
o título; a capa vai logo antes dele, para ser o frame que anuncia a peça.

## QUANDO O PROVEDOR DIZ "VOLTE DEPOIS"

Dois limites da Agnes não são falha — são espera, e o adaptador espera sozinho:

| resposta | o que ele faz |
|---|---|
| `503 video_queue_full` | dorme 60s e tenta de novo, dentro do teto do polling |
| `429 Daily API usage limit reached` | **vira para a conta reserva**; se não houver, dorme até o horário que a própria mensagem informa (`Please try again after **2026-08-26 00:00 UTC**`), com teto de 8h |

**Contas em cascata:** a cota da Agnes é diária E por conta, então uma conta
esgotada não para o render — ele troca de conta.

| ordem | variável | conta |
|---|---|---|
| 1 | `AGNES_API_KEY` | principal |
| 2 | `AGNES_API_KEY_2` | inemaccbottime |
| 3 | `AGNES_API_KEY_3` | inemaccbot-ftd |
| 4 | `AGNES_API_KEY_4` | inemaccbot-futuro |

As chaves moram nos `.env` autorizados (`openpcbotv2/.env`, `wifi/.env`) e a
cascata é por existência: chave ausente é pulada. Só depois de esgotar TODAS é
que ele dorme até o reset. Cada corrida nova recomeça pela principal — no dia
seguinte ela voltou.

Sem horário legível na mensagem, espera 1h. O clipe segue de onde parou: shot
que já está no disco não é refeito.

Isso existe porque cota estourada deixava cicatriz — a parte ficava marcada
`erro` e a produção parava a noite inteira com música e capa já pagas, mesmo
depois de a cota virar.

## ESTILOS

O planejador escolhe um sozinho a partir da sua descrição. Para forçar, use
`--estilo <id>` (o id, não o nome do gênero):

| id | gênero | BPM | tom |
|---|---|---|---|
| `uplifting-ambient-electronic` | uplifting ambient electronic, corporate instrumental, chill tech | 103 | C maior |
| `corporate-tech-electro-pop` | corporate tech electro pop, ambient house, synthwave | 118 | F maior |
| `uplifting-progressive-trance` | uplifting progressive trance, tech house, melodic techno | 132 | — |
| `anthem-pop-rock` | anthem pop rock | — | — |
| `female-anthem-rock` | anthem rock, pop rock (voz feminina) | — | — |

O estilo é ponto de PARTIDA, não camisa de força: o plano final traz o gênero, o
BPM, o tom, a instrumentação e a voz decididos para a sua música — e tudo isso
aparece no `PLANO.md`, que é o que o portão manda no chat.

**Idioma da letra:** default `pt-BR`. Para outro, `--idioma en-US` (ou o que for)
— o pedido vai para a letra E para o prompt do Suno, que são dois lugares
diferentes e precisam concordar. Os dois são escritos por CÓDIGO, não pedidos ao
planejador: a frase `Lyrics in <idioma>` é imposta no fim do `prompt_estilo` e
qualquer declaração de idioma que o modelo tenha posto ali é apagada antes (duas
declarações no mesmo prompt é o que produz portunhol acidental). Acento cai na
frase do estilo (`português` → `Lyrics in portugues`), porque prompt de provedor
é recusado com acento; o rótulo em `musica.letra.idioma` fica como você digitou.

Sem `--idioma`, nada disso acontece: o `prompt_estilo` fica como o planejador
escreveu, e o rótulo cai em `pt-BR` só se ele não declarar nada. Pedir o idioma
em prosa dentro do texto ("language = portuguese or spanish") funciona pela boa
vontade do modelo — foi assim no MVD#96 e o rótulo virou a frase inteira.

## RESPONDER AO PORTÃO (pelo bot)

Quando o material chega no chat, `/aprovar` segue e estas palavras corrigem —
cada fase aceita as suas, e o bot as lista junto com o material:

| fase | resposta | o que faz | custo |
|---|---|---|---|
| música | `refaz` | descarta a faixa e gera outra, mesma letra e estilo | uma geração |
| música | `correcao <instrução>` | reescreve a seção `musica` do plano e regera | uma geração |
| música | `a` / `b` | escolhe a faixa 1 ou 2 como principal | **zero** — as duas já têm clipe |
| capa | `refaz` | descarta e gera outra com o mesmo plano | uma geração |
| capa | `correcao <instrução>` | reescreve o conceito da capa e regera | uma geração |
| clipe | `reprova 4,17,23` | apaga esses shots; só eles são gerados de novo | N shots |
| clipe | `ritmo variado\|dinamico\|calmo` | recorta o que já existe | **zero**, ~19s |
| clipe | `correcao <instrução>` | reescreve a decupagem e regera | o clipe inteiro |

`a`/`b` e `ritmo` não refazem nada: as duas faixas já ganharam o MESMO vídeo em
`montar_todas`, e o `recorta` reusa os shots do disco. As outras devolvem a fase
para a fila e o portão reabre com o material novo.

Como o laço funciona, por dentro:

    portão abre  →  você responde  →  o bot roda o comando do domínio
                                   →  a fase volta para a fila e RODA
                                   →  o portão REABRE com o material novo
                                   →  ...até você dar /aprovar

O comando é o mesmo que você rodaria no terminal (`reprova`, `ajusta --refaz`,
`aprova --faixa N`, `recorta`) — o bot não tem lógica própria de correção, ele
só sabe que esta fase declarou esta palavra. O que vem depois da palavra vai
INTEIRO para o domínio, num argumento só: `clipe: MVD#7 correcao menos zoom nos
rostos` chega como uma instrução, não como flags que o bot tentou entender.

Duas faixas: o Suno entrega duas e as DUAS aparecem no portão da música (a
segunda vem do campo `musica_alt` do recibo). Escolher entre elas é `a` ou `b`,
e não custa nada — o clipe das duas é o mesmo vídeo.

## TEMPLATES

Também escolhidos pelo planejador, e visíveis no `PLANO.md`.

Capa:

| id | o que é |
|---|---|
| `tipografia-dominante` | título enorme ocupa 60%+ do quadro; fundo texturizado simples |
| `retrato-centralizado` | persona no centro, luz dramática, espaço pro título |
| `paisagem-simbolica` | cena que simboliza o tema, sem figura humana em destaque |
| `minimal-abstrato` | formas geométricas em 2-3 cores; lê bem em miniatura |

Clipe:

| id | o que é |
|---|---|
| `performance` | persona "cantando" em cenário; câmera orbita e alterna planos |
| `narrativo` | mini-história em 6-12 shots seguindo o arco da letra |
| `lyric-video` | letra em tipografia animada, um fundo por seção |
| `abstrato-loop` | visuais que respiram com o BPM; loops curtos por seção |

Para mudar depois do plano pronto, fale em português:

```
bash musicavideo.sh ajusta <slug> clipe "usa narrativo, menos close em rosto, mais mar e gelo"
```

## CANAL: SEMPRE lives10, E SEMPRE AS DUAS FAIXAS

O destino padrão é o **lives10** — é para lá que vai toda produção, sem precisar
pedir. O **lives2 só quando você mandar**, caso a caso (é onde se testa modelo
de imagem, marca de título, etc.).

E vão **as duas faixas**: o Suno entrega duas MÚSICAS, não duas versões da
mesma. O pacote de canal leva dois vídeos:

```
publicacao/
  <slug>-1.mp4   capa-yt-1.jpg   → "<título> (faixa 1)"
  <slug>-2.mp4   capa-yt-2.jpg   → "<título> (faixa 2)"
  manifest.json  (clips: [ {...}, {...} ])
```

Cada peça leva **capa própria com o selo da versão** — é para isso que o selo
existe: duas capas iguais no feed confundem. Descrição e tags são as mesmas (a
música é a mesma ideia; o que muda é a gravação).

Com uma faixa só, nada muda: um vídeo, `<slug>.mp4`, `capa-yt.jpg`, sem sufixo
no título.

## ENTREGA

O que chega no chat quando cada portão abre:

| fase | o que você recebe |
|---|---|
| plano | o `PLANO.md` inteiro, para ler e decidir |
| musica | `faixa-1.mp3` como **arquivo** |
| capa | `capa.png` como **arquivo** |
| clipe | o clipe como **link** |

O clipe vai por link e não anexado porque mp4 de música passa dos 50 MB que o
Telegram aceita como documento. Tudo também fica em
`~/projetos/output/musicavideo/<slug>/`.

O Suno entrega DUAS faixas. A que vale é a `faixa-1.mp3`, e o clipe é montado
com as duas (`clipe-1.mp4`, `clipe-2.mp4`) — trocar depois é `aprova <slug>
musica --faixa 2`, que só reaponta, sem re-render e sem custo.

## CAMPOS

São dois conjuntos, e os dois podem ir na mesma mensagem.

**1. Parâmetros da MÚSICA** (deste projeto) — escreva junto com a descrição, em
qualquer lugar. Aceitam `--flag valor` e `--flag=valor`:

```
/musicavideo balada sobre recomeço --idioma en-US --estilo anthem-pop-rock
```

| parâmetro | o que faz |
|---|---|
| `--idioma X` | idioma da letra (default `pt-BR`) — ex.: `en-US`, `es-ES` |
| `--estilo X` | força um estilo do `data/estilos.json` (ver `/musicavideo help estilos`) |
| `--faixa-pronta <arq>` | **você traz a música**: o pipeline faz só capa e clipe, e a duração real do arquivo ancora a decupagem. Nada é gasto na parte paga |
| `--letra <arq>` | usa a sua letra como RASCUNHO; o `PLANO.md` mostra o diff do que mudou |
| `--letra-final` | com `--letra`, a letra vira LEI: nem o `ajusta` mexe |
| `--ritmo X` | quão picado é o clipe (ver `/musicavideo help ritmo`). Default `auto`: o planejador escolhe |
| `--pesquisa` | pesquisa antes de planejar (custa tempo; desligado por default) |
| `--motor parte=prov:modelo` | troca o motor de uma parte (ver `/musicavideo help padroes`) |
| `--autorizo-pago` | obrigatório junto com `--motor` para `kie`, `kling` ou `fal` — eles gastam crédito ou dinheiro |

**2. Campos do BOT** — depois de um `|` no fim da mensagem, ou `--campo=valor`:

| campo | o que faz |
|---|---|
| `\| de=<fase>` | começa nessa fase — `plano`, `musica`, `capa`, `clipe`, `entrega` |
| `\| sem-portao` | não para para você aprovar (vai até o fim de uma vez) |
| `\| versao=N` | versão do assunto |
| `\| sombra` | mostra o plano de execução sem enfileirar nada |

Não existem aqui: `| alvos=` (o fluxo tem um público só, `unico`) e
`| legenda=` (é campo de reel do promoavatar; nada nesta definição usa).

## CUSTO

| parte | quem gera | custo |
|---|---|---|
| plano | Fable, local | zero |
| música | kie.ai / Suno v4.5 | ~US$ 0,08 por geração (2 faixas) |
| capa | Agnes AI | US$ 0 |
| clipe | Agnes AI | US$ 0 |

Chave lida em runtime de `~/projetos/openpcbotv2/.env` ou `~/projetos/wifi/.env`
(`KIE_API_KEY`, `AGNES_API_KEY`). Provedor sem chave não derruba o fluxo:
aparece como INDISPONÍVEL COM O MOTIVO no plano, e só aquela parte vira `erro`.

## ESTADOS

Cada parte (música, capa, clipe) tem portão próprio e sua própria máquina:

  planejado → (aprovar) → aprovado → (faz) → gerando → pronto | erro

`erro` aceita nova tentativa ou ajuste. `pronto` só volta com `ajusta --refaz` —
e o artefato antigo vai para `raw/` com sufixo `-vN`, nunca é sobrescrito.

## DEPOIS DE PRONTO

As respostas do portão (`refaz`, `reprova`, `ritmo`, `correcao`) só valem
**enquanto o portão está aberto**. Quando o fluxo termina, elas somem do chat, e
o `/refazer` não substitui: ele só recoloca na fila as fases que FALHARAM — uma
fase `feito` nunca é refeita por ele.

Para mudar uma produção já entregue, o caminho é o terminal:

| quero | comando | gasta? |
|---|---|---|
| a outra capa | `arte <slug> "<título>" --versao 2` | **não** |
| outro ritmo no clipe | `recorta <slug> --ritmo dinamico` | **não** |
| o clipe com cada faixa | `monta <slug> --completo` | **não** |
| refazer alguns shots | `reprova <slug> clipe "4,17,23"` e depois `faz <slug> clipe --sim` | os shots |
| outra capa, com instrução | `ajusta <slug> capa "<instrução>" --refaz` e depois `faz <slug> capa --sim` | uma geração |
| publicar a mudança | `publica-hf <slug>` | não gera, mas PUBLICA |

`ajusta ... --refaz` é obrigatório antes do `faz` numa parte já `pronto` — é ele
que destrava. Sem isso vem `estado 'pronto' não permite faz`.

⚠️ O `--dry` do `publica-hf` NÃO segura o manifesto: ele evita subir mídia para
o Hugging Face, mas o `manifest.json` é escrito, commitado e empurrado assim
mesmo. E ele cobre só a vitrine — vídeo já publicado no YouTube pelo `yt-pub`
não é atualizado por aqui.

Todos os comandos e todas as flags: **docs/REFAZER.md**.

## DOCS

Refazer o que já foi feito: docs/REFAZER.md
Guia de uso: https://inematds.github.io/musicavideo/guia/
As fases em detalhe: docs/FASES.md · Por dentro: docs/COMO-FUNCIONA.md
Interface para o bot: SKILL.md

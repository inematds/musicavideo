/musicavideo — uma frase vira música + capa + clipe, planejados juntos.

Uso: /musicavideo balada pop sobre recomeço
     /musicavideo <descrição> [--idioma en-US] [--estilo <id>] [--letra <arq>]
     (todos os parâmetros: /musicavideo help campos)

Fases (cada uma para e espera /aprovar, menos a última):
  1. plano       (fila texto)  → PLANO.md no chat · NÃO gasta nada
  2. musica      (fila io)     → a faixa, como arquivo · ÚNICA parte paga (~US$ 0,08)
  3. capa-clipe  (fila render) → a capa (arquivo) e o clipe (link) · US$ 0 no default
  4. entrega     (fila io)     → PACOTE.md

Acompanhar: /status MVD#N · /aprovar MVD#N · /refazer MVD#N · /cancelar MVD#N

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
| pesquisa prévia | **desligada** (opt-in) | `--pesquisa` |
| letra | o planejador escreve | `--letra <arq>`, e `--letra-final` para ela virar lei |
| idioma da letra | **pt-BR** | `--idioma en-US` |
| pasta de saída | `~/projetos/output/musicavideo/<slug>/` | `MUSICAVIDEO_OUT` |
| slug | derivado da solicitação, com `-2`, `-3` se repetir | 2º argumento do `plano` |

O plano é sempre de graça: quem gasta é só a fase `musica`, e o custo estimado
aparece antes.

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
diferentes e precisam concordar.

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

## ENTREGA

O que chega no chat quando cada portão abre:

| fase | o que você recebe |
|---|---|
| plano | o `PLANO.md` inteiro, para ler e decidir |
| musica | `faixa-1.mp3` como **arquivo** |
| capa-clipe | `capa.png` como **arquivo**, e o clipe como **link** |

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
| `--letra <arq>` | usa a sua letra como RASCUNHO; o `PLANO.md` mostra o diff do que mudou |
| `--letra-final` | com `--letra`, a letra vira LEI: nem o `ajusta` mexe |
| `--pesquisa` | pesquisa antes de planejar (custa tempo; desligado por default) |
| `--motor parte=prov:modelo` | troca o motor de uma parte (ver `/musicavideo help padroes`) |
| `--autorizo-pago` | obrigatório junto com `--motor` para `kie`, `kling` ou `fal` — eles gastam crédito ou dinheiro |

**2. Campos do BOT** — depois de um `|` no fim da mensagem, ou `--campo=valor`:

| campo | o que faz |
|---|---|
| `\| de=<fase>` | começa nessa fase — `plano`, `musica`, `capa-clipe`, `entrega` |
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

## DOCS

Guia de uso: https://inematds.github.io/musicavideo/guia/
As fases em detalhe: docs/FASES.md · Por dentro: docs/COMO-FUNCIONA.md
Interface para o bot: SKILL.md

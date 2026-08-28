# Refazer: como mudar o que já foi feito

Guia de consulta para **depois** que uma parte saiu — no bot, enquanto o portão
está aberto, e no terminal, depois que o fluxo terminou.

A regra que explica quase tudo: **o bot só age enquanto o portão está aberto.**
Assim que o fluxo vira `feito`, `reprova`/`ritmo`/`correcao` somem do chat, e o
que resta é o terminal. O `/refazer` do bot **não** cobre isso — ele só recoloca
na fila as fases que **falharam**.

---

## 1. No bot, com o portão aberto

A sintaxe é `<fase>: <ref> <resposta>`. O verbo é o nome da FASE porque um fluxo
pode ter dois portões abertos ao mesmo tempo. Esta tabela é o resumo — a versão
comentada, com o custo de cada resposta, está no [HELP.md](../HELP.md), seção
`RESPONDER AO PORTÃO` (no chat: `/musicavideo help responder`).

| fase | resposta | o que faz | gasta? |
|---|---|---|---|
| `musica` | `a` / `b` | escolhe a faixa 1 ou a 2 | não |
| `musica` | `refaz` | descarta a faixa e gera outra, mesma letra e estilo | sim |
| `musica` | `correcao <instrução>` | replaneja com a instrução e gera | sim |
| `capa` | `refaz` | gera outra capa | sim |
| `capa` | `correcao <instrução>` | replaneja a capa e gera | sim |
| `clipe` | `reprova 4,17,23` | descarta SÓ esses shots e remonta | sim (só os shots) |
| `clipe` | `ritmo <nome>` | remonta com outro ritmo, mesmos shots | **não** |
| `clipe` | `correcao <instrução>` | replaneja a decupagem e gera | sim |

```
musica: MVD#135 a
capa: MVD#135 correcao menos escura, o rosto mais em foco
clipe: MVD#135 reprova 4,17,23
clipe: MVD#135 ritmo dinamico
```

Fora dos portões, o bot tem só **consultas** (leitura):

```
/musicavideo lista
/musicavideo busca sertanejo
/musicavideo custo MVD#135
/musicavideo estilos
```

Mais `/status <ref>`, `/dados <ref>`, `/refazer <ref>` (só fase falhada) e
`/cancelar <ref>`.

---

## 2. No terminal, depois de pronto

```bash
S=/home/nmaldaner/projetos/musicavideo/musicavideo.sh
SLUG=quero-contar-a-historia-da-africa-por-ou
```

### Não gasta — reusa o que já foi gerado e pago

```bash
bash $S arte    $SLUG "Vivo ao Amanhã" --versao 2   # troca para a outra capa
bash $S recorta $SLUG --ritmo dinamico              # outro ritmo, mesmos shots
bash $S monta   $SLUG --completo                    # casa o clipe com CADA faixa
bash $S curto   $SLUG --inicio 45                   # Short 9:16 de 12s
bash $S pacote  $SLUG                               # regera o PACOTE.md
```

### Gasta — gera material novo

```bash
# só alguns shots do clipe
bash $S reprova $SLUG clipe "4,17,23"
bash $S faz     $SLUG clipe --sim

# a capa, com uma instrução nova
bash $S ajusta $SLUG capa "menos escura, o rosto da mãe mais em foco" --refaz
bash $S faz    $SLUG capa --sim
```

**`ajusta ... --refaz` é obrigatório antes do `faz` numa parte já `pronto`.** É
ele que destrava. Sem isso vem `estado 'pronto' não permite faz (precisa
aprovado ou erro)` — o erro mais comum deste guia.

### Publicar a mudança

```bash
bash $S publica-hf $SLUG      # sobe os arquivos novos e reescreve o manifesto
```

⚠️ **`--dry` não segura o manifesto.** Ele evita subir mídia para o Hugging
Face, mas o `manifest.json` é escrito, commitado e empurrado do mesmo jeito.

O `publica-hf` cobre só a **vitrine**. Um vídeo já publicado no YouTube pelo
`yt-pub` não é atualizado por aqui.

---

## 3. Todos os parâmetros

### Comandos

| comando | para quê | gasta? |
|---|---|---|
| `plano "<solicitação>" [slug]` | planeja música + capa + clipe juntos | não¹ |
| `faz <slug> [parte]` | executa uma parte (ou a próxima) | sim |
| `ver <slug> [parte]` | mostra o PLANO.md ou uma seção | não |
| `revisa <slug> [parte]` | o que está esperando você olhar | não |
| `aprova <slug> <parte>` | fecha a parte | não |
| `reprova <slug> <parte> ["4,17,23"]` | descarta e devolve pro `faz` | não² |
| `ajusta <slug> <parte> "<instrução>"` | replaneja a parte | não² |
| `ok <slug> <parte>` | marca a parte como vista | não |
| `tudo "<solicitação>"` | plano + as três partes, sem portão | sim |
| `monta <slug>` | casa o clipe com cada faixa | não |
| `curto <slug>` | Short 9:16 de 12s do núcleo | não |
| `recorta <slug>` | novo ritmo reusando os shots | não |
| `arte <slug> ["<título>"]` | recompõe a capa | não |
| `pacote <slug>` | gera o PACOTE.md | não |
| `custo <slug>` | o que já foi gasto | não |
| `lista [N]` · `busca "<termo>"` · `reindex` | acervo | não |
| `nuvem <slug>` | aprova para a vitrine | não |
| `publica-hf [slug]` | sobe para o HF e reescreve o manifesto | não³ |
| `likes` | traz as curtidas da vitrine | não |
| `painel [--porta N]` | acervo no navegador | não |

¹ o `plano` chama o modelo (Claude Code), que não é cobrado por chamada.
² só marca o estado — quem gera é o `faz` seguinte.
³ não gera nada, mas **publica**: é ação de saída.

### Flags

| flag | onde | o que faz |
|---|---|---|
| `--sim` | `faz`, `tudo` | confirma o gasto sem perguntar |
| `--teto N` | `tudo` | aborta se passar de N dólares |
| `--sem-revisao` | `faz` | não para para você olhar |
| `--aprovar` | `faz` | aprova a parte ao terminar |
| `--refaz` | `ajusta` | devolve a parte para o `faz` (destrava `pronto`) |
| `--faixa N` | `aprova` | qual das duas faixas fica |
| `--versao N` | `arte` | qual capa compor |
| `--tagline "..."` | `arte` | a linha de baixo da capa |
| `--ritmo X` | `plano`, `recorta` | `auto`, `calmo`, `padrao`, `variado`, `dinamico` |
| `--inicio N` | `curto` | segundo onde o Short começa |
| `--estilo X` | `plano` | id de `data/estilos.json` |
| `--idioma X` | `plano` | `pt-BR`, `en-US`, `sw`… |
| `--letra arq` | `plano` | usa a sua letra |
| `--letra-final` | `plano` | a letra é definitiva, não replaneja |
| `--faixa-pronta a.mp3` | `plano` | entra com música pronta (só capa e clipe) |
| `--pesquisa` | `plano` | pesquisa antes de planejar |
| `--motor parte=prov:modelo` | `plano`, `faz` | troca o motor de uma parte |
| `--autorizo-pago` | `faz` | libera motor pago fora do padrão |
| `--forca` | `plano` | replaneja por cima de um slug que já existe |
| `--completo` | `monta` | monta com todas as faixas |
| `--dry` | `publica-hf` | não sobe mídia (**mas publica o manifesto**) |
| `--manifesto` | `publica-hf` | só reescreve o manifesto |
| `--bruto` | `plano` | o texto do chat inteiro num argumento só |

`--flag=valor` e `--flag valor` são a mesma coisa.

### Ritmos

| ritmo | por plano | quando |
|---|---|---|
| `auto` | — | o planejador decide pelo bpm/gênero (padrão) |
| `calmo` | ~8 s | balada, ambiente |
| `padrao` | 5 s | o de sempre |
| `variado` | ~5 s | refrão pica, verso respira |
| `dinamico` | ~3 s | 20–30 cortes/min, o regime dos virais |

### Motores padrão

| parte | motor |
|---|---|
| música | `kie:suno-v4.5` |
| capa | `agnes:agnes-image-2.1-flash` |
| clipe | `agnes:agnes-video-v2.0` |

Trocar exige autorização explícita, e o id é o exato do provedor
(`providers/*.models.json`):

```bash
--motor clipe=kling:kling-v2_5 --autorizo-pago
```

Disponíveis no kling: `kling-v2_5`, `kling-v2_6`, `kling-v3_0_turbo`.

---

## 4. Armadilhas

- **`estado 'pronto' não permite faz`** — a parte já está pronta. Use
  `ajusta ... --refaz` (ou `reprova`) antes do `faz`.
- **`/refazer` não refaz o que deu certo.** Ele só reenfileira fases que
  **falharam**. Se o `plano` está `feito`, ele nunca é refeito — e é o plano que
  guarda o slug. Fluxo com slug errado só se resolve com fluxo novo.
- **Pedido repetido vira pasta irmã.** O slug sai dos 40 primeiros caracteres da
  solicitação; dois pedidos que começam igual geram `...`, `...-2`, `...-3`. São
  produções diferentes, com faixa e clipe próprios.
- **`aprova` não vale em `planejado`.** A transição é `ok`: `ok <slug> clipe` e
  só então `faz`. O `aprova` serve para fechar uma parte já gerada.
- **O número MVD nunca muda.** Renomear pasta, reindexar ou republicar não
  renumera — é o que permite citar o número depois.

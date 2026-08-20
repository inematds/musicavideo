# As fases, passo a passo

Cada fase aqui está descrita como ela realmente roda: o comando, o que acontece
por dentro, o que fica no disco, o que custa e onde você decide.

Referência rápida do ciclo inteiro:

```
0. pesquisa (opt-in)
1. plano  ──▶ ok ──▶ 2. faz MÚSICA ──▶ revisa ──▶ aprova --faixa N
                                                      │
                                    2.1 reajuste da decupagem pela faixa real
                                                      │
                                     2. faz CAPA e CLIPE (com cascata)
                                                      │
                                          revisa ──▶ reprova 9,11 ──▶ faz
                                                      │
                                                   aprova
                                                      │
                                   2.5 montagem ──▶ 3. entrega (PACOTE.md)
```

---

## Fase 0 — pesquisa *(opcional)*

**Comando:** `musicavideo plano "<frase>" --pesquisa`
**Custo:** tempo (uma chamada com WebSearch). Nenhuma API de mídia.
**Default:** desligada.

**Passos:**

1. Monta um pedido de pesquisa a partir da sua frase.
2. Chama `claude -p ... --allowedTools WebSearch`, que busca: referências sonoras
   atuais do nicho, o que funciona em capa e clipe naquele gênero hoje, e se o
   tema tem tração.
3. Grava `pesquisa.md` na pasta do slug.
4. O texto entra como **contexto** do planejamento — nunca sobrescreve o que você
   pediu explicitamente.

---

## Fase 1 — plano

**Comando:** `musicavideo plano "<frase>" [slug] [--estilo X] [--letra arq [--letra-final]]`
**Custo:** zero de API de mídia.
**Produz:** `plano.json` (contrato), `PLANO.md` (legível), `estado.json`, linha no `index.jsonl`.

**Passos:**

1. **Deriva o slug** da frase (kebab-case, ≤40 chars, sufixo `-2` se colidir), ou usa o que você deu.
2. **Recusa slug existente** sem `--forca`; e com `--forca`, ainda recusa se alguma parte estiver `pronto` (protege o que já foi pago).
3. **Carrega o registry** de provedores a partir dos `providers/*.models.json`.
4. **Monta o contexto** do planejador com:
   - sua solicitação, verbatim;
   - `data/estilos.json` — estilos medidos (BPM, tom, instrumentação, voz, prompts de Suno);
   - `data/templates-capa.json` e `data/templates-clipe.json`;
   - o acervo (últimas 5 do `index.jsonl` + as que casam com sua frase);
   - **referências visuais medidas** do `analisevideo` (paleta, câmera, cortes/min) que casem com o gênero e o mood;
   - `pesquisa.md`, se houver;
   - as regras: prompts de provedor em inglês, cobrir a música inteira, plano B (`prompt_alt`) por shot, schema fechado.
5. **Chama o Fable**, que faz um passe de autocrítica e devolve **um JSON só** com música, capa e clipe decididos juntos.
6. **Impõe o que não se delega ao modelo:** slug, data, solicitação, motores (e o `--motor`), e o status da letra.
   - `--letra-final` → a letra vai **byte a byte**, `origem: final_usuario`.
   - `--letra` sem `--letra-final` → `origem: rascunho_usuario` e o original guardado em `texto_original` (é o que gera o diff no `PLANO.md`).
7. **Valida:** schema fechado (campo a mais é erro), prompts sem acento, params existentes no modelo, motor no registry, campos de lista de fato listas, e cobertura do clipe ≥90% da música.
8. **Um retry:** se algo falhou, devolve os erros ao Fable e valida de novo. Falhou outra vez, para e mostra — plano inválido não é gravado.
9. **Grava** `plano.json`, `PLANO.md` (com a tabela de shots e a disponibilidade de cada provedor), `estado.json` com as três partes em `planejado`, e a linha do índice.

---

## Revisão do plano *(sempre que quiser)*

**Comandos:** `ver`, `ajusta`
**Custo:** zero.

**Passos:**

1. `musicavideo ver <slug>` mostra o `PLANO.md` inteiro; `ver <slug> clipe` mostra só a seção.
2. `musicavideo ajusta <slug> <parte> "<instrução>"`:
   - manda o **plano atual + sua instrução** ao Fable;
   - ele reescreve **apenas aquela seção**;
   - se a música tem letra `final_usuario`, alterar a letra é **recusado**;
   - o resultado é validado igual à fase 1;
   - imprime o **diff** do antes/depois;
   - a parte volta para `planejado` — **a aprovação anterior cai**.
3. Parte já `pronto` exige `--refaz`; o artefato antigo vai para `raw/<arquivo>-vN`.

---

## Portão do plano

**Comando:** `musicavideo ok <slug> <parte>`
**Custo:** zero.

Marca a parte como `aprovado`. Sem isso, o `faz` recusa. Cada parte tem portão próprio — aprovar a música não aprova a capa.

---

## Fase 2 — execução

**Comando:** `musicavideo faz <slug> [parte] [--sim] [--sem-revisao] [--motor parte=prov:modelo]`
**Custo:** **gasta** — só a música (~US$ 0,08); capa e clipe são US$ 0 no Agnes.

### Antes de chamar qualquer API

1. **Carrega** plano e estado; `gerando` órfão de um crash vira `erro: interrompido` (a menos que exista processo vivo com o lock de PID).
2. **Aplica e persiste** o `--motor`, se você passou.
3. **Escolhe as partes.** Sem argumento:
   - se a música ainda não está pronta, roda **só a música** — capa e clipe esperam;
   - se está pronta, segue com capa e clipe;
   - nada aprovado e algo em `revisao` → avisa que está esperando você.
   Nomear a parte (`faz <slug> capa`) ignora a ordem: você mandou.
4. **Confere a pré-condição:** parte tem que estar `aprovado` ou `erro`.
5. **Estima o custo** por parte; motor inexistente vira mensagem legível, exit 1.
6. **Mostra a conta e pergunta.** `--sim` pula. Até aqui, nada foi chamado.

### Por parte

7. **Disponibilidade:** sem chave, a parte vira `erro` com o motivo e o loop segue nas outras.
8. **Teto** (`tudo --teto N`): estouraria? pula, mantém `aprovado`, exit 3 no fim.
9. **Marca `gerando` e salva em disco** antes da chamada, mais o lock de PID.
10. **Reajuste da decupagem** (só no clipe): se a faixa aprovada difere em mais de 5 s do que o plano previa, o planejador refaz a decupagem para a duração real — **antes** de gerar vídeo.
11. **Chama o provedor** (detalhe por parte abaixo). Vindo de `erro`, manda `retry=True`, o que permite reaproveitar geração já paga.
12. **Fecha a parte:** vai para `revisao` (padrão) ou direto para `pronto` (`--sem-revisao`). Qualquer exceção vira `erro` — adapter mal-comportado não derruba a corrida.
13. **Salva estado e reescreve o índice a cada parte**, não no fim.

### O que cada provedor faz

**Música — `kie:suno-v4.5`**

1. `POST /generate` com `customMode`, style (EN), letra, e `callBackUrl` (sem ele a API responde 422).
2. Grava o `taskId` no `raw/` **imediatamente** — o dinheiro saiu nesse instante.
3. Poll a cada 15 s até `SUCCESS`/`FIRST_SUCCESS` **com `audioUrl` de verdade** (em `FIRST_SUCCESS` uma das faixas ainda vem vazia).
4. Baixa as **duas** faixas (`faixa-1.mp3`, `faixa-2.mp3`) — a geração já pagou pelas duas. User-Agent de browser, senão o CDN dá 403.
5. Timeout de 15 min.

**Capa — `agnes:agnes-image-2.1-flash`**

1. `POST /v1/images/generations` com `size` em pixels e prompt em inglês.
2. Baixa a URL, que é temporária.

**Clipe — `agnes:agnes-video-v2.0`**

Por shot:

1. Já existe `raw/shot-NN.mp4`? reaproveita e segue.
2. Espera 12 s (limite real de 5 req/min).
3. `POST /v1/videos` com `num_frames` na regra 8n+1 (teto 441; 5 s = 121).
4. Poll a cada 10 s até `completed`; baixa o shot.
5. **Barrou no filtro?** cascata: `prompt_alt` → reescrita na hora pelo Fable → variação espelhada de um vizinho da mesma seção → buraco registrado. A duração total é preservada em todos os casos menos o último.

No fim: falha se sobrarem menos de 80% dos shots; senão `ffmpeg concat -c copy` e `ffprobe` para medir o arquivo real (a resposta da API mente o tamanho).

**Exit codes:** `0` ok · `1` uso/validação · `2` alguma parte em erro · `3` teto estourado.

---

## Fase 2.2 — revisão do artefato

**Comandos:** `revisa`, `aprova`, `reprova`
**Custo:** zero para olhar. Regerar música custa; capa e clipe não.

**Passos:**

1. `musicavideo revisa <slug>` lista o que está parado no portão, com o caminho de cada arquivo.
   - **Música:** as duas faixas aparecem como opções.
   - **Clipe:** gera `revisao/contato-clipe.jpg` — grade com um frame do meio de cada shot, **numerada**.
2. Você olha/ouve.
3. **Aprovar:** `musicavideo aprova <slug> musica --faixa 2` (sem `--faixa`, fica a 1). A parte vira `pronto`.
4. **Reprovar:**
   - `reprova <slug> clipe 4,17,23` — apaga **só esses** shots e a montagem velha; o próximo `faz` regenera esses e reaproveita o resto;
   - `reprova <slug> clipe` (sem números) — descarta todos os shots;
   - `reprova <slug> capa` — apaga a capa (regerar é grátis);
   - `reprova <slug> musica` — apaga as duas faixas e avisa que a nova geração custa.
   A parte volta para `aprovado`, pronta para o `faz`.
5. Aprovada a música, o comando lembra: `musicavideo faz <slug>` para capa e clipe.

`--sem-revisao` no `faz` pula este portão. O `tudo` já roda sem ele.

---

## Fase 2.5 — montagem

**Comando:** automático no `faz clipe`, ou `musicavideo monta <slug> [--completo]`
**Custo:** zero.

**Passos:**

1. Guarda o vídeo cru dos shots em `raw/clipe-sem-musica.mp4`.
2. Mede vídeo e faixa com `ffprobe`.
3. Troca o áudio ambiente dos shots pela faixa, com fade-out de 2 s.
4. Vídeo mais curto que a música? `--completo` repete o vídeo em loop até a faixa acabar. Vídeo mais longo? a música toca até o fim e o resto fica em silêncio (`apad`), sem cortar imagem.
5. Se a faixa ainda não existir, avisa e entrega o clipe com o áudio dos shots — e diz para rodar `monta` depois.

---

## Fase 3 — entrega

**Comando:** automática quando as três partes ficam `pronto`; `--telegram` liga o envio.
**Custo:** zero.

**Passos:**

1. Gera `PACOTE.md`: tabela parte/estado/arquivo/motor/custo, custo total, caminho da pasta.
2. Entrega parcial é permitida — lista o que falta e o comando para retomar.
3. Com `--telegram` e as chaves nos `.env` autorizados, envia faixa (`sendAudio`), capa (`sendPhoto`) e clipe (`sendVideo`). Sem chave, avisa e segue — nunca quebra.
4. Marca `fase: entregue` no estado e reescreve o índice.

---

## Consulta, a qualquer momento

| comando | o que faz |
|---|---|
| `musicavideo custo <slug>` | estimado vs gasto, por parte |
| `musicavideo lista [N]` | últimos slugs com estado e custo |
| `musicavideo busca "<termo>"` | slug, título, solicitação, gênero e tags |
| `musicavideo reindex` | reconstrói o índice a partir das pastas |

# Melhorias pedidas — para depois

Backlog do dono, com data. **Nada aqui está implementado.** Quem for mexer:
leia o que existe hoje antes de propor, porque metade destes itens é ajuste no
que já está de pé, não construção nova.

---

## 2026-08-22 — depois do MVD#89 (Born Where Winter Kills)

Contexto: os dois primeiros clipes completos saíram neste dia. O material foi
aprovado ("achei muito bons os clipes"), e o que segue são melhorias, não
correções de defeito.

### 1. Capa: gerar a imagem NO TAMANHO da capa

**Hoje:** a imagem é gerada uma vez, quadrada (1:1), e a versão 16:9 do YouTube
é derivada dela — o quadrado no centro e as laterais preenchidas com ele mesmo,
ampliado e borrado (`arte._fundo_16x9`). Funciona, mas é remendo: metade do
quadro 16:9 é borrão.

**Pedido:** **refazer a imagem** em cada proporção, em vez de derivar. Cada
destino pede um enquadramento próprio — o que é bom em 1:1 não é bom em 16:9.

Pontos a decidir antes de codar:
- Duas gerações por capa dobram o custo da parte (hoje US$ 0,00 na Agnes, mas
  isso é do motor, não uma garantia).
- O prompt precisa mudar junto com a proporção: em 16:9 o espaço vazio para o
  título fica nas laterais ou no terço inferior, não em cima.
- `templates-capa.json` teria de declarar composição por proporção, não uma só.

### 2. Tipografia com cara de PÔSTER DE FILME

**Hoje:** `arte.py` compõe só o **título**, em Anton/Bebas/Montserrat, com
posição e contraste declarados pelo template. É legível, mas é "título sobre
imagem", não pôster.

**Pedido:** estilo de capa de filme. Da referência que o dono passou (grade de
pôsteres de filmes de viking), o que caracteriza o formato:

- **Título no terço inferior**, não no topo — e ocupando a largura quase toda.
- **Serifada ou condensada em caixa alta**, com textura (metal desgastado,
  pedra, arranhado), não fonte chapada.
- **Tagline curta** acima ou abaixo do título — uma linha, menor, com tracking
  largo ("THE BATTLE HAS BEGUN", "YOU CAN'T ESCAPE YOUR FATE").
- **Bloco de créditos** no topo (nomes) e/ou *billing block* na base, em
  condensada pequena — é o que "faz o olho ler pôster".
- Paleta fria dessaturada com um ponto quente (fogo, pôr do sol).

Decisões abertas: de onde sai a **tagline** (o planner escreveria, como faz com
a descrição?), o que entra no bloco de créditos num projeto sem elenco, e se a
textura da fonte vem de arquivo (fonte já texturizada) ou de composição
(máscara sobre o texto).

### 3. O clipe termina com uma MENSAGEM

**Hoje:** o clipe acaba no último shot, com fade-out de 2s no áudio.

**Pedido:** um fecho, como fim de filme — no caso, **inema.club**.

A decidir: cartela estática ou animada, quanto tempo, se entra antes ou depois
do fade da música, e se é fixa para todo clipe ou declarada no `flow.json` (o
inemaccbot já tem o conceito de *clipe de CTA por variante* no promoavatar —
vale olhar antes de inventar outro).

### 4. Clipe: durações diferentes, e transição como CONEXÃO

**Hoje:** todo shot tem a mesma duração (`DUR_SHOT_PADRAO`) e a montagem é corte
seco entre todos.

**Pedido, com a correção do dono (2026-08-22):**

> *"transição não é apenas ter efeito, e sim fazer a CONEXÃO."*

Isso muda o alvo. Não é aplicar cross-fade porque corte seco cansa — é decidir
**como um plano entra no outro**: o que do fim do plano A justifica o começo do
plano B. Um match cut liga por forma ou movimento (o remo que vira espada, o
horizonte que vira lâmina); um corte no beat liga por música; um whip pan liga
por direção. Efeito escolhido no gosto é enfeite; conexão é montagem.

Consequência prática: a decisão de transição **pertence ao par de shots**, não ao
shot isolado — o contrato hoje não tem onde guardar isso. Um campo por shot
("como este entra") ou uma lista de ligações entre `n` e `n+1`.

- **Durações diferentes.** O contrato **já tem** `duracao_s` por shot; o planner
  é que distribui tudo parelho. É usar a liberdade que existe, não criar campo.
  Ritmo de corte é o que separa videoclipe de slideshow.

#### Como o planner pode ESTUDAR o que o analisevideo já mediu

Esta é a parte com achado concreto — **os dados existem e estão sendo jogados
fora no meio do caminho.**

O `analise.json` de cada vídeo real analisado já traz, em `montagem`:

```json
"tipos_de_transicao": ["corte seco", "whip pan de IA"],
"match_cut": false, "jump_cut": false,
"corte_no_beat": true, "uso_de_slowmo_speedramp": true,
"cortes_por_minuto": 22.3, "ritmo": "acelerado"
```

e ainda `pos_producao` (efeitos, `lut_sugerida`, `sound_design`) e
`narrativa.arco`.

Mas `referencias.resumir_para_contexto()` — a ponte que alimenta o planejador —
só repassa **look, paleta, movimentos, ritmo, cortes/min e bpm**. Tudo que diz
respeito a *como os planos se ligam* morre ali. O planner nunca viu a palavra
"match cut" vinda de um vídeo que funcionou.

Caminho, em ordem de esforço:

1. **Passar o que já existe.** Incluir `tipos_de_transicao`, `match_cut`,
   `corte_no_beat` e `slowmo/speedramp` no resumo enviado ao planner. É a
   mudança menor e provavelmente a de maior efeito: o planner passa a ter
   exemplo medido, não adjetivo.
2. **O `index.jsonl` é o gargalo — CONFERIDO em 2026-08-22.** Ele é uma projeção
   do `analise.json`, e os campos dele são exatamente:

   `bpm, canal, cortes_por_minuto, duracao_s, look, mood, movimentos, musica,
   paleta, quando, referencias, resumo, ritmo, slug, tags, tipo, titulo, url`

   **Nenhum campo de montagem ou transição.** Então não adianta só mexer no
   resumo: a ponte lê o índice e nunca abre o `analise.json` completo. Ou o
   indexador do analisevideo passa a projetar `montagem` (e `pos_producao`), ou
   a ponte passa a ler o arquivo completo das 3 referências escolhidas — que são
   poucas, o custo é baixo, e é onde o detalhe está.
3. **Dar ao contrato onde guardar a ligação** (campo de transição entre shots) e
   ao planner a instrução de justificá-la — "por que ESTE plano entra ASSIM".
4. **Só então a montagem** aplica. `montagem.py` hoje concatena.

**Cuidado registrado:** transição come duração. Um cross-fade de 1s por lado
encurta a soma dos shots, e "o clipe cobre a música inteira" é validado no
planner (`precisa_reajuste`). Mexer na montagem obriga a mexer lá — senão o
clipe fica mais curto que a faixa e o reajuste refaz a decupagem sozinho.

---

## Como usar este arquivo

Item que sair daqui vira commit e **sai da lista** (não fica marcado como
feito — o `git log` é que conta essa história). Item que se provar má ideia
fica, com o motivo: saber o que foi descartado vale tanto quanto a lista.

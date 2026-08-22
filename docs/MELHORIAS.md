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

### 4. Clipe: durações diferentes e produção mais elaborada

**Hoje:** todo shot tem a mesma duração (`DUR_SHOT_PADRAO`), e a montagem é
corte seco entre eles.

**Pedido:**
- **Durações diferentes por shot.** O planner já decide `duracao_s` por shot no
  contrato — o que falta é ele *usar* essa liberdade (hoje distribui parelho) e
  a montagem respeitar. Ritmo de corte é o que separa videoclipe de slideshow.
- **Efeitos e transições.** Corte seco em tudo achata o arco. Vale mapear o que
  o `analisevideo` já mede em vídeos reais (ritmo de corte, movimento de
  câmera) e usar como base, em vez de escolher no gosto.

Cuidado registrado: transição custa duração. Se um cross-fade come 1s de cada
lado, a soma dos shots deixa de bater com a faixa — e a regra de que **o clipe
cobre a música inteira** é validada no planner. Mexer aqui exige mexer lá.

---

## Como usar este arquivo

Item que sair daqui vira commit e **sai da lista** (não fica marcado como
feito — o `git log` é que conta essa história). Item que se provar má ideia
fica, com o motivo: saber o que foi descartado vale tanto quanto a lista.

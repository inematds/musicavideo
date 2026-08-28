# Melhorias pedidas — para depois

Backlog do dono, com data. **Nada aqui está implementado.** Quem for mexer:
leia o que existe hoje antes de propor, porque metade destes itens é ajuste no
que já está de pé, não construção nova.

---

## 2026-08-28 — miniatura pesada na grade do painel

**Hoje:** o card usa a capa INTEIRA como miniatura (`capa.png` / `capa-vN.png`,
~1,2 MB cada, 1024px). Com 45 produções e duas faixas por produção, a grade
pede dezenas de megabytes de PNG para desenhar quadradinhos de ~260px — e a
vitrine puxa isso do HF, não do disco local.

**A rever:** gerar uma miniatura pequena por capa (ex.: `capa-thumb.jpg`, 400px,
qualidade 80) e apontar o card para ela, deixando o PNG inteiro só para o clique
"abrir em tamanho real" e para o modal. `loading=lazy` já está lá — o problema
não é quando carrega, é o tamanho de cada uma.

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

### 2. ~~Tipografia com cara de PÔSTER DE FILME~~ — FEITO em 2026-08-22

Saiu: `arte.compor_poster` (degradê na base, tagline, título no terço inferior,
filete, billing block) + **selo de VERSÃO** grande, porque o Suno entrega duas
faixas e capa sem marca faz escolher no chute. O template declara `estilo`
(`poster` nos de cena, `simples` onde a imagem já É o título), e a tagline vem
de `capa.tagline`, escrita pelo planejador.

**O que ficou de fora, e é o próximo passo natural:** a fonte. Usamos Bebas Neue
porque é a condensada que existe na máquina — não há serifada de cartaz (Cinzel,
Trajan) instalada, e instalar exige o dono. Com uma serifada texturizada isso
sobe bastante. Também ficou fixa a posição da tagline (na 16:9 ela pode encostar
no sujeito) — o certo é escolher a faixa mais vazia.

### 3. O clipe termina com uma MENSAGEM

**Hoje:** o clipe acaba no último shot, com fade-out de 2s no áudio.

**Pedido:** um fecho, como fim de filme — no caso, **inema.club**.

A decidir: cartela estática ou animada, quanto tempo, se entra antes ou depois
do fade da música, e se é fixa para todo clipe ou declarada no `flow.json` (o
inemaccbot já tem o conceito de *clipe de CTA por variante* no promoavatar —
vale olhar antes de inventar outro).

### 4. Clipe: durações diferentes, e transição como CONEXÃO
> **PARCIALMENTE FEITO em 2026-08-23** — ritmo (`--ritmo`, default `auto`), a
> ponte passando a `montagem` medida ao planner, e o núcleo de 12s medido na
> onda. **Falta a transição** (campo de ligação entre shots + re-encode):
> `concat_ffmpeg` ainda é `-c copy`, então corte seco é tudo que existe.

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

## 2026-08-27 — FICHA DO PERSONAGEM CANTOR (pedido do dono)

**Hoje:** o cantor nasce e morre dentro de uma produção. O planejador escreve
`capa.prompt_imagem` e os `prompt` de cada shot da decupagem a partir da
solicitação daquele pedido — e mais nada atravessa para o pedido seguinte. Duas
produções do mesmo "personagem" só se parecem por coincidência de adjetivo, e é
por isso que os slugs longos (`woman-young-tall-black-slender-elegant-s`,
`woman-yung-tall-black-slender-elegant-st`) são quase o mesmo texto digitado
duas vezes: a descrição do personagem está sendo redigitada a cada produção.

**Pedido:** uma **ficha** do personagem cantor, com **fotos** e com as
definições **de texto e de imagem**, para que toda música feita com ele herde as
mesmas características. Com **código, nome e o resto** — ou seja, o personagem
passa a ser uma entidade citável, como o `MVD#N` é para a produção.

### O que já existe e serve

- **`data/estilos.json`, `templates-capa.json`, `templates-clipe.json`** já são
  exatamente esse tipo de dado: catálogo versionado (`schema_version` +
  lista) que o planejador consulta. Uma ficha de personagem cabe no mesmo
  formato — é um quarto catálogo, não uma invenção estrutural.
- **A numeração estável** (`src/mvd.py`) resolve o "dar um código a ele" com um
  padrão já testado: número atribuído uma vez, gravado, que nunca muda. Vale
  reler antes de inventar outro esquema de id.
- **A skill `inemaref-folder`** já monta folder de personagem com
  `referencia.json` (e o `inemaref-quadrinho` consome esse folder). Antes de
  desenhar o formato daqui, olhar o de lá: personagem que existe em dois
  formatos diferentes na mesma casa é o começo de uma divergência.
- **`arte.py`** já compõe pôster com selo de versão a partir da imagem gerada —
  a ficha não precisa refazer a camada de tipografia.

### O que falta decidir antes de codar

1. **Onde a ficha mora.** Catálogo no repo (`data/personagens.json`, versionado,
   viaja com o código) ou pasta por personagem no acervo (`~/projetos/output`,
   junto das fotos)? As fotos empurram para o acervo; a citação em plano
   empurra para o repo. Provável: ficha no repo, fotos no acervo, com a ficha
   apontando para elas.
2. **O que é "definição de imagem" — RESPONDIDO em 2026-08-27, consultando o
   provedor.** A dúvida era se a Agnes (motor de graça e default) aceita
   referência de personagem, porque disso dependia a ficha entregar consistência
   de verdade ou só descrição parecida. **Aceita**, e o projeto irmão
   `~/projetos/videos-agnes` já usa isso em produção há semanas. Os fatos
   medidos estão em `~/projetos/agnes-nei/NOTAS-API.md` §5, e valem mais que
   qualquer decisão de gosto:

   | fato | consequência para a ficha |
   |---|---|
   | campo é `extra_body.image` (array); os outros nomes são descartados em silêncio | o adaptador daqui **não passa nada** — `_gerar_imagem` monta só `model`/`prompt`/`size` |
   | aceita 1–5 refs, mas o teto **ÚTIL é 2** | a ficha guarda muitas fotos e **manda no máximo 2** |
   | **5 refs QUEBRAM**: confete de pixels e o prompt é ignorado — 16 imagens saíram assim, **todas com HTTP 200** | o status não sabe se a imagem presta; um teto no código, não na disciplina |
   | 1 ref **não** preserva identidade; 2+ preservam | uma foto só é pior que parece — é o caso que engana |
   | máx. 10 MB por imagem; `ratio` é ignorado (cai em 1:1) — usar `size` em pixels | a ficha guarda a foto já no formato que o provedor aceita |
   | img2img é **2× mais rápido** que text2img (23–27s vs 56s) | usar a ficha é mais barato em tempo, não mais caro |
   | `/v1/images/edits` existe (não documentado); `/v1/images/variations` → 501 | não inventar endpoint sem medir |

   **E o método já está resolvido lá:** *model sheet se DERIVA, não se gera em
   paralelo*. Gerar N vistas com text2img dá N personagens diferentes (text2img
   não trava identidade). O certo é **uma âncora-mãe em text2img e as outras
   vistas derivadas dela por img2img**. Preço registrado: a preservação de
   composição puxa as vistas para a pose da mãe, então o model sheet sai com
   pouca variedade de ângulo.

   Fica então: a ficha tem **texto** (portátil entre provedores) **e fotos**
   (consistência real onde o motor aceita), e o adaptador de cada provedor
   decide o que usar — como já se faz com resolução e negativo.

   **E não é só a Agnes:** o Wan 2.7 (Alibaba) aceita `first_frame`/`last_frame`
   como âncora do plano e `driving_audio` para lip sync — levantado em
   `WANVIDEO.md`. Reforça a decisão acima: a ficha guarda texto E fotos, e cada
   adaptador pega o que o seu motor entende.
3. **Como o plano cita o personagem.** O contrato é FECHADO (`esquemas.py`:
   campo desconhecido = erro), então um `personagem: "PSG#3"` no topo do plano
   exige tocar `validar_plano` junto. E é preciso decidir se o personagem
   *substitui* trechos do `prompt_imagem`/dos shots ou se é *prefixado* a eles —
   substituir dá consistência e tira liberdade do planejador; prefixar mantém a
   liberdade e arrisca contradição ("cabelos prateados" na ficha, "morena" no
   shot).
4. **Personagem por produção ou por shot.** Um clipe pode ter mais de uma
   pessoa em cena. Começar por UM cantor (o sujeito da capa e do refrão) é o
   recorte honesto; elenco vem depois, se vier.

**Onde o conhecimento da API mora, e por quê isto importa:** nada disso está no
código deste repo — está em `~/projetos/agnes-nei/NOTAS-API.md` (medições) e em
`~/projetos/videos-agnes/pipeline.py` (uso em produção). O `providers/agnes.py`
daqui já aponta para esses dois no cabeçalho. **Antes de escrever o formato da
ficha, consultar o provedor**: a forma da ficha é consequência do que a API
aceita, não o contrário.

**Cuidado registrado:** a ficha só vale se o planejador **for obrigado** a usá-la.
Um campo opcional que o prompt "pode considerar" produz o que já temos — descrição
parecida e resultado diferente. E o defeito de 2026-08-25 (garatuja de texto na
capa) mostra que prompt de imagem só deve chegar ao provedor por um caminho
único e sanitizado: a ficha entra nesse caminho, não por uma porta nova.

---

## Como usar este arquivo

Item que sair daqui vira commit e **sai da lista** (não fica marcado como
feito — o `git log` é que conta essa história). Item que se provar má ideia
fica, com o motivo: saber o que foi descartado vale tanto quanto a lista.

#### Análise técnica do item 4 (2026-08-22) — o que trava, e em que ordem sai

Levantamento no código, não no palpite. Cada eixo: **o que existe → o que falta
→ menor mudança → custo.**

**a) Durações variáveis — o contrato já permite; quem achata é o planner.**
`DUR_SHOT_PADRAO = 5` (planner.py:17) entra em dois lugares: no prompt inicial
(`~N shots de 5s`, l.92) **e no reajuste pós-faixa** (`_reajustar`, l.388–405),
que recalcula `alvo_shots = duração/5` depois que a música real chega. Mexer só
no prompt não resolve: o reajuste re-achata o ritmo. Teto físico por shot:
441 frames @24fps = **18,4s** (`agnes.num_frames_para`). Invariante a manter:
`soma(duracao_s) ≈ duração da faixa`. Custo: US$ 0 (prompt + planner).

**b) Transição com efeito — hoje é impossível por construção.**
`agnes.concat_ffmpeg` junta com `-c copy`. Sem re-encode não existe xfade,
whip, dissolve — só corte seco. Duas consequências: (1) qualquer efeito exige
re-encode do trecho; (2) todo overlap **consome duração dos dois planos**, então
o cross-fade encurta o clipe e desloca a sincronia — a compensação tem de entrar
no cálculo, não depois. E a validação é FECHADA (`esquemas.py`: campo
desconhecido = erro): o campo de ligação entre `n` e `n+1` exige tocar
`validar_plano` junto. Custo: CPU local, minutos.

**c) Corte no beat.** O `bpm` já está no plano e nas referências. Barato:
quantizar `duracao_s` a múltiplos de `60/bpm` — sem dependência nova, sem custo.
Caro e certo: detectar o beat do MP3 (librosa/aubio) e ancorar os cortes na
grade real — dependência nova, US$ 0, e só faz sentido depois de (a).

**d) Ponte de referências.** Endossado o passo 1 já descrito acima (repassar
`tipos_de_transicao`, `match_cut`, `corte_no_beat`, `slowmo/speedramp`): é a
mudança menor de maior efeito, porque troca adjetivo por exemplo medido.

**e) CUSTO — dinâmica custa TEMPO, não dinheiro.**
Na Agnes o dólar é zero; o custo real é parede. Rate limit de 5 req/min (sleep
de 12s entre shots) + fila: ~36 shots de 5s para 180s ≈ as **4h** já vividas.
Ritmo mais picado (média 3s) ≈ 60 shots ≈ **+60–70% de horas**, e mais exposição
a fila cheia e a shot barrado. Em provedor pago por segundo o dólar **não muda**
com o ritmo: `custo.estimar_partes` soma `duracao_s`, e a soma continua sendo a
duração da música. Cortes curtos ⇒ mais chamadas, mesma metragem.

**Ordem recomendada:**
1. durações variáveis + repasse da montagem nas referências (só prompt/planner,
   US$ 0, sem tocar em render);
2. campo de ligação por par de shots + render com efeito só onde declarado
   (re-encode localizado, compensando o overlap na sincronia);
3. beat-grid do áudio.

**Boa prática, e coerente com a correção do dono:** corte seco no beat é o padrão
de videoclipe profissional; efeito entra quando ele É a conexão (troca de seção,
speedramp, match cut de movimento), nunca como enfeite distribuído.


## 2026-08-25 — o que ficou aberto depois do MVD "Stay" (Kling)

- **Boca cantando: RESOLVIDO no prompt** (planner + reajuste). A regra é não
  descrever a boca; o canto se lê no corpo. Os clipes JÁ gerados continuam com
  o defeito — refazer é gerar de novo, então fica para quando valer a pena.
- **O Wan 2.7 tem lipsync POR DENTRO — ver `WANVIDEO.md` (2026-08-27).** O
  `driving_audio` do `wan2.7-i2v` dirige o vídeo pelo áudio, e o exemplo da
  própria doc é um personagem cantando em sincronia. Resolveria este item e o da
  boca acima de uma vez — mas é provedor PAGO e sem preço nem rate limit
  medidos, então é candidato, não decisão.
- **Lipsync existe, mas por fora.** O CLI do Kling só tem t2i/i2i/t2v/i2v. A
  Magnific tem 6 modelos, 3 aceitam VÍDEO como fonte (`lipsync-2.0`,
  `veed-sync-2-v2v`, `latentsync`) — dá para aplicar em cima de um plano já
  gerado. O empecilho é ÁUDIO: lipsync quer voz isolada e o que existe é a
  mixagem. Sem demucs instalado, o caminho honesto é testar em UM plano de
  refrão antes de decidir.
- **Preço medido do Kling direto (2026-08-25):** 5s = 25 créditos em 1080p,
  10s = 50; em 720p a tomada de 10s saiu por 30. O plano de 44 planos custaria
  ~1.400 em 1080p; as 20 tomadas de 10s em 720p custaram **600** (675 com as
  duas de teste). Reduzir a duração dos planos NÃO economiza — um plano de 3s
  paga uma geração de 5s. O que economiza é: menos gerações, menor resolução,
  e cortar/reaproveitar o que já foi gerado.
- **Créditos do Kling expiram:** 3.000/mês que não são gastos, são perdidos.
  Isso inverte a lógica de economia — o caro é NÃO usar.


## 2026-08-25 — DUAS FAIXAS = DUAS PRODUÇÕES (pedido do dono)

**Hoje:** o Suno entrega duas faixas; o pipeline monta `clipe-1.mp4` e
`clipe-2.mp4` (mesmo vídeo, trilhas diferentes), mas só UMA vira produção: a
faixa aprovada vira `clipe.mp4`, e é ela que aparece no painel como a peça e é
ela que vai no pacote de canal. A segunda faixa existe no disco e morre ali.

**Pedido:** cada faixa é uma MÚSICA DIFERENTE — logo, uma produção diferente.
As duas têm que aparecer **no painel** e **subir no YouTube**, cada uma com a
sua capa. O que elas compartilham é só o material de vídeo.

Do que já existe e serve:
- `capa-v1.png` / `capa-v2.png` já são geradas com selo de versão, uma por
  faixa (foi o motivo de o selo existir).
- `montar_todas` já monta um clipe por faixa.
- O painel já lista `versoes[]` por trilha — o que falta é tratá-las como
  **peças**, não como variantes de uma peça.

O que falta decidir/fazer:
1. O pacote de canal (`montar_publicacao`) monta UM clipe. Precisa montar um
   por faixa, com título/descrição próprios (ou o mesmo título com marca de
   versão) e a capa correspondente.
2. O `index.jsonl` e o painel tratam slug = peça. Duas peças no mesmo slug
   exigem ou um sufixo (`<slug>-f1`, `<slug>-f2`) ou o card virar duas peças.
3. Título no YouTube: duas faixas com o mesmo nome competem entre si. Precisa
   de diferenciação (v1/v2, ou títulos escritos pelo planejador para cada uma).

### E a ideia que vale mais que a duplicação

> *"até podemos pensar que o videoclipe pode ser montado de forma diferente com
> os mesmos shots feitos."*

Isso já é possível HOJE, e de graça: o `recorta` monta ritmo diferente sobre o
mesmo material, e o `ritmo-kling` mostrou que dá para tirar 44 planos de 20
tomadas cortando em pontos diferentes. Então a segunda faixa não precisa levar
o MESMO clipe — pode levar **outra montagem do mesmo material**: outra ordem,
outro ritmo, outros trechos das mesmas tomadas.

Duas peças que dividem o custo de geração e não parecem a mesma coisa. É o
melhor uso do material já pago, e não depende de crédito nenhum — só de corte.

Ponto a resolver: as faixas têm durações diferentes (185s e 191s no MVD
gaúcho), então cada montagem tem seu próprio total — que é justamente o que o
`recortar(total_s=...)` já sabe fazer.

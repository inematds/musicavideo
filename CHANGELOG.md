# CHANGELOG

Semver `vX.XX.YY`: patch incrementa o último; recurso incrementa o do meio e
carrega o último; major zera o resto.

## 2.3.1 — 2026-08-28

- **Todo card mostra o MVD.** Onze produções estavam sem número: `numerar_acervo`
  só roda no `reindex`, e quem nasceu depois do último ficou sem. Rodado — e as
  cinco que apareciam sem `MVD#` no fim da vitrine agora têm o seu.
- **Derivado herda o número de quem o gerou.** Recorte e variante (`-variado`,
  `-dinamico`) não são produção nova e não ganham número próprio — a sequência
  contaria recortes, não músicas —, mas apareciam sem nada. Agora mostram o
  `MVD#` do pai, ao lado do rótulo da variante.
- Derivado passa a nascer com selo de nuvem (`local`) e com miniatura, como
  qualquer outro card.

## 2.2.1 — 2026-08-28

- **Miniatura de verdade no card.** A grade desenha ~260px e vinha puxando a
  capa inteira — 1024px de PNG, ~1,2 MB por faixa. Agora cada capa ganha uma
  `-thumb.jpg` (480px, JPEG q78: 1,2 MB viram ~30 KB) e é ela que o card pede,
  no painel e na vitrine. A capa cheia continua subindo e continua sendo o que
  o detalhe, o poster do vídeo e o "abrir em tamanho real" mostram.
- As miniaturas são feitas na hora de publicar (`arte.garantir_miniaturas`) e
  só refeitas quando a capa é mais nova que elas.

## 2.1.1 — 2026-08-28

- **Clicar em uma faixa mandava as duas.** O botão do painel dispara
  `publica-hf <slug>`, e o alvo nomeado montava o pacote com `arquivos_de` — a
  pasta inteira. Ele existe para ignorar o filtro de "já subiu e não mudou",
  nunca a escolha de faixa. Agora nomear um slug reenvia só as faixas
  aprovadas (`arquivos_a_subir(..., forcar=True)`).

## 2.1.0 — 2026-08-28

- **A vitrine passa a ser escolhida faixa a faixa.** O Suno entrega duas músicas
  por pedido, e elas são músicas diferentes: aprovar a produção obrigava a levar
  as duas — ou nenhuma. A marca de nuvem agora mora em `nuvem.faixas.<n>`, com
  `aprovado`/`publicado_em`/`remover` por faixa; o bloco de topo continua sendo
  escrito como resumo, para quem só sabe perguntar pela produção.
- **O botão saiu de dentro do modal e foi para a capa do card.** O card já é uma
  faixa desde a v1.6.0; o selo `☁` virou o gesto. Subir (ou tirar) é um clique
  na grade, sem abrir nada. No modal, cada música ganhou o seu botão e o do
  rodapé agora diz o que faz: "subir as duas faixas".
- **O reenvio deixa de olhar mtime e passa a olhar a faixa.** `publicado_em` era
  da produção: aprovar a segunda faixa depois da primeira ter subido não mudava
  nada no disco, e ela nunca subia. `publicahf.arquivos_a_subir` responde por
  faixa, e `subida.proxima` pergunta a ele em vez de ao carimbo do topo.
- **Tirar uma faixa de duas não apaga a pasta na nuvem** — some o arquivo dela
  (`delete_file`), e o manifesto deixa de listá-la. A pasta só sai quando não
  resta faixa nenhuma lá fora.
- Estado antigo (`aprovado: true`, sem `faixas`) é lido como "todas as faixas":
  o acervo já publicado continua na vitrine sem migração.

## 2.0.0 — 2026-08-28

- **A versão do repo alcança a linha 2.x.** O painel e a vitrine já eram a segunda
  geração do projeto; só o marcador em `src/versao.py` tinha ficado na 1.7.0.

## 1.7.0 — 2026-08-27

**Recursos**

- **"Subir para a nuvem" agora SOBE.** O botão prometia uma ação e fazia outra:
  marcava a produção e parava ali. Quem subia era o `publica-hf`, à mão — e com
  o cron retirado na v1.3.0 nada rodava sozinho, então o card ficava em
  `aprovado` para sempre. Agora o clique dispara a publicação **daquela
  produção** em segundo plano, e o card mostra `☁ subindo…` pulsando até
  terminar. A grade se atualiza sozinha enquanto houver algo subindo.
- **A fila se esvazia sozinha.** Nada subindo + alguém aprovado = começa.
  Uma subida por vez, com trava em arquivo — dois uploads de gigabytes
  concorrendo só multiplicam banda e confusão. Aprovar é consentimento
  explícito para subir; drenar a fila não inventa decisão nenhuma.

**Correções encontradas testando isto**

- **Zumbi contava como "subindo".** O painel é o pai do processo de upload e
  nunca o colhia: terminado, ele virava zumbi, seguia em `/proc` e o
  `os.kill(pid, 0)` respondia que estava vivo. O selo `subindo…` ficaria
  pulsando para sempre numa subida concluída — foi o que aconteceu com o
  MVD#124, já publicado no HF. Agora o estado é lido de `/proc` e o filho é
  colhido, o que resolve as duas coisas de uma vez.
- **A fila apontava para pasta inexistente.** `subida.proxima(base /
  "musicavideo")` com `base` já sendo o acervo — e o `except OSError` que
  protege o painel de acervo ausente engolia o erro em silêncio, então a fila
  simplesmente nunca começava. Tem teste agora.

## 1.6.0 — 2026-08-27

**Recursos**

- **O painel V1 adota o formato do V2: uma música, um card.** O Suno entrega
  duas faixas por pedido e cada uma é uma música diferente — mesma letra, mesmo
  material de vídeo, outra interpretação. Elas viviam empilhadas dentro de um
  card só, o que obrigava a escolher antes de ouvir. Agora cada faixa tem o seu
  card, com o selo da versão e um selo **▶ clipe** quando há vídeo. A barra
  mostra `N músicas · M produções`, porque os dois números importam aqui.
- **As AÇÕES continuam sendo da produção.** Lixeira e "subir para a nuvem"
  operam sobre a PASTA, e por isso seguem no modal: o card é a peça, a pasta é a
  unidade de trabalho. Clicar num card abre a produção **já na aba daquela
  faixa** — comparar as duas continua a um clique.
- **♥ por faixa.** A vitrine conta curtida por versão (`MVD#113:1`); o painel
  passa a ler essa chave, com a da produção como reserva para o acervo antigo.
- **A nuvem virou selo NA CAPA**, não pill no corpo: "já subiu ou não?" é a
  pergunta que se faz varrendo a grade com o olho, e ler uma pill lá embaixo
  custa uma parada por card. Os quatro estados aparecem — `☁ na nuvem` em âmbar
  cheio, `☁ aprovado` em contorno, `☁ sai` em vermelho e `☁ local` apagado mas
  **legível**, porque "não foi" é metade da resposta que o selo dá.

**Correção**

- **`MVD-031` → `MVD#124`.** A última produção com número local adotou o do bot.
  A primeira tentativa não pegou porque escrevi o `estado.json` direto, por fora
  do `salvar_estado`, e o arquivo foi sobrescrito por um processo que tinha o
  estado antigo em memória. Escrito pelo caminho oficial, ficou — e sobrevive ao
  `reindex`.

## 1.5.0 — 2026-08-27

**Correção que muda dado**

- **O número exibido é o do bot, mesmo depois de renumerar.** A v1.2.0 fez o
  acervo adotar o `MVD#N` do `inemaccbot`, e o disco obedeceu: 30 das 31
  produções já tinham `MVD#NNN` no `estado.json`. Só que painel e vitrine liam o
  número do `index.jsonl` — que só é reescrito por quem mexe em estado ou por um
  `reindex`. O resultado é que a renumeração ficou invisível: a vitrine seguiu
  mostrando `MVD-013` enquanto o disco já dizia `MVD#113`. Agora `coletar` lê o
  `mvd` do `estado.json`, que é a fonte de verdade, com o índice apenas como
  reserva.
- **A última pasta com número local adotou o do bot**
  (`uma-garota-rebelde-provocante-nada-sensu`: `MVD-031` → `MVD#124`). Ela
  escapou porque `atribuir` nunca renumera quem já tem número — invariante que
  continua valendo, e é por isso que a adoção foi um gesto explícito, não
  automático. As 27 produções da vitrine agora exibem o número do bot.

## 1.4.0 — 2026-08-27

**Correção que muda comportamento**

- **O `publica-hf` sobe o que falta, não o acervo inteiro.** `nuvem.pendentes`
  devolve tudo que está *aprovado* — publicado ou não — e a docstring dizia "que
  ainda não subiram". Não era verdade: cada passada relia 27 produções e 4,13 GB
  do disco para reenviar o que já estava idêntico no HF, gastando ~20 minutos
  para não mudar nada. É também o motivo real de o cron de meia em meia hora ser
  caro. Agora `publicahf.a_subir` tira quem já subiu e não mudou, comparando o
  mtime dos arquivos **finais** com o `publicado_em` — o `estado.json` fica de
  fora da conta de propósito, porque `marcar_publicado` reescreve ele *depois*
  de carimbar a hora e ele faria toda produção parecer mudada para sempre.
  Medido no acervo real: **4,13 GB → 0,31 GB**. Carimbo ilegível sobe em vez de
  adivinhar, e `publica-hf <slug>` continua ignorando o filtro — é como se força
  o reenvio.

## 1.3.0 — 2026-08-27

**Recursos**

- **Publicar é um comando só.** O `publica-hf` não para mais no meio: depois de
  subir o acervo e escrever o `manifest.json` no repo da vitrine, ele **commita
  e empurra**. Antes o arquivo certo ficava parado no repo local e a vitrine
  continuava desenhando o manifesto anterior — foi assim que 7 produções
  ficaram no HF e fora do manifesto. Manifesto igual ao versionado não vira
  commit vazio; app sem repo git é aviso, não falha.
- **O painel V1 sobe sozinho.** `musicavideo-painel.service` (systemd do
  usuário, `Restart=always`, com `linger` ligado) serve o painel na LAN em
  `:5400` a partir do boot. Ele é a bancada de trabalho: ficar fora do ar por
  esquecer de rodar o comando era o defeito.

**Retirado**

- **`cron-nuvem.sh`.** A ideia era que aprovar fosse o único gesto, com um cron
  subindo o aprovado de meia em meia hora. Ele nunca fechou o ciclo — parava
  antes do `git push` do manifesto — e nunca chegou a ser instalado no
  `crontab`. Em vez de somar um elo a uma varredura cega, o elo foi para dentro
  do `publica-hf`, que roda quando você sabe que mudou algo.

**Correção**

- **Pedir ajuda não executa.** `publica-hf --help` não mostrava ajuda: começava
  a publicação real de 27 produções / 4,13 GB. Cada `_cmd_*` faz parsing solto
  (`"--x" in args`) e ignora flag desconhecida, e o `main()` só olhava `-h` na
  posição 0 — a flag virava um `publica-hf` sem alvo. Agora `-h`/`--help` em
  qualquer posição imprime o uso e sai.

## 1.2.0 — 2026-08-27

**Correção que muda dado**

- **O número da produção passa a ser o do bot.** O `inemaccbot` já numerava os
  fluxos como `MVD#122` — é o que aparece no Telegram, no `/aprovar MVD#N` e nas
  linhas de FALHAS deste repo. A numeração própria (`MVD-001…031`) criava dois
  "MVD 25" falando de produções diferentes, que é o oposto do que um
  identificador serve. Agora o acervo adota o id do fluxo que gerou a pasta
  (casando pelo prefixo do slug, porque o bot guarda o slug inteiro e a pasta
  usa os 40 primeiros caracteres) e só inventa número — acima do topo do bot —
  para o que nasceu fora dele. Reprocessamento (`...-2`) não divide o número da
  pasta original: material diferente, número diferente.
- **A segunda faixa do Suno não se perde mais** (ver abaixo).

## 1.1.0 — 2026-08-27

**Recursos**

- **`MVD-000`**: número estável por produção, atribuído uma vez na ordem de
  criação e gravado no `estado.json`. Visível no painel, aceito na busca e no
  lugar do slug nos comandos. Número apagado não volta (contador de teto).
- **Nuvem**: `nuvem` aprova a subida (ou o botão "subir para a nuvem" no card),
  `publica-hf` leva o acervo aprovado para o Hugging Face e escreve o manifesto
  no repo da vitrine, `likes` traz as curtidas de volta, `cron-nuvem.sh` faz
  isso sozinho.
- **Capa própria por versão**: da versão 2 em diante o `inemaimg` gera uma
  imagem só dela, com o mesmo prompt — antes as duas capas eram a mesma imagem
  com o selo trocado.
- **Painel**: as duas capas com os dois players já na grade; no card aberto, as
  versões empilhadas (capa → música → clipe) e um expansível com os prompts que
  foram para os provedores. Nome e versão no topo.

**Correções**

- **A segunda faixa não se perde mais.** Sair no `FIRST_SUCCESS` deixava para
  trás a segunda música do Suno — gerada e paga do mesmo jeito, com URL que
  expira. Agora espera o `SUCCESS` (com teto de 5 min).
- Capa de versão saía com garatuja de texto: o prompt ia cru para o flux, sem o
  `prompt_sem_tipografia` que já existia.
- Namespace do Hugging Face é `Inematds` (maiúsculo), não o login do GitHub.
- URL do painel nasce com `musicavideo/` na frente: a reescrita para o HF
  ignorava esse prefixo e a vitrine mostrava capa quebrada.

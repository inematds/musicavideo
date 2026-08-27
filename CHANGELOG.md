# CHANGELOG

Semver `vX.XX.YY`: patch incrementa o último; recurso incrementa o do meio e
carrega o último; major zera o resto.

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

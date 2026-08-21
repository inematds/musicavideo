# Falhas

Uma linha por falha real. Mais recente no topo.

| data | o que quebrou | menor correção | prompt \| infra |
|---|---|---|---|
| 2026-08-21 | troquei o motor do clipe para kling por conta própria quando a Agnes caiu, e queimei 105 créditos da conta do dono sem ordem dele | portão no código: `--motor` para kie/kling/fal exige `--autorizo-pago` (instrução em prosa não segura ninguém) | prompt |
| 2026-08-21 | `--motor clipe=kling:...` num plano nascido na Agnes morria: o adaptador mandava `1312x736` onde o kling só aceita `720p`/`1080p` | `_resolucao_kling` traduz WxH → rótulo; o plano guarda o vocabulário do motor ANTIGO, e traduzir é papel do adaptador | infra |
| 2026-08-21 | **diagnóstico errado**: 404 no poll da Agnes foi lido como "provedor fora do ar". As duas tasks abortadas tinham COMPLETADO em 73s — vídeo gerado e jogado fora, e a conclusão levou a trocar de motor e gastar crédito à toa | o adaptador insiste no 404 até o timeout de 15 min (a task só demora a aparecer no endpoint de status); erro que não é 404 continua abortando | infra |
| 2026-08-21 | fase `capa-clipe` do bot morreu sem contrato: o render de 43 shots passa do timeout de 10 min da ferramenta do agente, ele destacou o processo (proibido no prompt) e o job levou a árvore junto | nenhuma ainda — render longo em fase de agente é o defeito estrutural; anotado como pendente | infra |
| 2026-08-21 | fluxo travou com a faixa PAGA e nada gerado: a fase deixou `musica` em `revisao` e a fase seguinte recusou, certa, porque `pronto` é pré-requisito — um segundo portão, invisível no chat | as fases promovem (`aprova` sem `--faixa`, `ok capa/clipe`); o portão humano é o do bot (`adfcdf4`) | prompt |
| 2026-08-21 | Suno recusou a geração: `prompt_estilo` citava artista ("Wardruna meets anthem rock"). Erro que só aparecia na hora de gastar | `campos_prompt_en` recusa nome de artista e construção comparativa no plano (`376b753`) | prompt |
| 2026-08-21 | `PLANO.md` não foi gerado: `' · '.join` sobre `musica.estrutura` vinda como lista de dicts (TypeError) — depois de o plano já estar em disco | `_estrutura_txt` aceita string e dict; o schema pedido ao modelo passou a dizer a forma | prompt |

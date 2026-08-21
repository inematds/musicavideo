# Falhas

Uma linha por falha real. Mais recente no topo.

| data | o que quebrou | menor correção | prompt \| infra |
|---|---|---|---|
| 2026-08-21 | fluxo travou com a faixa PAGA e nada gerado: a fase deixou `musica` em `revisao` e a fase seguinte recusou, certa, porque `pronto` é pré-requisito — um segundo portão, invisível no chat | as fases promovem (`aprova` sem `--faixa`, `ok capa/clipe`); o portão humano é o do bot (`adfcdf4`) | prompt |
| 2026-08-21 | Suno recusou a geração: `prompt_estilo` citava artista ("Wardruna meets anthem rock"). Erro que só aparecia na hora de gastar | `campos_prompt_en` recusa nome de artista e construção comparativa no plano (`376b753`) | prompt |
| 2026-08-21 | `PLANO.md` não foi gerado: `' · '.join` sobre `musica.estrutura` vinda como lista de dicts (TypeError) — depois de o plano já estar em disco | `_estrutura_txt` aceita string e dict; o schema pedido ao modelo passou a dizer a forma | prompt |

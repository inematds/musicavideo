# Lip Sync com Kling (testes em Stay)

Anotações para continuar os testes de deixar a cantora do clipe cantando de verdade.
A ideia é sincronizar a boca com a voz da música pela assinatura Kling AI do Nei.
Os primeiros testes foram feitos em 09 e 10/10/2026, na música **Stay** (`~/projetos/output/musicavideo/stay-kling/`).

## Por que pelo site

- A CLI `kling` e o MCP não aceitam áudio de entrada: não têm lip-sync nem avatar.
- O Lip Sync existe só no site: `https://kling.ai/app/lip-sync/new`. O Avatar fica em `/app/ai-human/new`.
- Ele roda pela assinatura (créditos da conta), por meio de um Chromium com o login do Nei. Nenhuma API é usada.

## Preparar o navegador

O perfil `~/.cache/inemaccbot/perfil-kling` já está logado (login feito pelo Nei em 09/10/2026).

Antes de subir, confira se a porta 9333 está livre com `ss -ltn | grep 9333`. Depois:

```bash
rm -f ~/.cache/inemaccbot/perfil-kling/Singleton{Lock,Cookie,Socket}   # se sobrou trava de execução anterior
DISPLAY=:99 nohup ~/.cache/ms-playwright/chromium-1248/chrome-linux-arm64/chrome --no-sandbox \
  --user-data-dir=$HOME/.cache/inemaccbot/perfil-kling --remote-debugging-port=9333 \
  --password-store=basic --no-first-run --no-default-browser-check --window-size=1400,950 \
  https://kling.ai/app/lip-sync/new >/dev/null 2>&1 &
```

- Sem `--password-store=basic` o Chromium fica parado e não abre a porta.
- A tela `:99` (Xvfb do `explicavideos-display`) funciona. A janela no RDP (`:10`) deixou de renderizar screenshots.
- `node docs/lipsync-kling/kling_shot.mjs /tmp/x.png` tira uma foto da aba, para conferir.
- Se o login vencer, abra a janela na tela do Nei e peça a ele que entre na conta.
- No fim, mate o PID do Chromium numa chamada separada.

## Passo a passo

1. **Voz isolada** (demucs htdemucs na GPU, usando o venv do inemavox):

   ```bash
   P=<pasta com demucs==4.0.1 instalado por pip --target, sem deps>
   systemd-run --user --scope -p MemoryMax=16G env PYTHONPATH=$P \
     ~/projetos/inemavox/venv/bin/python docs/lipsync-kling/sep_vocals.py faixa.mp3 vocals.wav inst.wav
   ```

   - O demucs 4.1.0 exige `sphn`, que não compila nesta máquina. Use a 4.0.1.
   - O `sep_vocals.py` grava com soundfile, porque o torchaudio pede torchcodec.
   - Não use `python -I`: ele ignora o PYTHONPATH.

2. **Achar os cortes reais do clipe montado.**

   O `clipe.mp4` NÃO segue as 20 tomadas de 10 s do `plano.json`. Ele segue a montagem do `ritmo-44.json`: 44 cortes de 2 a 12 s, e a mesma tomada volta várias vezes.

   ```bash
   ffmpeg -i clipe.mp4 -vf "select='gt(scene,0.12)',showinfo" -an -f null - 2>&1 | grep -o "pts_time:[0-9.]*"
   ```

   Depois, tire um quadro a cada 2 s e veja em quais cortes o rosto dela aparece cantando.

   - Fora: plano geral pequeno, perfil e olhos fechados.
   - O áudio do clipe começa junto com a faixa (offset 0, medido).

3. **Cortar os trechos** do próprio clipe, com a voz do mesmo intervalo:

   ```bash
   bash docs/lipsync-kling/cortar.sh clipe.mp4 vocals.wav <dir> 0:2 2:12 21:29 ...
   ```

4. **Enviar ao Kling.** O script confere o custo mostrado no botão antes de clicar:

   ```bash
   node docs/lipsync-kling/kling_lote.mjs <dir> 05:5 06:5 08:10 ...   # nn:custo esperado
   ```

   - Se o custo for diferente do esperado ou o áudio não aparecer, o script pula o trecho e não cobra nada. O registro fica em `<dir>/lote.log`.
   - O Kling mostra o aviso "audio longer than the video", e o script clica em Proceed.
   - Se o áudio demorar a subir, o trecho é pulado: reenvie só ele.

5. **Baixar os resultados** (dá para rodar várias vezes; o que já foi baixado é pulado):

   ```bash
   node docs/lipsync-kling/kling_baixar.mjs <dir>     # gera ksNN.mp4
   ```

   - O script lê o histórico do site (`/api/user/works/personal/feeds`) numa aba nova.
   - Casa cada tarefa pelo nome do arquivo enviado (`vNN.mp4`) e baixa `works[0].resource.resource`.
   - É mais confiável que clicar no ícone de download.

6. **Montar** o clipe com os trechos no tempo exato. O áudio original é mantido:

   ```bash
   python3 docs/lipsync-kling/montar_clipe.py clipe.mp4 <dir> saida.mp4
   ```

   - O Kling devolve 30 fps e 0,03 s mais curto. O script converte para 24 fps e repete o último quadro.

7. Para conferir, faça uma folha com um quadro do original em cima e um do Kling embaixo, por trecho. Depois mande para o bot v3 com `~/projetos/refazvideo/ferramentas/enviar_bot_v3.mjs` (limite de 49 MB).

## Custos medidos

- O Kling cobra em **blocos de 5 s**: trecho de 2 a 5 s = 5 créditos; trecho de 6 a 10 s = 10 créditos.
- Cortes curtos saem caros por segundo. Juntar cortes vizinhos só compensa se o rosto for o mesmo.
- Fila de 3 a 5 min por trecho, e vários rodam em paralelo.
- A saída é 1280x720, com marca "KlingAI" no canto (as tomadas originais já tinham).
- Total gasto em Stay: 20 créditos no teste e 85 na v2.

## Estado em Stay (10/10/2026)

| # | trecho | o que aparece | status |
|---|---|---|---|
| 01 | 0:00–0:02 | close de abertura | **falta** (5 cr) |
| 02 | 0:02–0:12 | plano médio no teatro | feito (mudança discreta, rosto pequeno) |
| 03 | 0:21–0:29 | palco, mãos nas poltronas | feito |
| 04 | 0:37–0:45 | palco, mãos nas poltronas | feito |
| 05–07 | 0:45–0:48, 0:51–0:54, 0:57–1:00 | closes do refrão | feito (melhor resultado) |
| 08 | 1:03–1:10 | close do refrão | feito |
| 09–12 | 1:35–1:38, 1:44–1:47, 1:53–1:56, 2:02–2:05 | close vestido dourado | feito |
| 13 | 2:05–2:15 | plano médio no teatro | feito |
| 14 | 2:29–2:32 | aeroporto, de frente | **falta** (5 cr) |
| 15 | 2:32–2:35 | igreja, braços abertos | **falta** (5 cr) |
| 16 | 2:42–2:45 | aeroporto | **falta** (5 cr) |
| 17 | 2:45–2:49 | igreja | **falta** (5 cr) |
| 18 | 2:53–2:56 | aeroporto | **falta** (5 cr) |
| 19 | 3:04–3:08 | igreja | **falta** (5 cr) |

Os cortes dos 19 trechos (vídeo e voz) foram feitos na pasta temporária da sessão. Para os 7 que faltam, refaça com `cortar.sh` usando os mesmos tempos e os números 01 e 14–19.

Arquivos:

- `stay-kling/lipsync-v2/stay-clipe-lipsync.mp4`: clipe inteiro com os 12 trechos. Enviado ao bot v3.
- `stay-kling/lipsync-v2/ks02–ks13.mp4`: trechos devolvidos pelo Kling, mais `segs.txt` e `qcheck.jpg`.
- `stay-kling/lipsync-teste/`: o 1º teste (cenas 1 e 6 cortadas das tomadas cruas). Foi encaixado no lugar errado; serve só para comparação.
- `stay-kling/lipsync-teste/stay-voz-isolada.wav`: a voz da música inteira.

## O que aprendemos

- **Cortar do clipe montado, não das tomadas do plano.** No 1º teste o encaixe caiu em cortes errados.
- **Funciona melhor em close ou plano médio**, com a boca visível. Com o rosto pequeno no quadro, a mudança é pequena.
- Se a tomada original estiver com a boca escancarada o tempo todo, o Kling não fecha a boca no silêncio. Foi o caso da cena 1 do teste.
- **Botões do site só respondem a clique de mouse** (coordenada ou `getBoundingClientRect`), não a `click()` do DOM.
- **Upload pelo input de arquivo:**
  - vídeo em `input[accept='.mp4,.mov']`;
  - áudio em `input[accept='.wav,.aac,.ogg,.flac,.mp3,.m4a']`.

## Próximos testes possíveis

- Fazer os 7 trechos que faltam (~35 créditos).
- Comparar com o Avatar do Kling (`/app/ai-human/new`) nos closes.
- Testar sem a marca: o histórico tem `downloadInfo.fileTypes[].watermark` e a configuração fica no site.
- Levar o fluxo para outra música do musicavideo cantada em inglês.

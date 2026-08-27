# Plano — INEMA MUSICAVIDEO V2 (acervo no Hugging Face, painel na nuvem)

> Status em 2026-08-27: **executado — passos 1 a 11 feitos**, exceto os dois que
> não são do agente: importar o repo na Vercel e criar o KV do like (seção 7).
> O V1 (painel local) continua funcionando como está.
>
> O que foi medido durante a execução e vale mais que o plano: o portão do passo
> 6 **passou** (o `clipe-1.mp4` de 101 MB responde 206 com `Content-Range` direto
> do HF), o namespace do HF é **`Inematds`** com maiúscula, e o acervo publicável
> é de **4,14 GB em 254 arquivos** — os `--dry` bateram com a estimativa.

## O que se quer

Hoje o painel só existe onde o acervo existe: os `<video>` e `<audio>` tocam
porque um servidor Python está enraizado em `~/projetos/output`. Fora da
máquina (ou fora da LAN) não há painel.

A V2 separa as duas coisas:

- **Os arquivos** (clipes, faixas, capas) vão para o **Hugging Face**, que serve
  direto por HTTPS, com range request.
- **O painel** vira um app na **Vercel** (repo `musicavideo-pub`), que lê um
  manifesto com metadados + URLs do HF.

| | V1 — o painel | V2 — `musicavideo-pub` |
|---|---|---|
| nome no topo | `INEMA MUSICAVIDEO V1.x.x` | `INEMA MUSICAVIDEO V2.x.x` |
| onde roda | `musicavideo painel`, local/LAN | Vercel, público |
| de onde vêm os arquivos | disco (`~/projetos/output`) | Hugging Face |
| escrita | move para `.lixo/`, **aprova subir** | **like** do público |
| quando atualiza | a cada request | quando o `publica-hf` roda (manual ou cron) |
| código | `src/painel.py`, neste repo | repo próprio `inematds/musicavideo-pub` |

**São dois apps, não uma migração.** O V1 é o painel de TRABALHO: é onde se
ouve, se compara, se manda para a lixeira e é onde se **aprova o que vai para a
nuvem**. O V2 é a VITRINE. Ligar o V2 não desliga nada; com o V2 desligado o V1
funciona igual.

---

## 1. O identificador: `MVD-000`

Hoje uma produção é referida pelo slug, que é um pedaço da solicitação
(`woman-young-athetic-toned-wild-haired-gl`) — ilegível, às vezes repetido, e
inútil para dizer em voz alta. No dia a dia a gente já diz "o MVD gaúcho", "o MVD
Stay".

**Cada produção ganha um número estável: `MVD-001`, `MVD-002`, …**

- Atribuído **uma vez**, na ordem de criação, e gravado no `index.jsonl` (e no
  `estado.json` da pasta). Nunca é recalculado: renomear pasta, apagar produção
  ou reordenar o índice não muda o número de ninguém.
- **É o que aparece no painel** — no card (junto ao título), no topo do card
  aberto, e no V2 como caminho da produção (`/mvd-014`).
- É o que se digita na busca e o que se cita numa conversa ou num `FALHAS.md`.
- O slug continua sendo o nome da pasta no disco e no HF: o MVD é o rótulo
  humano, não um segundo sistema de arquivos.

Produções que já existem recebem o número na primeira execução da migração, na
ordem de `criado_em`.

---

## 2. O que sobe para o Hugging Face

Medido em 2026-08-27: **15 GB** em `~/projetos/output/musicavideo`, 1365 `.mp4`.
Mas **1209 desses mp4 estão em `raw/`** — shot a shot, antes da montagem. Não
aparecem no painel e não saem da máquina.

| o quê | quantos | tamanho |
|---|---|---|
| `clipe-N.mp4` (o clipe final de cada versão) | 55 | ~3,9 GB |
| `clipe.mp4` **só quando não há versionado** | 1 | ~75 MB |
| `faixa*.mp3` | ~60 | ~248 MB |
| capas (`capa*.png`, `publicacao/capa-yt.jpg`) | 176 | ~186 MB |
| `plano.json`, `PACOTE.md`, `PLANO.md` | ~30 × 3 | KBs |

**Total: ~4,4 GB.**

### Só os clipes finais — e o `clipe.mp4` é cópia

`clipe-1.mp4` e `clipe-2.mp4` são os finais, um por versão. O `clipe.mp4` é a
**cópia da versão aprovada**, criada para quem quer “o clipe” sem escolher — e
medido em 2026-08-27, **28 dos 29 `clipe.mp4` do acervo são byte a byte
idênticos** a um dos versionados. Subir os dois é pagar 2,2 GB por nada.

Então sobe só o versionado, e o manifesto marca qual é o aprovado (a informação
que o `clipe.mp4` carregava). A única exceção é a produção antiga que só tem
`clipe.mp4`, sem versionado: essa sobe como está.

**Não sobe:** `raw/` inteiro, `estado.json`, `nucleo.json`, `.lixo/` — e **as
pastas de teste** (`teste-conserto`, `status`, recortes de experimento) **ficam
locais**. O que sobe é produção de verdade: com clipe montado, capa pronta e
aprovação (seção 5).

### O analisevideo sobe como TEXTO, e só

Nenhum arquivo binário da aba de análises vai para a nuvem — **nada de `fonte.mp4`**.
Aquele arquivo é o vídeo de terceiros baixado do YouTube: re-hospedar é
redistribuição de obra alheia, e não serve para nada aqui.

O que vai é **o texto**, dentro do próprio app: `analise.md` / `analise.json` —
resumo, look, paleta, movimentos de câmera, ritmo, cortes por minuto, mood,
tags, referências. O vídeo analisado, quando é do YouTube, aparece pelo **embed
oficial** (o painel já monta isso com `ytid()` → `youtube-nocookie.com/embed/`).
Sem URL de origem, fica só a análise escrita — que é o valor real dela.

Consequência prática: a aba de análises da V2 não pesa nada. É texto no repo do
app, não arquivo no HF.

---

## 3. Como fica no HF

Dataset repo **público**: `inematds/musicavideo-acervo`. Um diretório por slug:

```
inematds/musicavideo-acervo
├── manifest.json                  ← o que o app V2 lê
├── hands-to-the-sky/              (MVD-014)
│   ├── capa.png  capa-v1.png  capa-v2.png  capa-yt.jpg
│   ├── faixa-1.mp3  faixa-2.mp3
│   ├── clipe-1.mp4  clipe-2.mp4
│   └── plano.json  PACOTE.md  PLANO.md
└── ...
```

URL de consumo:

```
https://huggingface.co/datasets/inematds/musicavideo-acervo/resolve/main/hands-to-the-sky/clipe-1.mp4
```

**Verificado (2026-08-27):** o `resolve/main` responde **HTTP 206** com
`Content-Range` a um pedido com `Range:`. É a premissa que sustenta tudo — sem
range request o `<video>` não navega na barra. Está de pé.

**Credenciais:** `HF_TOKEN` do usuário `inematds` já existe em
`~/projetos/wifi/.env`; `huggingface_hub` 1.26 e o CLI `hf` já estão na máquina.
Token carregado em runtime, nunca copiado para dentro de repo nenhum.

---

## 4. O comando de publicação (`publica-hf`)

Um comando novo **neste repo** — é aqui que o acervo vive:

```bash
bash musicavideo.sh publica-hf                 # tudo que está aprovado e mudou
bash musicavideo.sh publica-hf <slug|MVD-014>  # uma produção
bash musicavideo.sh publica-hf --dry           # só diz o que subiria
```

1. Percorre o acervo pela **mesma `painel.coletar()`** que o V1 usa. Não se
   escreve um segundo coletor: no dia em que os dois divergissem, o V2 mostraria
   coisa diferente do V1 e ninguém saberia qual está certo.
2. Filtra pelo **flag de aprovação** (seção 5) e pela lista da seção 2.
3. Sobe via `huggingface_hub`, pulando o que não mudou (o HF compara por hash).
4. Grava o `manifest.json`: o MESMO dicionário do `coletar()`, com `_url()`
   trocando a base local pela base HF, mais o `MVD-000` de cada produção. **Uma
   função, dois destinos** — é o único ponto onde a V2 encosta no código da V1.

---

## 5. Aprovar a subida: um clique no painel local

Subir é decisão, não automatismo. Quem decide é quem está olhando o material —
no V1.

- **No card do painel local, um botão: “subir para a nuvem”.** Um clique marca a
  produção como aprovada para publicação (um campo no `estado.json`, ao lado dos
  estados de parte que já existem). O botão mostra o estado atual: *não
  publicado* / *aprovado, aguardando* / *publicado em <data>*.
- É o **mesmo desenho do botão da lixeira** que já existe: um POST para o
  servidor local, que escreve no disco. Não sobe arquivo na hora — só marca.
- **Desmarcar também é um clique**, e desmarcar não apaga o que já está no HF;
  gera uma pendência de remoção que o `publica-hf` executa na próxima passada.

**O cron.** Com o sistema de nuvem ativo, um cron roda o `publica-hf`
periodicamente e sobe o que estiver aprovado e ainda não publicado. Assim
aprovar é o único gesto: o resto acontece sozinho. Sem o sistema ativo, o cron
não existe e o comando continua rodando à mão — o V1 não depende dele para nada.

---

## 6. O app V2 — `musicavideo-pub`

- **Repo:** `inematds/musicavideo-pub` (pasta local `~/projetos/musicavideo-pub`).
  O nome “painel” continua sendo o do local.
- **Stack:** Next.js (App Router) na Vercel. Os arquivos pesados vêm do HF; o app
  serve HTML, o manifesto e o texto das análises.
- **O que se importa na Vercel:** o **repositório `inematds/musicavideo-pub`**,
  com o app na **raiz** — ou seja, *Root Directory* = `./`, o default. Por isso o
  app tem repo próprio e não uma subpasta deste: a Vercel importa um repo, e um
  app no fundo de `~/projetos/musicavideo/algum/lugar` obrigaria a apontar a
  raiz na mão e arrastaria os 15 GB do acervo para dentro do build. O `output/`
  nunca entra no repo do app — ele lê o HF por HTTPS. Feita a importação uma
  vez, publicar é `git push` e nada mais.
- **Topo da página:** `INEMA MUSICAVIDEO V2.x.x`, versão visível, semver do
  ecossistema. O V1 recebe o mesmo tratamento: `INEMA MUSICAVIDEO V1.x.x` no
  cabeçalho, em vez do “painel INEMA — o que já foi feito” de hoje.
- **Interface:** a do V1, portada — grade com as duas capas e os dois players,
  card aberto com as versões empilhadas (capa → player → clipe) e o expansível
  dos prompts. `MVD-000` visível em cada produção. Mesma paleta dark âmbar.
- **O que NÃO vai:** o botão da lixeira (move arquivo no disco; na nuvem não há
  disco) e o botão de aprovar subida (é gesto de trabalho, é do V1).

### O like

A V2 tem **like** — é a única escrita do público, e a razão de o V2 não ser um
site estático puro.

- Um like por produção (`MVD-000`), anônimo, sem login: um contador e um estado
  local no navegador para não deixar a mesma pessoa somar dez vezes num clique.
- **Precisa de persistência**, e é a única decisão técnica que este plano deixa
  para a hora de implementar: um KV/Postgres da própria Vercel é o caminho curto
  (uma tabela `mvd → contagem`); a alternativa de commitar no dataset do HF a
  cada like é ruim (cada like vira um commit).
- **O like volta para o V1**: o `publica-hf` lê as contagens na ida e grava junto
  ao acervo, e o painel local mostra quantos likes cada produção tem. Sem isso o
  sinal do público morre na nuvem, e ele é justamente o que não existe hoje —
  hoje não há como saber qual produção agradou.

---

## 7. Ordem de execução

| # | passo | onde | entrega |
|---|---|---|---|
| ✅ 1 | Numerar o acervo: `MVD-000` gravado no índice, na ordem de `criado_em` | musicavideo | id estável em tudo |
| ✅ 2 | Mostrar o MVD no painel local + `INEMA MUSICAVIDEO V1.x.x` no topo | musicavideo | V1 já falando a nova língua |
| ✅ 3 | Botão “subir para a nuvem” no card (marca no `estado.json`) | musicavideo | aprovação existe antes de haver nuvem |
| ✅ 4 | Criar o dataset `inematds/musicavideo-acervo` (público, vazio) | HF | repo de pé |
| ✅ 5 | `publica-hf --dry` | musicavideo | confere a seleção antes de gastar banda |
| ✅ 6 | Subir **uma** produção e abrir o mp4 no navegador | HF | **portão**: prova o range request num arquivo real |
| ✅ 7 | Subir o acervo aprovado + `manifest.json` | HF | dataset completo (~4,4 GB) |
| ✅ 8 | Criar `musicavideo-pub` e portar a interface | app novo | painel rodando local contra o manifest |
| ✅ 9 | Like (KV) e o retorno das contagens para o V1 | app novo + musicavideo | código pronto; **falta criar o KV e pôr as variáveis — é do dono** |
| ✅ 10 | `git push` | app novo | **falta importar o repo na Vercel — é do dono** |
| ✅ 11 | Cron do `publica-hf` | máquina | aprovar vira o único gesto |
| 12 | Card no portal (`inema.club`) | portal | espera a URL da Vercel |

O passo 6 é o portão de propósito: se um `clipe-1.mp4` de ~70 MB não navegar
direto do HF, o plano muda de forma — melhor descobrir com um arquivo do que com
nove gigas.

---

## 8. Decisões já tomadas (2026-08-27)

| | decisão |
|---|---|
| (a) | **O acervo vai público.** Dataset público no HF; qualquer um com o link baixa clipe, faixa, capa e o `PLANO.md` (que inclui letra e prompts). Assumido. |
| (b) | **Repo do V2: `musicavideo-pub`.** “Painel” segue sendo o nome do local. |
| (c) | **Nome com a versão no topo** dos dois: `INEMA MUSICAVIDEO V1.x.x` e `V2.x.x`. |
| (d) | **Pastas de teste ficam locais** — não sobem. |
| (e) | **Analisevideo: nada de binário na nuvem.** Só o texto da análise, dentro do app; vídeo de origem por embed do YouTube. |
| (f) | **Like só na nuvem**, e as contagens voltam para o painel local. |
| (g) | **Aprovar a subida é um clique no painel local**; com a nuvem ativa, um cron faz a subida do que está aprovado. |
| (h) | **Referência por `MVD-000`** em todo o painel. |

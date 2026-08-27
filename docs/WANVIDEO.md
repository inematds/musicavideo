# Wan (WanVideo) — pela Alibaba direto, ou pela Kie

Notas de uso do **Wan**, o gerador de vídeo da Alibaba. Levantado em 2026-08-27
a partir da documentação oficial, a pedido do dono.

**Há dois caminhos até o mesmo modelo**, e para este projeto eles não valem o
mesmo:

| | Alibaba direto (Model Studio / DashScope) | **Kie** (`api.kie.ai`) |
|---|---|---|
| conta e chave | nova, mais `{WorkspaceId}` e região | **já temos** — é a do Suno |
| adaptador aqui | do zero | `providers/kie.py` já existe |
| protocolo | `media[]` + header `X-DashScope-Async` | `{model, input}` num POST só |
| lipsync | `driving_audio` no `wan2.7-i2v` | `2-2-a14b-speech-to-video-turbo` ou `reference_voice` do `2-7-r2v` |
| referência de personagem | primeiro quadro | **`2-7-r2v`: várias refs citadas por índice** |
| preço | tabela oficial | declara 30–50% abaixo |

A leitura abaixo começa pela Alibaba (que é o que o dono mandou) e termina na
**seção da Kie**, que é o caminho mais curto daqui — pule para lá se o que
interessa é o que dá para fazer esta semana.

> **Status: NADA AQUI FOI RODADO.** Isto é leitura de doc, não medição. As notas
> da Agnes (`~/projetos/agnes-nei/NOTAS-API.md`) valem mais que este arquivo
> porque custaram chamadas de verdade — e a lição delas se aplica aqui:
> **a API devolve HTTP 200 em imagem quebrada**. Enquanto ninguém gerar um vídeo
> com este provedor, trate tudo abaixo como "o que a doc promete".
>
> Console do pedido: <https://modelstudio.console.alibabacloud.com/ap-southeast-1>
> (região **Singapura**, `ap-southeast-1`).

## Por que este provedor interessa a este projeto

Três itens abertos do `MELHORIAS.md` encostam direto no que o Wan 2.7 oferece:

| item aberto aqui | o que o Wan 2.7 tem |
|---|---|
| **Ficha do personagem** — consistência entre produções | `first_frame` (e `first_clip`) como âncora do plano |
| **Boca cantando** — o clipe finge que canta | **`driving_audio`**: o vídeo é dirigido pelo áudio, com lip sync |
| **Transição como conexão** — hoje só corte seco | `first_frame + last_frame`: o plano nasce ligando duas pontas |

O `driving_audio` é o mais direto: o exemplo da própria doc é um personagem
**cantando um rap em sincronia com o MP3 enviado**. É exatamente o problema que
a regra de prompt daqui contorna ("não descrever a boca; o canto se lê no
corpo") — aqui não seria contorno, seria a coisa.

## O básico

**Região é contrato.** Modelo, URL e chave têm de ser da MESMA região; chamada
cruzada falha. O link do dono é de Singapura.

**Domínios por workspace** (recomendados pela Alibaba; os antigos ainda
funcionam):

```
Singapura : https://{WorkspaceId}.ap-southeast-1.maas.aliyuncs.com
Pequim    : https://{WorkspaceId}.cn-beijing.maas.aliyuncs.com
antigo    : https://dashscope-intl.aliyuncs.com  (intl) / dashscope.aliyuncs.com (CN)
```

`{WorkspaceId}` sai da página **Workspace Details** do console.

**Dois endpoints, e só isso:**

```
POST /api/v1/services/aigc/video-generation/video-synthesis   # cria a tarefa
GET  /api/v1/tasks/{task_id}                                  # busca o resultado
```

**O header que não pode faltar:** `X-DashScope-Async: enable`. Sem ele o HTTP
responde `current user api does not support synchronous calls` — não é chave
errada, é o header.

```
Authorization: Bearer $DASHSCOPE_API_KEY
Content-Type: application/json
X-DashScope-Async: enable
```

## O ciclo — é assíncrono, e o relógio corre

- A geração leva **1 a 5 minutos**. Polling recomendado: **a cada 15s**.
- Estados: `PENDING` → `RUNNING` → `SUCCEEDED` | `FAILED`.
- **A URL do vídeo vale 24h** e depois é apagada. **Baixar na hora** — é a mesma
  regra da Agnes, e aqui está escrita na doc.
- **O `task_id` também vale 24h**; depois a consulta devolve `UNKNOWN`. Um id
  guardado num `estado.json` velho não recupera nada.
- Falha vem com `task_status: FAILED` + `code` + `message`
  (ex.: `InvalidParameter: The size is not match ...`).

A resposta traz `usage` com `duration`, `output_video_duration`, `video_count` e
`SR` (a resolução entregue) — dá para conferir o que veio contra o que se pediu.

## Texto → vídeo (`wan2.7-t2v`)

```bash
curl --location 'https://{WorkspaceId}.ap-southeast-1.maas.aliyuncs.com/api/v1/services/aigc/video-generation/video-synthesis' \
  -H 'X-DashScope-Async: enable' \
  -H "Authorization: Bearer $DASHSCOPE_API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{ "model": "wan2.7-t2v",
        "input":  { "prompt": "..." },
        "parameters": { "size": "1280*720", "duration": 10,
                        "negative_prompt": "", "prompt_extend": true,
                        "watermark": false, "seed": 12345 } }'
```

## Imagem/áudio/vídeo → vídeo (`wan2.7-i2v-...`)

**Este é o protocolo novo, e é o que interessa.** Ele faz três tarefas —
primeiro quadro, primeiro+último quadro, e continuação de vídeo — e o material
entra num array `media`, cada item com `type` e `url`:

| `type` | o que é |
|---|---|
| `first_frame` | imagem que abre o plano |
| `last_frame` | imagem que fecha o plano |
| `first_clip` | vídeo de partida (continuação) |
| `driving_audio` | **áudio que dirige o vídeo** — lip sync |

**As combinações são fechadas** — combinação inválida devolve erro. As que a doc
mostra em exemplo: `first_frame` sozinho, `first_frame + last_frame`,
`first_frame + driving_audio`, `first_clip`, `first_clip + last_frame`.
*(A lista completa está na doc; não a copiei inteira porque não a li inteira.)*

Cantando, com lip sync:

```json
{ "model": "wan2.7-i2v-2026-04-25",
  "input": {
    "prompt": "... He sings ... The audio of the video consists entirely of the rap, with no other dialogue or noise.",
    "media": [ { "type": "first_frame",   "url": "https://.../rap.png" },
               { "type": "driving_audio", "url": "https://.../rap.mp3" } ] },
  "parameters": { "resolution": "720P", "duration": 10,
                  "prompt_extend": true, "watermark": true } }
```

Repare no fim do prompt do exemplo oficial: *"o áudio do vídeo é inteiramente o
rap, sem outro diálogo ou ruído"*. O prompt precisa **dizer** que o áudio manda,
senão o modelo inventa som por cima.

## Parâmetros — o que muda em relação ao que já usamos

- **`size` usa asterisco**, não `x`: `"1280*720"`. Cada provedor tem seu
  vocabulário de resolução, e este é mais um — a tradução é papel do adaptador,
  como já está escrito no `providers/agnes.py`. No protocolo novo do i2v o campo
  é outro: **`resolution`**, com rótulo (`"720P"`).
- **`negative_prompt` EXISTE** e é respeitado (máx. 500 caracteres). Vale
  registrar porque o default global de imagem (`flux2-klein`) **ignora** negativo
  — são contratos opostos.
- **`prompt_extend`**: o serviço reescreve o prompt antes de gerar. Ajuda em
  storyboard, mas significa que **o prompt que gerou o vídeo não é o que você
  mandou**. Para reprodutibilidade, `false`; para "melhora sozinho", `true`.
- **`watermark`**: pode ser `false`.
- **`seed`**: existe.
- **Idioma**: chinês e inglês. Português não é mencionado — assumir que **não**
  passa, como na Agnes, até alguém medir.
- **Tamanho do prompt**: `wan2.7` até **5.000** caracteres; `wan2.6`/`2.5` até
  1.500; `wan2.2` e anteriores, menos.
- **Áudio**: WAV ou MP3, **2–30s**, até **15 MB**, por URL pública.

### Multi-shot: o prompt é que decide

O `wan2.7-t2v` aceita narrativa de vários planos **descrita em linguagem
natural** — "Generate a multi-shot video", ou planos com marcação de tempo
(`Shot 1 [0–3 seconds] wide shot: ...`). Há um `shot_type: "multi"`, mas na
variante multi-shot a doc diz que **`shot_type` não tem efeito** — quem manda é o
texto. Sem instrução, o modelo decide sozinho.

### ⚠️ A proporção NÃO é garantida

O formato de saída é derivado **do material de entrada** (primeiro quadro ou
clipe), combinado com o total de pixels da faixa de `resolution` — e como o
encoder exige largura e altura múltiplas de 16, o resultado é arredondado.

Exemplo da própria doc: entrada 750×1000 (3:4 = 0,75) em `720P` sai **816×1104**
(≈0,739). **Deriva.** Para proporção exata: entrar com material já na proporção
alvo e, se precisar ser exato, cortar depois. Somado ao fato de que a Agnes
**mente o tamanho na resposta**, a regra da casa continua valendo para qualquer
provedor: *conferir o arquivo com `ffprobe`, nunca acreditar no JSON*.

## O que eu NÃO confirmei

Está aqui para ninguém tratar como sabido:

- **Preço.** Não achei o valor por segundo nesta leitura. A doc manda para
  *Model pricing* (`/help/en/model-studio/model-pricing`). Diferente da Agnes,
  isto **não é de graça** — e o `custo.estimar_partes` daqui precisaria de um
  número real antes de qualquer produção.
- **Cota gratuita**, se houver.
- **Rate limit e tarefas concorrentes.** Não encontrei o número. Na Agnes o
  limite (5 req/min) é o que define a parede de horas de um clipe; aqui é
  desconhecido, e é a primeira coisa a medir.
- **A lista completa de combinações válidas** de `media`.
- **Se prompt em português passa.**
- **Quais IDs de modelo estão vivos em Singapura.** Vistos na doc:
  `wan2.7-t2v`, `wan2.7-t2v-2026-06-12`, `wan2.7-i2v-2026-04-25`,
  `wan2.7-image-pro`. Confirmar no console antes de codar.

## O MESMO Wan pela Kie — e é aqui que ele fica prático

Levantado em 2026-08-27, a partir da observação do dono: *"no kie tem a wan, ela
tem lipsync"*. Tem, e muda bastante o custo de entrada.

**Por que muda.** A Kie é o provedor que este projeto **já usa** para a música
(`providers/kie.py`, Suno). A `KIE_API_KEY` já está no `.env` autorizado, o
adaptador já existe, e o padrão de tarefa assíncrona da Kie já está implementado
aqui. Usar o Wan pela Kie dispensa conta nova, região, `{WorkspaceId}` e o
header `X-DashScope-Async` — o payload é plano e o endpoint é um só:

```
POST https://api.kie.ai/api/v1/jobs/createTask     # { model, callBackUrl, input }
```

A Kie declara preços **30–50% abaixo das APIs oficiais** (até 80% em alguns
modelos). *Não confirmei os números do Wan: a página de preços é renderizada no
navegador e não veio no fetch.*

### `wan/2-2-a14b-speech-to-video-turbo` — o lipsync

Uma imagem parada + um áudio → vídeo com a boca sincronizada.

```json
{ "model": "wan/2-2-a14b-speech-to-video-turbo",
  "input": { "prompt": "The lady is talking",
             "image_url": "https://.../rosto.png",
             "audio_url": "https://.../fala.mp3",
             "num_frames": 80, "frames_per_second": 16,
             "resolution": "480p", "negative_prompt": "",
             "num_inference_steps": 27, "guidance_scale": 3.5, "shift": 5 } }
```

É **Wan 2.2**, não 2.7, e o exemplo da doc está em **480p** com 16 fps — isso
importa: 80 frames a 16 fps são **5 segundos**. Para um refrão inteiro seriam
várias chamadas, ou uma resolução maior se o modelo aceitar. Expõe knobs de
difusão (`num_inference_steps`, `guidance_scale`, `shift`) que os outros
provedores daqui escondem.

### `wan/2-7-r2v` — reference-to-video, que é a FICHA DO PERSONAGEM

Este é o achado. Ele aceita **várias referências de personagem ao mesmo tempo**,
citadas por índice dentro do prompt, mais um **primeiro quadro** e uma
**referência de voz**:

```json
{ "model": "wan/2-7-r2v",
  "input": {
    "prompt": "Image 1 is eating, while video 1 and image 2 are singing beside it.",
    "negative_prompt": "low resolution, errors, worst quality, ...",
    "reference_image": ["https://.../ref-1.png", "https://.../ref-2.png"],
    "reference_video": ["https://.../ref-video-1.mp4"],
    "first_frame":     "https://.../first-frame.png",
    "reference_voice": "https://.../voz.mp3",
    "resolution": "1080p", "aspect_ratio": "16:9", "duration": 5,
    "prompt_extend": true, "watermark": false, "seed": 0 } }
```

Três coisas para reter:

1. **O prompt cita as referências por índice** ("image 1", "video 1", "image 2").
   Isso resolve o que ficou em aberto na ficha — *elenco*, não só um cantor. E
   dá ao planejador uma gramática para dizer quem faz o quê.
2. **`aspect_ratio` é declarado.** Pela API direta da Alibaba a proporção
   **deriva** do material de entrada e não é garantida (ver acima); aqui existe
   o campo. *Não medi se ele é obedecido.*
3. **`reference_voice`** é a ponte com o lipsync sem sair do mesmo modelo.

### As três rotas que a Kie expõe do Wan, e o que cada uma serve

| modelo na Kie | entrada | serve para |
|---|---|---|
| `wan/2-7-image-to-video` | `first_frame_url`, `last_frame_url`, `first_clip_url` | **transição como conexão** — o plano nasce ligando duas pontas |
| `wan/2-7-r2v` | `reference_image[]`, `reference_video[]`, `reference_voice`, `first_frame` | **ficha do personagem** e elenco |
| `wan/2-2-a14b-speech-to-video-turbo` | `image_url` + `audio_url` | **lipsync** (boca cantando) |

Há ainda `2-7-text-to-video`, `2-7-videoedit`, `2-7-image`/`2-7-image-pro`
(imagem), a linha `2-5`/`2-6` e `3-0-video`/`3-0-video-prime`.

**⚠️ Uma diferença que engana:** o `wan/2-7-image-to-video` da Kie **não expõe o
`driving_audio`** que a API direta da Alibaba tem — a doc dela lista só três
modos (primeiro quadro, primeiro+último, continuação). Ou seja, **o lipsync do
2.7 não está nessa rota**: pela Kie ele vem do `2-2-a14b-speech-to-video-turbo`
ou do `reference_voice` do `2-7-r2v`. Escolher a rota errada é descobrir isso
depois de codar.

### E não é só o Wan que faz lipsync na Kie

Se o objetivo for só a boca sincronizada, há modelos dedicados no mesmo
provedor, com a mesma chave: `infinitalk/from-audio`, `omnihuman-1-5`,
`kling/ai-avatar-standard` e `ai-avatar-pro`, `volcengine/video-to-video-lip-sync`
(este aplica em cima de um vídeo **já pronto** — encaixaria nos clipes que já
existem, sem regerar) e a linha `gemini-omni-character`. Nenhum foi medido.

**O empecilho registrado em 2026-08-25 continua de pé:** lipsync quer **voz
isolada**, e o que existe aqui é a mixagem do Suno. Sem `demucs`, o caminho
honesto é testar em UM plano de refrão antes de decidir qualquer coisa.

## Se um dia virar adaptador aqui

O `providers/` deste projeto é plugável — um `wan.py` + `wan.models.json`
seguiriam o mesmo molde de `agnes.py`/`kling.py`. Antes disso:

1. **Medir o rate limit e o preço.** São eles que decidem se o Wan entra como
   motor de clipe ou só como recurso pontual (o lip sync do refrão, por
   exemplo). O `custo.estimar_partes` soma `duracao_s` — sem preço real, ele
   mente.
2. **Traduzir vocabulário no adaptador**, nunca no plano: `size` com `*`,
   `resolution` com rótulo, e o plano continuando a guardar o que o planejador
   escreveu. Foi um `"1080p".split("x")` que estourou o clipe do MVD#90 com a
   música já paga.
3. **Baixar na hora** (24h) e conferir com `ffprobe`.
4. **`X-DashScope-Async: enable`** e polling de 15s com teto — o teto de 45 min
   da Agnes veio de dor, não de chute; começar por ele.

## Fontes

- Wan2.7 texto→vídeo: <https://www.alibabacloud.com/help/en/model-studio/text-to-video-api-reference>
- Wan2.7 imagem→vídeo (protocolo novo): <https://www.alibabacloud.com/help/en/model-studio/image-to-video-general-api-reference>
- Wan 2.1–2.6 imagem→vídeo (legado, só primeiro quadro): <https://www.alibabacloud.com/help/en/model-studio/image-to-video-api-reference>
- Modelos e preços: <https://www.alibabacloud.com/help/en/model-studio/models>

# musicavideo — Documento de Design (spec aprovado)

**Data:** 2026-08-20
**Status:** aprovado pelo usuário — este documento é o contrato de implementação.
**Molde:** `analisevideo` (`.sh` fino + python, banco em `~/projetos/output/<projeto>/<slug>/`, `index.jsonl`, SKILL.md, guia GitHub Pages) + padrão de provedores plugáveis do `bench-studio-br` (adapter + `<prov>.models.json` declarativo, registry, indisponível-com-motivo).

---

## 1. Objetivo

O usuário passa uma **solicitação em texto livre** e o projeto produz **MÚSICA + CAPA + CLIPE**, em fases, com **portão de aprovação por parte** (ou sem portão nenhum, via `tudo`). O projeto é **autossuficiente**: não depende do bench-studio nem do musicaclone. Depois será acoplado como skill em outros projetos — por isso o `plano.json` tem **esquema fechado**: ele é o contrato entre quem planeja e quem executa.

Princípio central: **planejar é barato, executar é caro.** A fase de plano é escrita pelo modelo (Fable) e não gasta API de mídia. Só o `faz` gasta crédito — e sempre mostra o custo estimado antes.

---

## 2. Forma do projeto

- Repositório: `~/projetos/musicavideo`.
- `musicavideo.sh` **fino**: só valida args, resolve caminhos e roteia subcomandos para `python3 src/main.py <subcomando> ...`. Zero lógica no bash.
- Saída (banco): `~/projetos/output/musicavideo/<slug>/`.
- `SKILL.md` na raiz (para o bot do Telegram / acoplamento como skill).
- `guia/index.html` (landing+guia, GitHub Pages, padrão INEMA dark âmbar — via skill `projetos-landing-guia` na hora de publicar).
- `.env.example` documentando cada chave usada (só documentação: valores reais são lidos em runtime de `~/projetos/openpcbotv2/.env` ou `~/projetos/wifi/.env` — **nunca copiados nem impressos**).

### 2.1 Layout do repositório

```
musicavideo/
├── musicavideo.sh              # roteador fino (bash)
├── SKILL.md                    # interface pro bot/skill
├── .env.example                # chaves documentadas (sem valores)
├── README.md
├── guia/
│   └── index.html              # landing+guia (GitHub Pages)
├── src/
│   ├── main.py                 # dispatch dos subcomandos
│   ├── planner.py              # fase 1: monta contexto e escreve plano.json + PLANO.md
│   ├── executor.py             # fase 2: roda cada parte via provider
│   ├── estado.py               # leitura/escrita atômica do estado.json + máquina de estados
│   ├── custo.py                # estimativa e contabilização de custo
│   ├── entrega.py              # fase 3: PACOTE.md + envio Telegram opcional
│   ├── indexer.py              # index.jsonl: append, lista, busca, reindex
│   ├── pesquisa.py             # fase 0 opt-in: pesquisa web → pesquisa.md
│   └── registry.py             # merge dos providers/*.models.json + disponibilidade
├── providers/
│   ├── base.py                 # contrato do adapter (ver §7)
│   ├── kie.py                  # música (Suno via KIE)
│   ├── kie.models.json
│   ├── inemaimg.py             # capa (flux2-klein via inemaimg)
│   ├── inemaimg.models.json
│   ├── kling.py                # clipe (Kling)
│   ├── kling.models.json
│   ├── agnes.py                # clipe (Agnes, custo zero)
│   └── agnes.models.json
├── data/
│   ├── estilos.json            # banco de estilos (semeado das análises Gemini)
│   ├── templates-capa.json     # composições de capa
│   └── templates-clipe.json    # decupagens de clipe
└── docs/superpowers/specs/
    └── 2026-08-20-musicavideo-design.md   # este arquivo
```

### 2.2 Layout da pasta de saída de um slug

```
~/projetos/output/musicavideo/
├── index.jsonl                 # 1 linha por slug (ver §8.5)
└── <slug>/
    ├── plano.json              # contrato (ver §8.1)
    ├── PLANO.md                # o mesmo plano legível pra humano (aprovação)
    ├── estado.json             # fonte de verdade (ver §8.2)
    ├── pesquisa.md             # só se --pesquisa
    ├── faixa.mp3               # parte musica pronta
    ├── capa.png                # parte capa pronta
    ├── clipe.mp4               # parte clipe pronta
    ├── PACOTE.md               # entrega final
    └── raw/                    # respostas cruas dos provedores (debug), 1 json por chamada
```

---

## 3. Fases

| # | Fase | Gatilho | Produz | Custo |
|---|------|---------|--------|-------|
| 0 | pesquisa | **opt-in** `--pesquisa` (default DESLIGADO) | `pesquisa.md` | web search, sem API de mídia |
| 1 | plano | `musicavideo plano` | `plano.json` + `PLANO.md` + `estado.json` inicial | zero API de mídia |
| 2 | execução | `musicavideo faz` (por parte, com portão) | `faixa.mp3` / `capa.png` / `clipe.mp4` | **gasta crédito** |
| 3 | entrega | automática quando as 3 partes ficam `pronto` (ou sob demanda) | `PACOTE.md` + Telegram opcional | zero |

- Cada parte (`musica`, `capa`, `clipe`) tem **portão próprio**: `ver` → `ajusta` (quantas vezes quiser) → `ok` → `faz`.
- `estado.json` é a **fonte de verdade**: fase de cada parte, o que foi aprovado, custo acumulado, erros. Permite parar e retomar dias depois, ou refazer só uma parte.
- Conhecimento local (estilos, templates, acervo/index) está **sempre ligado** no plano — leitura local, custo zero. Só a pesquisa web é opt-in.

---

## 4. Entrada

Solicitação em **texto livre** (obrigatória). Opcionais:

- `--estilo X` — tipo/estilo de música (livre ou id do `estilos.json`).
- `--letra <arquivo>` — letra fornecida. Sem `--letra-final`, é **rascunho**: o planejador termina/ajusta e o `PLANO.md` mostra o **diff** entre o que veio e o que ficou. Com `--letra-final`, a letra é **lei**: vai pro plano verbatim, ninguém altera (nem `ajusta` mexe nela — `ajusta musica` pode mudar estilo/voz/estrutura, não a letra).
- O status da letra é campo **explícito** no plano (`musica.letra.origem`: `"gerada" | "rascunho_usuario" | "final_usuario"`) — **nunca adivinhado**.

---

## 5. Comandos (CLI)

```
musicavideo plano "<solicitação>" [slug] [--pesquisa] [--estilo X] [--letra arq [--letra-final]]
musicavideo ver    <slug> [musica|capa|clipe]      # mostra o plano da parte (ou PLANO.md inteiro)
musicavideo ajusta <slug> <parte> "<instrução>"    # replaneja SÓ a parte, mostra diff
musicavideo ok     <slug> <parte>                  # aprova a parte (abre o portão)
musicavideo faz    <slug> [parte]                  # executa parte(s) aprovada(s); sem parte = todas as aprovadas
musicavideo tudo   "<solicitação>" [--teto N] [demais flags de plano]   # sem portão: plano + auto-ok + faz + entrega
musicavideo custo  <slug>                          # estimado vs gasto, por parte
musicavideo lista  [N]                             # últimos slugs do index.jsonl
musicavideo busca  "<termo>"                       # busca no index.jsonl (estilo, tag, título, letra)
```

Regras transversais:
- `slug` omitido em `plano`/`tudo`: derivado da solicitação (kebab-case, ≤40 chars, sufixo `-2`, `-3`... se colidir).
- Todo `faz` imprime **custo estimado** por parte e total **antes** de chamar qualquer API.
- `--motor <parte>=<provider:modelo>` (aceito em `plano`, `ajusta`, `faz`): sobrescreve o motor do plano. O motor **nunca é chumbado no código** — vem do plano, que pode vir da flag.
- Exit codes: `0` ok; `1` erro de uso/validação; `2` parte(s) terminou em `erro` (a corrida seguiu); `3` teto estourado (`tudo`).

### 5.1 O que cada comando faz com a máquina de estados (ver §6)

| Comando | Pré-condição (parte) | Efeito |
|---|---|---|
| `plano` | slug novo (ou `--forca` p/ replanejar slug sem parte `pronto`) | cria plano.json/PLANO.md; todas as partes → `planejado` |
| `ver` | qualquer | leitura, não muda estado |
| `ajusta` | `planejado`, `aprovado` ou `erro` | reescreve a seção da parte no plano (diff na tela); parte → `planejado` (aprovação anterior cai); se estava `pronto`, exige `--refaz` e volta pra `planejado` |
| `ok` | `planejado` | parte → `aprovado` |
| `faz` | `aprovado` (ou `erro`, que é retry) | parte → `gerando` → `pronto` \| `erro`; grava custo real |
| `tudo` | slug novo | plano + todas → `aprovado` (auto) + `faz` respeitando `--teto` + entrega |
| `custo`/`lista`/`busca` | — | leitura |

---

## 6. Máquina de estados de cada parte

```
planejado ──ok──▶ aprovado ──faz──▶ gerando ──▶ pronto
    ▲                │                  │
    │              ajusta               ▼
    └──── ajusta ────┘                erro ──faz (retry)──▶ gerando
                                        └──ajusta──▶ planejado
pronto ──ajusta --refaz──▶ planejado   (artefato antigo vai pra raw/ com sufixo -vN)
```

Estados: `planejado`, `aprovado`, `gerando`, `pronto`, `erro`. Transições fora do desenho são rejeitadas com mensagem clara. `gerando` interrompido (crash/ctrl-c) é tratado no próximo comando como `erro` com motivo `"interrompido"`.

**Entrega:** quando as 3 partes estão `pronto`, o próximo comando que tocar o slug gera `PACOTE.md` e (se `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID` disponíveis e `--telegram` passado, ou `telegram: true` no estado) envia faixa+capa+clipe. Entrega parcial é permitida: `PACOTE.md` lista o que está pronto e o que falta.

---

## 7. Provedores plugáveis

Padrão bench-studio: **um adapter por provedor + um `<prov>.models.json` declarativo ao lado**; o `registry.py` mescla todos num registry único; **provedor sem chave aparece como INDISPONÍVEL COM O MOTIVO** (ex.: `kie: indisponível — KIE_API_KEY não encontrada em openpcbotv2/.env nem wifi/.env`) em vez de estourar erro na hora de gerar. O `plano` já valida disponibilidade e avisa; o `faz` recusa parte cujo motor está indisponível (parte → `erro` com o motivo, as outras seguem).

### 7.1 Contrato do adapter (`providers/base.py`)

```python
class Provider:                      # cada providers/<nome>.py implementa
    nome: str                        # "kie", "kling", ...

    def disponivel(self) -> tuple[bool, str]:
        """(True, "") ou (False, "motivo legível"). Checa chave nos .env
        autorizados EM RUNTIME; nunca loga o valor da chave."""

    def estimar_custo(self, modelo: str, params: dict) -> float:
        """Custo estimado em USD (ou créditos convertidos) ANTES de gerar.
        Base: campo `custo` do models.json + params (duração, resolução)."""

    def gerar(self, modelo: str, params: dict, workdir: Path) -> Resultado:
        """Executa a geração. Bloqueante (faz o polling internamente).
        Grava resposta crua em workdir/raw/. Retorna Resultado ou levanta
        ProviderError(msg) — o executor captura e marca a parte `erro`."""

@dataclass
class Resultado:
    arquivo: Path        # artefato final já no lugar (faixa.mp3 etc.)
    custo_real: float    # USD efetivamente gasto (ou estimado se a API não informa)
    meta: dict           # ids remotos, seed, duração, o que ajudar no refazer
```

### 7.2 `providers/<nome>.models.json`

```jsonc
{
  "provider": "kie",
  "env_keys": ["KIE_API_KEY"],          // chaves que disponivel() procura
  "modelos": [
    {
      "id": "suno-v4.5",                // referenciado pelo plano como "kie:suno-v4.5"
      "capacidade": "musica",           // musica | imagem | video
      "custo": {"base_usd": 0.08, "por": "geracao"},   // ou {"por": "segundo"} p/ video
      "params": {                        // params aceitos, com default e domínio
        "duracao_s": {"default": 180, "max": 240},
        "instrumental": {"default": false},
        "estilo_prompt_max_chars": 1000
      }
    }
  ]
}
```

Sementes (mínimo viável): `kie` (música/Suno v4.5), `inemaimg` (capa, modelo `flux2-klein` — default de imagem do parque), `kling` (clipe, `kling-2.5` custo-benefício) e `agnes` (clipe, custo zero, qualidade menor). Adicionar provedor = criar o par `.py` + `.models.json`; nada mais muda.

---

## 8. Esquemas de dados (contratos fechados)

Todos os JSON têm `schema_version` (string `"1"`) no topo. Campo desconhecido = erro de validação no `plano`/`faz` (esquema fechado de verdade).

### 8.1 `plano.json` — O CONTRATO

```jsonc
{
  "schema_version": "1",
  "slug": "aniversario-da-lu",
  "criado_em": "2026-08-20T14:00:00-03:00",
  "solicitacao": "música de aniversário pop pra Lu, clipe alegre",   // texto livre original, verbatim
  "pesquisa": false,                       // fase 0 rodou?
  "estilo_ref": "pop-uplifting-electronic", // id do estilos.json usado como base, ou null
  "titulo": "Parabéns, Lu",                // título da obra

  "musica": {
    "motor": "kie:suno-v4.5",              // provider:modelo — NUNCA chumbado no código
    "params": {"duracao_s": 180, "instrumental": false},  // subconjunto válido do models.json
    "estilo": {                             // material criativo — o que o Suno recebe
      "genero": "Pop / Uplifting Electronic",
      "bpm": 120,
      "tom": "C maior",
      "mood": ["alegre", "festivo"],
      "instrumentacao": ["synth bass", "bateria eletrônica", "pads", "piano"],
      "voz": {"tipo": "feminina", "registro": "médio-agudo", "entrega": "melódica, calorosa", "harmonias": "backing nos refrões"},
      "prompt_estilo": "Uplifting pop, 120 bpm, C major, female warm vocals..."  // pronto p/ campo Style (respeita max_chars do modelo)
    },
    "estrutura": ["intro 4c", "verso 1", "refrão", "verso 2", "refrão", "ponte", "refrão final", "outro"],
    "letra": {
      "origem": "gerada",                   // "gerada" | "rascunho_usuario" | "final_usuario"
      "texto": "[Verse 1]\n...",            // letra completa com tags de seção
      "texto_original": null,               // o rascunho do usuário, se origem=rascunho_usuario (p/ diff)
      "idioma": "pt-BR"
    }
  },

  "capa": {
    "motor": "inemaimg:flux2-klein",
    "params": {"tamanho": "1024x1024"},
    "template": "retrato-centralizado",     // id do templates-capa.json, ou null (livre)
    "conceito": "Lu de perfil sorrindo sob confetes dourados, luz quente de festa",  // 1-2 frases, o porquê
    "prompt_imagem": "album cover, centered portrait of a smiling woman under golden confetti, warm party light, bokeh, bold title space at top, cinematic, 1:1",  // PRONTO pra colar no gerador
    "prompt_negativo": "text, watermark, logo",
    "paleta": ["#F5B942", "#2B1B4E"]
  },

  "clipe": {
    "motor": "kling:kling-2.5",
    "params": {"resolucao": "720p", "duracao_shot_s": 5},
    "template": "narrativo",                // id do templates-clipe.json
    "sincronia": "cortes no beat, um shot por seção da música",
    "decupagem": [                          // shots ordenados; duração total ~ duração da faixa (ou trecho)
      {
        "n": 1,
        "secao": "intro",                   // amarra com musica.estrutura
        "duracao_s": 5,
        "camera": "dolly-in lento",
        "descricao": "mesa de festa vazia ao amanhecer, balões",
        "prompt": "slow dolly-in, empty birthday party table at dawn, balloons, warm golden light, cinematic, 5s"  // PRONTO por shot
      }
      // ... shots 2..N
    ]
  }
}
```

Regras do contrato:
- `motor` sempre `"provider:modelo"` existente no registry (validado no `plano` e no `faz`).
- `params` só com chaves declaradas no `models.json` do modelo.
- `musica.letra.origem == "final_usuario"` ⇒ `texto` é imutável (o `ajusta` valida e recusa mudanças na letra).
- `clipe.decupagem[].prompt` e `capa.prompt_imagem` são **prontos** — o executor não reescreve prompt, só injeta params.

### 8.2 `estado.json` — fonte de verdade

```jsonc
{
  "schema_version": "1",
  "slug": "aniversario-da-lu",
  "atualizado_em": "2026-08-20T15:12:00-03:00",
  "fase": "execucao",                       // "plano" | "execucao" | "entregue"
  "telegram": false,                        // enviar na entrega?
  "teto_usd": null,                         // setado por `tudo --teto`
  "partes": {
    "musica": {
      "estado": "pronto",                   // planejado|aprovado|gerando|pronto|erro
      "aprovado_em": "2026-08-20T14:30:00-03:00",   // null se nunca aprovado
      "ajustes": 1,                         // quantas vezes passou por `ajusta`
      "tentativas": 1,                      // quantos `faz`
      "custo_estimado_usd": 0.08,
      "custo_real_usd": 0.08,
      "artefato": "faixa.mp3",              // null até pronto
      "erro": null,                         // {"quando": iso, "motor": "...", "msg": "..."} quando estado=erro
      "meta": {"kie_task_id": "abc123", "duracao_s": 178}
    },
    "capa":  { /* mesmo shape */ },
    "clipe": { /* mesmo shape */ }
  },
  "custo_total_usd": {"estimado": 1.28, "gasto": 0.08},
  "historico": [                            // log append-only de eventos (auditoria)
    {"quando": "2026-08-20T14:00:00-03:00", "evento": "plano", "detalhe": "criado"},
    {"quando": "2026-08-20T14:30:00-03:00", "evento": "ok", "parte": "musica"}
  ]
}
```

Escrita sempre atômica (tmp + rename). `estado.json` nunca contém chave de API nem prompt duplicado — prompts vivem no `plano.json`.

### 8.3 `data/estilos.json`

Campos derivados das análises reais do Gemini em `output/musical/analises/` (que trazem gênero, BPM, tonalidade, instrumentação, estrutura, mood, caracterização de voz por gênero/registro/entrega, produção/mix e prompts Suno prontos em versões curta e longa). Semeado **agora** com essas 7 análises + faixas do acervo (`output/musical/musicas/`, 28 mp3 Suno com variantes A/B).

```jsonc
{
  "schema_version": "1",
  "estilos": [
    {
      "id": "uplifting-ambient-electronic",
      "nome": "Uplifting Ambient Electronic",
      "genero": ["ambient electronic", "corporate tech", "uplifting"],
      "bpm": 103,
      "tom": "C maior",
      "mood": ["inspirador", "tecnológico", "moderno"],
      "instrumentacao": ["electronic drums", "clean synth bass", "ethereal pads", "bright synth melody"],
      "voz": {
        "presenca": "vocal chops",           // "lead" | "backing" | "vocal chops" | "instrumental"
        "tipos": [
          {"genero": "feminina", "registro": "agudo", "entrega": "ooh/aah etéreo"},
          {"genero": "masculina", "registro": "médio", "entrega": "chops rítmicos sutis"}
        ]
      },
      "estrutura_tipica": ["intro pad+arpejo", "main theme", "variação", "fade out"],
      "producao": "mix limpo, brilho nos médios-altos, sidechain sutil",
      "prompt_suno_curto": "Uplifting Ambient Electronic, 103 bpm, C Major. Smooth electronic drums, clean synth bass, ethereal pads, bright synth melody, female vocal chops, modern inspiring tech mood.",  // ≤200 chars, campo Style curto do Suno
      "prompt_suno_longo": "Uplifting ambient electronic at 103 bpm in C Major. Foundation of smooth programmed electronic drums with soft transients and a clean rounded synth bass locked to the kick. Ethereal evolving pads fill the midrange while a bright plucked synth melody carries the theme in sixteenth-note arpeggios. High-pitched female vocal chops (ooh/aah) float above, answered by subtle rhythmic male vocal chops. Clean modern mix, gentle sidechain pumping, airy top end, wide stereo pads, controlled low end. Mood: inspiring, optimistic, technological, forward-moving. Structure: pad+arp intro, main theme with full drums, subtle variation, gradual fade.",  // ≤1000 chars, campo Style longo
      "referencias": ["Counting Stars (OneRepublic) — vibe", "reel-facebook-2026-08"],
      "fonte": "output/musical/analises/analise-vozes-musica-fbvideo-gemini-v2.md",
      "tags": ["reel", "tech", "motivacional"]
    }
    // ... 1 entrada por análise + entradas do acervo Suno
  ]
}
```

### 8.4 `data/templates-capa.json` e `data/templates-clipe.json`

```jsonc
// templates-capa.json
{
  "schema_version": "1",
  "templates": [
    {
      "id": "tipografia-dominante",
      "nome": "Tipografia dominante",
      "descricao": "título enorme ocupa 60%+ do quadro; fundo texturizado simples",
      "composicao": "título centralizado, fundo gradiente/textura, sem figura humana",
      "quando_usar": ["música conceitual", "eletrônica", "sem persona"],
      "prompt_base": "album cover, massive bold typography as the main subject, textured gradient background, {paleta}, minimal, 1:1",
      "negativo_base": "faces, photo, watermark"
    },
    {
      "id": "retrato-centralizado",
      "nome": "Retrato centralizado",
      "descricao": "artista/persona no centro do quadro, luz dramática, espaço pro título em cima ou embaixo",
      "composicao": "retrato frontal ou 3/4 centralizado, fundo desfocado ou sólido, título fora do rosto",
      "quando_usar": ["música com persona forte", "voz lead marcante", "pop", "MPB"],
      "prompt_base": "album cover, centered dramatic portrait of {persona}, {luz}, shallow depth of field, {paleta}, space for bold title, cinematic, 1:1",
      "negativo_base": "text, watermark, logo, extra limbs"
    },
    {
      "id": "paisagem-simbolica",
      "nome": "Paisagem simbólica",
      "descricao": "cena ou paisagem que simboliza o tema central da letra, sem figura humana em destaque",
      "composicao": "paisagem/cena em plano aberto, horizonte na regra dos terços, título integrado ao céu ou área vazia",
      "quando_usar": ["letra temática/narrativa", "instrumental", "ambient", "trilha"],
      "prompt_base": "album cover, wide symbolic landscape of {simbolo}, {clima}, {paleta}, cinematic lighting, negative space for title, 1:1",
      "negativo_base": "text, watermark, logo, people in foreground"
    },
    {
      "id": "minimal-abstrato",
      "nome": "Minimal abstrato",
      "descricao": "formas geométricas ou abstratas em 2-3 cores; leitura instantânea em thumbnail",
      "composicao": "1 forma dominante no centro ou em terço, fundo chapado, máximo 3 cores",
      "quando_usar": ["eletrônica", "lo-fi", "conceitual", "séries/coleções de faixas"],
      "prompt_base": "album cover, minimal abstract geometric composition, {formas}, flat background, exactly {paleta}, high contrast, 1:1",
      "negativo_base": "text, watermark, photo, gradient noise, clutter"
    }
  ]
}
```

```jsonc
// templates-clipe.json
{
  "schema_version": "1",
  "templates": [
    {
      "id": "performance",
      "nome": "Performance",
      "descricao": "artista/persona 'cantando' em cenário; câmera orbita e alterna planos",
      "estrutura_shots": ["plano geral do cenário", "médio do intérprete", "close no refrão", "detalhe instrumental", "repetir alternando"],
      "sincronia": "corte no beat; close em todo refrão",
      "quando_usar": ["música com voz lead forte"]
    },
    {
      "id": "narrativo",
      "nome": "Narrativo",
      "descricao": "mini-história em 6-12 shots seguindo o arco da letra (setup → tensão → virada → resolução)",
      "estrutura_shots": ["setup do cenário/personagem", "gatilho da história", "desenvolvimento (2-4 shots)", "clímax no refrão final", "resolução no outro"],
      "sincronia": "1 shot por seção da música; virada da história cai no primeiro refrão",
      "quando_usar": ["letra com história clara", "balada", "sertanejo", "MPB"]
    },
    {
      "id": "lyric-video",
      "nome": "Lyric video",
      "descricao": "letra em tipografia animada sobre fundos gerados, um fundo por seção da música",
      "estrutura_shots": ["fundo do verso 1", "fundo do refrão (mais energia)", "fundo do verso 2", "fundo da ponte", "fundo do refrão final"],
      "sincronia": "troca de fundo exatamente na troca de seção; tipografia entra no beat",
      "quando_usar": ["letra é a estrela", "orçamento baixo de vídeo", "lançamento rápido"]
    },
    {
      "id": "abstrato-loop",
      "nome": "Abstrato / loop",
      "descricao": "visuais abstratos que respiram com o BPM; loops curtos reutilizados por seção",
      "estrutura_shots": ["loop A (versos)", "loop B mais intenso (refrões)", "loop C (ponte)", "variação de A no outro"],
      "sincronia": "pulso do visual casado com o BPM; troca de loop na troca de seção",
      "quando_usar": ["eletrônica", "instrumental", "ambient", "quando não há persona"]
    }
  ]
}
```

Cada template de clipe declara `estrutura_shots` (esqueleto) e `sincronia` — o planejador preenche a `decupagem` do plano a partir disso + estrutura da música.

### 8.5 Linha do `index.jsonl` (uma por slug)

```jsonc
{"slug": "aniversario-da-lu", "titulo": "Parabéns, Lu", "criado_em": "2026-08-20T14:00:00-03:00", "solicitacao": "música de aniversário pop pra Lu...", "estilo_ref": "pop-uplifting-electronic", "genero": "Pop / Uplifting Electronic", "bpm": 120, "tom": "C maior", "motores": {"musica": "kie:suno-v4.5", "capa": "inemaimg:flux2-klein", "clipe": "kling:kling-2.5"}, "estados": {"musica": "pronto", "capa": "aprovado", "clipe": "planejado"}, "custo_gasto_usd": 0.08, "tags": ["aniversario", "pop", "festa"]}
```

A linha é criada no `plano` e **reescrita por todo comando que muda estado** (`ok`, `ajusta`, `faz`, entrega) — estados e custo do index nunca ficam defasados; `reindex` é só recuperação de desastre (reconstrói tudo a partir das pastas). `lista` e `busca` leem só este arquivo. `busca` faz match case-insensitive em slug, título, solicitação, gênero e tags. Comando interno `reindex` (não listado no help principal) reconstrói o index a partir das pastas, como no analisevideo. O acervo **engorda a cada uso** e alimenta o planejador: no `plano`, as últimas N linhas + matches da busca pela solicitação entram no contexto do Fable.

---

## 9. Quem planeja, quem executa

- **Fable** escreve o plano das 3 partes, recebendo: solicitação + `estilos.json` + `templates-*.json` + acervo (`index.jsonl` relevante) + `pesquisa.md` (se houver). Fable também faz a **crítica/revisão** dos planos (um passe de auto-crítica antes de gravar: coerência letra↔estrutura↔decupagem, prompts completos, params válidos).
- **Opus** executa (`faz`): orquestra providers, valida contrato, contabiliza custo. O executor **não recria material criativo** — se falta algo no plano, é erro de validação, volta pro `ajusta`.
- `ajusta` reusa o Fable com o plano atual + a instrução, reescrevendo **só a seção da parte** e imprimindo diff.

---

## 10. Erros, custo e teto

- **Custo estimado na tela antes de todo `faz`** (por parte + total), via `estimar_custo()` do provider. Confirmação interativa (`--sim` pula).
- **Falha de um provedor NÃO derruba a corrida:** a parte vira `erro` no `estado.json` com a mensagem; as outras partes seguem. Exit code `2` sinaliza que houve erro parcial.
- `tudo --teto N` (USD): antes de cada parte, se `gasto + estimativa_da_parte > N`, a parte não roda (fica `aprovado`), imprime o motivo e o comando para: partes já feitas ficam; retomar depois é `musicavideo faz <slug>`.
- Retry: `faz` sobre parte `erro` re-executa com o mesmo plano. Timeout de polling por provider (default 15 min) → `erro` com motivo.
- Chaves: lidas em runtime de `~/projetos/openpcbotv2/.env` ou `~/projetos/wifi/.env` (nesta ordem); **nunca** copiadas para o repo, para a saída ou para logs; **nunca** impressas.

---

## 11. Critérios de sucesso

1. `musicavideo tudo "balada pop sobre recomeço" --teto 2` produz, sem intervenção, `faixa.mp3` + `capa.png` + `clipe.mp4` + `PACOTE.md` num slug novo, gastando ≤ US$ 2.
2. Fluxo com portão: `plano` → `ver musica` → `ajusta musica "mais lento, voz masculina"` (diff na tela) → `ok musica` → `faz musica` gera só a faixa; `capa` e `clipe` intocados.
3. `--letra arq --letra-final`: a letra sai no plano e na faixa **byte a byte** igual ao arquivo; `ajusta musica` recusa alterá-la.
4. Derrubar a chave do Kling: `faz` marca `clipe: erro` com motivo legível e ainda entrega música e capa (exit 2).
5. Parar depois do `ok capa`, voltar 3 dias depois: `faz <slug>` retoma exatamente de onde parou, lendo só o `estado.json`.
6. `busca "pop"` encontra o slug pelo index; a linha do index reflete estados e custo reais.
7. Provedor sem chave aparece em `plano` como indisponível **com o motivo**, sem stacktrace.
8. Nenhum valor de chave de API aparece em arquivo de saída, log ou tela.

---

## 12. Fora de escopo (YAGNI)

- **Nada de UI web** — CLI + SKILL.md apenas (o guia GitHub Pages é documentação estática, não app).
- **Nada de lote** — um slug por vez; sem fila, sem workers.
- **Não reescrever/absorver musicaclone nem bench-studio** — só o padrão de providers é emprestado.
- Sem edição de vídeo pós-geração (concat/legendas/mixagem do clipe com a faixa fica pra depois; o clipe entregue são os shots concatenados simples via ffmpeg, sem grading).
- Sem versionamento de planos além do `-vN` em `raw/`; sem multiusuário; sem banco relacional.
- Pesquisa web é fase 0 opt-in e ponto final — sem RAG, sem scraping contínuo.

---

## 13. Ordem de implementação (fatias entregáveis)

1. **Esqueleto + contrato:** repo, `musicavideo.sh`, `main.py`, validadores dos esquemas (§8), `estado.py` com a máquina de estados, `index.jsonl` (`lista`/`busca`/`reindex`). Testável sem nenhuma API.
2. **Dados-semente:** `data/estilos.json` a partir das 7 análises Gemini + acervo; `templates-capa.json` e `templates-clipe.json` com os 4 templates de cada.
3. **Planner:** `plano` + `ver` + `ajusta` + `ok` (Fable escreve/critica; letra rascunho vs final com diff). Fim da fatia: portão completo funciona, zero crédito gasto.
4. **Registry + provider música:** `registry.py`, `base.py`, `kie` (Suno). `faz musica` + `custo` de ponta a ponta.
5. **Capa:** `inemaimg` (flux2-klein). `faz capa`.
6. **Clipe:** `kling` + `agnes`; concat dos shots com ffmpeg. `faz clipe` + `tudo --teto`.
7. **Entrega + acabamento:** `PACOTE.md`, Telegram opcional, `pesquisa` (fase 0), `SKILL.md`, `.env.example`, `guia/index.html`, README.

Cada fatia termina rodável e testada antes da seguinte.

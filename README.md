# 🎬 musicavideo

## 📖 Guia de uso

Guia completo (landing + passo a passo): **https://inematds.github.io/musicavideo/guia/**

## 🔎 Como funciona por dentro

Fases e onde atuar, como refazer uma música, como a busca funciona, como o
planejamento decide e em cima de quê música e clipe são montados:
**[docs/COMO-FUNCIONA.md](docs/COMO-FUNCIONA.md)**

Você manda **uma solicitação em texto livre**. Sai **música + capa + clipe** —
em fases, com portão de aprovação em cada parte, ou sem portão nenhum.

```bash
bash musicavideo.sh plano "música de virada, rock feminino, sobre quem constrói em silêncio e agora cobra"
```

O plano das três partes é escrito antes de qualquer centavo sair. Você lê,
ajusta o que quiser, aprova parte por parte — e só então gera.

## Por que existe

Pedir "faz uma música sobre X" pra um agente genérico entrega uma faixa
qualquer, uma capa que não conversa com ela e nenhum clipe. Os três artefatos
saem desconexos porque nunca houve um plano comum.

Aqui a **fase de plano é o produto**: um `plano.json` de esquema fechado onde a
estrutura da música, o conceito da capa e a decupagem do clipe são decididos
juntos, olhando dois bancos medidos de material real — estilos musicais
(BPM, tom, instrumentação, voz) e referências visuais vindas do
[analisevideo](https://github.com/inematds/analisevideo) (paleta, câmera,
cortes por minuto). A execução é só a consequência — e é plugável.

## Como funciona

```
0. pesquisa   --pesquisa (opt-in)   → pesquisa.md            tempo
1. plano      Fable                 → plano.json + PLANO.md   ZERO
2. execução   por parte, com portão → faixa.mp3 capa.png clipe.mp4   gasta
3. entrega    automática            → PACOTE.md (+ Telegram)  ZERO
```

Cada parte anda sozinha:
`planejado → (ok) → aprovado → (faz) → gerando → pronto | erro`

Pode parar depois do `ok capa` e voltar três dias depois: o `estado.json` é a
fonte de verdade, `faz <slug>` retoma exatamente de onde parou.

## Instalação

```bash
git clone https://github.com/inematds/musicavideo.git && cd musicavideo
sudo apt install ffmpeg          # concat dos shots do clipe
# python3 stdlib apenas — nenhum pip install
```

As chaves são lidas em runtime de `~/projetos/openpcbotv2/.env` ou
`~/projetos/wifi/.env` (veja `.env.example`). Nada é copiado pro repo.

## Uso

```bash
S=./musicavideo.sh

# COM PORTÃO
bash $S plano "balada pop sobre recomeço" recomeco
bash $S ver    recomeco musica
bash $S ajusta recomeco musica "mais lento, voz masculina"   # mostra o diff
bash $S ok     recomeco musica
bash $S faz    recomeco musica                                # gasta

# SEM PORTÃO (com trava de gasto)
bash $S tudo "rock feminino de virada" --teto 2 --sim

# LETRA SUA
bash $S plano "sertanejo" --letra minha-letra.txt              # rascunho: ele termina
bash $S plano "sertanejo" --letra final.txt --letra-final      # lei: ninguém mexe

# ACERVO
bash $S lista 10
bash $S busca "rock"
bash $S custo recomeco
```

## Motores

| parte | default | custo | alternativas |
|---|---|---|---|
| música | `kie:suno-v4.5` | ~US$ 0,08 | — |
| capa | `agnes:agnes-image-2.1-flash` | **US$ 0** | `inemaimg:flux2-klein` (servidor local) |
| clipe | `agnes:agnes-video-v2.0` | **US$ 0** | `kling:kling-2.5`, `fal:kling-video-v2.5-turbo-pro` |

Os defaults são de custo zero na capa e no clipe de propósito: **roda em
qualquer VPS**. Trocar é `--motor clipe=kling:kling-2.5` — o motor mora no
plano, nunca no código.

Provedor sem chave não estoura erro na hora de gerar: aparece **indisponível
com o motivo** já no `plano`, e o `faz` daquela parte vira `erro` enquanto as
outras seguem (exit 2).

Adicionar um provedor = dois arquivos, `providers/<nome>.py` (implementando
`disponivel`/`estimar_custo`/`gerar`) e `providers/<nome>.models.json`
(declarando modelos, custo e params). Nada mais muda.

## Saída

```
~/projetos/output/musicavideo/
├── index.jsonl              # 1 linha por slug — lista/busca leem daqui
└── <slug>/
    ├── plano.json           # o contrato
    ├── PLANO.md             # o mesmo plano, pra você ler e aprovar
    ├── estado.json          # fonte de verdade (fases, custo, erros, histórico)
    ├── faixa.mp3  capa.png  clipe.mp4
    ├── PACOTE.md            # entrega (completa ou parcial, com o que falta)
    └── raw/                 # respostas cruas dos provedores
```

## Detalhes

- **Prompts de provedor saem em inglês** — a Agnes bloqueia português legítimo.
  O material criativo (conceito, letra, mood) continua em PT; o validador
  recusa o plano se um prompt de provedor vier acentuado.
- **Custo na tela antes de todo `faz`**, por parte e total. `--sim` pula a
  confirmação; `--teto N` no `tudo` para antes de estourar.
- **Exit codes:** `0` ok · `1` uso/validação · `2` parte em erro · `3` teto.
- `kling` e `fal` estão implementados por contrato e testados com mock — o
  teste contra a API real ainda não foi feito.

## Licença

MIT.

# 🎬 musicavideo

Você manda **uma frase**. Sai **música + capa + clipe** — em fases, aprovando
cada parte, e sem gastar nada até você mandar gastar.

```bash
bash musicavideo.sh plano "música de virada, rock feminino, sobre quem constrói em silêncio e agora cobra"
```

## 📖 Documentação

| | |
|---|---|
| **Guia de uso** (landing + passo a passo) | https://inematds.github.io/musicavideo/guia/ |
| **As fases, passo a passo** | [docs/FASES.md](docs/FASES.md) |
| **Como funciona por dentro** | [docs/COMO-FUNCIONA.md](docs/COMO-FUNCIONA.md) |
| **Interface pro bot / skill** | [SKILL.md](SKILL.md) |

---

## Por que existe

Pedir "faz uma música sobre X" para um agente genérico entrega uma faixa
qualquer, uma capa que não conversa com ela e nenhum clipe. Os três saem
desconexos porque nunca houve um plano comum.

Aqui **o plano é o produto**: um `plano.json` de esquema fechado onde a estrutura
da música, o conceito da capa e a decupagem do clipe são decididos **juntos**,
olhando dois bancos medidos de material real — estilos musicais (BPM, tom,
instrumentação, voz) e referências visuais vindas do
[analisevideo](https://github.com/inematds/analisevideo) (paleta em hex, câmera,
cortes por minuto). A execução é só a consequência — e é plugável.

**Planejar é barato, executar é caro.** Toda a qualidade se decide antes do
primeiro centavo.

---

## O que ele faz

**Escreve a música inteira** — estilo, BPM, tom, instrumentação, tipo de voz,
estrutura por seção e a letra. Ou usa a **sua** letra: como rascunho, ele termina
e mostra o diff; com `--letra-final`, ela é lei e nem o ajuste altera.

**Desenha a capa** — conceito, paleta e um prompt de imagem pronto, a partir de
4 composições (tipografia dominante, retrato centralizado, paisagem simbólica,
minimal abstrato).

**Decupa o clipe** — shot a shot, cobrindo a música **inteira**, com seção,
câmera, descrição e prompt próprio para cada um. Mais shots nos refrões. E um
**plano B** por shot, para quando o filtro de conteúdo barrar o principal.

**Gera de verdade** — faixa no Suno, capa e vídeo no Agnes, shots concatenados e
**casados com a música** por ffmpeg. Sai um clipe, não três arquivos soltos.

**Faz o clipe com as duas músicas** — o Suno entrega duas faixas pelo mesmo
preço, então o mesmo vídeo é casado com cada uma: `clipe-1.mp4` e `clipe-2.mp4`.
`clipe.mp4` é a versão da faixa aprovada — trocar de faixa depois (`aprova
<slug> musica --faixa 2`) só reaponta, sem re-render e sem custo.

**Deixa você aprovar duas vezes** — o plano, e depois o artefato gerado. Escolhe
entre as duas faixas que o Suno produz, reprova shots pelo número numa folha de
contato, regenera só o que não prestou.

**Não te surpreende na conta** — custo estimado na tela antes de cada geração,
teto opcional, e o que já foi pago nunca é apagado sem você mandar.

---

## Instalação

```bash
git clone https://github.com/inematds/musicavideo.git && cd musicavideo
sudo apt install ffmpeg          # concat, montagem e folha de contato
# python3 stdlib apenas — nenhum pip install
```

Chaves lidas em runtime de `~/projetos/openpcbotv2/.env` ou `~/projetos/wifi/.env`
(veja [.env.example](.env.example)). Nada é copiado para o repositório.

---

## Uso

### O caminho normal, com portões

```bash
S=./musicavideo.sh

bash $S plano "balada pop sobre recomeço" recomeco    # não gasta
bash $S ver     recomeco musica                       # lê o plano
bash $S ajusta  recomeco musica "mais lento, voz masculina"   # mostra o diff
bash $S ok      recomeco musica                       # portão do plano

bash $S faz     recomeco                              # gera SÓ a música (~US$ 0,08)
bash $S revisa  recomeco                              # ouve as 2 faixas
bash $S aprova  recomeco musica --faixa 2             # portão do artefato

bash $S faz     recomeco                              # agora capa e clipe (US$ 0)
bash $S revisa  recomeco clipe                        # folha de contato numerada
bash $S reprova recomeco clipe 9,11,12                # regenera só esses shots
bash $S faz     recomeco clipe
bash $S aprova  recomeco clipe                        # → PACOTE.md
```

### Sem portão, com trava de gasto

```bash
bash $S tudo "rock feminino de virada" --teto 2 --sim
```

### Sua letra

```bash
bash $S plano "sertanejo" --letra rascunho.txt              # ele termina, mostra o diff
bash $S plano "sertanejo" --letra final.txt --letra-final   # lei: ninguém mexe
```

### Acervo

```bash
bash $S lista 10
bash $S busca "rock"
bash $S custo recomeco
bash $S painel                  # abre o acervo no navegador (:5400)
```

**O painel** (`painel [--porta N] [--lan]`) sobe um servidor local em :5400 — só leitura,
sem chave nenhuma — com duas abas: os pacotes do musicavideo (capa, clipe,
faixa aprovada, PACOTE.md, estado por parte) e as análises do
[analisevideo](https://github.com/inematds/analisevideo) (paleta, look, ritmo,
tags, analise.md). Busca em tudo, na hora — a página é montada a cada request,
então nunca fica velha. Por padrão só em `127.0.0.1`; `--lan` publica na rede.

---

## Motores

| parte | default | custo | alternativas |
|---|---|---|---|
| música | `kie:suno-v4.5` | ~US$ 0,08 (traz 2 faixas) | — |
| capa | `agnes:agnes-image-2.1-flash` | **US$ 0** | `inemaimg:flux2-klein` (servidor local) |
| clipe | `agnes:agnes-video-v2.0` | **US$ 0** | `kling:kling-2.5`, `fal:kling-video-v2.5-turbo-pro` |

Os defaults de capa e clipe são de custo zero de propósito: **roda em qualquer
VPS**, sem conta em lugar nenhum. Trocar é uma flag —
`--motor clipe=kling:kling-2.5` — porque o motor mora no plano, nunca no código.

Provedor sem chave não estoura erro na hora de gerar: aparece **indisponível com
o motivo** já no plano, e o `faz` daquela parte vira `erro` enquanto as outras
seguem (exit 2).

**Adicionar um provedor são dois arquivos:** `providers/<nome>.py` (implementando
`disponivel` / `estimar_custo` / `gerar`) e `providers/<nome>.models.json`
(declarando modelos, custo e params aceitos). Nada mais no projeto muda.

---

## O que ele faz sozinho, e você nem vê

- **Retomada limpa** — parou no meio, caiu a luz, ctrl-c: o `estado.json` sabe
  exatamente onde estava. `faz <slug>` continua de onde parou.
- **Não paga duas vezes** — falha depois da geração (download, rede) reaproveita a
  task já paga em vez de gerar de novo.
- **Não regera o que já existe** — shots baixados numa corrida anterior são
  reaproveitados; só o que falta é gerado.
- **Shot barrado não encurta o clipe** — cascata: plano B → reescrita pelo Fable →
  variação de um vizinho da mesma seção. A duração total é sagrada, porque é ela
  que mantém imagem e música alinhadas.
- **Decupagem reajustada pela faixa real** — o plano chuta a duração; quando a
  música fica pronta com 30 s a mais, a decupagem é refeita **antes** de gerar
  vídeo.
- **Uma parte que falha não derruba as outras** — e o exit code diz isso.
- **Chave de API nunca aparece** em arquivo, log ou tela.

---

## Saída

```
~/projetos/output/musicavideo/
├── index.jsonl              # 1 linha por música — lista/busca leem daqui
└── <slug>/
    ├── plano.json           # o contrato
    ├── PLANO.md             # o mesmo plano, para você ler e aprovar
    ├── estado.json          # fonte de verdade: fases, custo, erros, histórico
    ├── faixa-1.mp3  faixa-2.mp3   # as duas da mesma geração
    ├── capa.png  clipe.mp4
    ├── revisao/contato-clipe.jpg  # folha de contato numerada dos shots
    ├── PACOTE.md            # entrega (completa ou parcial, com o que falta)
    └── raw/                 # respostas cruas, shots, versões anteriores
```

---

## Detalhes que importam

- **Prompts de provedor saem em inglês** — a Agnes bloqueia português legítimo. O
  material criativo (conceito, letra, mood) continua em PT; o validador recusa o
  plano se um prompt de provedor vier acentuado.
- **Exit codes:** `0` ok · `1` uso/validação · `2` parte em erro · `3` teto.
- **133 testes**, rodando em ~3 s: `python3 -m pytest tests/ -q`. Nenhum toca API
  real; os de montagem e folha de contato usam ffmpeg de verdade com mídia
  sintética.
- `kling` e `fal` estão implementados e cobertos por teste de contrato, mas ainda
  não foram exercitados contra a API real.

## Licença

MIT.

# 🎬 musicavideo

Você manda **uma frase**. Sai **música + capa + clipe** — em fases, aprovando
cada parte, e sem gastar nada até você mandar gastar.

```bash
bash musicavideo.sh plano "música de virada, rock feminino, sobre quem constrói em silêncio e agora cobra"
```

Melhorias pedidas e ainda não feitas: [`docs/MELHORIAS.md`](docs/MELHORIAS.md).

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
bash $S nuvem MVD-014           # aprova essa produção para a vitrine pública
bash $S publica-hf              # sobe o aprovado para o Hugging Face
```

**Cada produção tem um número: `MVD-001`, `MVD-002`, …** Atribuído uma vez, na
ordem de criação, gravado no `estado.json` e nunca renumerado — nem quando a
pasta é apagada. É o que aparece no card, o que a busca aceita e o que os
comandos entendem no lugar do slug (`arte MVD-014 --versao 2`). O slug continua
sendo o nome da pasta; o MVD é o nome que se diz em voz alta.

**O painel** (`painel [--porta N] [--lan]`) sobe um servidor local em :5400 — só leitura,
sem chave nenhuma — com duas abas: os pacotes do musicavideo e as análises do
[analisevideo](https://github.com/inematds/analisevideo) (paleta, look, ritmo,
tags, analise.md). Busca em tudo, na hora — a página é montada a cada request,
então nunca fica velha. Por padrão só em `127.0.0.1`; `--lan` publica na rede local (sem senha — quem
alcançar a porta vê o acervo inteiro).

**Um card por PRODUÇÃO, as duas versões dentro dele.** O Suno entrega duas
faixas por música e cada uma vira um clipe — mas é uma produção só: uma pasta,
um plano, uma letra, um custo, um botão de lixeira. Dois cards separados
duplicariam esses números e quebrariam a comparação, que é justamente a decisão
que se toma ali (qual das duas aprovar).

Na **grade**, o topo do card traz as duas capas lado a lado, cada uma com o seu
play — `v1 ✓` marca a aprovada. Dá para ouvir as duas sem abrir nada. Produção
antiga que só tem uma capa mostra a mesma imagem nas duas colunas: o que não
pode faltar é o play da segunda faixa.

**Abrindo o card**, as versões vêm empilhadas — capa da versão, player da faixa,
link para assistir o clipe daquela versão — e embaixo, fechado, o expansível
**"ver os prompts que foram para os provedores"**: conceito e tagline da capa, o
prompt de estilo que o Suno leu, o prompt da capa e o negativo, e a decupagem
plano a plano (seção, câmera, prompt e o `prompt_alt` de cada shot). É o que se
quer ver quando o resultado sai diferente do plano, e antes só existia dentro do
`plano.json`. Depois dele seguem o PACOTE.md e o PLANO.md.

**Cada versão tem a SUA capa**, não a mesma imagem com um selo trocado: a versão
1 usa o fundo da capa aprovada e, da 2 em diante, o `inemaimg` (flux2-klein,
local, custo zero) gera uma imagem própria com o mesmo prompt — mesma direção de
arte, cena nova. O título NÃO muda: é a mesma música, e nome diferente faria o
acervo e a busca mentirem; quem separa as duas é o selo `VERSÃO`. Servidor local
fora do ar não quebra nada — a versão cai de volta no fundo compartilhado e o
comando avisa. Para refazer numa produção que já existe:

```bash
bash $S arte <slug> --versao 2 --nova     # gera imagem nova para a versão 2
bash $S arte <slug> --versao 2            # só recompõe a arte sobre a crua (de graça)
```

### A nuvem (V2): Hugging Face + `musicavideo-pub`

O painel local (`INEMA MUSICAVIDEO V1.x.x`) só existe onde o acervo existe. A
vitrine é a outra metade: os finais vão para um dataset público do Hugging Face
e o painel público roda na Vercel, em repo próprio
([musicavideo-pub](https://github.com/inematds/musicavideo-pub),
`INEMA MUSICAVIDEO V2.x.x`). São dois apps — ligar um não desliga o outro.

```bash
bash $S nuvem MVD-014            # aprova a subida (o mesmo que o botão no card)
bash $S nuvem MVD-014 --cancela  # tira do ar (marca pendência de remoção)
bash $S nuvem --todos            # aprova tudo que tem clipe e capa
bash $S publica-hf --dry         # o que subiria, sem subir
bash $S publica-hf               # sobe o aprovado e reescreve o manifest.json
bash $S publica-hf --manifesto   # só o manifesto, sem reenviar arquivo nenhum
```

**Aprovar é o único gesto.** Subir não é consequência de ficar pronto: produção
pronta é material de trabalho, vitrine é escolha. O clique marca no
`estado.json`; quem sobe é o `publica-hf`, à mão ou pelo `cron-nuvem.sh`
(instruções de instalação dentro do próprio arquivo).

**Sobe só o final.** O `raw/` inteiro fica na máquina — 1209 dos 1365 mp4 do
acervo são shots intermediários. E o `clipe.mp4` não sobe quando existe
versionado: 28 dos 29 são cópia byte a byte de um `clipe-N.mp4`, e o manifesto
guarda qual é a aprovada. Acervo de 15 GB, ~4,4 GB publicáveis.

**A aba de análises sobe como TEXTO.** Nada de `fonte.mp4`: é vídeo de terceiros
baixado do YouTube, e re-hospedar seria redistribuição. Vai a análise escrita, e
o vídeo original aparece pelo embed oficial.

**Um coletor só.** O `manifest.json` sai do mesmo `painel.coletar()` que a tela
local usa, com as URLs reescritas para o HF — dois coletores divergiriam e
ninguém saberia qual painel está certo.

---

## Motores

| parte | default | custo | alternativas |
|---|---|---|---|
| música | `kie:suno-v4.5` | ~US$ 0,08 (traz 2 faixas) | — |
| capa | `agnes:agnes-image-2.1-flash` | **US$ 0** | `inemaimg:flux2-klein` (servidor local) |
| clipe | `agnes:agnes-video-v2.0` | **US$ 0** | `kling:kling-v2_5`, `fal:kling-v3-turbo` |

Os defaults de capa e clipe são de custo zero de propósito: **roda em qualquer
VPS**, sem conta em lugar nenhum. Trocar é uma flag —
`--motor clipe=kling:kling-v2_5` — porque o motor mora no plano, nunca no código.

Provedor sem chave não estoura erro na hora de gerar: aparece **indisponível com
o motivo** já no plano, e o `faz` daquela parte vira `erro` enquanto as outras
seguem (exit 2).

**Trocar para provedor que gasta exige autorização explícita.** `kie`, `kling` e
`fal` consomem crédito de conta ou dinheiro, então um `--motor` que aponte para
eles é recusado sem `--autorizo-pago` no mesmo comando. É portão e não aviso
porque o caso real foi este: em 2026-08-21, com a Agnes parecendo fora do ar no
meio de um clipe, a troca "óbvia" de motor queimou 105 créditos antes de alguém
perceber — e a Agnes nem estava fora, era um 404 transitório no poll que o
adaptador tratava como fatal.

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

## No bot do Telegram (inemaccbot)

Este repo é plugado no bot como FLUXO: `/musicavideo <sua descrição>`. Desde
2026-08-21 as quatro fases rodam **sem agente** — o `flow.json` declara o comando
de cada uma (`plano`, `faz musica`, `faz` capa+clipe, `pacote`) e quem executa é
o bot. Detalhe da mecânica em [SKILL.md](SKILL.md); a ajuda dentro do chat é
`/musicavideo help`, que sai do [HELP.md](HELP.md) deste repo.

O que chega no chat, em cada portão: o `PLANO.md` para você ler e aprovar, a
faixa e a capa como arquivo, e o clipe como **link** — mp4 de música passa dos
50 MB que o Telegram aceita como documento.

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

# Nota — plano `musicavideo-artista` (a fazer)

Status: **anotação**, não implementado. Definir o plano antes de codar.

Versão alvo: **v3.0.0** (major). A linha atual é a 2.x.x, aberta pelos recursos de
painel e vitrine. Como é major, o resto zera: `3.0.0`.

## Ideia

Criar a noção de **artista** no musicavideo: uma identidade persistente que, ao gerar
música/vídeo, injeta automaticamente referências de voz, estilo e aparência — em vez de
redescrever tudo a cada geração.

## O que um artista guarda

- **Identidade**: código curto (ex.: `agnes`, `nyx`), nome artístico, bio de uma linha.
- **Voz**: tipo (timbre, gênero vocal, tessitura), sotaque/idioma, `styleWeight` e tags de
  vocal que o Suno/Kie entende.
- **Estilo musical**: gêneros, BPM típico, instrumentação, referências sonoras, negativos.
- **Referências físicas** (para vídeo/capa): descrição do rosto/corpo/figurino, paleta,
  imagens de referência em disco (reference-to-video do Wan, capa, lipsync).
- **Estética visual**: look, LUT/grain, tipo de cenário, enquadramentos preferidos.

## Duas formas de fazer (decidir)

1. **Novo domínio `artista/`** — pasta própria com esquema, validação e CRUD; o artista vira
   entidade de primeira classe do pipeline, referenciada por id nas músicas.
2. **Só um seletor** — `--artista <codigo>` na CLI/painel, lendo um YAML/JSON em `data/artistas/`
   e mesclando os campos nos prompts existentes, no mesmo formato dos parâmetros atuais.

Inclinação: começar por (2) — arquivo por artista + flag — e só promover a domínio se a
duplicação aparecer. Menor mudança que entrega o valor.

## Perguntas abertas

- O artista sobrescreve ou só preenche default do que o usuário não passou?
- Onde ficam as imagens de referência (repo vs. `~/projetos/output`)?
- Um artista pode ter variações (looks) como os avatares do HeyGen?

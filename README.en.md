# 🎬 musicavideo

**🇧🇷 [Português](README.md) · 🇺🇸 [English](README.en.md) · 🇪🇸 [Español](README.es.md)**

You send **one sentence**. You get **music + cover art + video** — in stages, approving each part, and spending nothing until you tell it to.

```bash
bash musicavideo.sh plano "turnaround song, female rock, about someone who builds in silence and is now demanding their due"
```

Requested improvements that haven’t been made yet: [`docs/MELHORIAS.md`](docs/MELHORIAS.md).

## 📖 Documentation

| | |
|---|---|
| **User guide** (landing page + step-by-step instructions) | https://inematds.github.io/musicavideo/guia/en/ |
| **The stages, step by step** | [docs/FASES.md](docs/FASES.md) |
| **Redo: change what’s already been done** (all commands and flags) | [docs/REFAZER.md](docs/REFAZER.md) |
| **How it works under the hood** | [docs/COMO-FUNCIONA.md](docs/COMO-FUNCIONA.md) |
| **Interface for the bot / skill** | [SKILL.md](SKILL.md) |

---

## Why it exists

Asking a generic agent to “make a song about X” gets you some song, cover art that doesn’t fit it, and no video. The three come out disconnected because there was never a shared plan.

Here, **the plan is the product**: a `plano.json` with a fixed schema where the song structure, cover concept, and video shot breakdown are decided **together**, using two measured databases of real material — musical styles (BPM, key, instrumentation, vocals) and visual references from [analisevideo](https://github.com/inematds/analisevideo) (hex palette, camera, cuts per minute). Execution is just the result — and it’s pluggable.

**Planning is cheap; execution is expensive.** All the quality decisions are made before the first cent is spent.

---

## What it does

**Writes the entire song** — style, BPM, key, instrumentation, vocal type, section-by-section structure, and lyrics. Or use **your** lyrics: as a draft, it finishes them and shows the diff; with `--letra-final`, they’re final, and not even the adjustment step can change them.

**Designs the cover art** — concept, palette, and a ready-to-use image prompt, based on 4 compositions (dominant typography, centered portrait, symbolic landscape, abstract minimalism).

**Breaks down the video** — shot by shot, covering the **entire** song, with a section, camera, description, and custom prompt for each shot. More shots in the choruses. And a **Plan B** for each shot in case the content filter blocks the main one.

**Actually generates everything** — a track in Suno, cover art and video in Agnes, shots concatenated and **matched to the music** with ffmpeg. You get a video, not three separate files.

**Makes the video with both songs** — Suno delivers two tracks for the same price, so the same video is matched to each one: `clipe-1.mp4` and `clipe-2.mp4`. `clipe.mp4` is the version for the approved track — switching tracks later (`aprova <slug> musica --faixa 2`) just redirects it, with no re-render or cost.

**Lets you approve twice** — the plan, then the generated artifact. Choose between the two tracks Suno produces, reject shots by number on a contact sheet, and regenerate only the ones that didn’t work.

**No surprises on your bill** — estimated cost shown before each generation, an optional spending cap, and anything already paid for is never deleted unless you ask.

---

## Installation

```bash
git clone https://github.com/inematds/musicavideo.git && cd musicavideo
sudo apt install ffmpeg          # concat, assembly, and contact sheet
# python3 stdlib only — no pip install
```

Keys are read at runtime from `~/projetos/openpcbotv2/.env` or `~/projetos/wifi/.env`
(see [.env.example](.env.example)). Nothing is copied into the repository.

---

## Usage

### The normal flow, with approval gates

```bash
S=./musicavideo.sh

bash $S plano "pop ballad about starting over" recomeco    # costs nothing
bash $S ver     recomeco musica                            # reads the plan
bash $S ajusta  recomeco musica "slower, male vocals"       # shows the diff
bash $S ok      recomeco musica                            # plan approval gate

bash $S faz     recomeco                                    # generates ONLY the music (~US$ 0,08)
bash $S revisa  recomeco                                    # listen to the 2 tracks
bash $S aprova  recomeco musica --faixa 2                   # artifact approval gate

bash $S faz     recomeco                                    # now the cover art and video (US$ 0)
bash $S revisa  recomeco clipe                              # numbered contact sheet
bash $S reprova recomeco clipe 9,11,12                      # regenerates only those shots
bash $S faz     recomeco clipe
bash $S aprova  recomeco clipe                              # → PACOTE.md
```

### Without approval gates, with a spending lock

```bash
bash $S tudo "female rock turnaround song" --teto 2 --sim
```

### Your lyrics

```bash
bash $S plano "sertanejo" --letra rascunho.txt              # it finishes them and shows the diff
bash $S plano "sertanejo" --letra final.txt --letra-final   # final: no one can change them
```

### Archive

```bash
bash $S lista 10
bash $S busca "rock"
bash $S custo recomeco
bash $S painel                  # opens the archive in the browser (:5400)
bash $S nuvem MVD-014           # approves this production for the public showcase
bash $S publica-hf              # uploads the approved production to Hugging Face
```

**Each production has a number: `MVD-001`, `MVD-002`, …** Assigned once, in creation order, recorded in `estado.json`, and never renumbered — even when the folder is deleted. It’s what appears on the card, what search accepts, and what commands understand in place of the slug (`arte MVD-014 --versao 2`). The slug remains the folder name; MVD is the name you say out loud.

**The dashboard** (`painel [--porta N] [--lan]`) starts a local server on :5400 — read-only, with no keys — with two tabs: musicavideo packages and [analisevideo](https://github.com/inematds/analisevideo) analyses (palette, look, rhythm, tags, analise.md). Searches everything instantly — the page is built on every request, so it never goes stale. By default, it’s only available at `127.0.0.1`; `--lan` makes it available on the local network (no password — anyone who can reach the port can see the entire archive).

**It stays up on its own.** The dashboard is the workbench: being down because you forgot to run the command is a defect, not a saving. A user systemd service keeps it running from boot.

```bash
systemctl --user status  musicavideo-painel     # check its status
systemctl --user restart musicavideo-painel     # after editing painel.py
journalctl --user -u musicavideo-painel -f      # what it’s reporting
```

The file is `~/.config/systemd/user/musicavideo-painel.service` (runs
`painel --lan`, `Restart=always`, and requires `loginctl enable-linger $USER` to
start without an open session). You can still run `musicavideo painel` manually —
just choose another port so it doesn’t conflict with the service.

**One card per PRODUCTION, with both versions inside.** Suno delivers two tracks per song, and each gets its own video — but it’s one production: one folder, one plan, one set of lyrics, one cost, one trash button. Two separate cards would duplicate those numbers and break the comparison, which is exactly the decision being made there (which of the two to approve).

In the **grid**, the top of the card shows both covers side by side, each with its own play button — `v1 ✓` marks the approved one. You can listen to both without opening anything. Older productions with only one cover show the same image in both columns: the important thing is that the second track has a play button.

**When you open the card**, the versions are stacked — version cover, track player, link to watch that version’s video — with a collapsed **“see the prompts sent to providers”** section below: cover concept and tagline, the style prompt Suno received, the cover prompt and negative prompt, and the shot-by-shot breakdown (section, camera, prompt, and each shot’s `prompt_alt`). This is what you want to see when the result differs from the plan; before, it was only available inside `plano.json`. PACOTE.md and PLANO.md follow.

**Each version has ITS OWN cover**, not the same image with a different badge: version 1 uses the approved cover background, and version 2 onward uses `inemaimg` (flux2-klein, local, zero cost) to generate its own image with the same prompt — same art direction, new scene. The title does NOT change: it’s the same song, and a different name would mislead the archive and search; the `VERSÃO` badge distinguishes the two. If the local server is down, nothing breaks — the version falls back to the shared background and the command displays a message. To redo this for an existing production:

```bash
bash $S arte <slug> --versao 2 --nova     # generates a new image for version 2
bash $S arte <slug> --versao 2            # just recomposes the art over the raw image (free)
```

### The cloud (V2): Hugging Face + `musicavideo-pub`

The local dashboard (`INEMA MUSICAVIDEO V1.x.x`) exists only where the archive exists. The showcase is the other half: final files go to a public Hugging Face dataset, and the public dashboard runs on Vercel, in its own repo
([musicavideo-pub](https://github.com/inematds/musicavideo-pub),
`INEMA MUSICAVIDEO V2.x.x`). These are two apps — starting one doesn’t shut down the other.

```bash
bash $S nuvem MVD-014            # approves the upload (same as the card button)
bash $S nuvem MVD-014 --cancela  # takes it offline (marks it for removal)
bash $S nuvem --todos            # approves everything that has a video and cover
bash $S publica-hf --dry         # what would be uploaded, without uploading
bash $S publica-hf               # uploads approved items and rewrites manifest.json
bash $S publica-hf --manifesto   # only the manifest, without re-uploading any files
```

**Approval is the only action.** Uploading doesn’t happen automatically when something is finished: a finished production is work material; the showcase is a choice. The click marks it in `estado.json`; `publica-hf`, run manually, does the rest: uploads to HF, writes `manifest.json` in the showcase repo, and **commits and pushes**. Publishing is a single command.

**It uploads what’s missing, not the whole archive.** Items already uploaded and unchanged since then are skipped (final files’ mtimes compared with `publicado_em`). To force a production to be re-uploaded, specify its name: `publica-hf <slug>` ignores the filter.

**Only the final file is uploaded.** The entire `raw/` directory stays on the machine — 1209 of the archive’s 1365 mp4 files are intermediate shots. And `clipe.mp4` isn’t uploaded when versioned files exist: 28 of the 29 are byte-for-byte copies of a `clipe-N.mp4`, and the manifest records which one is approved. A 15 GB archive, ~4.4 GB available for publishing.

**The analyses tab is uploaded as TEXT.** No `fonte.mp4`: it’s a third-party video downloaded from YouTube, and re-hosting it would be redistribution. The written analysis is uploaded, and the original video appears through the official embed.

**Just one collector.** `manifest.json` comes from the same `painel.coletar()` function the local dashboard uses, with URLs rewritten for HF — two collectors would diverge, and no one would know which dashboard is correct.

---

## Engines

| part | default | cost | alternatives |
|---|---|---|---|
| music | `kie:suno-v4.5` | ~US$ 0,08 (includes 2 tracks) | — |
| cover art | `agnes:agnes-image-2.1-flash` | **US$ 0** | `inemaimg:flux2-klein` (local server) |
| video | `agnes:agnes-video-v2.0` | **US$ 0** | `kling:kling-v2_5`, `fal:kling-v3-turbo` |

The cover art and video defaults are intentionally free: **runs on any VPS**, with no account anywhere. Switching is a flag —
`--motor clipe=kling:kling-v2_5` — because the engine lives in the plan, never in the code.

A provider without a key doesn’t throw an error when it’s time to generate: it appears as **unavailable, with the reason**, in the plan, and `faz` for that part returns `erro` while the others continue (exit 2).

**Switching to a paid provider requires explicit authorization.** `kie`, `kling`, and `fal` use account credits or money, so a `--motor` pointing to one of them is rejected unless `--autorizo-pago` is included in the same command. This is a gate, not a warning, because this actually happened: on 2026-08-21, with Agnes seemingly down in the middle of a video, the “obvious” engine switch burned 105 credits before anyone noticed — and Agnes wasn’t even down; it was a transient 404 during polling that the adapter treated as fatal.

**Adding a provider takes two files:** `providers/<nome>.py` (implementing
`disponivel` / `estimar_custo` / `gerar`) and `providers/<nome>.models.json`
(declaring models, cost, and accepted params). Nothing else in the project changes.

---

## What it handles on its own, without you seeing it

- **Clean resumption** — stopped midway, lost power, ctrl-c: `estado.json` knows exactly where it was. `faz <slug>` picks up where it left off.
- **No double charges** — if it fails after generation (download, network), it reuses the already-paid task instead of generating again.
- **Doesn’t regenerate what already exists** — shots downloaded in a previous run are reused; only missing ones are generated.
- **A blocked shot doesn’t shorten the video** — fallback sequence: Plan B → rewrite by Fable → variation of a neighbor from the same section. The total duration is fixed because it keeps the image and music aligned.
- **Breakdown adjusted to the actual track** — the plan estimates the duration; when the finished song is 30 seconds longer, the breakdown is redone **before** generating the video.
- **One failed part doesn’t stop the others** — and the exit code tells you that.
- **API keys never appear** in files, logs, or on screen.

---

## In the Telegram bot (inemaccbot)

This repo is plugged into the bot as a FLOW: `/musicavideo <your description>`. Since 2026-08-21, the four stages run **without an agent** — `flow.json` declares the command for each one (`plano`, `faz musica`, `faz` cover + video, `pacote`), and the bot executes them. Mechanics are detailed in [SKILL.md](SKILL.md); in-chat help is `/musicavideo help`, from this repo’s [HELP.md](HELP.md).

At each approval gate, the chat receives the `PLANO.md` for you to read and approve, the track and cover art as files, and the video as a **link** — music video mp4 files exceed Telegram’s 50 MB document limit.

## Output

```
~/projetos/output/musicavideo/
├── index.jsonl              # 1 line per song — list/search read from here
└── <slug>/
    ├── plano.json           # the contract
    ├── PLANO.md             # the same plan, for you to read and approve
    ├── estado.json          # source of truth: stages, cost, errors, history
    ├── faixa-1.mp3  faixa-2.mp3   # both from the same generation
    ├── capa.png  clipe.mp4
    ├── revisao/contato-clipe.jpg  # numbered contact sheet of the shots
    ├── PACOTE.md            # delivery (complete or partial, with what’s missing)
    └── raw/                 # raw responses, shots, previous versions
```

---

## Details that matter

- **Provider prompts are in English** — Agnes blocks legitimate Portuguese. The creative material (concept, lyrics, mood) stays in PT; the validator rejects the plan if a provider prompt contains accented characters.
- **Exit codes:** `0` ok · `1` usage/validation · `2` part failed · `3` cap reached.
- **133 tests**, running in ~3 s: `python3 -m pytest tests/ -q`. None call a real API; assembly and contact sheet tests use ffmpeg with synthetic media.
- `kling` and `fal` are implemented and covered by contract tests, but haven’t yet been exercised against the real API.

## License

MIT.

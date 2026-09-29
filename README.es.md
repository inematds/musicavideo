# 🎬 musicavideo

**🇧🇷 [Português](README.md) · 🇺🇸 [English](README.en.md) · 🇪🇸 [Español](README.es.md)**

Envías **una frase**. Obtienes **música + portada + videoclip** — por etapas, aprobando cada parte y sin gastar nada hasta que indiques que se gaste.

```bash
bash musicavideo.sh plano "música de giro, rock femenino, sobre quienes construyen en silencio y ahora exigen lo suyo"
```

Mejoras solicitadas y aún pendientes: [`docs/MELHORIAS.md`](docs/MELHORIAS.md).

## 📖 Documentación

| | |
|---|---|
| **Guía de uso** (landing + paso a paso) | https://inematds.github.io/musicavideo/guia/es/ |
| **Las fases, paso a paso** | [docs/FASES.md](docs/FASES.md) |
| **Rehacer: cambiar lo que ya se hizo** (todos los comandos y flags) | [docs/REFAZER.md](docs/REFAZER.md) |
| **Cómo funciona por dentro** | [docs/COMO-FUNCIONA.md](docs/COMO-FUNCIONA.md) |
| **Interfaz para el bot / skill** | [SKILL.md](SKILL.md) |

---

## Por qué existe

Pedirle a un agente genérico «haz una canción sobre X» da como resultado cualquier tema, una portada que no conecta con él y ningún videoclip. Los tres quedan desconectados porque nunca hubo un plan común.

Aquí **el plan es el producto**: un `plano.json` de esquema cerrado donde la estructura de la música, el concepto de la portada y el desglose del videoclip se deciden **juntos**, consultando dos bancos de material real medido: estilos musicales (BPM, tono, instrumentación, voz) y referencias visuales provenientes de [analisevideo](https://github.com/inematds/analisevideo) (paleta en hex, cámara, cortes por minuto). La ejecución es solo la consecuencia, y se puede conectar con distintos motores.

**Planificar es barato; ejecutar es caro.** Toda la calidad se decide antes del primer centavo.

---

## Qué hace

**Escribe la canción completa** — estilo, BPM, tono, instrumentación, tipo de voz, estructura por sección y letra. O usa **tu** letra: como borrador, la completa y muestra el diff; con `--letra-final`, es la ley y ni siquiera el ajuste puede cambiarla.

**Diseña la portada** — concepto, paleta y un prompt de imagen listo, a partir de 4 composiciones (tipografía dominante, retrato centrado, paisaje simbólico, minimalismo abstracto).

**Desglosa el videoclip** — plano a plano, cubriendo **toda** la canción, con sección, cámara, descripción y un prompt propio para cada uno. Más planos en los estribillos. Y un **plan B** por plano, por si el filtro de contenido bloquea el principal.

**Genera de verdad** — pista en Suno, portada y video en Agnes, planos concatenados y **sincronizados con la música** mediante ffmpeg. Obtienes un videoclip, no tres archivos sueltos.

**Crea el videoclip con las dos canciones** — Suno entrega dos pistas por el mismo precio, así que el mismo video se sincroniza con cada una: `clipe-1.mp4` y `clipe-2.mp4`. `clipe.mp4` es la versión de la pista aprobada; cambiar de pista después (`aprova
<slug> musica --faixa 2`) solo cambia la referencia, sin volver a renderizar ni generar costo.

**Te deja aprobar dos veces** — el plan y luego el artefacto generado. Elige entre las dos pistas que produce Suno, rechaza planos por número en una hoja de contacto y regenera solo lo que no quedó bien.

**No te sorprende con la cuenta** — costo estimado en pantalla antes de cada generación, límite opcional y lo que ya se pagó nunca se borra sin que lo indiques.

---

## Instalación

```bash
git clone https://github.com/inematds/musicavideo.git && cd musicavideo
sudo apt install ffmpeg          # concat, montaje y hoja de contacto
# solo python3 stdlib — no requiere pip install
```

Las claves se leen en runtime desde `~/projetos/openpcbotv2/.env` o `~/projetos/wifi/.env`
(consulta [.env.example](.env.example)). No se copia nada al repositorio.

---

## Uso

### El flujo normal, con etapas de aprobación

```bash
S=./musicavideo.sh

bash $S plano "balada pop sobre volver a empezar" recomeco    # no gasta
bash $S ver     recomeco musica                       # lee el plan
bash $S ajusta  recomeco musica "más lenta, voz masculina"   # muestra el diff
bash $S ok      recomeco musica                       # aprobación del plan

bash $S faz     recomeco                              # genera SOLO la música (~US$ 0,08)
bash $S revisa  recomeco                              # escucha las 2 pistas
bash $S aprova  recomeco musica --faixa 2             # aprobación del artefacto

bash $S faz     recomeco                              # ahora portada y videoclip (US$ 0)
bash $S revisa  recomeco clipe                        # hoja de contacto numerada
bash $S reprova recomeco clipe 9,11,12                # regenera solo esos planos
bash $S faz     recomeco clipe
bash $S aprova  recomeco clipe                        # → PACOTE.md
```

### Sin etapas de aprobación, con límite de gasto

```bash
bash $S tudo "rock femenino de giro" --teto 2 --sim
```

### Tu letra

```bash
bash $S plano "sertanejo" --letra rascunho.txt              # la completa y muestra el diff
bash $S plano "sertanejo" --letra final.txt --letra-final   # es la ley: nadie la toca
```

### Colección

```bash
bash $S lista 10
bash $S busca "rock"
bash $S custo recomeco
bash $S painel                  # abre la colección en el navegador (:5400)
bash $S nuvem MVD-014           # aprueba esta producción para la vitrina pública
bash $S publica-hf              # sube la aprobada a Hugging Face
```

**Cada producción tiene un número: `MVD-001`, `MVD-002`, …** Se asigna una sola vez, en orden de creación, se guarda en `estado.json` y nunca se vuelve a numerar, ni siquiera cuando se borra la carpeta. Es lo que aparece en la tarjeta, lo que acepta la búsqueda y lo que entienden los comandos en lugar del slug (`arte MVD-014 --versao 2`). El slug sigue siendo el nombre de la carpeta; MVD es el nombre que se dice en voz alta.

**El panel** (`painel [--porta N] [--lan]`) inicia un servidor local en :5400 — solo lectura, sin ninguna clave — con dos pestañas: los paquetes de musicavideo y los análisis de [analisevideo](https://github.com/inematds/analisevideo) (paleta, look, ritmo, tags, analise.md). Busca en todo, al instante: la página se genera con cada request, así que nunca queda desactualizada. Por defecto, solo en `127.0.0.1`; `--lan` lo publica en la red local (sin contraseña: quien pueda acceder al puerto verá toda la colección).

**Se mantiene en línea por sí solo.** El panel es la mesa de trabajo: que esté fuera de línea por olvidar ejecutar el comando es un defecto, no un ahorro. Un servicio de systemd del usuario lo mantiene activo desde el arranque.

```bash
systemctl --user status  musicavideo-painel     # en qué estado está
systemctl --user restart musicavideo-painel     # después de modificar painel.py
journalctl --user -u musicavideo-painel -f      # lo que está diciendo
```

El archivo es `~/.config/systemd/user/musicavideo-painel.service` (ejecuta
`painel --lan`, `Restart=always` y requiere `loginctl enable-linger $USER` para
iniciarse sin una sesión abierta). Sigue siendo válido ejecutar `musicavideo painel` a mano: solo elige otro puerto para que no entre en conflicto con el servicio.

**Una tarjeta por PRODUCCIÓN, con las dos versiones dentro.** Suno entrega dos pistas por canción y cada una se convierte en un videoclip, pero es una sola producción: una carpeta, un plan, una letra, un costo y un botón de papelera. Dos tarjetas separadas duplicarían esos datos y romperían la comparación, que es precisamente la decisión que se toma ahí (cuál de las dos aprobar).

En la **cuadrícula**, la parte superior de la tarjeta muestra las dos portadas lado a lado, cada una con su botón de reproducción: `v1 ✓` marca la aprobada. Puedes escuchar ambas sin abrir nada. Las producciones antiguas que tienen una sola portada muestran la misma imagen en ambas columnas: lo que no puede faltar es el botón de reproducción de la segunda pista.

**Al abrir la tarjeta**, las versiones aparecen apiladas: portada de la versión, reproductor de la pista y enlace para ver el videoclip de esa versión. Debajo está el desplegable cerrado **«ver los prompts que se enviaron a los proveedores»**: concepto y tagline de la portada, el prompt de estilo que leyó Suno, el prompt de la portada y el negativo, y el desglose plano a plano (sección, cámara, prompt y el `prompt_alt` de cada plano). Es lo que se quiere ver cuando el resultado no coincide con el plan, y antes solo existía dentro de `plano.json`. Después aparecen PACOTE.md y PLANO.md.

**Cada versión tiene SU PROPIA portada**, no la misma imagen con un sello distinto: la versión 1 usa el fondo de la portada aprobada y, desde la 2 en adelante, `inemaimg` (flux2-klein, local, costo cero) genera una imagen propia con el mismo prompt: misma dirección de arte, nueva escena. El título NO cambia: es la misma canción, y usar nombres diferentes haría que la colección y la búsqueda dieran información falsa; lo que distingue ambas es el sello `VERSÃO`. Si el servidor local está fuera de línea, no se rompe nada: la versión vuelve a usar el fondo compartido y el comando avisa. Para rehacerlo en una producción existente:

```bash
bash $S arte <slug> --versao 2 --nova     # genera una imagen nueva para la versión 2
bash $S arte <slug> --versao 2            # solo recompone el arte sobre la imagen original (gratis)
```

### La nube (V2): Hugging Face + `musicavideo-pub`

El panel local (`INEMA MUSICAVIDEO V1.x.x`) solo existe donde está la colección. La vitrina es la otra mitad: los finales van a un dataset público de Hugging Face y el panel público se ejecuta en Vercel, en un repositorio propio ([musicavideo-pub](https://github.com/inematds/musicavideo-pub),
`INEMA MUSICAVIDEO V2.x.x`). Son dos aplicaciones; activar una no desactiva la otra.

```bash
bash $S nuvem MVD-014            # aprueba la subida (igual que el botón de la tarjeta)
bash $S nuvem MVD-014 --cancela  # la retira (marca la solicitud de eliminación)
bash $S nuvem --todos            # aprueba todo lo que tenga videoclip y portada
bash $S publica-hf --dry         # lo que subiría, sin subirlo
bash $S publica-hf               # sube lo aprobado y vuelve a escribir manifest.json
bash $S publica-hf --manifesto   # solo el manifiesto, sin volver a enviar ningún archivo
```

**Aprobar es el único paso.** Subirlo no es consecuencia de que esté listo: una producción lista es material de trabajo; la vitrina es una elección. El clic lo marca en `estado.json`; quien lo sube es `publica-hf`, ejecutado a mano, y este se encarga del resto: lo sube a HF, escribe `manifest.json` en el repositorio de la vitrina y **hace commit y push**. Publicar es un solo comando.

**Y sube lo que falta, no toda la colección.** Omite lo que ya se subió y no cambió desde entonces (mtime de los archivos finales comparado con `publicado_em`). Para forzar el reenvío de una producción, indícala por nombre: `publica-hf <slug>` ignora el filtro.

**Solo sube el resultado final.** Todo `raw/` se queda en la máquina: 1209 de los 1365 mp4 de la colección son planos intermedios. Y `clipe.mp4` no se sube cuando existe una versión numerada: 28 de los 29 son copias byte a byte de un `clipe-N.mp4`, y el manifiesto guarda cuál está aprobada. Colección de 15 GB, ~4,4 GB publicables.

**La pestaña de análisis se sube como TEXTO.** Nada de `fonte.mp4`: es un video de terceros descargado de YouTube y volver a alojarlo sería redistribuirlo. Se publica el análisis escrito y el video original aparece mediante el embed oficial.

**Un solo recolector.** `manifest.json` sale del mismo `painel.coletar()` que usa la interfaz local, con las URL reescritas para HF: dos recolectores divergentes harían imposible saber cuál panel es el correcto.

---

## Motores

| parte | predeterminado | costo | alternativas |
|---|---|---|---|
| música | `kie:suno-v4.5` | ~US$ 0,08 (incluye 2 pistas) | — |
| portada | `agnes:agnes-image-2.1-flash` | **US$ 0** | `inemaimg:flux2-klein` (servidor local) |
| videoclip | `agnes:agnes-video-v2.0` | **US$ 0** | `kling:kling-v2_5`, `fal:kling-v3-turbo` |

Los motores predeterminados de portada y videoclip no cuestan nada a propósito: **funcionan en cualquier VPS**, sin necesidad de una cuenta. Cambiarlos requiere un flag: `--motor clipe=kling:kling-v2_5`, porque el motor está en el plan, nunca en el código.

Si el proveedor no tiene clave, no se produce un error al momento de generar: ya aparece como **no disponible, con el motivo** en el plan, y `faz` marca esa parte como `erro`, mientras las demás continúan (exit 2).

**Cambiar a un proveedor que cobra requiere autorización explícita.** `kie`, `kling` y `fal` consumen créditos de cuenta o dinero, por lo que se rechaza un `--motor` que los indique si no incluye `--autorizo-pago` en el mismo comando. Es una etapa de aprobación, no una advertencia, porque esto fue lo que pasó: el 2026-08-21, cuando Agnes parecía estar fuera de servicio a mitad de un videoclip, el cambio «obvio» de motor consumió 105 créditos antes de que alguien se diera cuenta. Agnes ni siquiera estaba fuera de servicio: fue un 404 transitorio durante el poll que el adaptador trató como fatal.

**Agregar un proveedor requiere dos archivos:** `providers/<nome>.py` (que implemente `disponivel` / `estimar_custo` / `gerar`) y `providers/<nome>.models.json` (que declare modelos, costo y params aceptados). No hay que cambiar nada más del proyecto.

---

## Lo que hace solo, sin que lo notes

- **Reanudación limpia** — si se detiene a mitad del proceso, se corta la luz o presionas ctrl-c: `estado.json` sabe exactamente dónde se quedó. `faz <slug>` continúa desde ahí.
- **No paga dos veces** — si falla después de generar (descarga, red), reutiliza la task ya pagada en vez de generar de nuevo.
- **No vuelve a generar lo que ya existe** — reutiliza los planos descargados en una ejecución anterior; solo genera lo que falta.
- **Un plano bloqueado no acorta el videoclip** — aplica una cascada: plan B → reescritura mediante Fable → variación de un plano vecino de la misma sección. La duración total es intocable, porque mantiene la imagen y la música sincronizadas.
- **Desglose reajustado a la duración real de la pista** — el plan calcula una duración; cuando la música queda lista con 30 s adicionales, el desglose se rehace **antes** de generar el video.
- **Si una parte falla, las otras continúan** — y el exit code lo indica.
- **La clave de API nunca aparece** en archivos, logs ni en pantalla.

---

## En el bot de Telegram (inemaccbot)

Este repositorio se conecta al bot como FLUJO: `/musicavideo <tu descripción>`. Desde 2026-08-21, las cuatro fases se ejecutan **sin agente**: `flow.json` declara el comando de cada una (`plano`, `faz musica`, `faz` portada+videoclip, `pacote`) y quien las ejecuta es el bot. Los detalles de la mecánica están en [SKILL.md](SKILL.md); la ayuda dentro del chat es `/musicavideo help`, que se obtiene de [HELP.md](HELP.md) de este repositorio.

Lo que llega al chat en cada etapa de aprobación: el `PLANO.md` para que lo leas y lo apruebes, la pista y la portada como archivos, y el videoclip como **enlace**: los mp4 de música superan los 50 MB que Telegram acepta como documento.

## Resultado

```
~/projetos/output/musicavideo/
├── index.jsonl              # 1 línea por canción — lista/busca leen de aquí
└── <slug>/
    ├── plano.json           # el contrato
    ├── PLANO.md             # el mismo plan, para que lo leas y lo apruebes
    ├── estado.json          # fuente de verdad: fases, costo, errores, historial
    ├── faixa-1.mp3  faixa-2.mp3   # las dos de la misma generación
    ├── capa.png  clipe.mp4
    ├── revisao/contato-clipe.jpg  # hoja de contacto numerada de los planos
    ├── PACOTE.md            # entrega (completa o parcial, con lo que falta)
    └── raw/                 # respuestas sin procesar, planos, versiones anteriores
```

---

## Detalles importantes

- **Los prompts de proveedores están en inglés** — Agnes bloquea el portugués legítimo. El material creativo (concepto, letra, mood) sigue en PT; el validador rechaza el plan si algún prompt de proveedor lleva acentos.
- **Exit codes:** `0` ok · `1` uso/validación · `2` parte con error · `3` límite.
- **133 pruebas**, que tardan ~3 s: `python3 -m pytest tests/ -q`. Ninguna se conecta a una API real; las de montaje y hoja de contacto usan ffmpeg real con medios sintéticos.
- `kling` y `fal` están implementados y cubiertos por pruebas de contrato, pero aún no se han probado contra la API real.

## Licencia

MIT.

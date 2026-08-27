#!/usr/bin/env bash
# O cron da nuvem: sobe o que foi aprovado no painel e ainda não subiu.
#
# Aprovar é o único gesto humano — um clique no card do painel local. Este
# script é o que faz o resto acontecer sozinho, e por isso ele é BURRO de
# propósito: não escolhe nada, não apaga nada que não tenha sido marcado para
# sair, e não roda duas vezes ao mesmo tempo (um upload de gigabytes concorrendo
# com outro só multiplicaria banda e confusão).
#
# Instalar (a cada 30 minutos):
#   crontab -e
#   */30 * * * * /home/nmaldaner/projetos/musicavideo/cron-nuvem.sh
#
# Sem o sistema de nuvem ativo, simplesmente não se instala: o painel local
# funciona igual, e o `publica-hf` continua rodando à mão.
set -uo pipefail
cd "$(dirname "$0")" || exit 1

TRAVA=/tmp/musicavideo-nuvem.lock
LOG="${MUSICAVIDEO_LOG:-$HOME/projetos/output/nuvem.log}"

exec 9>"$TRAVA"
flock -n 9 || { echo "$(date -Is) já rodando — pulei" >> "$LOG"; exit 0; }

echo "$(date -Is) publica-hf" >> "$LOG"
./musicavideo.sh publica-hf >> "$LOG" 2>&1
echo "$(date -Is) fim (saida=$?)" >> "$LOG"

# O like volta: as contagens da vitrine viram `likes.json` no acervo, e o painel
# local mostra ♥ em cada card. Sem MUSICAVIDEO_PUB_URL isto não faz nada.
[ -n "${MUSICAVIDEO_PUB_URL:-}" ] && ./musicavideo.sh likes >> "$LOG" 2>&1

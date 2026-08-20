#!/usr/bin/env bash
# roteador fino: zero lógica além de resolver a raiz e delegar.
set -euo pipefail
RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$RAIZ/src/main.py" "$@"

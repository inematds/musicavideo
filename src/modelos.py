"""Modelo Claude do ecossistema INEMA — fonte única em ~/.config/inema/modelos.env
(doc: ~/projetos/wifi/MODELOS.md). Ordem: variável de ambiente → arquivo central → reserva."""
import os
import re
from pathlib import Path

ARQUIVO_CENTRAL = Path.home() / ".config" / "inema" / "modelos.env"


def _ler_central(chave: str) -> str | None:
    if os.environ.get(chave):
        return os.environ[chave]
    try:
        m = re.search(rf"^{chave}=(.*)$", ARQUIVO_CENTRAL.read_text(encoding="utf-8"), re.M)
    except OSError:
        return None
    return (m.group(1).strip() or None) if m else None


CLAUDE_TOPO = _ler_central("INEMA_CLAUDE_TOPO") or "claude-opus-5-5"
# O Opus 5.5 exige CLI >= 2.1.280; `claude` solto no PATH do painel cai no /usr/bin 2.1.63.
CLAUDE_BIN = _ler_central("INEMA_CLAUDE_BIN") or "claude"

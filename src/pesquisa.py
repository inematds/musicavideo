"""Fase 0 (OPT-IN, `--pesquisa`): o que existe lá fora sobre a solicitação.

Desligada por default de propósito: custa tempo e traz ruído. Quando ligada,
o resultado entra como CONTEXTO do planejador — nunca sobrescreve o que o
usuário pediu explicitamente.
"""
import subprocess
from pathlib import Path

PEDIDO = """Pesquise na web e resuma, em markdown curto e direto, o que ajuda a planejar
uma música/capa/clipe para esta solicitação: "{s}"

Cubra:
- referências sonoras atuais desse nicho (artistas, faixas, sonoridade dominante);
- o que costuma funcionar em capa e em clipe nesse gênero hoje;
- se o tema tem tração e por quê.

Sem enrolação, sem introdução. Só o resumo."""


def pesquisar_texto(solicitacao: str, chamar_llm=None) -> str:
    chamar_llm = chamar_llm or _claude_web
    return chamar_llm(PEDIDO.format(s=solicitacao))


def _claude_web(prompt: str) -> str:
    try:
        r = subprocess.run(["claude", "-p", prompt, "--allowedTools", "WebSearch"],
                           capture_output=True, text=True, timeout=900)
    except FileNotFoundError:
        raise RuntimeError("binário 'claude' não encontrado — a pesquisa precisa dele no PATH")
    if r.returncode != 0:
        raise RuntimeError(f"claude -p (pesquisa) falhou: {r.stderr[:300]}")
    return r.stdout


def pesquisar(solicitacao: str, workdir: Path | None = None, chamar_llm=None):
    """Sem workdir: devolve o texto (o planner grava depois, na pasta do slug).
    Com workdir: grava `pesquisa.md` e devolve o Path."""
    texto = pesquisar_texto(solicitacao, chamar_llm)
    if workdir is None:
        return texto
    alvo = Path(workdir) / "pesquisa.md"
    alvo.parent.mkdir(parents=True, exist_ok=True)
    alvo.write_text(texto, encoding="utf-8")
    return alvo

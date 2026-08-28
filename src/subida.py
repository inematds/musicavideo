"""A subida acontecendo — o botão do painel deixa de ser só uma marcação.

O botão dizia "subir para a nuvem" e só marcava: quem subia de fato era o
`publica-hf`, rodado à mão. Com o cron retirado (v1.3.0), nada rodava sozinho, e
o card ficava em `aprovado` para sempre. Um botão que promete uma ação e faz
outra é pior que um botão que não existe — este módulo faz a ação acontecer.

O que ele NÃO é: uma fila. É um processo por vez, com trava em arquivo, porque
dois uploads de gigabytes concorrendo só multiplicam banda e confusão — a mesma
razão que o `cron-nuvem.sh` tinha para usar `flock`.
"""
import os
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
TRAVA = Path("/tmp/musicavideo-subida.lock")
LOG_PADRAO = "nuvem.log"


def _pid_vivo(pid: int) -> bool:
    """Vivo de verdade — ZUMBI não conta.

    O painel é o pai deste processo e nunca o colhe, então quando ele termina
    vira zumbi: a entrada continua em `/proc` e `os.kill(pid, 0)` responde que
    está vivo. O selo `subindo…` ficaria pulsando para sempre numa subida que já
    acabou (medido em 2026-08-27, com o MVD#124 já publicado no HF). Colher aqui
    resolve os dois problemas: o estado passa a ser verdade e o zumbi some.
    """
    try:
        pid = int(pid)
        os.waitpid(pid, os.WNOHANG)     # somos o pai: colhe se já terminou
    except (ChildProcessError, ValueError, OSError):
        pass
    try:
        estado = Path(f"/proc/{pid}/status").read_text(encoding="utf-8")
    except OSError:
        # Sem /proc (outro SO): cai no sinal, que ao menos pega processo que sumiu.
        try:
            os.kill(pid, 0)
        except (ProcessLookupError, ValueError):
            return False
        except PermissionError:
            return True
        return True
    for linha in estado.splitlines():
        if linha.startswith("State:"):
            return "Z" not in linha.split(None, 1)[1][:2]
    return True


def em_andamento() -> str | None:
    """O slug que está subindo agora, ou None.

    A trava guarda `pid:slug`. Processo morto sem apagar a trava (kill -9, queda
    da máquina) não trava o painel para sempre: se o pid não vive, a trava não
    vale nada.
    """
    try:
        pid, _, slug = TRAVA.read_text(encoding="utf-8").strip().partition(":")
        return slug if _pid_vivo(int(pid)) else None
    except (OSError, ValueError):
        return None


def proxima(outdir: Path, log=None) -> str | None:
    """Começa a subir o próximo APROVADO, se nada estiver subindo.

    Sem isto, `aprovado` seria um beco: com o cron retirado e a trava ocupada no
    momento do clique, a produção ficaria marcada para sempre esperando alguém
    rodar o comando à mão — que é exatamente a reclamação que originou tudo
    isto. Aprovar é consentimento explícito para subir; drenar a fila não
    inventa decisão nenhuma.
    """
    if em_andamento():
        return None
    # QUEM DECIDE É O `publica-hf`, não o carimbo da produção. Com aprovação
    # por faixa, `publicado_em` no topo passa a valer assim que UMA faixa sobe:
    # perguntar por ele deixaria a segunda faixa, aprovada depois, esperando
    # para sempre. `arquivos_a_subir` responde a pergunta certa — falta algo?
    from src.publicahf import arquivos_a_subir
    for w in sorted(p for p in outdir.iterdir() if p.is_dir()):
        try:
            if arquivos_a_subir(w):
                iniciar(w.name, outdir=outdir, log=log)
                return w.name
        except OSError:
            continue
    return None


def iniciar(slug: str, outdir: Path | None = None, log: Path | None = None) -> str:
    """Dispara `publica-hf <slug>` em segundo plano. Devolve o que aconteceu.

    Nomear o slug é de propósito: `publica-hf` sem alvo varre o acervo inteiro,
    e o gesto aqui é sobre UMA produção. O comando nomeado ignora o filtro de
    "já subiu e não mudou", que é o certo — quem clicou quer esta subindo.
    """
    ativo = em_andamento()
    if ativo:
        return f"ja-subindo:{ativo}"
    alvo = log or (Path.home() / "projetos/output" / LOG_PADRAO)
    try:
        alvo.parent.mkdir(parents=True, exist_ok=True)
        saida = open(alvo, "a", encoding="utf-8")
    except OSError:
        saida = subprocess.DEVNULL
    amb = dict(os.environ)
    if outdir is not None:
        amb["MUSICAVIDEO_OUT"] = str(outdir)
    p = subprocess.Popen([sys.executable, str(RAIZ / "src/main.py"), "publica-hf", slug],
                         cwd=str(RAIZ), stdout=saida, stderr=subprocess.STDOUT,
                         start_new_session=True, env=amb)
    try:
        TRAVA.write_text(f"{p.pid}:{slug}\n", encoding="utf-8")
    except OSError:
        pass
    return f"subindo:{slug}"

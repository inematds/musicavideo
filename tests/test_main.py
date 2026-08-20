import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]


def test_main_sem_args_exit_1():
    r = subprocess.run([sys.executable, str(RAIZ / "src/main.py")],
                       capture_output=True, text=True)
    assert r.returncode == 1
    assert "uso:" in (r.stdout + r.stderr).lower()


def test_main_comando_desconhecido_exit_1():
    r = subprocess.run([sys.executable, str(RAIZ / "src/main.py"), "xyzzy"],
                       capture_output=True, text=True)
    assert r.returncode == 1


def test_sh_roteia_pro_python():
    r = subprocess.run(["bash", str(RAIZ / "musicavideo.sh")],
                       capture_output=True, text=True)
    assert r.returncode == 1
    assert "uso:" in (r.stdout + r.stderr).lower()

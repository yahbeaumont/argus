import resource
import subprocess
import sys
import tempfile
from pathlib import Path

CPU_SECONDS = 10
MEMORY_BYTES = 512 * 1024 * 1024
MAX_OUTPUT = 8_000


def _limits() -> None:
    resource.setrlimit(resource.RLIMIT_CPU, (CPU_SECONDS, CPU_SECONDS))
    resource.setrlimit(resource.RLIMIT_AS, (MEMORY_BYTES, MEMORY_BYTES))
    resource.setrlimit(resource.RLIMIT_NPROC, (32, 32))


def run(code: str) -> str:
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "snippet.py"
        script.write_text(code, encoding="utf-8")
        try:
            proc = subprocess.run(
                [sys.executable, "-I", "-S", str(script)],
                capture_output=True, text=True, timeout=CPU_SECONDS + 2,
                cwd=tmp, preexec_fn=_limits, env={"PYTHONHASHSEED": "0"},
            )
        except subprocess.TimeoutExpired:
            return "erro: timeout de 10s"
        if proc.returncode != 0:
            return f"erro (exit {proc.returncode}):\n{proc.stderr[-2000:]}"
        out = proc.stdout
        return out if len(out) <= MAX_OUTPUT else out[:MAX_OUTPUT] + "\n…[truncado]"

"""Run model-written code somewhere it can't hurt anything: a throwaway Docker
container with no network, a memory cap, one CPU, a read-only mount and a hard
timeout. Code that an LLM wrote should never run on the host directly.
"""
import os
import re
import subprocess
import tempfile

PY_IMAGE = "python:3.12-slim"
EX_IMAGE = "elixir:1.18.3-otp-27"


def extract_block(text: str, lang: str) -> str | None:
    blocks = re.findall(rf"```(?:{lang})[^\n]*\n(.*?)```", text, re.S | re.I)
    if not blocks:
        blocks = re.findall(r"```[^\n]*\n(.*?)```", text, re.S)
    return max(blocks, key=len) if blocks else None


def _docker(image: str, filename: str, source: str, cmd: list[str], timeout: int = 60):
    with tempfile.TemporaryDirectory() as d:
        with open(os.path.join(d, filename), "w") as f:
            f.write(source)
        try:
            p = subprocess.run(
                ["docker", "run", "--rm", "--network", "none", "--memory", "512m",
                 "--cpus", "1", "--pids-limit", "128", "--read-only",
                 "--tmpfs", "/tmp:size=64m", "-e", "HOME=/tmp",
                 "-v", f"{d}:/w:ro", "-w", "/tmp", image, *cmd],
                capture_output=True, text=True, timeout=timeout)
            return p.returncode == 0, (p.stdout + p.stderr)[-2000:]
        except subprocess.TimeoutExpired:
            return False, "TIMEOUT"


def run_python(code: str, tests: str):
    src = code + "\n\n# ---- tests ----\n" + tests + "\nprint('ALL_TESTS_PASSED')\n"
    ok, out = _docker(PY_IMAGE, "t.py", src, ["timeout", "20", "python", "/w/t.py"])
    return ok and "ALL_TESTS_PASSED" in out, out


def run_elixir(code: str, tests: str):
    body = "\n".join("    " + l for l in tests.strip().splitlines())
    src = (f"ExUnit.start(autorun: false)\n{code}\n\n"
           f"defmodule BenchTest do\n  use ExUnit.Case\n  test \"task\" do\n{body}\n  end\nend\n\n"
           "%{failures: f} = ExUnit.run()\n"
           "if f == 0, do: IO.puts(\"ALL_TESTS_PASSED\"), else: System.halt(1)\n")
    ok, out = _docker(EX_IMAGE, "t.exs", src, ["timeout", "40", "elixir", "/w/t.exs"])
    return ok and "ALL_TESTS_PASSED" in out, out

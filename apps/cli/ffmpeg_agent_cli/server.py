"""Supervise a local llama-server for one CLI call (loopback only, always terminated)."""

import json
import socket
import subprocess
import time
import urllib.request
from pathlib import Path

from training import config

TEMPLATE = config.PROTOCOL_DIR / "prompts" / "chat-template.jinja"


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def server_argv(
    binary: Path, model: Path, port: int, ctx: int = 4096, *,
    template: Path = TEMPLATE, kv: str | None = None, flash: bool | None = None,
) -> list[str]:  # fmt: skip
    """kv/flash are None for the legacy GGUF-only run (llama.cpp defaults); a release manifest sets both."""
    kv_flags = ["-ctk", kv, "-ctv", kv] if kv else []
    fa_flags = ["-fa", "on" if flash else "off"] if flash is not None else []
    return [
        str(binary), "--jinja", "--chat-template-file", str(template), "-m", str(model),
        "--host", "127.0.0.1",  # never 0.0.0.0 (RULES §2.1)
        "--port", str(port), "-c", str(ctx), "-np", "1", "--cache-ram", "0", "-ngl", "99",
        *kv_flags, *fa_flags,
    ]  # fmt: skip


class LlamaServer:
    def __init__(
        self, binary: Path, model: Path, ctx: int = 4096, startup_s: int = 120, **flags
    ):  # flags: template, kv, flash (see server_argv)
        self.binary, self.model, self.ctx, self.startup_s = binary, model, ctx, startup_s
        self.flags = flags
        self.port = free_port()
        self.proc: subprocess.Popen | None = None

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}/v1"

    def post(self, path: str, body: dict) -> dict:
        """POST JSON to a llama-server endpoint outside /v1 (/tokenize, /completion)."""
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}{path}",
            json.dumps(body).encode(),
            {"Content-Type": "application/json"},
        )
        return json.load(urllib.request.urlopen(req, timeout=600))

    def count_tokens(self, text: str) -> int:
        body = {"content": text, "add_special": False, "parse_special": True}
        return len(self.post("/tokenize", body)["tokens"])

    def __enter__(self) -> "LlamaServer":
        self.proc = subprocess.Popen(
            server_argv(self.binary, self.model, self.port, self.ctx, **self.flags),
            shell=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        deadline = time.time() + self.startup_s
        while time.time() < deadline:
            if self.proc.poll() is not None:
                raise RuntimeError(
                    "llama-server exited during startup (check --model and --llama-server)"
                )
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{self.port}/health", timeout=1)
                return self
            except OSError:
                time.sleep(0.5)
        self.__exit__(None, None, None)
        raise TimeoutError("llama-server did not become healthy in time")

    def __exit__(self, *exc) -> None:
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(10)
            except subprocess.TimeoutExpired:
                self.proc.kill()

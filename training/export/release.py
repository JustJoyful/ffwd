"""Build the local release package of a model (D-053): the GGUFs byte-identical to the evaluated files, `ffwd-model.json`,
the card as README.md, the licence, `SHA256SUMS`. Nothing is uploaded here.

    uv run python -m training.export.release build --version 1.0.0 --out releases/ffwd-0.6b-v1.0.0
    uv run python -m training.export.release verify --out releases/ffwd-0.6b-v1.0.0

Fail closed: the build refuses on any hash that differs from the one the evaluation manifests recorded, and it never
re-quantises (it copies). The output is deterministic: no timestamps, commits or absolute paths in the manifest.
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

from training import config
from training.env.chat_template import render
from training.export.hub import sha256_file
from training.protocol import validate

NAME = "ffwd-0.6b"
BASE_MODEL = "Qwen/Qwen3-0.6B"
LICENCE_ID = "Apache-2.0"
MIN_APP_VERSION = (
    "1.0.0"  # the first app generation that knows this manifest format (schema: model.schema.json)
)
CHAT_TEMPLATE_ID = "ffwd-agent-chat-v1"  # D-026: Qwen3 non-thinking, no tools, empty think block in EVERY assistant turn
# Runtime defaults = the owner-confirmed configuration (D-050, D-051). The site reads them from this manifest (2026-11-24).
# (checked against that file at build time). Greedy decoding, max reply 512 tokens.
RUNTIME = {
    "n_ctx": 8192,
    "kv_cache_type": "q8_0",
    "flash_attention": True,
    "temperature": 0,
    "max_tokens": 512,
}
# How the canary reference was made (scripts/make-canary-reference.mjs header of ffwd-web): native llama.cpp on the
# CPU, f16 KV, no flash attention. The build id comes from canary-reference.json itself.
CANARY_REFERENCE = {"backend": "cpu", "kv_cache_type": "f16", "flash_attention": False}
CANARY_MIN_MATCH = (
    18  # canary match rule (18 of the first 20 ids); the site reads it from this manifest
)
SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
# Pins for the small files the package ships (protocol prompts and the owner-supplied licence text).
SYSTEM_PROMPT_SHA = "56e7d7217b97c122662235cceb96acbf62bd822c6fec25f880035bfff805c724"
CHAT_TEMPLATE_SHA = "8d12c21330339015cf3856b2c8fd0ade15556f92c87958d3426b832bae029af5"
LICENCE_SHA = "832dd9e00a68dd83b3c3fb9f5588dad7dcf337a0db50f7d9483f310cd292e92e"
ADAPTER_SHA = "67958a13b78bd3588b583a22fb2a50a9cbca7efc8312dcbc227b6c15e7958e06"  # = the Hub LFS etag of checkpoint-60


class ReleaseError(Exception):
    pass


@dataclass(frozen=True)
class Model:
    src: Path
    sha256: str  # the evaluated file's hash, from the evaluation manifests
    size_bytes: int
    quant: str
    role: str  # shipped | evaluated


@dataclass(frozen=True)
class Inputs:
    q5: Model
    q8: Model
    adapter: Path  # folder with adapter_model.safetensors + adapter_config.json
    adapter_sha256: str
    card: Path
    licence: Path
    system_prompt: Path
    chat_template: Path
    canary_reference: Path
    pins: tuple[str, str, str] = (SYSTEM_PROMPT_SHA, CHAT_TEMPLATE_SHA, LICENCE_SHA)


def _check_hash(path: Path, expected: str, what: str) -> str:
    got = sha256_file(path)
    if got != expected:
        raise ReleaseError(f"{what}: sha256 {got} != expected {expected} ({path})")
    return got


def _copy(src: Path, dst: Path, sha: str) -> None:
    """Copy `src` to `dst` byte for byte; skip when `dst` already has the hash; verify the copy."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    if not (dst.is_file() and sha256_file(dst) == sha):
        part = dst.with_name(dst.name + ".part")
        shutil.copyfile(src, part)
        os.replace(part, dst)
    _check_hash(dst, sha, f"copy {dst.name}")


def expected_model_hashes(repo: Path = config.REPO_ROOT) -> dict[str, tuple[str, int]]:
    """{'Q5_K_M': (sha, bytes), 'Q8_0': ...} from the evaluation manifests; every other record must agree."""
    g = json.loads((repo / "reports/2026-11-23-browser-gguf/manifest.json").read_text())["ggufs"]
    out = {q: (g[q]["sha256"], g[q]["bytes"]) for q in ("Q5_K_M", "Q8_0")}
    p1 = json.loads((repo / "reports/2026-11-23-phase-1/manifest.json").read_text())
    if p1["hashes"]["models"]["M3"] != out["Q8_0"][0]:
        raise ReleaseError(
            "Phase 1 manifest M3 hash differs from the browser-gguf manifest Q8_0 hash"
        )
    row = (repo / "reports/2026-11-23-phase-1-browser-row/report/manifest.json").read_text()
    if f"[sha256:{out['Q5_K_M'][0][:8]}]" not in row:
        raise ReleaseError("browser-row manifest does not carry the Q5_K_M hash prefix")
    frozen = re.search(
        r'"gguf_sha256": "([0-9a-f]{64})"', (repo / "eval/browser_test_run.py").read_text()
    )
    if not frozen or frozen.group(1) != out["Q5_K_M"][0]:
        raise ReleaseError(
            "eval/browser_test_run.py FROZEN gguf_sha256 differs from the Q5_K_M hash"
        )
    return out


def default_inputs(repo: Path = config.REPO_ROOT) -> Inputs:
    exp = expected_model_hashes(repo)
    gguf = repo / "data/models/grpo-m3-ckpt60-gguf"
    web = Path(os.environ.get("FFWD_WEB_DIR", repo.parent / "ffwd-web"))

    def mk(q: str, f: str, role: str) -> Model:
        return Model(gguf / f, exp[q][0], exp[q][1], q, role)

    return Inputs(
        q5=mk("Q5_K_M", "grpo-m3-ckpt60-q5_k_m.gguf", "shipped"),
        q8=mk("Q8_0", "grpo-m3-ckpt60-q8_0.gguf", "evaluated"),
        adapter=repo / "data/models/grpo-m3-ckpt60-hub/checkpoints/checkpoint-60",
        adapter_sha256=ADAPTER_SHA,
        card=repo / "docs/hf-cards/model-card-m3.md",
        licence=repo / "docs/hf-cards/LICENSE-Qwen3-Apache-2.0.txt",
        system_prompt=config.PROTOCOL_DIR / "prompts/system-v1.txt",
        chat_template=config.PROTOCOL_DIR / "prompts/chat-template.jinja",
        canary_reference=web / "app/model/canary-reference.json",
    )


def _sub(text: str, pattern: str, new: str, *, count: int = 1) -> str:
    """Regex replace that must hit exactly `count` times, so a card edit cannot silently skip a fix."""
    text, n = re.subn(pattern, lambda _m: new, text, flags=re.M)
    if n != count:
        raise ReleaseError(f"card replacement {pattern!r} hit {n} times, expected {count}")
    return text


def make_readme(card: str, version: str, f: dict) -> str:
    """The model card as README.md: the draft wording and the pre-release file names become the package's.
    `f` has the package names 'q5', 'q8' and the Q5_K_M 'q5_sha' and 'q5_bytes'."""
    q5, q8 = f["q5"], f["q8"]
    head, sep, rest = card.partition("\n---\n")  # drop the draft YAML comments of the front matter
    kept = [ln for ln in head.splitlines() if not ln.startswith("#")]
    if not sep or len(head.splitlines()) - len(kept) != 3:
        raise ReleaseError("card front matter does not have exactly 3 draft comment lines")
    card = "\n".join(kept) + sep + rest
    card = _sub(
        card,
        r"^> DRAFT: .*$",
        f"> Release v{version} of ffwd-0.6b. Every file is listed with its sha256 in `ffwd-model.json` and `SHA256SUMS` (`sha256sum -c SHA256SUMS`).",
    )
    card = _sub(card, r"^# ffwd M3 \(ffmpeg-agent-m3-0\.6b\): ", f"# ffwd-0.6b v{version} (M3): ")
    card = _sub(
        card,
        r"^Repo id: .*$",
        f"Repo id: `JustJoyful/ffwd-0.6b`, version **v{version}** (semantic versioning, D-053): GRPO checkpoint-60, `{q5}` shipped and `{q8}` evaluated. Hub and Kaggle identifiers in this card (`JustJoyful/ffmpeg-agent-ckpt-grpo`, the private M1 repo `JustJoyful/ffmpeg-agent-m1-0.6b`) are the current names of those objects until the planned rename (D-046).",
    )
    card = _sub(card, r"ffmpeg-agent-m3-0\.6b-q8_0\.gguf", q8, count=4)
    card = _sub(
        card,
        r"^The user message is a JSON object with `request`",
        f"The shipped configuration (the runtime defaults recorded in `ffwd-model.json`) runs `{q5}` with the same flags plus `-ctk q8_0 -ctv q8_0 -fa on` (q8_0 KV cache with flash attention).\n\nThe user message is a JSON object with `request`",
    )
    card = _sub(
        card,
        r"the Q5_K_M file named above \(shipping format\)",
        f"`{q5}` (the shipping format, {f['q5_bytes']:,} bytes, sha256 `{f['q5_sha']}`)",
    )
    card = _sub(
        card,
        r"`chat-template\.jinja`, `system-v1\.txt`, `SHA256SUMS`, `LICENSE`",
        "`ffwd-model.json` (the manifest apps read), `chat-template.jinja`, `system-v1.txt`, `SHA256SUMS`, `LICENSE`",
    )
    card = _sub(
        card,
        r"The LoRA adapter of checkpoint-60 \(now on.*$",
        "`adapter/adapter_model.safetensors` and `adapter/adapter_config.json` are the LoRA adapter of checkpoint-60 as trained. Its base is the merged M1 model (`base_model_name_or_path` is `/kaggle/working/m1-merged`), not Qwen3-0.6B itself: to re-merge, first merge the M1 SFT adapter into Qwen3-0.6B (private repo `JustJoyful/ffmpeg-agent-m1-0.6b`), then this adapter into the result.",
    )
    return card


def canary_manifest(ref: dict, system: str, q5_sha: str) -> dict:
    """The canary block. The prompt is not stored: the build re-renders it from the system prompt and the user turn
    with the chat template and requires byte equality with the site's stored prompt."""
    if ref["model"]["sha256"] != q5_sha or ref.get("ggufSha256Checked") is not True:
        raise ReleaseError("canary reference was not made with the shipped Q5_K_M file")
    if ref["roundTrips"] is not True or len(ref["tokens"]) != ref["maxTokens"]:
        raise ReleaseError("canary reference does not round-trip or has the wrong length")
    prompt = ref["prompt"]
    head = f"<|im_start|>system\n{system}<|im_end|>\n<|im_start|>user\n"
    tail = "<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n"
    if not (prompt.startswith(head) and prompt.endswith(tail)):
        raise ReleaseError(
            "canary prompt is not system-v1.txt + one user turn + the generation prompt"
        )
    user = prompt[len(head) : -len(tail)]
    msgs = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    if render(msgs, add_generation_prompt=True) != prompt:
        raise ReleaseError("canary prompt is not what the chat template renders")
    return {
        "file_sha256": q5_sha,
        "user_turn": user,
        "rendered_prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
        "prompt_tokens": ref["promptTokenCount"],
        "n_predict": ref["maxTokens"],
        "expected_token_ids": ref["tokens"],
        "expected_text": ref["text"],
        "match": {"kind": "prefix", "min_matched": CANARY_MIN_MATCH, "of": ref["maxTokens"]},
        "reference": {"llama_cpp_build": ref["llamaCpp"]["build"], **CANARY_REFERENCE},
    }


def build_manifest(i: Inputs, version: str, out: Path) -> dict:
    names = {"q5": f"{NAME}-v{version}-Q5_K_M.gguf", "q8": f"{NAME}-v{version}-Q8_0.gguf"}
    system = i.system_prompt.read_text()
    ref = json.loads(i.canary_reference.read_text())

    def entry(path: str, role: str, fmt: str, quant: str | None = None) -> dict:
        p = out / path
        q = {"quant": quant} if quant else {}
        return {
            "path": path,
            "role": role,
            "format": fmt,
            **q,
            "sha256": sha256_file(p),
            "size_bytes": p.stat().st_size,
        }

    return {
        "name": NAME,
        "version": version,
        "min_app_version": MIN_APP_VERSION,
        "protocol_version": config.PROTOCOL_VERSION,
        "base_model": BASE_MODEL,
        "licence": LICENCE_ID,
        "licence_file": "LICENSE",
        "card": "README.md",
        "files": [
            entry(names["q5"], "shipped", "gguf", "Q5_K_M"),
            entry(names["q8"], "evaluated", "gguf", "Q8_0"),
            entry("adapter/adapter_model.safetensors", "adapter", "safetensors"),
            entry("adapter/adapter_config.json", "adapter", "json"),
            entry("system-v1.txt", "prompt", "text"),
            entry("chat-template.jinja", "template", "jinja"),
        ],
        "prompt": {
            "version": "v1",
            "file": "system-v1.txt",
            "sha256": sha256_file(out / "system-v1.txt"),
        },
        "chat_template": {
            "id": CHAT_TEMPLATE_ID,
            "file": "chat-template.jinja",
            "sha256": sha256_file(out / "chat-template.jinja"),
            "add_generation_prompt": True,
        },
        "runtime": dict(RUNTIME),
        "canary": canary_manifest(ref, system, i.q5.sha256),
    }


def write_sums(out: Path) -> None:
    """SHA256SUMS over every file in the package except itself, sorted, in `sha256sum -c` format."""
    rows = [
        (p.relative_to(out).as_posix(), sha256_file(p))
        for p in out.rglob("*")
        if p.is_file() and p.name != "SHA256SUMS"
    ]
    (out / "SHA256SUMS").write_text("".join(f"{h}  {n}\n" for n, h in sorted(rows)))


def build(i: Inputs, version: str, out: Path) -> dict:
    if not SEMVER.match(version):
        raise ReleaseError(f"version {version!r} is not MAJOR.MINOR.PATCH")
    pin_sys, pin_tmpl, pin_lic = i.pins
    names = {"q5": f"{NAME}-v{version}-Q5_K_M.gguf", "q8": f"{NAME}-v{version}-Q8_0.gguf"}
    # 1. verify every source against its recorded hash BEFORE writing anything
    for m in (i.q5, i.q8):
        _check_hash(m.src, m.sha256, f"source {m.src.name}")
        if m.src.stat().st_size != m.size_bytes:
            raise ReleaseError(
                f"{m.src.name}: {m.src.stat().st_size} bytes != recorded {m.size_bytes}"
            )
    _check_hash(i.adapter / "adapter_model.safetensors", i.adapter_sha256, "adapter")
    _check_hash(i.system_prompt, pin_sys, "system prompt")
    _check_hash(i.chat_template, pin_tmpl, "chat template")
    _check_hash(i.licence, pin_lic, "licence")
    card = i.card.read_text()
    for m in (i.q5, i.q8):  # the card quotes both hashes: it must agree with the manifests
        if m.sha256 not in card:
            raise ReleaseError(f"model card does not quote the {m.quant} sha256")
    readme = make_readme(
        card, version, {**names, "q5_sha": i.q5.sha256, "q5_bytes": i.q5.size_bytes}
    )
    out.mkdir(parents=True, exist_ok=True)
    # 2. copy (never re-quantise)
    _copy(i.q5.src, out / names["q5"], i.q5.sha256)
    _copy(i.q8.src, out / names["q8"], i.q8.sha256)
    for f in ("adapter_model.safetensors", "adapter_config.json"):
        _copy(i.adapter / f, out / "adapter" / f, sha256_file(i.adapter / f))
    _copy(i.system_prompt, out / "system-v1.txt", pin_sys)
    _copy(i.chat_template, out / "chat-template.jinja", pin_tmpl)
    _copy(i.licence, out / "LICENSE", pin_lic)
    # 3. text files, manifest, sums
    (out / "README.md").write_text(readme)
    manifest = build_manifest(i, version, out)
    errors = validate("model", manifest)
    if errors:
        raise ReleaseError(f"manifest does not match model.schema.json: {errors}")
    (out / "ffwd-model.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    write_sums(out)
    return manifest


def verify_sums(out: Path) -> list[str]:
    """Problems with SHA256SUMS (empty = fine): a listed file missing or different, or a file in the package not listed."""
    sums = out / "SHA256SUMS"
    if not sums.is_file():
        return ["SHA256SUMS is missing"]
    listed = {n: h for h, _, n in (line.partition("  ") for line in sums.read_text().splitlines())}
    problems = []
    for n, h in listed.items():
        if not (out / n).is_file():
            problems.append(f"{n}: missing")
        elif sha256_file(out / n) != h:
            problems.append(f"{n}: sha256 differs")
    present = {
        p.relative_to(out).as_posix()
        for p in out.rglob("*")
        if p.is_file() and p.name != "SHA256SUMS"
    }
    return problems + [f"{n}: not listed in SHA256SUMS" for n in sorted(present - set(listed))]


def file_problem(out: Path, entry: dict, sha=sha256_file) -> str | None:
    """Why one `files[]` entry of a manifest does not match the file on disk (None = fine). Size is compared before
    the hash, so a truncated file is refused without reading it. The CLI passes a caching `sha` (apps/cli release.py).
    """
    p = out / entry["path"]
    if not p.is_file():
        return f"{entry['path']}: listed in ffwd-model.json but missing"
    if p.stat().st_size != entry["size_bytes"] or sha(p) != entry["sha256"]:
        return f"{entry['path']}: differs from ffwd-model.json"
    return None


def verify_package(out: Path) -> list[str]:
    """SHA256SUMS, the manifest's schema, and every manifest file's size and hash."""
    problems = verify_sums(out)
    mpath = out / "ffwd-model.json"
    if not mpath.is_file():
        return problems + ["ffwd-model.json is missing"]
    manifest = json.loads(mpath.read_text())
    problems += [f"ffwd-model.json: {e}" for e in validate("model", manifest)]
    for f in manifest.get("files", []):
        if problem := file_problem(out, f):
            problems.append(problem)
    return problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="release")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser(
        "build", help="build the package (copies the evaluated GGUFs; refuses on any hash mismatch)"
    )
    b.add_argument("--version", required=True)
    b.add_argument("--out", type=Path, required=True)
    v = sub.add_parser("verify", help="check SHA256SUMS and ffwd-model.json of a built package")
    v.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    try:
        if a.cmd == "build":
            build(default_inputs(), a.version, a.out)
            print(f"built {a.out}")
        problems = verify_package(a.out)
    except ReleaseError as e:
        print(f"REFUSED: {e}", file=sys.stderr)
        return 1
    for p in problems:
        print(f"PROBLEM: {p}", file=sys.stderr)
    print("package OK" if not problems else "package NOT OK")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())

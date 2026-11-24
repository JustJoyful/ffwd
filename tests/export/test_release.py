"""The release build (D-053) on tiny fake files; the real GGUFs are never touched here."""

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from training import config
from training.env.chat_template import render
from training.export import release
from training.export.release import Inputs, Model, ReleaseError, build, verify_package
from training.protocol import validate

PROMPTS = config.PROTOCOL_DIR / "prompts"
USER = '{"request": "Cut the first 2 seconds off", "inputs": [], "outputs": ["out1"]}'


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


CARD = f"""---
# DRAFT front matter
# second comment
# third comment
license: apache-2.0
---

> DRAFT: for a PRIVATE repo.

# ffwd M3 (ffmpeg-agent-m3-0.6b): a test card

Repo id: `JustJoyful/ffwd-0.6b` (owner decision).

Files: `ffmpeg-agent-m3-0.6b-q8_0.gguf` sha256 `{sha(b"q8")}` and `{sha(b"q5")}`.
`llama-server -m ffmpeg-agent-m3-0.6b-q8_0.gguf`
`ffmpeg-agent-m3-0.6b-q8_0.gguf` again, and `ffmpeg-agent-m3-0.6b-q8_0.gguf`.

The user message is a JSON object with `request` and more.

## Files

the Q5_K_M file named above (shipping format), `chat-template.jinja`, `system-v1.txt`, `SHA256SUMS`, `LICENSE`. The LoRA adapter of checkpoint-60 (now on the private repo) will be included.
"""


@pytest.fixture
def inputs(tmp_path: Path) -> Inputs:
    src = tmp_path / "src"
    (src / "adapter").mkdir(parents=True)
    (src / "q5.gguf").write_bytes(b"q5")
    (src / "q8.gguf").write_bytes(b"q8")
    (src / "adapter" / "adapter_model.safetensors").write_bytes(b"lora")
    (src / "adapter" / "adapter_config.json").write_text("{}")
    (src / "card.md").write_text(CARD)
    (src / "lic.txt").write_text("licence text")
    system = (PROMPTS / "system-v1.txt").read_text()
    prompt = render(
        [{"role": "system", "content": system}, {"role": "user", "content": USER}],
        add_generation_prompt=True,
    )
    ref = {
        "model": {"sha256": sha(b"q5")},
        "ggufSha256Checked": True,
        "llamaCpp": {"build": "b1-x"},
        "prompt": prompt,
        "promptTokenCount": 7,
        "maxTokens": 3,
        "tokens": [1, 2, 3],
        "text": "abc",
        "roundTrips": True,
    }
    (src / "canary.json").write_text(json.dumps(ref))
    (src / "config.js").write_text(
        f'bytes: 2,\nsha256: "{sha(b"q5")}",\nnCtx: 8192,\nkvCache: "q8_0",\nmaxTokens: 512,\ncanaryMinMatch: 18,\n'
    )
    return Inputs(
        q5=Model(src / "q5.gguf", sha(b"q5"), 2, "Q5_K_M", "shipped"),
        q8=Model(src / "q8.gguf", sha(b"q8"), 2, "Q8_0", "evaluated"),
        adapter=src / "adapter",
        adapter_sha256=sha(b"lora"),
        card=src / "card.md",
        licence=src / "lic.txt",
        system_prompt=PROMPTS / "system-v1.txt",
        chat_template=PROMPTS / "chat-template.jinja",
        canary_reference=src / "canary.json",
        site_config=src / "config.js",
        pins=(release.SYSTEM_PROMPT_SHA, release.CHAT_TEMPLATE_SHA, sha(b"licence text")),
    )


def test_build_is_valid_byte_identical_and_verifies(inputs, tmp_path):
    out = tmp_path / "pkg"
    m = build(inputs, "1.0.0", out)
    assert validate("model", m) == []
    assert (out / "ffwd-0.6b-v1.0.0-Q5_K_M.gguf").read_bytes() == b"q5"
    assert (out / "ffwd-0.6b-v1.0.0-Q8_0.gguf").read_bytes() == b"q8"
    assert verify_package(out) == []
    assert [f["role"] for f in m["files"][:2]] == ["shipped", "evaluated"]
    assert m["protocol_version"] == config.PROTOCOL_VERSION
    c = m["canary"]
    assert (
        c["user_turn"] == USER
        and c["file_sha256"] == sha(b"q5")
        and c["match"] == {"kind": "prefix", "min_matched": 18, "of": 3}
    )
    readme = (out / "README.md").read_text()
    assert (
        "ffmpeg-agent-m3" not in readme.replace("`JustJoyful/ffmpeg-agent", "")
        and "DRAFT" not in readme
        and "# DRAFT" not in readme
    )
    assert "ffwd-0.6b-v1.0.0-Q8_0.gguf" in readme and "adapter/adapter_model.safetensors" in readme
    sums = (out / "SHA256SUMS").read_text().splitlines()
    assert sorted(ln.split("  ")[1] for ln in sums) == sorted(
        str(p.relative_to(out)) for p in out.rglob("*") if p.is_file() and p.name != "SHA256SUMS"
    )
    if shutil.which("sha256sum"):
        subprocess.run(["sha256sum", "-c", "SHA256SUMS"], cwd=out, check=True, capture_output=True)


def test_manifest_output_is_deterministic(inputs, tmp_path):
    build(inputs, "1.0.0", tmp_path / "a")
    build(inputs, "1.0.0", tmp_path / "b")
    assert (tmp_path / "a/ffwd-model.json").read_bytes() == (
        tmp_path / "b/ffwd-model.json"
    ).read_bytes()
    assert (tmp_path / "a/SHA256SUMS").read_bytes() == (tmp_path / "b/SHA256SUMS").read_bytes()
    text = (tmp_path / "a/ffwd-model.json").read_text()
    assert str(tmp_path) not in text and text.endswith("}\n")


def test_rebuild_into_existing_folder_is_idempotent(inputs, tmp_path):
    out = tmp_path / "pkg"
    build(inputs, "1.0.0", out)
    (out / "ffwd-0.6b-v1.0.0-Q8_0.gguf").write_bytes(
        b"corrupt"
    )  # a damaged copy is replaced, not trusted
    build(inputs, "1.0.0", out)
    assert verify_package(out) == []


@pytest.mark.parametrize("which", ["q5", "q8"])
def test_hash_mismatch_refuses_and_writes_nothing(inputs, tmp_path, which):
    m = getattr(inputs, which)
    m.src.write_bytes(b"tampered")
    out = tmp_path / "pkg"
    with pytest.raises(ReleaseError, match="sha256"):
        build(inputs, "1.0.0", out)
    assert not out.exists()


def test_other_pins_refuse(inputs, tmp_path):
    (inputs.adapter / "adapter_model.safetensors").write_bytes(b"other")
    with pytest.raises(ReleaseError, match="adapter"):
        build(inputs, "1.0.0", tmp_path / "pkg")


def test_card_must_quote_both_hashes(inputs, tmp_path):
    inputs.card.write_text(CARD.replace(sha(b"q5"), "0" * 64))
    with pytest.raises(ReleaseError, match="Q5_K_M"):
        build(inputs, "1.0.0", tmp_path / "pkg")


def test_card_replacement_that_misses_fails(inputs, tmp_path):
    inputs.card.write_text(CARD.replace("# ffwd M3 (ffmpeg-agent-m3-0.6b): ", "# Other title: "))
    with pytest.raises(ReleaseError, match="replacement"):
        build(inputs, "1.0.0", tmp_path / "pkg")


def test_canary_must_match_the_rendered_prompt_and_the_shipped_file(inputs, tmp_path):
    ref = json.loads(inputs.canary_reference.read_text())
    inputs.canary_reference.write_text(
        json.dumps({**ref, "prompt": ref["prompt"].replace("ffmpeg-agent", "other", 1)})
    )
    with pytest.raises(ReleaseError, match="canary"):
        build(inputs, "1.0.0", tmp_path / "a")
    inputs.canary_reference.write_text(json.dumps({**ref, "model": {"sha256": "0" * 64}}))
    with pytest.raises(ReleaseError, match="shipped"):
        build(inputs, "1.0.0", tmp_path / "b")


def test_site_runtime_defaults_must_agree(inputs, tmp_path):
    inputs.site_config.write_text(
        inputs.site_config.read_text().replace("nCtx: 8192", "nCtx: 4096")
    )
    with pytest.raises(ReleaseError, match="runtime defaults"):
        build(inputs, "1.0.0", tmp_path / "pkg")


def test_bad_version_refused(inputs, tmp_path):
    with pytest.raises(ReleaseError, match="MAJOR"):
        build(inputs, "1.0", tmp_path / "pkg")


def test_verify_catches_edits_missing_and_extra_files(inputs, tmp_path):
    out = tmp_path / "pkg"
    build(inputs, "1.0.0", out)
    (out / "README.md").write_text("edited")
    (out / "stray.txt").write_text("x")
    (out / "system-v1.txt").unlink()
    problems = " | ".join(verify_package(out))
    assert (
        "README.md: sha256 differs" in problems
        and "stray.txt: not listed" in problems
        and "system-v1.txt: missing" in problems
    )


def test_manifest_conformance_cases():
    path = config.PROTOCOL_DIR / "conformance" / "model-manifest.jsonl"
    cases = [json.loads(line) for line in path.read_text().splitlines()]
    assert len(cases) >= 10 and {c["ok"] for c in cases} == {True, False}
    for c in cases:
        assert (validate("model", c["manifest"]) == []) == c["ok"], c["name"]

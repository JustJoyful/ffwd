"""The release build (D-053) on tiny fake files; the real GGUFs are never touched here."""

import hashlib
import json
import shutil
import subprocess

import pytest

from training import config
from training.export.release import ReleaseError, build, verify_package
from training.protocol import validate


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


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
        c["user_turn"].startswith('{"request": "Cut the first')
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
    inputs.card.write_text(inputs.card.read_text().replace(sha(b"q5"), "0" * 64))
    with pytest.raises(ReleaseError, match="Q5_K_M"):
        build(inputs, "1.0.0", tmp_path / "pkg")


def test_card_replacement_that_misses_fails(inputs, tmp_path):
    inputs.card.write_text(
        inputs.card.read_text().replace("# ffwd M3 (ffmpeg-agent-m3-0.6b): ", "# Other title: ")
    )
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

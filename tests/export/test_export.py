from pathlib import Path

import pytest

from training.export.gguf import ExportToolsMissing, convert_argv, quantize_argv, to_gguf


def test_convert_argv_is_a_list_and_requires_the_script(tmp_path):
    with pytest.raises(ExportToolsMissing):
        convert_argv(tmp_path / "m", tmp_path / "o.gguf", tmp_path)
    (tmp_path / "convert_hf_to_gguf.py").write_text("")
    argv = convert_argv(tmp_path / "m", tmp_path / "o.gguf", tmp_path)
    assert argv[-2:] == ["--outtype", "f16"] and all(isinstance(a, str) for a in argv)


def test_quantize_argv_and_unknown_quant_rejected(tmp_path):
    assert quantize_argv(Path("a.gguf"), Path("b.gguf"), "q8_0", Path("/bin/q"))[-1] == "Q8_0"
    with pytest.raises(ValueError):
        quantize_argv(Path("a"), Path("b"), "q2_k", Path("/bin/q"))


def test_to_gguf_refuses_without_explicit_tool_paths(tmp_path, monkeypatch):
    monkeypatch.delenv("LLAMA_CPP_DIR", raising=False)
    monkeypatch.delenv("LLAMA_QUANTIZE", raising=False)
    with pytest.raises(ExportToolsMissing):
        to_gguf(tmp_path, tmp_path / "out")


def test_merged_model_carries_the_agent_template():
    torch = pytest.importorskip("torch")  # noqa: F841
    pytest.importorskip("peft")
    adapter = Path.home() / ".cache/sft-smoke/ckpt2/adapter-final"
    if not adapter.exists():
        pytest.skip("smoke adapter not present")
    from training.export.merge import merge_lora

    out = (
        Path.home() / ".cache/sft-smoke/merged-test"
    )  # scratch dir (not tmpfs: 1.2 GB), reused between runs
    if not out.exists():
        merge_lora("Qwen/Qwen3-0.6B", adapter, out)
    template = (
        out / "chat_template.jinja"
    ).read_text()  # transformers 5 stores it beside tokenizer_config.json
    assert "<think>" in template and (out / "model.safetensors").exists()
    from training.env.chat_template import AGENT_CHAT_TEMPLATE

    assert template.strip() == AGENT_CHAT_TEMPLATE.strip()


def test_convert_argv_uses_the_given_converter_python(tmp_path):
    (tmp_path / "convert_hf_to_gguf.py").write_text("")
    argv = convert_argv(tmp_path / "m", tmp_path / "o.gguf", tmp_path, "/venv/bin/python")
    assert argv[0] == "/venv/bin/python" and argv[1].endswith("convert_hf_to_gguf.py")

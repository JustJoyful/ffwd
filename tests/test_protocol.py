from training.protocol import validate

ARCH_SPEC = {
    "family": ["F1", "F4", "F6"],
    "outputs": [
        {
            "id": "out1",
            "kind": "video",
            "container": "mp4",
            "per_input": True,
            "video": {
                "codec": "h264",
                "width": 1080,
                "height": 1920,
                "fps": None,
                "pix_fmt": "yuv420p",
                "rotation": 0,
            },
            "audio": {"present": True, "codec": "aac", "loudness_lufs": None, "offset_ms": None},
            "time": {"start_s": 12.0, "end_s": 40.0, "tolerance_s": 0.1},
            "size_max_bytes": 10485760,
            "frames": {"interval_s": None, "expected_count": None, "format": None},
            "lossless": False,
        }
    ],
}

ARCH_CHECK = {
    "passed": False,
    "checks": [
        {"field": "video.height", "expected": 1920, "actual": 1080, "ok": False},
        {"field": "size_max_bytes", "expected": 10485760, "actual": 9830400, "ok": True},
    ],
    "measurements": {"duration_s": 28.02, "re_encoded": True, "loudness_lufs": -14.2},
    "error": None,
}


def test_arch_spec_example_is_valid():
    assert validate("spec", ARCH_SPEC) == []


def test_arch_check_example_is_valid():
    assert validate("check", ARCH_CHECK) == []


def test_run_action_rejects_string_args():
    assert validate("action", {"action": "run", "args": "-i x", "inputs": [], "outputs": []})


def test_unknown_action_rejected():
    assert validate("action", {"action": "shell", "cmd": "echo hi"})


def test_spec_rejects_extra_field():
    bad = {**ARCH_SPEC, "outputs": [{**ARCH_SPEC["outputs"][0], "shell": "x"}]}
    assert validate("spec", bad)


def test_spec_action_embeds_spec_schema():
    assert validate("action", {"action": "spec", "spec": ARCH_SPEC}) == []
    assert validate("action", {"action": "spec", "spec": {"family": ["F99"], "outputs": []}})


def test_schema_ids_carry_protocol_version():
    from training import config
    from training.protocol import KINDS, load_schema

    for kind in KINDS:
        assert load_schema(kind)["$id"].endswith(f"/v{config.PROTOCOL_VERSION}/{kind}")

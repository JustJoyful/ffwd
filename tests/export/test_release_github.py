import importlib.util

from training import config

spec = importlib.util.spec_from_file_location(
    "release_github", config.REPO_ROOT / "scripts" / "release_github.py"
)
rg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rg)


def test_command_is_an_argument_list_with_the_assets_and_a_draft(inputs, tmp_path):
    from training.export.release import build

    build(inputs, "1.0.0", tmp_path / "pkg")
    (tmp_path / "pkg" / "RELEASE_NOTES.md").write_text("notes")
    cmd = rg.command(tmp_path / "pkg", "o/r")
    assert cmd[:4] == ["gh", "release", "create", "v1.0.0"] and "--draft" in cmd
    assert {p.split("/")[-1] for p in cmd[4:8]} == {
        "ffwd-0.6b-v1.0.0-Q5_K_M.gguf", "ffwd-0.6b-v1.0.0-Q8_0.gguf", "ffwd-model.json", "SHA256SUMS",
    }  # fmt: skip
    assert cmd[cmd.index("--repo") + 1] == "o/r" and "LICENSE" in cmd[8]


def test_dry_run_runs_nothing_and_a_bad_package_is_refused(inputs, tmp_path, monkeypatch, capsys):
    from training.export.release import build

    build(inputs, "1.0.0", tmp_path / "pkg")
    (tmp_path / "pkg" / "RELEASE_NOTES.md").write_text("notes")
    monkeypatch.setattr(
        rg.subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(AssertionError("ran"))
    )
    assert (
        rg.main(["--repo", "o/r", "--package", str(tmp_path / "pkg")]) == 1
    )  # notes not in SHA256SUMS yet
    from training.export.release import write_sums

    write_sums(tmp_path / "pkg")
    assert rg.main(["--repo", "o/r", "--package", str(tmp_path / "pkg")]) == 0
    assert "DRY RUN" in capsys.readouterr().out

import json

from eval.native_timing import time_chores


def test_time_chores_runs_every_shared_chore(tmp_path, corpus):
    out = tmp_path / "native-timing.json"
    rows = time_chores(corpus, out, jobs_root=tmp_path / "jobs")
    assert [r["name"] for r in rows] == ["F1-trim-copy", "F4-scale-480p", "F7-frames-every-2s"]
    assert all(r["ok"] and r["seconds"] > 0 for r in rows)
    saved = json.loads(out.read_text())
    assert saved["chores"] == rows and saved["ffmpeg_version"]

import json

from eval.native_bench import JOBS, time_bench
from training.corpus.make_bench import make_bench


def test_time_bench_runs_every_job_on_tiny_clips(tmp_path):
    bench = tmp_path / "bench"
    bench.mkdir()
    (bench / "manifest.json").write_text(json.dumps(make_bench(bench, duration_s=1.0)))
    rows = time_bench(bench, tmp_path / "native.json")
    assert [r["name"] for r in rows] == [j[0] for j in JOBS]
    assert all(r["ok"] and r["output_bytes"] > 0 for r in rows)

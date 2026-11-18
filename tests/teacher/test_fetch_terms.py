import json
import subprocess

from training.teacher import fetch_terms


def test_curl_is_called_with_an_argument_list_and_the_snapshot_records_status_time_and_hashes(
    tmp_path, monkeypatch
):
    seen = []

    def fake_run(argv, **kw):
        seen.append(argv)
        body = argv[argv.index("--output") + 1]
        open(body, "w").write("<html>" + argv[-1] + "</html>")
        open(argv[argv.index("--dump-header") + 1], "w").write("HTTP/2 200\n")
        return subprocess.CompletedProcess(argv, 0, stdout="200", stderr="")

    monkeypatch.setattr(fetch_terms.subprocess, "run", fake_run)
    meta = fetch_terms.fetch(
        tmp_path / "snap", "owner read it", urls=("https://x.test/a.html", "https://x.test/b.html")
    )
    assert all(isinstance(a, list) and a[0] == "curl" for a in seen) and "--user-agent" in seen[0]
    assert [p["http_status"] for p in meta["pages"]] == [200, 200]
    assert meta["snapshot_sha256"] == fetch_terms.snapshot_sha256(meta["pages"])
    saved = json.loads((tmp_path / "snap" / "terms.json").read_text())
    assert saved["owner_confirmation"] == "owner read it" and saved["pages"][0][
        "fetched_utc"
    ].endswith("Z")

import re
import subprocess

from training import config

# RULES §5.6: keys never in git. Cheap local guard alongside GitHub secret scanning.
KEY_LIKE = re.compile(r"sk-[A-Za-z0-9]{20,}")


def test_no_api_keys_in_tracked_files():
    files = subprocess.run(
        ["git", "ls-files"], cwd=config.REPO_ROOT, capture_output=True, text=True, check=True
    ).stdout.split()
    offenders = []
    for f in files:
        path = config.REPO_ROOT / f
        if path.is_file() and path.stat().st_size < 2_000_000:
            if KEY_LIKE.search(path.read_text(errors="ignore")):
                offenders.append(f)
    assert offenders == []

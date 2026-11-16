"""Build the hash-pinned task splits (plan T10, D-027).

uv run python -m training.taskgen.build --out data/tasks [--workers 3]

Draw contents (a content = what must be built: inputs + gold spec + reference), verify every reference solution
against the checker in parallel, drop failures (counted in the manifest), assign a split by content hash, render each
content in its style(s), validate against the task schema, and write data/tasks/<split>/v1.jsonl + MANIFEST.json.
Deterministic: the same seed, corpus and code give byte-identical files.
"""

import argparse
import hashlib
import json
import random
import subprocess
import tempfile
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from training import config
from training.protocol import validate
from training.taskgen import phrasing
from training.taskgen.clips import ClipIndex
from training.taskgen.compose import sample_composition
from training.taskgen.families import SAMPLERS
from training.taskgen.phrasing_heldout import HELDOUT_STYLES
from training.taskgen.special import sample_ambiguous, sample_unsupported
from training.taskgen.splits import assign_split
from training.taskgen.verify import content_key, draft_task_core, verify_task

ABBR = {
    "train": "tr",
    "dev": "dv",
    "test-iid": "ti",
    "test-compositional": "tc",
    "test-phrasing": "tp",
}


def draw_candidate(rng: random.Random, ci: ClipIndex) -> dict | None:
    """One unverified content: {core, intents, slots}."""
    x = rng.random()
    if x < config.MIX_AMBIGUOUS:
        s = sample_ambiguous(rng, ci)
        core = {
            "inputs": s["inputs"], "gold_spec": None, "families": s["families"], "difficulty": 1,
            "reference_runs": None, "clarification": s["clarification"],
            "flags": {"ambiguous": True, "unsupported": False},
            "content_key": content_key(s["families"], s["inputs"], {"amb": s["intent"], "answer": s["clarification"]}),
        }  # fmt: skip
        return {"core": core, "intents": [s["intent"]], "slots": {}}
    if x < config.MIX_AMBIGUOUS + config.MIX_UNSUPPORTED:
        s = sample_unsupported(rng, ci)
        core = {
            "inputs": s["inputs"], "gold_spec": None, "families": [], "difficulty": 1, "reference_runs": None,
            "clarification": None, "nearest_supported": s["nearest_supported"],
            "flags": {"ambiguous": False, "unsupported": True},
            "content_key": content_key([], s["inputs"], {"unsup": s["intent"]}),
        }  # fmt: skip
        return {"core": core, "intents": [s["intent"]], "slots": {}}
    k = rng.choices([1, 2, 3, 4], weights=config.MIX_FAMILY_COUNT)[0]
    if k == 1:
        draft = SAMPLERS[rng.choice(sorted(SAMPLERS, key=lambda f: int(f[1:])))](rng, ci)
    else:
        draft = sample_composition(rng, ci, k)
    if draft is None:
        return None
    core = draft_task_core(draft, ci) | {
        "clarification": None,
        "flags": {"ambiguous": False, "unsupported": False},
    }
    return {"core": core, "intents": draft.intents, "slots": draft.slots}


def _verify_job(args: tuple[dict, dict[str, str]]) -> tuple[str, bool, list]:
    core, corpus = args
    if core["gold_spec"] is None:
        return core["content_key"], True, []
    config.JOBS_DIR.mkdir(parents=True, exist_ok=True)  # not /tmp: that is RAM-backed
    with tempfile.TemporaryDirectory(prefix="tgv-", dir=config.JOBS_DIR) as d:
        row = verify_task(core | {"id": "v"}, {k: Path(v) for k, v in corpus.items()}, Path(d))
    return core["content_key"], row["passed"], row["failed"]


def _styles_for(split: str, key: str, rng: random.Random) -> list[str]:
    if split == "train":
        return rng.sample(phrasing.TRAIN_STYLES, config.TRAIN_STYLES_PER_CONTENT)
    if split == "test-phrasing":
        return [HELDOUT_STYLES[int(key[:8], 16) % len(HELDOUT_STYLES)]]
    return [rng.choice(phrasing.TRAIN_STYLES)]


def render_tasks(split: str, contents: list[dict]) -> list[dict]:
    tasks, seen = [], set()
    for c in contents:
        core, key = c["core"], c["core"]["content_key"]
        rng = random.Random(f"{config.TASKGEN_SEED}:{key}")
        for style in _styles_for(split, key, rng):
            text = phrasing.render_request(
                c["intents"], c["slots"], style, random.Random(f"{key}:{style}")
            )
            if (text, tuple(core["inputs"])) in seen:
                continue
            seen.add((text, tuple(core["inputs"])))
            task = {
                "id": f"{ABBR[split]}-{key[:10]}-{style[:5]}",
                "split": split,
                "source": f"taskgen-{config.TASKGEN_VERSION}",
                "request": text,
                "style": style,
            } | {k: v for k, v in core.items()}
            problems = validate("task", task)
            assert not problems, (task["id"], problems)
            tasks.append(task)
    return sorted(tasks, key=lambda t: t["id"])


def build(
    out: Path,
    targets: dict[str, int] | None = None,
    workers: int = 3,
    seed: int = config.TASKGEN_SEED,
    batch: int = 120,
    max_rounds: int = 80,
) -> dict:
    targets = targets or config.SPLIT_TARGETS
    ci = ClipIndex()
    corpus = {c.id: str(c.path) for c in ci.clips.values()}
    need = {
        s: (-(-t // config.TRAIN_STYLES_PER_CONTENT) if s == "train" else t)
        for s, t in targets.items()
    }
    have: dict[str, list[dict]] = {s: [] for s in targets}
    seen: set[str] = set()
    dropped: Counter = Counter()
    attempts = 0
    for _round in range(max_rounds):
        if all(len(have[s]) >= need[s] for s in need):
            break
        pending: dict[str, list[dict]] = {s: [] for s in need}
        for _ in range(batch * 4):
            if sum(len(v) for v in pending.values()) >= batch:
                break
            attempts += 1
            cand = draw_candidate(random.Random(f"{seed}:{attempts}"), ci)
            if cand is None:
                dropped["no_draft"] += 1
                continue
            core = cand["core"]
            if core["content_key"] in seen:
                dropped["duplicate"] += 1
                continue
            split = assign_split(core["content_key"], core["families"] or ["F0"], seed)
            if split not in need or len(have[split]) + len(pending[split]) >= need[split]:
                continue
            seen.add(core["content_key"])
            pending[split].append(cand)
        flat = [(s, c) for s, cs in pending.items() for c in cs]
        with ProcessPoolExecutor(workers) as pool:
            results = list(pool.map(_verify_job, [(c["core"], corpus) for _, c in flat]))
        for (s, c), (_, ok, _why) in zip(flat, results, strict=True):
            if ok:
                have[s].append(c)
            else:
                dropped[f"verify_failed:{'+'.join(c['core']['families'])}"] += 1
    out.mkdir(parents=True, exist_ok=True)
    manifest: dict = {
        "generator_version": config.TASKGEN_VERSION, "seed": seed, "attempts": attempts, "dropped": dict(dropped),
        "heldout_combos": [list(c) for c in config.HELDOUT_COMBOS], "train_styles": list(phrasing.TRAIN_STYLES),
        "heldout_styles": list(HELDOUT_STYLES),
        "corpus_manifest_sha256": hashlib.sha256((config.CORPUS_DIR / "manifest.json").read_bytes()).hexdigest(),
        "git_commit": subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip(),
        "splits": {},
    }  # fmt: skip
    for split in targets:
        tasks = render_tasks(split, have[split])
        d = out / split
        d.mkdir(parents=True, exist_ok=True)
        blob = "".join(json.dumps(t, sort_keys=True) + "\n" for t in tasks)
        (d / "v1.jsonl").write_text(blob)
        fam = Counter(f for t in tasks for f in (t["families"] or ["unsupported"]))
        manifest["splits"][split] = {
            "target": targets[split], "tasks": len(tasks), "contents": len(have[split]),
            "sha256": hashlib.sha256(blob.encode()).hexdigest(),
            "difficulty": dict(sorted(Counter(t["difficulty"] for t in tasks).items())),
            "families": dict(sorted(fam.items())),
            "ambiguous": sum(t["flags"]["ambiguous"] for t in tasks),
            "unsupported": sum(t["flags"]["unsupported"] for t in tasks),
        }  # fmt: skip
    (out / "MANIFEST.json").write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n")
    return manifest


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=config.DATA_DIR / "tasks")
    ap.add_argument("--workers", type=int, default=3)
    a = ap.parse_args()
    m = build(a.out, workers=a.workers)
    for s, v in m["splits"].items():
        print(s, v["tasks"], "tasks", v["contents"], "contents", v["difficulty"])
    print("dropped:", m["dropped"])


if __name__ == "__main__":
    main()

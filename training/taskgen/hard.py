"""Hard-variant train pool (pilot of the T18 follow-up, owner instruction 20 Nov 2026).

uv run python -m training.taskgen.hard --out data/tasks-hard/pilot --n 300 [--workers 3]

Same generator, verification and phrasing as `training.taskgen.build`, but the draw is reweighted toward the patterns M1
fails or flip-flops on (more 3-4 family tasks, more of the file-dependent families in `config.HARD_FAMILIES`, more F9
combinations). Parameter distributions are unchanged. Guarantees, by construction and not by reading any other split:

* a candidate is kept only if `assign_split(content_key, families)` puts it in `train`, so it can never share content with
  dev, test-iid, test-phrasing (hash buckets) or test-compositional (held-out family combinations);
* styles are drawn from `phrasing.TRAIN_STYLES` only (the held-out styles are never rendered);
* its content key differs from every task already in the train split (only the train file's keys are read);
* every reference solution is executed against its gold spec and dropped if it does not pass.
"""

import argparse
import hashlib
import json
import random
import subprocess
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from training import config
from training.protocol import validate
from training.taskgen import phrasing
from training.taskgen.build import CACHE, _cache_key, _load_cache, _verify_job, corpus_hash
from training.taskgen.clips import ClipIndex
from training.taskgen.compose import sample_composition
from training.taskgen.families import SAMPLERS
from training.taskgen.splits import assign_split
from training.taskgen.verify import draft_task_core


def combo_weight(combo: tuple[str, ...]) -> float:
    """Valid combinations with more hard families (and an F9) are drawn more often; weight is always >= 1."""
    return 1 + 2 * len(set(combo) & set(config.HARD_FAMILIES)) + (1 if "F9" in combo else 0)


def draw_hard(rng: random.Random, ci: ClipIndex) -> dict | None:
    """One unverified content {core, intents, slots}: never ambiguous or unsupported (those have no gradable run)."""
    k = rng.choices([1, 2, 3, 4], weights=config.HARD_FAMILY_COUNT_WEIGHTS)[0]
    if k == 1:
        draft = SAMPLERS[rng.choice(config.HARD_FAMILIES)](rng, ci)
    else:
        draft = sample_composition(rng, ci, k, combo_weight=combo_weight)
    if draft is None:
        return None
    core = draft_task_core(draft, ci) | {
        "clarification": None,
        "flags": {"ambiguous": False, "unsupported": False},
    }
    return {"core": core, "intents": draft.intents, "slots": draft.slots}


def render_hard(cand: dict) -> dict:
    """One train task (one train style) for a verified content."""
    core, key = cand["core"], cand["core"]["content_key"]
    style = random.Random(f"{config.HARD_POOL_SEED}:{key}").choice(phrasing.TRAIN_STYLES)
    text = phrasing.render_request(
        cand["intents"], cand["slots"], style, random.Random(f"{key}:{style}")
    )
    task = {
        "id": f"tr-{key[:10]}-{style[:5]}",
        "split": "train",
        "source": f"taskgen-{config.TASKGEN_VERSION}-hard",
        "request": text,
        "style": style,
    } | dict(core)
    problems = validate("task", task)
    assert not problems, (task["id"], problems)
    return task


def build_pool(
    n: int,
    *,
    seed: int = config.HARD_POOL_SEED,
    workers: int = 3,
    existing_keys: frozenset[str] = frozenset(),
    batch: int = 60,
    max_rounds: int = 400,
    manifest: Path | None = None,
) -> tuple[list[dict], dict]:
    """n verified train tasks and a stats dict (attempts, drops by reason)."""
    ci = ClipIndex(manifest) if manifest else ClipIndex()
    corpus = {c.id: str(c.path) for c in ci.clips.values()}
    have: list[dict] = []
    seen, dropped, attempts = set(existing_keys), Counter(), 0
    cache = _load_cache()
    for _ in range(max_rounds):
        if len(have) >= n:
            break
        pending: list[dict] = []
        while len(have) + len(pending) < n and len(pending) < batch and attempts < 100_000:
            attempts += 1
            cand = draw_hard(random.Random(f"{seed}:hard:{attempts}"), ci)
            if cand is None:
                dropped["no_draft"] += 1
                continue
            core = cand["core"]
            key = core["content_key"]
            if key in seen:
                dropped["duplicate_or_in_train"] += 1
                continue
            if assign_split(key, core["families"], config.TASKGEN_SEED) != "train":
                dropped[
                    "not_train_bucket"
                ] += 1  # dev/test hash bucket or held-out combo: never used here
                continue
            seen.add(key)
            pending.append(cand)
        todo = [c for c in pending if _cache_key(c["core"]) not in cache]
        with ProcessPoolExecutor(workers) as pool:
            fresh = list(pool.map(_verify_job, [(c["core"], corpus) for c in todo]))
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        with CACHE.open("a") as f:
            for c, (_, ok, _w) in zip(todo, fresh, strict=True):
                cache[_cache_key(c["core"])] = ok
                f.write(json.dumps({"k": _cache_key(c["core"]), "ok": ok}) + "\n")
        for c in pending:
            if cache[_cache_key(c["core"])]:
                have.append(c)
            else:
                dropped["verify_failed:" + "+".join(c["core"]["families"])] += 1
        print(f"verified so far {len(have)}/{n} (attempts {attempts})", flush=True)
    else:
        raise RuntimeError(f"pool not filled after {attempts} draws: {dict(dropped)}")
    tasks = sorted((render_hard(c) for c in have[:n]), key=lambda t: t["id"])
    return tasks, {"attempts": attempts, "dropped": dict(dropped)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--n", type=int, default=config.HARD_PILOT_N)
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--seed", type=int, default=config.HARD_POOL_SEED)
    ap.add_argument("--train", type=Path, default=config.DATA_DIR / "tasks" / "train" / "v1.jsonl")
    ap.add_argument(
        "--exclude",
        type=Path,
        nargs="*",
        default=[],
        help="more task files (train-hard pools) whose contents to avoid",
    )
    a = ap.parse_args()
    if a.out.exists():
        raise SystemExit(f"refusing to overwrite {a.out}")
    train_keys = frozenset(
        json.loads(x)["content_key"]
        for path in [a.train, *a.exclude]
        for x in path.read_text().splitlines()
    )
    tasks, stats = build_pool(a.n, seed=a.seed, workers=a.workers, existing_keys=train_keys)
    a.out.mkdir(parents=True)
    blob = "".join(json.dumps(t, sort_keys=True) + "\n" for t in tasks)
    (a.out / "tasks.jsonl").write_text(blob)
    manifest = {
        "pool": "hard-variant",
        "n": len(tasks),
        "seed": a.seed,
        "generator_version": config.TASKGEN_VERSION,
        "taskgen_seed": config.TASKGEN_SEED,
        "corpus_manifest_sha256": corpus_hash(),
        "git_commit": subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True
        ).stdout.strip(),
        "tasks_sha256": hashlib.sha256(blob.encode()).hexdigest(),
        "train_tasks_file_sha256": hashlib.sha256(a.train.read_bytes()).hexdigest(),
        "family_count": dict(sorted(Counter(len(t["families"]) for t in tasks).items())),
        "families": dict(sorted(Counter(f for t in tasks for f in t["families"]).items())),
        "styles": dict(sorted(Counter(t["style"] for t in tasks).items())),
        "weights": {
            "family_count": config.HARD_FAMILY_COUNT_WEIGHTS,
            "hard_families": config.HARD_FAMILIES,
        },
        **stats,
    }
    (a.out / "manifest.json").write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n")
    print(json.dumps({k: manifest[k] for k in ("n", "family_count", "attempts", "dropped")}))


if __name__ == "__main__":
    main()

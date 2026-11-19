"""N-gram leakage audit (EVALUATION §6): how much of each test request's wording already appears in train/teacher prompts?

uv run python -m eval.leakage --train data/tasks/train/v1.jsonl --test data/tasks/test-phrasing/v1.jsonl

Word 4-grams, Jaccard similarity of the n-gram SETS. Reading test REQUEST TEXT for an audit is not training on it;
nothing here feeds back into data generation. Expectation by design: test-iid is the training distribution so it
overlaps (reported, not gated); test-phrasing and test-compositional must stay below `LEAKAGE_JACCARD_MAX` against train.
"""

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

from training import config

_WORD = re.compile(r"[a-z0-9:.]+")


def ngrams(text: str, n: int = 4) -> frozenset[tuple[str, ...]]:
    words = _WORD.findall(text.lower())
    if len(words) < n:
        return frozenset([tuple(words)]) if words else frozenset()
    return frozenset(tuple(words[i : i + n]) for i in range(len(words) - n + 1))


def leakage_report(
    train: list[str], test: list[str], n: int = 4, threshold: float = config.LEAKAGE_JACCARD_MAX
) -> dict:
    """max/mean over test requests of their best Jaccard against any train request, plus the offending pairs."""
    train_sets = [ngrams(t, n) for t in train]
    index: dict[tuple[str, ...], list[int]] = defaultdict(list)
    for i, s in enumerate(train_sets):
        for g in s:
            index[g].append(i)
    best, over = [], []
    for text in test:
        s = ngrams(text, n)
        cand = {i for g in s for i in index.get(g, ())}
        top, top_i = 0.0, -1
        for i in cand:
            j = len(s & train_sets[i]) / len(s | train_sets[i])
            if j > top:
                top, top_i = j, i
        best.append(top)
        if top >= threshold:
            over.append({"test": text, "train": train[top_i], "jaccard": round(top, 3)})
    return {
        "n": n,
        "tests": len(test),
        "max_jaccard": round(max(best, default=0.0), 3),
        "mean_jaccard": round(sum(best) / len(best), 3) if best else 0.0,
        "threshold": threshold,
        "pairs_over_threshold": over,
    }


def normalize(text: str) -> str:
    """Request identity for the exact-duplicate audit: lowercase word tokens, so case/punctuation/spacing don't hide a copy."""
    words = (
        w.strip(".:") for w in _WORD.findall(text.lower())
    )  # "2s." == "2s", but "0.5x" stays whole
    return " ".join(w for w in words if w)


def exact_duplicates(train: list[str], test: list[dict]) -> dict:
    """Test tasks whose request is word-for-word (after `normalize`) a train request. `test` = task rows (need id, request).
    `dedup_ids` is the deduplicated subset the preregistration reports next to the full split."""
    seen = {normalize(t) for t in train}
    dup = sorted(t["id"] for t in test if normalize(t["request"]) in seen)
    dupset = set(dup)
    return {
        "tests": len(test),
        "exact_duplicates": len(dup),
        "share": round(len(dup) / len(test), 4) if test else 0.0,
        "dedup_ids": sorted(t["id"] for t in test if t["id"] not in dupset),
        "duplicate_ids": dup,
    }


def _requests(path: Path) -> list[str]:
    return [json.loads(x)["request"] for x in path.read_text().splitlines()]


def _rows(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text().splitlines()]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", type=Path, nargs="+", required=True)
    ap.add_argument("--test", type=Path, nargs="+", required=True)
    ap.add_argument(
        "--exact-out",
        type=Path,
        help="write the exact-duplicate audit (counts + dedup id lists) here",
    )
    a = ap.parse_args()
    train = [r for p in a.train for r in _requests(p)]
    exact = {}
    for p in a.test:
        r = leakage_report(train, _requests(p))
        print(
            p.parent.name,
            {k: v for k, v in r.items() if k != "pairs_over_threshold"},
            len(r["pairs_over_threshold"]),
            "over",
        )
        exact[p.parent.name] = exact_duplicates(train, _rows(p))
        print(
            p.parent.name, {k: v for k, v in exact[p.parent.name].items() if not k.endswith("ids")}
        )
    if a.exact_out:
        a.exact_out.parent.mkdir(parents=True, exist_ok=True)
        a.exact_out.write_text(json.dumps(exact, indent=1) + "\n")


if __name__ == "__main__":
    main()

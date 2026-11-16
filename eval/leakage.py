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


def _requests(path: Path) -> list[str]:
    return [json.loads(x)["request"] for x in path.read_text().splitlines()]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", type=Path, nargs="+", required=True)
    ap.add_argument("--test", type=Path, nargs="+", required=True)
    a = ap.parse_args()
    train = [r for p in a.train for r in _requests(p)]
    for p in a.test:
        r = leakage_report(train, _requests(p))
        print(
            p.parent.name,
            {k: v for k, v in r.items() if k != "pairs_over_threshold"},
            len(r["pairs_over_threshold"]),
            "over",
        )


if __name__ == "__main__":
    main()

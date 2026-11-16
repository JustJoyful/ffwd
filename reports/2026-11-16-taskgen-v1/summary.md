# Task generator v1 build (16 Nov 2026)

Splits in `data/tasks/<split>/v1.jsonl`, pinned by `data/tasks/MANIFEST.json` (copy here). Every reference solution was executed
against checker v1.3 before a task was emitted (31 contents dropped, mostly F2+F9 merges; counted in the manifest).

| Split | Tasks | Contents | Difficulty 1/2/3/4 | Ambiguous | Unsupported |
|---|---|---|---|---|---|
| train | 4486 | 1500 (x3 styles) | 1564 / 1644 / 1026 / 252 | 94 | 171 |
| dev | 300 | 300 | 44 / 129 / 107 / 20 | 2 | 5 |
| test-iid | 500 | 500 | 117 / 205 / 135 / 43 | 12 | 12 |
| test-compositional | 200 | 200 | 0 / 191 / 9 / 0 | 0 | 0 |
| test-phrasing | 200 | 200 | 72 / 76 / 44 / 8 | 8 | 6 |

## Leakage audit (word 4-gram Jaccard vs train; gate: < 0.9 for the held-out splits)
- test-phrasing: max 0.692, mean 0.243, 0 pairs over. test-compositional: max 0.737, mean 0.423, 0 over. **Both pass.**
- dev / test-iid: max 1.0 (28 and 65 requests identical in wording to some train request). Expected and not a leak: same distribution, and identical
  wording with a different clip/parameters is a different task (content keys are disjoint across splits, tested). Reported, not gated.

## Honest limitations
1. **Difficulty mix is far from the 55/30/12/3 target** (dev: 15% single-family). The single-family content space is small (a few hundred distinct
   contents), so after de-duplication (14,671 duplicates rejected) the pools fill with compositions. Single-family skills are still covered by train
   (1564 tasks, 3 wordings per content) but dev/test-iid overstate multi-step difficulty. Fix options: more clips (owner's real clips help), more parameter variety.
2. **Few ambiguous/unsupported tasks in dev (2 and 5)**: those content spaces are tiny too. Clarification accuracy on dev is therefore weakly measured; the hand-written
   spike-v1 dev set (3 ambiguous, 3 unsupported + owner additions) complements it.
3. F11 (A/V sync) has 1 dev task, F8 (GIF) 5, F7 8: thin per-family dev numbers; report by family with CIs, do not over-read.
4. Synthetic clips only so far; real clips arrive with the owner's recordings (test-real).

# Notes on the mutation self-test (22 Nov 2026)

Command: `uv run python -m eval.checker_mutation --out reports/2026-11-22-checker-mutation --work <scratch>`; seed 20261115, 60 dev tasks with a video output (all 60 unmutated references passed their own spec: control failures 0). Dev only.

Result: 9 mutant kinds, 413 applicable mutants (60 + 44 + 60 + 60 + 60 + 7 + 12 + 7 + 3), **411 killed, 2 survivors**; both survivors are `truncate_half` and I checked them by hand:

| task | expected duration | reference output | mutant (stream-copy cut to half) | difference | tolerance |
|---|---|---|---|---|---|
| `dv-cdbeb8820a-verbo` | 0.667 s | 0.734 s | 0.500 s | 0.167 s | 0.2 s |
| `dv-82bcc50831-casua` | 0.667 s | 0.734 s | 0.467 s | 0.200 s | 0.2 s |

So they are not blind spots: the reference outputs are shorter than one second, "half" of them lands inside the preregistered `tolerance_s` of 0.2 s, and the check correctly accepts a result within tolerance. They are mutants too weak to be wrong, and are counted as survivors in the table rather than removed (a mutant is not dropped because the checker passed it). The checker has no real blind spot among the fields mutated here.

What the test does not cover: A/V offset, size targets, codec and pixel-format changes, audio-only or image-sequence outputs, and mutants of the input/probe side; those rest on the conformance suite (`packages/protocol/conformance/`).

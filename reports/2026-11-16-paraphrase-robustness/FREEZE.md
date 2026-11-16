# B0 freeze (recorded before any paraphrase exists)

- Repo commit at freeze: `98f5a6fc53a19d901914b7d0b9d83ad2622f6bec` (tag `b0-frozen-paraphrase`)
- `eval/b0_regex.py` sha256: `78bd78a021fdd2f29200c9f175c0043a743225c650e0cd52dcc9add3acbf811f` (last changed in `cfb2ab7`)
- `data/tasks/dev/spike-v0.jsonl` sha256: `25e9d18e2ddf486aa44f261c62fc168322c77c0808333838fa85943d516c0489`
- B0 is NOT edited after paraphrases are generated. The paraphraser never sees B0's patterns, and a
  paraphrase is generated once per task (no regenerating until B0 passes). If B0 is wrong on a paraphrase,
  that is the result. Re-check at the end: the hash above must still match.

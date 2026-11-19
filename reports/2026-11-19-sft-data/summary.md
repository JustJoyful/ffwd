# M1 SFT data (19 Nov 2026)

Built by `training.sft.build` from the bulk teacher run (`reports/2026-11-19-teacher-bulk/`), train tasks only. Nothing from dev or any test split.

| source | examples in train | notes |
|---|---|---|
| teacher (DeepSeek V4.1 Flash, kept = checker pass AND label ok) | 3021 | 3199 kept trajectories; 2 over 3072 tokens dropped; 1648 schema-invalid assistant turns (and their error replies) removed from 945 trajectories |
| teacher paraphrases | 1896 | 2005 kept of 2194 tried (93 dropped: digits differed; 96: judge said NO); $0.2661 of the $0.30 cap; a COPY of a kept trajectory with only the request reworded, teacher replies untouched |
| oracle (programmatic, D-032) | 1115 | 18.5% of train (cap 30%); 1163 played, 1163 passed; contents the teacher did not reach + unsupported top-ups |
| **total** | **6032 train + 333 val** | validation holds out whole contents (a paraphrase goes with its source); mean 1759 tokens, max 2922; 1.54 M trained tokens; largest family F1 = 7.2% (cap 25%) |

Unsupported examples per category after filtering (the teacher put an arbitrary family in `nearest_supported` and was filtered; the oracle tops up to >= 20): background 35, blur_faces 37, colour_grade 30, remove_object 27, stabilize 35, subtitles 41, transcribe 40, upscale 42, voice 31. Mostly oracle-written (canonical reasons, gold label), so the refusal *reasons* are templated; the teacher supplies them only for subtitles, transcribe and upscale.

Leakage of the paraphrase wordings (4-gram Jaccard, threshold 0.9): test-compositional max 0.43, test-phrasing max 0.42, dev max 0.50. test-iid shows 1 pair at 1.0 ("can you make this video 1.5x faster?"): test-iid is the training distribution (train vs test-iid already has 108 such pairs), the held-out splits are the gate.

Known limits: 27% of teacher trajectories had a schema-invalid turn (the probe's raw container string copied into the spec), fixed by dropping those turns, so the student never sees the correction; paraphrases add wording variety, not new solutions; the 982 train tasks the budget did not reach are covered only by the oracle's canonical solutions.

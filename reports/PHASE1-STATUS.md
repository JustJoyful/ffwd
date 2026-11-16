# Phase 1 status (autonomous run; owner away from 16 Nov 2026)

Plan: `docs/superpowers/plans/2026-11-16-phase-1-core-model.md`. Rule while the owner is away: do every ungated task; **never cross an [ASK] gate**
(DeepSeek spend incl. paraphrases/teacher/X1, the main GRPO run, the single test run, HF/public publishing beyond private repos already in use).
No questions to the owner; conservative defaults, documented.

| Task | Status |
|---|---|
| T1 protocol 0.2.0 + split guard | done (`training/taskgen/loader.py`) |
| T2 sandbox + rollout timeouts | done; FFmpeg pin **blocked on D-024** (owner decision + permission to fetch a 5.1.x build) |
| T3 corpus v1 + Hub distribution | done in code (22 clips); **Hub push not done** (creates a repo on the owner's HF account; do when Kaggle needs it); real clips wait for the owner |
| T4 checker quality floor | done (v1.3) |
| T5 spike-v1 owner tasks | waiting for the owner's ~20 tasks + 2-3 clips |
| T6 prompt v1 + agent chat template | done (D-026; llama.cpp/HF/Jinja parity verified); prompt v1 is a DRAFT until D-024 |
| T7-T10 taskgen v1 | done in code (F1-F12, compositions 2-4, ambiguous/unsupported, styles, content-hash splits, verified build); full build running/ran: see data/tasks/MANIFEST.json |
| T11 leakage audit | done (`eval/leakage.py`); **train paraphrases (DeepSeek) not run: gated** |
| T12 prereg + test lock | done (prereg is a DRAFT; `eval/testlock.py`); dev baselines on v1 wait for the owner's new spike tasks and are DeepSeek-gated for X1 |
| T13 teacher runner | done in code + tests; **pilot/bulk gated** (needs G-terms, off-peak window, frozen prompt, owner go-ahead) |
| T14-T15 | gated (teacher bulk) / rejection sampling code not yet written |
| T16-T25 | not started (SFT, lockstep rollouts, GRPO driver, parity, CLI, final report, cards) |
| Kaggle kill-and-resume | session 1 pushed 16 Nov ~18:00 IST and still QUEUED hours later |

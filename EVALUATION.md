# EVALUATION: ffmpeg-agent

How the model and product are measured. **The goal is believable numbers, not big numbers.**

---

## 1. Questions we answer

| ID | Question | Primary metric |
|---|---|---|
| Q1 | Is there a gap worth training for? (Phase 0) | Task success: base small model vs DeepSeek V4 Flash |
| Q2 | Does SFT on verified teacher trajectories help? | Task success: base vs SFT |
| Q3 | Does multi-turn GRPO help beyond SFT? Does single-turn? | SFT vs SFT+single-turn GRPO vs SFT+multi-turn GRPO |
| Q4 | How close does the small model get to a frontier agent, and at what cost? | Success ratio vs DeepSeek / Claude Code subset; cost per task |
| Q5 | Does it generalise to unseen combinations and phrasings? | Success on test-compositional and test-phrasing |
| Q6 | What does quantization and the browser runtime cost? | Parity eval across fp16 / MLC q4 / GGUF Q4 / Q8; seconds per chore browser vs native |
| Q7 | Where does AI beat simple presets? | Success by family: regex/preset baseline vs model |

**Predeclare:** Q2–Q5 comparisons and the minimum meaningful difference are written in `eval/PREREGISTRATION.md` **before** the test sets are run for the first time.

## 2. Task suite

| Split | Purpose | Size (target) |
|---|---|---|
| `train` | SFT + GRPO prompts | thousands (generated) |
| `dev` | Reward tuning, checkpoint selection, ablation sanity | ~300 |
| `test-iid` | Same distribution as training | ~500 |
| `test-compositional` | Family combinations never seen in training | ~200 |
| `test-phrasing` | Held-out phrasing styles / paraphrase templates | ~200 |
| `test-real` | Hand-written requests on real clips (own + volunteers, licence-clean) | ~100 |
| `ellmpeg-480` | External: ELLMPEG queries (FFmpeg subset), **if licence and format allow** | ≤480 |

Every task carries: `family tags`, `difficulty` (1–3 families), `ambiguous` / `unsupported` flags, gold spec, input clip IDs. Splits are **hash-pinned**. A manifest records the generator version and seed.

**Contamination rules:** test tasks never appear in teacher prompts, few-shot examples, paraphrase seeds or reward tuning. Teacher generation runs on `train` only.

## 3. Systems compared

| # | System | Notes |
|---|---|---|
| B0 | **Regex/preset baseline** (Ez FFmpeg-style) | Hand-written patterns for the most common phrasings per family |
| B1 | Base Qwen3-0.6B / 1.7B, single shot | Request + probe → one command, no retries |
| B2 | Base model + agent loop | Same harness, retries allowed |
| M1 | SFT | Verified teacher + rejection-sampled data |
| M2 | SFT + single-turn GRPO | Ablation |
| M3 | SFT + multi-turn GRPO | Main model |
| X1 | DeepSeek V4 Flash + agent loop | Frontier-ish baseline (budgeted; held-out test only) |
| X2 | Claude Code / Codex | Small manual subset (~30–50 tasks), owner's subscription |

All systems use the **same environment, allowlist, checker, turn budget and timeouts**.

## 4. Metrics

### 4.1 Model metrics
| Metric | Definition |
|---|---|
| **Task success** | Final output passes the **gold** spec (all set fields) within the turn budget |
| Partial score | Mean fraction of gold-spec fields satisfied |
| **Spec accuracy** | Field-level F1 of the emitted spec vs gold spec |
| Clarify accuracy | Correct `ask_user` on ambiguous tasks; correct `unsupported` on unsupported tasks; false-ask / false-refusal rates |
| Runs per task | Mean number of `run` actions (successes and failures reported separately) |
| **Unnecessary re-encode rate** | Share of tasks with a lossless solution where the model re-encoded |
| Invalid action rate | Share of turns rejected by the schema/allowlist |
| Quality floor violations | Size-target tasks that met size but failed SSIM/PSNR/VMAF floor |

### 4.2 Systems metrics
| Metric | Where |
|---|---|
| Model download size, cold load time, warm load time | Browser, 2–3 devices |
| Tokens/s, ms per action | Browser (WebLLM) vs native (llama.cpp) |
| Seconds per chore (end to end) | Browser vs helper, by family and input size bucket |
| Peak memory | Browser tab, by input size |
| Cost per task | DeepSeek API cost vs local (~0 marginal; report hardware) |

### 4.3 Product metrics
Defined in PRD §10 (activated, returning 30/60 days, monthly actives, funnel, success by family, unsupported categories). Product metrics are **reported separately** from offline model metrics and never mixed into the same table.

## 5. Statistics & reporting rules
- **Bootstrap 95% CIs** (≥10k resamples) on success rates; **paired bootstrap** for system-vs-system on the same tasks.
- **Holm correction** across the predeclared comparison family.
- **Seeds:** ≥3 training seeds for M3 vs M1 if compute allows; otherwise report it as a single-seed result and say so.
- Report **by family and by difficulty**, not only overall.
- **Denominators:** failed, timed-out, malformed and partial runs **count as failures**. Never drop them.
- **Null results are results:** if GRPO doesn't beat SFT beyond noise, report that plainly with the telemetry (reward variance, saturation step).
- Every report records: git commit, protocol version, model version, split hashes, checker version, hardware, date.
- Reports are written to fresh paths under `reports/` and never overwritten.

## 6. Sanity controls
- **Shuffled-reward GRPO run** (short): should not improve test success.
- **Checker self-test:** the conformance suite plus mutated outputs that must fail.
- **Leakage audit:** n-gram overlap between test requests and train/teacher prompts.
- **Human spot-check:** 50 random "passed" outputs per main model, inspected by eye (catches checker blind spots).

## 7. Report template (per milestone)

```text
reports/<date>-<milestone>/
  summary.md          # headline table + CIs + honest limitations
  results.json        # all metrics, per task
  by_family.csv
  telemetry/          # GRPO reward curves, variance, KL, step-wise eval
  manifest.json       # commit, versions, hashes, hardware, seeds, costs
```

Headline table format:

| System | test-iid | test-comp | test-phrasing | test-real | runs/task | re-encode↓ | cost/task |
|---|---|---|---|---|---|---|---|
| B0 regex | | | | | | | |
| B2 base+loop | | | | | | | |
| M1 SFT | | | | | | | |
| M3 SFT+MT-GRPO | | | | | | | |
| X1 DeepSeek | | | | | | | |

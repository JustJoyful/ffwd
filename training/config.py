"""Single config module for the Python harness (RULES §6.2). Every tunable lives here."""

import os
from datetime import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PROTOCOL_DIR = REPO_ROOT / "packages" / "protocol"
PROTOCOL_VERSION = "0.3.0"  # ARCH §12: shared by web, helper, training

# D-024/D-029: ONE pinned static FFmpeg for the checker, the executor and every reference run, everywhere (local,
# Kaggle, CI). The browser runs ffmpeg.wasm 5.1.4; no static native 5.1.4 exists, so the pin is 5.1.1 and the
# patch-level gap is covered by the native-vs-wasm parity test (D-024). Install: `python -m training.env.ffmpeg_pin
# install` (downloads, verifies the sha256 below, extracts into FFMPEG_PIN_HOME).
FFMPEG_PIN = {
    "version": "5.1.1-static",  # exactly what `ffmpeg -version` prints for this build (the check compares it verbatim)
    "url": "https://johnvansickle.com/ffmpeg/old-releases/ffmpeg-5.1.1-amd64-static.tar.xz",
    "sha256": "2d848c37f7f276be0262d9123a84fbfe72bb159921ffcce3bd7106f143d29f42",
    "dirname": "ffmpeg-5.1.1-amd64-static",
}
FFMPEG_PIN_HOME = Path(
    os.environ.get("FFMPEG_AGENT_PIN_HOME", Path.home() / ".cache" / "ffmpeg-agent" / "pin")
)
# Enforced since the pinned build was installed and run here (19 Nov 2026): any other FFmpeg is refused fail-closed.
# (False would still use the pinned binary when installed but tolerate a mismatching one on PATH.)
FFMPEG_PIN_ENFORCED = True


def _pinned_tool(name: str) -> str:
    p = FFMPEG_PIN_HOME / FFMPEG_PIN["dirname"] / name
    return str(p) if p.exists() else name  # not installed: PATH (refused when FFMPEG_PIN_ENFORCED)


# Binaries (ARCH §3.5): the pinned build when installed, else PATH; always invoked with argument lists.
FFMPEG_BIN = _pinned_tool("ffmpeg")
FFPROBE_BIN = _pinned_tool("ffprobe")

# Per-run limits (RULES §1.4)
RUN_TIMEOUT_S = 120
MAX_OUTPUT_BYTES = 200 * 2**20
# GRPO rollouts run thousands of FFmpeg jobs on small clips: a hung or runaway command must not burn GPU hours.
ROLLOUT_RUN_TIMEOUT_S = 20
ROLLOUT_MAX_OUTPUT_BYTES = 50 * 2**20
EXEC_CONCURRENCY = max(2, (os.cpu_count() or 2))  # concurrent FFmpeg processes (lockstep rollouts)
SANDBOX_DEFAULT = os.environ.get(
    "FFMPEG_AGENT_SANDBOX", "off"
)  # off | auto | require (training/env/sandbox.py)
STDERR_TAIL_CHARS = 2000

# Agent loop budget (ARCH §3.1)
MAX_RUNS_PER_JOB = 4
MAX_TURNS_PER_JOB = 8
MAX_ASK_USER = 1

# --- Checker tolerances (checker v1.2). Each one says what it measures, why that size, and its evidence. ---
# Time (seconds): explicit `time` fields use the spec's own tolerance_s, else this default.
DEFAULT_TIME_TOLERANCE_S = 0.1  # ARCH §3.2 example tolerance
# Implicit duration invariant: when no time field is set the output must last as long as the input (the
# sum of the inputs for a merge). Same size as the default: across the 17 spike-v1 reference solutions where it
# applies and nothing shifts audio, the largest deviation measured is 0.008 s (eval.verify_tasks), so 0.1 s
# has >10x margin, while the s07 failure mode (a 0.1 s clip from a 4 s input) is 3.9 s off. When
# audio.offset_ms is set the allowed deviation grows by |offset| (shifting audio stretches the container).
IMPLICIT_DURATION_TOLERANCE_S = 0.1
FPS_REL_TOLERANCE = 0.01  # 1 %: 29.97 vs 30 fps passes, 25 vs 30 fails
# Frame counts. A sample is wanted at t = k * interval for k = 0, 1, ...; sample k exists only while
# t_k < duration - (FRAME_SAMPLE_EPS_FRAMES / fps) (a sample inside the last half frame has no frame to take).
# An explicit expected_count is matched exactly. With only an interval, the count may be one lower when the last
# sample lies within half an interval of the end: FFmpeg's fps filter drops that final slot while the select
# filter keeps it (measured on FFmpeg 9.0.2 across 4 clips x 4 intervals), and both are reasonable readings.
FRAME_COUNT_TOLERANCE = 0
FRAME_SAMPLE_EPS_FRAMES = 0.5
# Loudness (EBU R128 integrated, LUFS): +-2.0 LU. Single-pass loudnorm and `volume=` chains land within about
# 1-2 LU of a target on short clips in general; the spike references measure -16.0 for a -16 request and
# -41.8 for +20 dB on a -61.8 LUFS clip (exact, because the gold values were derived from the same chain). Tighter
# would fail correct single-pass solutions on other clips; looser would pass a plain +6 dB boost when -16 LUFS
# was requested.
LOUDNESS_TOLERANCE_LU = 2.0
# A/V offset (milliseconds, audio first-packet pts minus video first-packet pts): +-40 ms. Measured on the
# reference solutions: requests of -500 / +300 / +200 ms read -521.3 / +278.7 / +178.7, i.e. every one is 21.3 ms
# early = exactly one AAC frame of encoder priming (1024 samples at 48 kHz). The window of OFFSET_PACKET_WINDOW
# packets absorbs B-frame reordering. 40 ms covers that priming with margin and stays well under the ~100 ms
# humans notice and the 200-500 ms offsets F11 requests, so a wrong shift cannot pass.
# Above this, ffprobe's avg_frame_rate is container junk (seen: 30000/1 on a 60 fps VP8 webm); use r_frame_rate.
PROBE_MAX_FPS = 1000.0
OFFSET_PACKET_WINDOW = 16
OFFSET_TOLERANCE_MS = 40.0
# Quality floor for size-target outputs that keep the input's timeline and framing (training/env/quality.py).
# Measured on a 20 s 720p test clip: 1 Mbps re-encode SSIM 0.98 / PSNR 38 dB; crf 45 SSIM 0.95 / 33 dB; a 64x36
# upscale (the cheap way to hit a size cap) SSIM 0.84 / 23 dB; a blank picture SSIM 0.40 / 7 dB. PSNR separates the
# tiny-picture hack that SSIM alone lets through, so both floors apply. Spike reference solutions pass (see report).
QUALITY_SAMPLE_FPS = 2
SSIM_FLOOR_DEFAULT = 0.90
PSNR_FLOOR_DB_DEFAULT = 28.0

# --- Task generator v1 (training/taskgen/build.py, D-027) ---
TASKGEN_VERSION = "1.0"
CHECKER_VERSION = (
    "v1.3"  # bump when checker behaviour changes: invalidates the task-verification cache
)
TASKGEN_SEED = 20261116
# Target TASK counts per split (EVALUATION §2; test-real is hand-written). Train contents are rendered in several
# styles, so train tasks = contents x TRAIN_STYLES_PER_CONTENT.
SPLIT_TARGETS = {
    "train": 4500,
    "dev": 300,
    "test-iid": 500,
    "test-compositional": 200,
    "test-phrasing": 200,
}
TRAIN_STYLES_PER_CONTENT = 3
# Content-hash buckets (0-99): <70 train, <75 dev, <90 test-iid, else the held-out-STYLE pool (test-phrasing).
SPLIT_BUCKETS = (70, 75, 90)
# Family combinations never generated outside test-compositional (D-027): "unseen combinations" really are unseen.
HELDOUT_COMBOS = (
    ("F3", "F4"), ("F5", "F12"), ("F1", "F8"), ("F4", "F10"), ("F6", "F9"), ("F9", "F12"), ("F1", "F4", "F6"),
)  # fmt: skip
# Draw mix: share of ambiguous / unsupported tasks, and of 1/2/3/4-family tasks among the rest.
MIX_AMBIGUOUS = 0.08
MIX_UNSUPPORTED = 0.08
MIX_FAMILY_COUNT = (0.55, 0.30, 0.12, 0.03)

# Leakage audit (eval/leakage.py): word 4-gram Jaccard between a test request and its most similar train request.
LEAKAGE_JACCARD_MAX = 0.9

# --- SFT (training/sft) ---
# Prompt v1 + probes are ~1.6k tokens of every example (only ~220 are trained); 3-input merges exceed 2048.
SFT_MAX_LEN = 3072  # tokens per example; longer streams are dropped and counted
SFT_FAMILY_CAP = 0.25  # no family above this share of the mix
SFT_ORACLE_SHARE_MAX = (
    0.30  # D-032: programmatic oracle trajectories, at most this share of the final mix
)
SFT_REJECTION_SHARE_MAX = 0.25  # base-model rejection samples: easy, low-information, capped
SFT_LORA = {"r": 16, "alpha": 32, "dropout": 0.0}  # all-linear LoRA, as in the GRPO toy
SFT_HPARAMS = {
    "lr": 1e-4,
    "epochs": 3,
    "per_device_batch": 4,
    "grad_accum": 4,
    "warmup_ratio": 0.03,
}

# GRPO stop rules (eval/PREREGISTRATION.md Phase 1; training/grpo/gates.py)
GRPO_STOP_RULES = {
    "no_signal_share": 0.60, "no_signal_steps": 10,  # share of groups with identical rewards, for N steps in a row
    "refusal_rate_max": 0.20, "refusal_steps": 3,  # `unsupported` on tasks that are supported
    "invalid_rising_steps": 10,  # invalid-action rate rising for N consecutive steps
    "max_gpu_hours": 15.0,
}  # fmt: skip

# --- Frozen agent format (plan T6, D-026) ---
SYSTEM_PROMPT_V1 = "system-v1.txt"
# Pinned once the prompt is frozen: changing it afterwards invalidates teacher data (the cached prefix) and
# every trained model. None = still a DRAFT; teacher runs refuse a draft or a prompt file that no longer matches.
SYSTEM_PROMPT_V1_SHA256: str | None = (
    "56e7d7217b97c122662235cceb96acbf62bd822c6fec25f880035bfff805c724"  # FROZEN 19 Nov 2026 (D-034): any edit invalidates teacher data
)
# Rotation: net clockwise rotation of the displayed picture is measured from content by comparing
# 32x32 thumbnails (training/env/orientation.py). The best of the 4 candidates must beat the runner-up by
# this ratio and absolute grey-level gap, else the measurement is None and the field fails (fail closed).
ORIENTATION_THUMB = 32
ORIENTATION_MAX_RATIO = 0.75
ORIENTATION_MIN_GAP = 4.0

# --- Task splits and who may read them (RULES §4.5; guard in training/taskgen/loader.py) ---
DEV_ONLY_SYSTEM_PREFIXES = ("M1-oracle",)  # D-032 ablation: dev, descriptive, outside Holm
TEST_SPLITS = ("test-iid", "test-compositional", "test-phrasing", "test-real")
# Phase 1 preregistered primary comparison family (eval/PREREGISTRATION.md): (name, system_a, system_b, split);
# reports b - a. Holm runs over exactly these. A split "x+y" pools the tasks of both splits into ONE comparison
# (per-split and per-family differences are descriptive only, outside Holm).
PREREG_COMPARISONS = (
    ("Q2 M1-B2", "B2", "M1", "test-iid"),
    ("Q3 M3-M1", "M1", "M3", "test-iid"),
    ("Q4 M3-X1", "X1", "M3", "test-iid"),
    ("Q5a M3-M1 compositional", "M1", "M3", "test-compositional"),
    ("Q5b M3-M1 phrasing", "M1", "M3", "test-phrasing"),
    ("Q7 M3-B0 real+phrasing", "B0", "M3", "test-real+test-phrasing"),
)
# D-027(b): real clips are split BY CLIP before any task is generated. A clip whose manifest `role` is
# "test-real" is the input of test-real tasks only; taskgen never sees it and CI fails if another split uses it.
CLIP_ROLES = ("taskgen", "test-real")
CLIP_ROLE_DEFAULT = "taskgen"  # synthetic clips and legacy manifest rows without a `role`
SPLIT_PURPOSES = {
    "train": ("train", "toy"),
    "teacher": ("train",),
    "sft": ("train",),
    "grpo": ("train", "toy"),
    "tune": ("dev",),  # reward/prompt/checkpoint tuning
    "dev-eval": ("dev",),
    "test-eval": TEST_SPLITS,  # only the final, preregistered, single run (eval/testlock.py)
}

# Local data (gitignored except manifests and tasks)
DATA_DIR = REPO_ROOT / "data"
CORPUS_DIR = DATA_DIR / "corpus"
JOBS_DIR = DATA_DIR / "jobs"
CORPUS_HUB_REPO = (
    "JustJoyful/ffmpeg-agent-corpus"  # private HF dataset repo (training/corpus/hub.py)
)
LEDGER_PATH = DATA_DIR / "budget-ledger.jsonl"

# Budget (PHASES budgets; RULES §5.1)
BUDGET_LIFETIME_USD = 4.00
BUDGET_PHASE0_PILOT_USD = 0.25

# DeepSeek V4 Flash (teacher + X1 baseline). Prices USD per 1M tokens, supplied by the owner from
# the official pricing page on 2026-11-15. Re-check before every bulk run (RULES §5.3).
DEEPSEEK_PRICES_USD_PER_MTOK = {
    "peak": {"input_cache_hit": 0.006, "input_cache_miss": 0.30, "output": 1.20},
    "off_peak": {"input_cache_hit": 0.003, "input_cache_miss": 0.15, "output": 0.60},
}
DEEPSEEK_PRICES_CHECKED = "2026-11-19"  # unchanged since 15 Nov (page re-read before the bulk run)
DEEPSEEK_MODEL_ID: str | None = "deepseek-flash"  # owner-supplied 2026-11-15
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_API_KEY_ENV = "DEEPSEEK_API_KEY"  # key lives only in the environment (RULES §5.6)
DEEPSEEK_CONCURRENCY_LIMIT = (
    2500  # deepseek-flash account limit per the pricing page of 19 Nov (was 3 on 15 Nov)
)
# What the pricing page said `deepseek-flash` resolves to on 2026-11-19 (the alias moves; recorded in the data card).
DEEPSEEK_MODEL_VERSION_SEEN = "DeepSeek-V4.1-Flash-1017"
TEACHER_WORKERS = 4  # parallel episodes (local ffmpeg is the limit, not the API)
TEACHER_CHUNK = 500  # tasks per bulk chunk; the kept-rate gate is evaluated per chunk
TEACHER_KEPT_GATE = (
    0.82  # preregistered: max(40%, X1_dev 97% - 15 pp); measured on the checker verdict (`passed`)
)
TEACHER_GATE_MIN_N = (
    100  # a chunk cut short by a peak window or the cap is only gated if it has at least this many
)
TEACHER_MAX_OUTPUT_TOKENS = 512
# DeepSeek peak windows, UTC (owner-supplied 17 Nov 2026, in force since 16 Aug 2026): 01:00-04:00 and 06:00-10:00
# are peak; every other hour is off-peak. Bulk teacher runs are refused during peak (RULES 5.3). Windows do not
# wrap midnight. (The 19 Nov page says peak applies Monday-Friday only, excluding Chinese public holidays; we keep
# treating every day as peak-windowed: safer, and the billing guard always charges peak rates.) Re-check the official pricing page before each bulk run: DeepSeek changed these several times.
DEEPSEEK_PEAK_UTC: tuple[tuple[time, time], ...] = (
    (time(1, 0), time(4, 0)),
    (time(6, 0), time(10, 0)),
)
# DeepSeek Open Platform ToS (release 22 Apr 2026, effective 29 Apr 2026) §4.2(3): outputs may be used for "training other
# models (such as model distillation)". Snapshot taken 2026-11-19 by training/teacher/fetch_terms.py (raw HTML, HTTP
# status, fetch time and sha256 per page in terms.json); the owner read §4.2 the same day (confirmation in terms.json).
TEACHER_TERMS_DIR = REPO_ROOT / "training" / "teacher" / "terms" / "2026-11-19"
TEACHER_TERMS_URL: str | None = (
    "https://cdn.deepseek.com/policies/en-US/deepseek-open-platform-terms-of-service.html"
)
# sha256 over the per-page sha256 digests of terms.json (fetch_terms.snapshot_sha256); datacard.py re-checks it.
TEACHER_TERMS_SNAPSHOT_SHA256: str | None = (
    "e700b82e5f9170d9ac20b0dc1424b718aed76c1ccc6d6b02cb6312f4beab22de"
)

# GRPO token stream (Qwen3 ChatML, non-thinking). Inserted after each model turn; masked from the
# loss. The empty think block matches what enable_thinking=False puts in the generation prompt.
QWEN3_OBSERVATION_TEMPLATE = (
    "\n<|im_start|>user\n{obs}<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n"
)

# GRPO reward v1 DRAFT: ARCHITECTURE §7.4 initial weights (tune on dev only, RULES §4.5). Terms are
# computed in training/grpo/telemetry.py; `invalid` is a per-action penalty, capped per episode.
# 20 Nov 2026 (owner, dev-only change): an `unsupported` task is graded on the action alone (refused, nothing run).
# `nearest_supported` is descriptive and is not scored by the eval (loop.score) or the reward (telemetry.grpo_reward);
# tests/env/test_loop.py pins that the outcome is the same for any label. See eval/PREREGISTRATION.md, DECISIONS.
REWARD_SCORES_NEAREST_SUPPORTED = False
REWARD_WEIGHTS = {
    "pass": 1.0,
    "partial": 0.3,
    "spec_acc": 0.2,
    "efficiency": 0.1,
    "clarify": 0.5,
    "invalid": -0.5,
}
REWARD_INVALID_CAP = 4

# Pre-GRPO task filter (T6): keep tasks whose pass rate over K samples is inside the band.
PASS_RATE_BAND = (0.2, 0.8)  # inclusive; tasks the model always/never solves give no GRPO signal
PASS_RATE_SAMPLES = 8
PASS_RATE_ALLOWED_SPLITS = ("train", "toy")  # never filter on dev/test tasks (RULES §4.5)

# GRPO telemetry (T6): hand-inspect the top-reward trajectories every N steps (reward-hacking guard)
TELEMETRY_SPOTCHECK_EVERY = 10
TELEMETRY_SPOTCHECK_TOP_K = 3

# Statistics (EVALUATION §5)
BOOTSTRAP_RESAMPLES = 10_000
BOOTSTRAP_SEED = 20261115

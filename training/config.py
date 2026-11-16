"""Single config module for the Python harness (RULES §6.2). Every tunable lives here."""

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PROTOCOL_DIR = REPO_ROOT / "packages" / "protocol"
PROTOCOL_VERSION = "0.2.0"  # ARCH §12: shared by web, helper, training

# Binaries (ARCH §3.5): resolved from PATH, always invoked with argument lists.
FFMPEG_BIN = "ffmpeg"
FFPROBE_BIN = "ffprobe"

# Per-run limits (RULES §1.4)
RUN_TIMEOUT_S = 120
MAX_OUTPUT_BYTES = 200 * 2**20
# GRPO rollouts run thousands of FFmpeg jobs on small clips: a hung or runaway command must not burn GPU hours.
ROLLOUT_RUN_TIMEOUT_S = 20
ROLLOUT_MAX_OUTPUT_BYTES = 50 * 2**20
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
OFFSET_PACKET_WINDOW = 16
OFFSET_TOLERANCE_MS = 40.0
# Rotation: net clockwise rotation of the displayed picture is measured from content by comparing
# 32x32 thumbnails (training/env/orientation.py). The best of the 4 candidates must beat the runner-up by
# this ratio and absolute grey-level gap, else the measurement is None and the field fails (fail closed).
ORIENTATION_THUMB = 32
ORIENTATION_MAX_RATIO = 0.75
ORIENTATION_MIN_GAP = 4.0

# --- Task splits and who may read them (RULES §4.5; guard in training/taskgen/loader.py) ---
TEST_SPLITS = ("test-iid", "test-compositional", "test-phrasing", "test-real")
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
DEEPSEEK_PRICES_CHECKED = "2026-11-15"
DEEPSEEK_MODEL_ID: str | None = "deepseek-flash"  # owner-supplied 2026-11-15
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_API_KEY_ENV = "DEEPSEEK_API_KEY"  # key lives only in the environment (RULES §5.6)
DEEPSEEK_CONCURRENCY_LIMIT = 3  # account limit per pricing page; runners are sequential anyway
TEACHER_MAX_OUTPUT_TOKENS = 512

# GRPO token stream (Qwen3 ChatML, non-thinking). Inserted after each model turn; masked from the
# loss. The empty think block matches what enable_thinking=False puts in the generation prompt.
QWEN3_OBSERVATION_TEMPLATE = (
    "\n<|im_start|>user\n{obs}<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n"
)

# GRPO reward v1 DRAFT: ARCHITECTURE §7.4 initial weights (tune on dev only, RULES §4.5). Terms are
# computed in training/grpo/telemetry.py; `invalid` is a per-action penalty, capped per episode.
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

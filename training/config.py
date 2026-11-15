"""Single config module for the Python harness (RULES §6.2). Every tunable lives here."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PROTOCOL_DIR = REPO_ROOT / "packages" / "protocol"
PROTOCOL_VERSION = "0.1.0"  # ARCH §12: shared by web, helper, training

# Binaries (ARCH §3.5): resolved from PATH, always invoked with argument lists.
FFMPEG_BIN = "ffmpeg"
FFPROBE_BIN = "ffprobe"

# Per-run limits (RULES §1.4)
RUN_TIMEOUT_S = 120
MAX_OUTPUT_BYTES = 200 * 2**20
STDERR_TAIL_CHARS = 2000

# Agent loop budget (ARCH §3.1)
MAX_RUNS_PER_JOB = 4
MAX_TURNS_PER_JOB = 8
MAX_ASK_USER = 1

# Checker tolerances (checker v0)
DEFAULT_TIME_TOLERANCE_S = 0.1  # ARCH §3.2 example tolerance
FPS_REL_TOLERANCE = 0.01
FRAME_COUNT_TOLERANCE = 1
LOUDNESS_TOLERANCE_LU = 2.0  # single-pass loudnorm lands within ~1-2 LU of target
OFFSET_PACKET_WINDOW = 16  # packets per stream inspected for the offset (B-frame safe)
OFFSET_TOLERANCE_MS = 40.0  # covers AAC encoder priming (1024 samples = 21 ms at 48 kHz)

# Local data (gitignored except manifests and tasks)
DATA_DIR = REPO_ROOT / "data"
CORPUS_DIR = DATA_DIR / "corpus"
JOBS_DIR = DATA_DIR / "jobs"
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

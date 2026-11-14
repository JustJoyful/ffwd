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
OFFSET_TOLERANCE_MS = 40.0  # covers AAC encoder priming (1024 samples = 21 ms at 48 kHz)

# Local data (gitignored except manifests and tasks)
DATA_DIR = REPO_ROOT / "data"
CORPUS_DIR = DATA_DIR / "corpus"
JOBS_DIR = DATA_DIR / "jobs"
LEDGER_PATH = DATA_DIR / "budget-ledger.jsonl"

# Budget (PHASES budgets; RULES §5.1)
BUDGET_LIFETIME_USD = 4.00
BUDGET_PHASE0_PILOT_USD = 0.25

# Statistics (EVALUATION §5)
BOOTSTRAP_RESAMPLES = 10_000
BOOTSTRAP_SEED = 20261115

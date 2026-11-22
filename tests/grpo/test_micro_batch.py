import pytest

pytest.importorskip("trl")
from trl import GRPOConfig  # noqa: E402


def cfg(micro: int, prompts: int = 8, gens: int = 8) -> GRPOConfig:
    # the same expression main_run.py uses for the two fields
    return GRPOConfig(
        output_dir="/tmp/unused-grpo-cfg",
        report_to="none",
        num_generations=gens,
        per_device_train_batch_size=micro,
        gradient_accumulation_steps=prompts * gens // micro,
        bf16=False,
    )


def test_a_smaller_micro_batch_keeps_the_generation_batch_and_so_the_8_prompts_x_8_samples_per_step():
    """The step-59 OOM fix must not change what one optimizer step learns from (22 Nov 2026)."""
    a, b = cfg(8), cfg(4)
    assert a.generation_batch_size == b.generation_batch_size == 64
    assert a.steps_per_generation == 8 and b.steps_per_generation == 16

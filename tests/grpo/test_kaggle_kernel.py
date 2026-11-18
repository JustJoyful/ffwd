def test_pinned_ffmpeg_is_installed_before_any_training_step_and_never_via_apt():
    from training.grpo import kaggle_kernel

    s = kaggle_kernel.SCRIPT
    assert "apt-get" not in s and "apt install" not in s and "ffmpeg_pin install" in s
    assert s.index("ffmpeg_pin install") < s.index(
        "toy_spike"
    )  # the checker fails closed without the pin

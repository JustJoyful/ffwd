import pytest

torch = pytest.importorskip("torch")
transformers = pytest.importorskip("transformers")


@pytest.fixture(scope="module")
def stub():
    from transformers import AutoModelForCausalLM, AutoTokenizer

    try:
        tok = AutoTokenizer.from_pretrained("Qwen/Qwen3-0.6B", local_files_only=True)
        model = AutoModelForCausalLM.from_pretrained(
            "Qwen/Qwen3-0.6B", local_files_only=True, dtype=torch.float32
        )
    except OSError:
        pytest.skip("Qwen3-0.6B not in the local HF cache")
    acc = type("A", (), {"unwrap_model": staticmethod(lambda m: m)})()
    return type("T", (), {"accelerator": acc, "model": model, "processing_class": tok})()


def test_batched_greedy_generation_equals_one_at_a_time_despite_padding(stub):
    from training.grpo.hf_batch import hf_batch_generator_for

    gen = hf_batch_generator_for(temperature=0.0)(stub)
    tok = stub.processing_class
    a = tok.encode(
        "<|im_start|>user\nsay hi<|im_end|>\n<|im_start|>assistant\n", add_special_tokens=False
    )
    b = tok.encode(
        "<|im_start|>user\nwrite one short sentence about the sea and the sky<|im_end|>\n<|im_start|>assistant\n",
        add_special_tokens=False,
    )
    assert len(a) != len(b)  # different lengths force padding
    together = gen([(a, 8), (b, 8)])
    alone = [gen([(a, 8)])[0], gen([(b, 8)])[0]]
    assert [t for t, _ in together] == [t for t, _ in alone]
    assert all(len(t) == len(lp) and len(t) <= 8 for t, lp in together)
    assert all(lp <= 0 for _, lps in together for lp in lps)

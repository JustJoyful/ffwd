"""Batched HF generation for lockstep rollouts. torch is imported lazily so the rest of training/ stays CPU-light."""

import gc

from training.grpo.lockstep import BatchGenerate


def run_chunks(reqs, one_chunk, max_batch: int, is_oom, on_oom=lambda: None):
    """Decode `reqs` in chunks of at most `max_batch`. A chunk that runs out of GPU memory is split in half and retried
    (a lone request that still does not fit raises): the 20 Nov 2026 control run died of one OOM at step 2 after hours of
    setup, and `output_scores=True` keeps the full-vocabulary scores of every new token of every sequence in the chunk.
    """

    def attempt(chunk):
        try:
            return one_chunk(chunk)
        except Exception as e:  # noqa: BLE001
            if not is_oom(e) or len(chunk) == 1:
                raise
        # The retry runs OUTSIDE the except block on purpose: while a handler is active the exception's traceback keeps the
        # failed attempt's frames, and the CUDA tensors they hold, alive, so a retry inside it starts with the failed batch's
        # memory still allocated and fails again (the main run died of exactly that at step 38, 21 Nov 2026).
        on_oom()
        half = len(chunk) // 2
        return attempt(chunk[:half]) + attempt(chunk[half:])

    out = []
    for i in range(0, len(reqs), max_batch):
        out += attempt(reqs[i : i + max_batch])
    return out


def hf_batch_generator_for(temperature: float, max_batch: int = 8):
    def factory(trainer) -> BatchGenerate:
        import torch  # noqa: PLC0415

        model = trainer.accelerator.unwrap_model(trainer.model)
        tok = trainer.processing_class
        im_end = tok.convert_tokens_to_ids("<|im_end|>")
        pad = tok.pad_token_id if tok.pad_token_id is not None else im_end

        def one_chunk(reqs):
            longest = max(len(ids) for ids, _ in reqs)
            max_new = max(m for _, m in reqs)
            x = torch.full((len(reqs), longest), pad, dtype=torch.long)
            mask = torch.zeros((len(reqs), longest), dtype=torch.long)
            for i, (ids, _) in enumerate(
                reqs
            ):  # left padding: generation continues from the last real token
                x[i, longest - len(ids) :] = torch.tensor(ids)
                mask[i, longest - len(ids) :] = 1
            was_training = model.training
            model.eval()
            with torch.no_grad():
                out = model.generate(
                    input_ids=x.to(model.device),
                    attention_mask=mask.to(model.device),
                    max_new_tokens=max_new,
                    do_sample=temperature > 0,
                    **(
                        {"temperature": temperature, "top_p": 1.0, "top_k": 0}
                        if temperature > 0
                        else {}
                    ),
                    eos_token_id=im_end,
                    pad_token_id=pad,
                    output_scores=True,
                    return_dict_in_generate=True,
                )
            if was_training:
                model.train()
            results = []
            for i, (_, limit) in enumerate(reqs):
                new = out.sequences[i, longest:].tolist()
                if im_end in new:
                    new = new[: new.index(im_end) + 1]
                new = new[:limit]
                lps = [
                    torch.log_softmax(out.scores[t][i].float(), -1)[tok_id].item()
                    for t, tok_id in enumerate(new)
                ]
                results.append((new, lps))
            del out  # the per-token full-vocabulary scores are the big allocation: release them before the next chunk
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            return results

        def release():
            gc.collect()  # drop reference cycles that still hold CUDA tensors, then return the blocks to the driver
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

        def generate_batch(reqs):
            release()  # the training step before this call leaves transient allocations behind
            return run_chunks(
                reqs,
                one_chunk,
                max_batch,
                is_oom=lambda e: isinstance(e, torch.OutOfMemoryError),
                on_oom=release,
            )

        return generate_batch

    return factory

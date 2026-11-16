"""Batched HF generation for lockstep rollouts. torch is imported lazily so the rest of training/ stays CPU-light."""

from training.grpo.lockstep import BatchGenerate


def hf_batch_generator_for(temperature: float, max_batch: int = 32):
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
            return results

        def generate_batch(reqs):
            out = []
            for i in range(0, len(reqs), max_batch):
                out += one_chunk(reqs[i : i + max_batch])
            return out

        return generate_batch

    return factory

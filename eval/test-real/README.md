# test-real: your clips and your requests

test-real is the one split that measures the real thing: **real clips, requests you wrote yourself**. About 10 clips and about 100 requests (EVALUATION.md §2; the 100 is also what the preregistration's power table assumes). It is run once (gate G4) and never used for training, prompting, tuning or checkpoint selection.

## 1. Add clips (the exact commands)

Run from the repo root. One command per clip; the file is copied into `data/corpus/`, its sha256 and probe are recorded, and the licence is required (an empty one is refused).

```
uv run python -m training.corpus.add_clip ~/path/to/clip.mp4 --id <id> \
    --licence "own recording; rights held by the owner; evaluation use only" \
    --source "<device>, <where/when>" --role test-real
```

For a volunteer's clip (you need their written permission first; RULES §5.5):

```
uv run python -m training.corpus.add_clip ~/path/to/clip.mp4 --id <id> \
    --licence "volunteer <initials>: written permission <date>; evaluation use only" \
    --source "<device>, <where/when>" --role test-real
```

* `--role test-real` is mandatory (there is no default). It holds the clip out of every generated split; CI fails if a generated task uses it. Do **not** use `--role taskgen` for these clips.
* `--id` must match `^[a-z][a-z0-9_]{0,15}$` (lowercase, digits, underscore, at most 16 characters) and be unique.
* Then commit only the manifest (media stays untracked): `git add data/corpus/manifest.json && git commit -m "data(corpus): register test-real clip <id>"` and run `uv run pytest tests/taskgen/test_clip_roles.py -q`.
* test-real clips are **never** uploaded to the training corpus repo (`push_corpus` skips them). Keep the originals safe: they cannot be regenerated.
* Adding a test-real clip does not change the task-generation corpus hash, so the existing splits stay valid.

Already registered as test-real (3 own recordings):

| id | what it is |
|---|---|
| `hevc_phone` | HEVC 3840x2160, 60 fps, stored rotated 90 (portrait), 14.2 s, 125 MB, AAC stereo |
| `screen_rec` | screen recording, H.264 1920x1080, 60 fps, 12.1 s, 2.5 MB, audio track present but silent |
| `wa_compressed` | WhatsApp-compressed portrait clip, H.264 478x850, ~60 fps, 14.2 s, 3.4 MB |

Which clips would add the most: a **true variable-frame-rate phone clip** (README §limitations says there is none), a clip with **no audio track**, a **long clip** (over a minute), a **quiet or noisy audio** clip, a **4:3 or old-camera** clip, an **MKV/MOV/AVI** clip. Keep each clip short enough to run in seconds.

## 2. Write requests: `requests-template.csv`

One row per request. Columns:

| column | what to put |
|---|---|
| `clip_id` | the `--id` of a clip registered as test-real (several rows per clip, about 10 each; a request that uses two clips: put both ids separated by `;`) |
| `request` | exactly what you would type to the app, in your own words |
| `expected_output` | the result you want, **in plain words, concrete enough to check**: container/format, length or the part to keep, resolution/orientation, with or without sound, size limit. I turn this into the machine-checked spec and show it to you for approval |
| `kind` | blank (normal), `ambiguous` (a person would have to ask a question first) or `unsupported` (FFmpeg cannot do it: say what the closest thing is in `expected_output`) |

Rules that keep the numbers meaningful:

1. **Write them yourself, by hand, from your own habits.** Do not copy from the dev/train files, do not paraphrase the generator's styles, and do not ask an LLM to write them (that would make test-real resemble the training phrasing and hide exactly the gap this split measures).
2. Make them messy and real: typos, missing details, "for my viva tomorrow", "it won't play on my phone". Mix terse and wordy.
3. Mix difficulty: about half single chores, the rest two or three chores in one request ("trim to the first 10 s, drop the sound, make it 720p").
3b. **At least about 30 of the 100 requests must be ones where a stream copy (no re-encoding) is a correct answer** ("copy-eligible"). They are what the preregistered efficiency endpoint Q3a is measured on, and with fewer the real-world result has no power. Cover the lossless-possible chores: trimming from the start (or a trim whose cut a stream copy can do), changing the container (remux, e.g. mkv to mp4), muting (dropping the audio and keeping the video as is), rotating by metadata without re-encoding, extracting the audio as is. Mix them: some where you say so ("without re-encoding", "keep the quality"), and some where you just ask for the chore and say nothing about quality; the second kind is where a model that re-encodes needlessly shows up. Do not add a request only because it is copy-eligible: it must still be something you would really ask for.
4. About 10 of the 100 should be `ambiguous` or `unsupported`; these are part of the denominator (the system should ask or refuse, and is graded on doing that).
5. Do not write the expected output after seeing what M1 does. Write the CSV first and do not run any system on it.
6. Do not edit a row after the set is frozen. At freeze I compute the sha256 of the task file and record it in the preregistration before anything is run on it.

Illustrative rows (**examples only, not part of the set; do not copy them**):

```
clip_id,request,expected_output,kind
hevc_phone,"too big to send on whatsapp, need it under 16 mb",an mp4 under 16 MB that still looks fine and still has sound,
screen_rec,"cut the first 3 seconds, they're just me opening the window",same recording without its first 3 seconds,
wa_compressed,"blur the background but keep me sharp",nothing can be run: it needs a person-segmentation model; the closest supported thing is a plain blur of the whole frame,unsupported
```

## 3. What happens next (not done yet)

1. You fill the CSV (and register the clips). Nothing runs on it.
2. I convert it to test-real tasks with gold specs, **show you every expected-output-to-spec translation for approval**, and execute a reference solution against each gold spec (a task whose reference does not pass is a task bug, fixed with you, never silently dropped).
3. We freeze the file (sha256 into the preregistration), then the preregistration goes FINAL, then G4: one run of every system, one time.

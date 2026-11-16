# Phase 2 bench: how to run it on another machine

1. Make the clips (needs ffmpeg + uv; ~1 GB, a few minutes) and copy `data/bench/*.mov|*.mp4` to the target machine:
   `uv run python -m training.corpus.make_bench data/bench`
2. Open https://ffmpeg-agent-spike.pages.dev/ in Chrome/Edge. Pick the four files under "Phase 2 bench", choose the model,
   type a machine label (e.g. `laptop-igpu-intel`), click **Run full bench**. The page warns instead of refusing on an
   integrated GPU (policy "warn", the default; `?gpuPolicy=refuse` for the strict policy).
3. When the status says `bench: done`, click **Download results JSON** and put the file in this folder.
4. If the tab crashes (the 500 MB or 4K step can), reopen the page: results so far are restored and the step that died is
   recorded as `previous_tab_crash`. Also note the OS-level peak memory from Task Manager/htop: the in-page memory API is unreliable (see summary.md).
5. Optional native comparison on the same machine: `uv run python -m eval.native_bench data/bench <this-folder>/native-<label>.json`.
Close other heavy tabs first; on a 16 GB machine keep Brave/Chrome tabs to a minimum.

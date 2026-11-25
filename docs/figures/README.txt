Figures for the root README.md. Rebuild them with:

    uv run --frozen --with matplotlib==3.11.2 python docs/figures/make_figures.py

matplotlib is not in the project environment (no lockfile change): `uv run --with` installs it for that one run only.
Inputs are the tracked result files under reports/ (listed in the script's docstring) plus data.json, which holds the
few counts that exist only in markdown reports, with the source path next to each value.

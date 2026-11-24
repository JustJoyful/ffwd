"""ffmpeg-agent command line (Phase 1): `ffmpeg-agent "<request>" file.mp4`.

shortcut: imports the training harness (training.env) directly instead of a shared package; extract a core
package when the Phase 3 helper needs the same loop (the harness is already torch-free).
"""

__version__ = "1.0.0"  # the one place the CLI version lives; a release manifest's min_app_version is compared with it

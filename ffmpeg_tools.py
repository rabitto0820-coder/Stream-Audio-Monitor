"""Locate FFmpeg for a portable Stream Audio Monitor installation."""

import os
from pathlib import Path
import shutil


def find_ffmpeg():
    """Prefer an FFmpeg bundled next to SAM, then fall back to Windows PATH."""
    executable = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
    app_folder = Path(__file__).resolve().parent
    bundled_paths = (
        app_folder / "tools" / "ffmpeg" / "bin" / executable,
        app_folder / "tools" / executable,
    )

    for candidate in bundled_paths:
        if candidate.is_file():
            return str(candidate)

    return shutil.which("ffmpeg")

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


def describe_ffmpeg_source():
    """Return a concise label explaining which FFmpeg SAM will use."""
    ffmpeg = find_ffmpeg()
    if ffmpeg is None:
        return "FFmpeg not found"

    app_folder = Path(__file__).resolve().parent
    bundled_folder = app_folder / "tools"
    try:
        Path(ffmpeg).resolve().relative_to(bundled_folder.resolve())
    except ValueError:
        return f"System FFmpeg: {ffmpeg}"

    return f"Bundled FFmpeg: {ffmpeg}"

"""Application identity and environment details for support reports."""

import platform
import sys

import sounddevice as sd


APP_NAME = "Stream Audio Monitor"
APP_VERSION = "1.2"


def support_environment_text():
    """Return compact runtime information safe to include in a support report."""
    return (
        f"SAM version: {APP_VERSION}\n"
        f"Windows: {platform.platform()}\n"
        f"Python: {platform.python_version()}\n"
        f"sounddevice: {getattr(sd, '__version__', 'unknown')}\n"
        f"Python executable: {sys.executable}"
    )

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


def saved_audio_setup_text(settings):
    """Return the last saved audio setup without exposing unrelated settings."""
    settings = settings if isinstance(settings, dict) else {}
    return (
        f"Input device: {_device_description(settings.get('input_device'))}\n"
        f"Output device: {_device_description(settings.get('output_device'))}\n"
        f"Sample rate: {settings.get('samplerate', '(not saved)')}\n"
        f"Buffer: {settings.get('blocksize', '(not saved)')}"
    )


def _device_description(device_index):
    """Show both the saved PortAudio index and its current device name."""
    if device_index is None:
        return "(not saved)"

    try:
        device_index = int(device_index)
        device = sd.query_devices(device_index)
        name = device.get("name", "unknown device")
        return f"{device_index}: {name}"
    except Exception:
        return f"{device_index} (not currently available)"

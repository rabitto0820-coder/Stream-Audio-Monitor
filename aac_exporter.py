"""Create an audible AAC encode/decode preview WAV using FFmpeg."""

from pathlib import Path
import subprocess
import tempfile

from ffmpeg_tools import find_ffmpeg


def export_aac_preview(
    source_path,
    destination_path,
    bitrate_kbps=128,
    playback_gain_db=0.0,
):
    """Create a 24-bit AAC preview WAV with optional playback gain."""
    ffmpeg = find_ffmpeg()
    if ffmpeg is None:
        raise RuntimeError("FFmpeg was not found. Install FFmpeg and restart.")

    source = Path(source_path)
    destination = Path(destination_path)

    if not source.is_file():
        raise ValueError("The source WAV file was not found.")

    if destination.suffix.lower() != ".wav":
        destination = destination.with_suffix(".wav")

    destination.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="stream_audio_monitor_") as folder:
        encoded = Path(folder) / "aac_preview.aac"

        _run_ffmpeg([
            ffmpeg,
            "-y",
            "-hide_banner",
            "-loglevel", "error",
            "-i", str(source),
            "-c:a", "aac",
            "-b:a", f"{int(bitrate_kbps)}k",
            "-f", "adts",
            str(encoded),
        ])

        decode_command = [
            ffmpeg,
            "-y",
            "-hide_banner",
            "-loglevel", "error",
            "-f", "aac",
            "-i", str(encoded),
        ]

        if playback_gain_db != 0.0:
            decode_command.extend([
                "-af",
                f"volume={float(playback_gain_db):.3f}dB",
            ])

        decode_command.extend([
            "-c:a", "pcm_s24le",
            str(destination),
        ])
        _run_ffmpeg(decode_command)

    return destination


def _run_ffmpeg(command):
    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=120,
    )

    if result.returncode != 0:
        message = result.stderr.strip() or "FFmpeg processing failed."
        raise RuntimeError(message)

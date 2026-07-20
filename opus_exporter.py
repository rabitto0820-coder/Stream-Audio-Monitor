"""Create an audible Opus encode/decode preview WAV using FFmpeg."""

from pathlib import Path
import shutil
import subprocess
import tempfile


def export_opus_preview(
    source_path,
    destination_path,
    bitrate_kbps=128,
    playback_gain_db=0.0,
):
    """Create a 24-bit Opus preview WAV with optional playback gain."""
    ffmpeg = shutil.which("ffmpeg")
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
        encoded = Path(folder) / "youtube_preview.opus.ogg"

        _run_ffmpeg([
            ffmpeg,
            "-y",
            "-hide_banner",
            "-loglevel", "error",
            "-i", str(source),
            "-c:a", "libopus",
            "-application", "audio",
            "-b:a", f"{int(bitrate_kbps)}k",
            str(encoded),
        ])

        decode_command = [
            ffmpeg,
            "-y",
            "-hide_banner",
            "-loglevel", "error",
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


def export_youtube_ab_previews(
    source_path,
    destination_folder,
    bitrate_kbps=128,
    playback_gain_db=0.0,
):
    """Create matching Opus-only and YouTube-volume preview WAV files."""
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise RuntimeError("FFmpeg was not found. Install FFmpeg and restart.")

    source = Path(source_path)
    folder = Path(destination_folder)

    if not source.is_file():
        raise ValueError("The source WAV file was not found.")

    if not folder.is_dir():
        raise ValueError("The selected output folder was not found.")

    bitrate = int(bitrate_kbps)
    opus_path, youtube_path = _available_ab_paths(source, folder, bitrate)

    with tempfile.TemporaryDirectory(prefix="stream_audio_monitor_") as temp_folder:
        encoded = Path(temp_folder) / "youtube_preview.opus.ogg"

        _run_ffmpeg([
            ffmpeg,
            "-y",
            "-hide_banner",
            "-loglevel", "error",
            "-i", str(source),
            "-c:a", "libopus",
            "-application", "audio",
            "-b:a", f"{bitrate}k",
            str(encoded),
        ])

        _decode_preview(ffmpeg, encoded, opus_path)
        _decode_preview(ffmpeg, encoded, youtube_path, playback_gain_db)

    return {
        "opus": opus_path,
        "youtube": youtube_path,
    }


def _available_ab_paths(source, folder, bitrate_kbps):
    """Return unused matching output names without overwriting old previews."""
    base = f"{source.stem}_opus_{bitrate_kbps}k"
    index = 0

    while True:
        suffix = "" if index == 0 else f"_{index:02d}"
        opus_path = folder / f"{base}{suffix}.wav"
        youtube_path = folder / f"{base}_youtube{suffix}.wav"

        if not opus_path.exists() and not youtube_path.exists():
            return opus_path, youtube_path

        index += 1


def _decode_preview(ffmpeg, encoded_path, destination_path, playback_gain_db=0.0):
    """Decode an already encoded Opus file to a 24-bit WAV preview."""
    command = [
        ffmpeg,
        "-y",
        "-hide_banner",
        "-loglevel", "error",
        "-i", str(encoded_path),
    ]

    if playback_gain_db != 0.0:
        command.extend([
            "-af",
            f"volume={float(playback_gain_db):.3f}dB",
        ])

    command.extend([
        "-c:a", "pcm_s24le",
        str(destination_path),
    ])
    _run_ffmpeg(command)


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

"""Create YouTube-volume Opus and AAC listening-preview WAV files."""

from pathlib import Path

from aac_exporter import export_aac_preview
from opus_exporter import export_opus_preview


def export_codec_pack(
    source_path,
    destination_folder,
    opus_bitrate_kbps=128,
    aac_bitrate_kbps=128,
    youtube_gain_db=0.0,
):
    """Create YouTube-volume previews for Opus and AAC."""
    source = Path(source_path)
    folder = Path(destination_folder)

    if not source.is_file():
        raise ValueError("The source WAV file was not found.")
    if not folder.is_dir():
        raise ValueError("The selected output folder was not found.")

    paths = _available_pack_paths(
        source,
        folder,
        int(opus_bitrate_kbps),
        int(aac_bitrate_kbps),
    )

    export_opus_preview(
        source,
        paths["opus_youtube"],
        bitrate_kbps=opus_bitrate_kbps,
        playback_gain_db=youtube_gain_db,
    )
    export_aac_preview(
        source,
        paths["aac_youtube"],
        bitrate_kbps=aac_bitrate_kbps,
        playback_gain_db=youtube_gain_db,
    )

    return paths


def _available_pack_paths(source, folder, opus_bitrate_kbps, aac_bitrate_kbps):
    """Choose one shared unused filename suffix for all pack files."""
    index = 0

    while True:
        suffix = "" if index == 0 else f"_{index:02d}"
        paths = {
            "opus_youtube": folder / (
                f"{source.stem}_opus_{opus_bitrate_kbps}k_youtube{suffix}.wav"
            ),
            "aac_youtube": folder / (
                f"{source.stem}_aac_{aac_bitrate_kbps}k_youtube{suffix}.wav"
            ),
        }

        if not any(path.exists() for path in paths.values()):
            return paths

        index += 1

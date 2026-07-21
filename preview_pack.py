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
    analysis=None,
    youtube_target_lufs=-14.0,
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

    _write_youtube_report(
        paths["report"],
        source,
        paths,
        opus_bitrate_kbps,
        aac_bitrate_kbps,
        youtube_gain_db,
        analysis,
        youtube_target_lufs,
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
            "report": folder / (
                f"{source.stem}_youtube_preview_report{suffix}.txt"
            ),
        }

        if not any(path.exists() for path in paths.values()):
            return paths

        index += 1


def _write_youtube_report(
    report_path,
    source,
    paths,
    opus_bitrate_kbps,
    aac_bitrate_kbps,
    youtube_gain_db,
    analysis,
    youtube_target_lufs,
):
    """Write the measurements used to create one codec preview pack."""
    analysis = analysis or {}
    volume_percent = 100.0 * (10.0 ** (youtube_gain_db / 20.0))
    lines = [
        "Stream Audio Monitor — YouTube Preview Report",
        "",
        f"Source WAV: {source}",
        f"YouTube reference: {float(youtube_target_lufs):.1f} LUFS",
        f"YouTube playback gain: {float(youtube_gain_db):+.1f} dB",
        f"YouTube normalized volume: {volume_percent:.0f}%",
        "",
        "Source analysis",
        f"Integrated LUFS: {float(analysis.get('lufs_i', -70.0)):.1f}",
        f"Estimated True Peak: {float(analysis.get('true_peak_db', -60.0)):.1f} dBTP",
        f"Sample Peak: {float(analysis.get('peak_db', -60.0)):.1f} dBFS",
        "",
        "Created preview files",
        f"Opus {int(opus_bitrate_kbps)} kbps + YouTube volume: {paths['opus_youtube']}",
        f"AAC {int(aac_bitrate_kbps)} kbps + YouTube volume: {paths['aac_youtube']}",
        "",
        "This report is a practical YouTube preview estimate, not an official YouTube measurement.",
    ]
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

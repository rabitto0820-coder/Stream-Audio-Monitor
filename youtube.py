"""Real-time YouTube-style Opus preview.

FFmpeg's libopus encoder is used when it is installed. Audio is collected in
short blocks on the audio thread, encoded and decoded on a worker thread, then
returned to the monitor with a small fixed delay. A filter-only preview is
kept as a fallback for systems that do not have FFmpeg.
"""

from concurrent.futures import ThreadPoolExecutor
import shutil
import subprocess

import numpy as np
from scipy.signal import butter, sosfilt


class YouTubeOpusPreview:
    """Stateful Opus encode/decode preview suitable for real-time monitoring."""

    def __init__(self, sample_rate=48000, channels=2, bitrate_kbps=128):
        self.sample_rate = int(sample_rate)
        self.channels = int(channels)
        self.bitrate_kbps = int(bitrate_kbps)

        self._executor = ThreadPoolExecutor(max_workers=1)
        self._ffmpeg_path = shutil.which("ffmpeg")
        self.real_codec_available = self._ffmpeg_path is not None

        self._future = None
        self._sos = None
        self._state = None

        self.reset()

    def configure(self, sample_rate, channels=2, bitrate_kbps=None):
        self.sample_rate = int(sample_rate)
        self.channels = int(channels)

        if bitrate_kbps is not None:
            self.bitrate_kbps = int(bitrate_kbps)

        self.reset()

    def reset(self):
        """Reset codec buffers and the fallback filter state."""
        self._future = None

        self._input_buffer = np.empty(
            (0, self.channels),
            dtype=np.float32
        )

        self._output_buffer = np.empty(
            (0, self.channels),
            dtype=np.float32
        )

        self._chunk_size = max(
            1,
            round(self.sample_rate * 0.25)
        )

        cutoff = self._cutoff_frequency()
        nyquist = self.sample_rate / 2.0

        if cutoff >= nyquist * 0.99:
            self._sos = None
            self._state = None
            return

        self._sos = butter(
            6,
            cutoff / nyquist,
            btype="low",
            output="sos",
        )

        self._state = np.zeros(
            (self._sos.shape[0], 2, self.channels)
        )

    def process(self, data):
        """Encode/decode audio through libopus, or use the fallback preview."""
        if data.ndim != 2 or data.shape[1] != self.channels:
            self.configure(self.sample_rate, data.shape[1])

        if self.real_codec_available:
            return self._process_real_codec(data)

        return self._process_fallback(data)

    def _process_real_codec(self, data):
        self._collect_completed_chunk()

        input_data = np.asarray(
            data,
            dtype=np.float32
        )

        self._input_buffer = np.vstack((
            self._input_buffer,
            input_data
        ))

        if (
            self._future is None
            and len(self._input_buffer) >= self._chunk_size
        ):
            chunk = self._input_buffer[
                :self._chunk_size
            ].copy()

            self._input_buffer = self._input_buffer[
                self._chunk_size:
            ]

            self._future = self._executor.submit(
                self._opus_round_trip,
                chunk,
            )

        frames = len(input_data)

        if len(self._output_buffer) >= frames:
            output = self._output_buffer[:frames]

            self._output_buffer = self._output_buffer[
                frames:
            ]

            return output.astype(
                data.dtype,
                copy=False
            )

        # Maintain codec delay instead of mixing dry and compressed audio.
        available = self._output_buffer

        self._output_buffer = np.empty(
            (0, self.channels),
            dtype=np.float32
        )

        silence = np.zeros(
            (frames - len(available), self.channels),
            dtype=np.float32
        )

        output = np.vstack((
            available,
            silence
        ))

        return output.astype(
            data.dtype,
            copy=False
        )

    def _collect_completed_chunk(self):
        if self._future is None or not self._future.done():
            return

        future = self._future
        self._future = None

        try:
            decoded = future.result()

        except (
            OSError,
            subprocess.SubprocessError,
            ValueError,
        ) as error:
            print(f"YouTube Opus Preview fallback: {error}")
            self.real_codec_available = False
            return

        self._output_buffer = np.vstack((
            self._output_buffer,
            decoded
        ))

    def _opus_round_trip(self, data):
        raw_audio = np.ascontiguousarray(
            data,
            dtype=np.float32
        ).tobytes()

        encode_command = [
            self._ffmpeg_path,
            "-hide_banner",
            "-loglevel", "error",
            "-f", "f32le",
            "-ar", str(self.sample_rate),
            "-ac", str(self.channels),
            "-i", "pipe:0",
            "-c:a", "libopus",
            "-application", "audio",
            "-b:a", f"{self.bitrate_kbps}k",
            "-f", "ogg",
            "pipe:1",
        ]

        encoded = subprocess.run(
            encode_command,
            input=raw_audio,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
            timeout=10,
        ).stdout

        decode_command = [
            self._ffmpeg_path,
            "-hide_banner",
            "-loglevel", "error",
            "-f", "ogg",
            "-i", "pipe:0",
            "-f", "f32le",
            "-acodec", "pcm_f32le",
            "pipe:1",
        ]

        decoded_bytes = subprocess.run(
            decode_command,
            input=encoded,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
            timeout=10,
        ).stdout

        decoded = np.frombuffer(
            decoded_bytes,
            dtype=np.float32
        )

        decoded = decoded[
            :len(data) * self.channels
        ]

        if len(decoded) < len(data) * self.channels:
            decoded = np.pad(
                decoded,
                (
                    0,
                    len(data) * self.channels - len(decoded),
                ),
            )

        return decoded.reshape(
            (-1, self.channels)
        )

    def _process_fallback(self, data):
        if self._sos is None:
            return data.copy()

        filtered, self._state = sosfilt(
            self._sos,
            data,
            axis=0,
            zi=self._state,
        )

        return filtered.astype(
            data.dtype,
            copy=False
        )

    def _cutoff_frequency(self):
        if self.bitrate_kbps <= 96:
            return 14000.0

        if self.bitrate_kbps <= 128:
            return 16000.0

        if self.bitrate_kbps <= 160:
            return 18000.0

        return 20000.0
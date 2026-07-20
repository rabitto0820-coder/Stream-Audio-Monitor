"""Real-time AAC preview using FFmpeg, with a low-latency fallback."""

from concurrent.futures import ThreadPoolExecutor
import shutil
import subprocess

import numpy as np
from scipy.signal import butter, sosfilt


class AACPreview:
    """Stateful AAC encode/decode preview suitable for monitoring."""

    def __init__(self, sample_rate=48000, channels=2, bitrate_kbps=128):
        self.sample_rate = int(sample_rate)
        self.channels = int(channels)
        self.bitrate_kbps = int(bitrate_kbps)

        self._executor = ThreadPoolExecutor(max_workers=1)
        self._ffmpeg_path = shutil.which("ffmpeg")
        self.real_codec_available = self._ffmpeg_path is not None
        self._future = None

        self.configure(sample_rate, channels)

    def configure(self, sample_rate, channels=2):
        self.sample_rate = int(sample_rate)
        self.channels = int(channels)
        self.reset()

    def reset(self):
        self._future = None
        self._input_buffer = np.empty((0, self.channels), dtype=np.float32)
        self._output_buffer = np.empty((0, self.channels), dtype=np.float32)
        # AAC uses fixed 1024-sample frames. Processing complete groups of
        # frames avoids clicks at the boundary between worker jobs.
        requested_frames = round(self.sample_rate * 0.50)
        self._chunk_size = max(
            1024,
            int(np.ceil(requested_frames / 1024.0)) * 1024,
        )
        self._decoder_delay_frames = 1024

        cutoff = min(18000.0, self.sample_rate * 0.45)
        self._sos = butter(
            4,
            cutoff / (self.sample_rate / 2.0),
            btype="low",
            output="sos",
        )
        self._state = np.zeros((self._sos.shape[0], 2, self.channels))

    def process(self, data):
        if data.ndim != 2 or data.shape[1] != self.channels:
            self.configure(self.sample_rate, data.shape[1])

        if self.real_codec_available:
            return self._process_real_codec(data)

        return self._process_fallback(data)

    def _process_real_codec(self, data):
        self._collect_completed_chunk()
        input_data = np.asarray(data, dtype=np.float32)
        self._input_buffer = np.vstack((self._input_buffer, input_data))

        if self._future is None and len(self._input_buffer) >= self._chunk_size:
            chunk = self._input_buffer[:self._chunk_size].copy()
            self._input_buffer = self._input_buffer[self._chunk_size:]
            self._future = self._executor.submit(self._aac_round_trip, chunk)

        frames = len(input_data)
        if len(self._output_buffer) >= frames:
            output = self._output_buffer[:frames]
            self._output_buffer = self._output_buffer[frames:]
            return output.astype(data.dtype, copy=False)

        available = self._output_buffer
        self._output_buffer = np.empty((0, self.channels), dtype=np.float32)
        silence = np.zeros((frames - len(available), self.channels), dtype=np.float32)
        output = np.vstack((available, silence))
        return output.astype(data.dtype, copy=False)

    def _collect_completed_chunk(self):
        if self._future is None or not self._future.done():
            return

        future = self._future
        self._future = None

        try:
            decoded = future.result()
        except (OSError, subprocess.SubprocessError, ValueError) as error:
            print(f"AAC Preview fallback: {error}")
            self.real_codec_available = False
            return

        self._output_buffer = np.vstack((self._output_buffer, decoded))

    def _aac_round_trip(self, data):
        raw_audio = np.ascontiguousarray(data, dtype=np.float32).tobytes()

        encode_command = [
            self._ffmpeg_path,
            "-hide_banner",
            "-loglevel", "error",
            "-f", "f32le",
            "-ar", str(self.sample_rate),
            "-ac", str(self.channels),
            "-i", "pipe:0",
            "-c:a", "aac",
            "-b:a", f"{self.bitrate_kbps}k",
            "-f", "adts",
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
            "-f", "aac",
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

        decoded = np.frombuffer(decoded_bytes, dtype=np.float32)
        delay_values = self._decoder_delay_frames * self.channels

        # Every independently encoded AAC chunk begins with one AAC frame of
        # decoder delay. Removing it preserves the timing at chunk joins.
        if len(decoded) > delay_values:
            decoded = decoded[delay_values:]

        expected_size = len(data) * self.channels
        decoded = decoded[:expected_size]

        if len(decoded) < expected_size:
            decoded = np.pad(decoded, (0, expected_size - len(decoded)))

        return decoded.reshape((-1, self.channels))

    def _process_fallback(self, data):
        filtered, self._state = sosfilt(
            self._sos,
            data,
            axis=0,
            zi=self._state,
        )
        return filtered.astype(data.dtype, copy=False)

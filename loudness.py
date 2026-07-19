"""Real-time, ITU-R BS.1770-style loudness measurement."""

from collections import deque

import numpy as np
from scipy.signal import lfilter


SILENCE_LUFS = -70.0
LUFS_OFFSET = -0.691


def _high_shelf_coefficients(sample_rate):
    frequency, gain_db, slope = 1681.974, 4.0, 1.0
    amplitude = 10 ** (gain_db / 40.0)
    omega = 2.0 * np.pi * frequency / sample_rate
    sine, cosine = np.sin(omega), np.cos(omega)
    alpha = (sine / 2.0) * np.sqrt(
        (amplitude + 1.0 / amplitude) * (1.0 / slope - 1.0) + 2.0
    )
    beta = 2.0 * np.sqrt(amplitude) * alpha
    b = np.array([
        amplitude * ((amplitude + 1.0) + (amplitude - 1.0) * cosine + beta),
        -2.0 * amplitude * ((amplitude - 1.0) + (amplitude + 1.0) * cosine),
        amplitude * ((amplitude + 1.0) + (amplitude - 1.0) * cosine - beta),
    ])
    a = np.array([
        (amplitude + 1.0) - (amplitude - 1.0) * cosine + beta,
        2.0 * ((amplitude - 1.0) - (amplitude + 1.0) * cosine),
        (amplitude + 1.0) - (amplitude - 1.0) * cosine - beta,
    ])
    return b / a[0], a / a[0]


def _high_pass_coefficients(sample_rate):
    frequency, quality = 38.135, 0.5
    omega = 2.0 * np.pi * frequency / sample_rate
    sine, cosine = np.sin(omega), np.cos(omega)
    alpha = sine / (2.0 * quality)
    b = np.array([
        (1.0 + cosine) / 2.0,
        -(1.0 + cosine),
        (1.0 + cosine) / 2.0,
    ])
    a = np.array([
        1.0 + alpha,
        -2.0 * cosine,
        1.0 - alpha,
    ])
    return b / a[0], a / a[0]


def energy_to_lufs(energy):
    if energy <= 0.0:
        return SILENCE_LUFS

    return max(
        SILENCE_LUFS,
        LUFS_OFFSET + 10.0 * np.log10(energy)
    )


class LoudnessMeter:
    """Maintains Momentary, Short-term, and Integrated loudness state."""

    def __init__(self, sample_rate=48000, channels=2):
        self.sample_rate = int(sample_rate)
        self.channels = int(channels)
        self.reset()

    def reset(self, sample_rate=None, channels=None):
        """Start a new programme measurement when a stream starts."""
        if sample_rate is not None:
            self.sample_rate = int(sample_rate)

        if channels is not None:
            self.channels = int(channels)

        shelf_b, shelf_a = _high_shelf_coefficients(self.sample_rate)
        high_pass_b, high_pass_a = _high_pass_coefficients(
            self.sample_rate
        )

        self._filters = (
            (shelf_b, shelf_a, np.zeros((2, self.channels))),
            (high_pass_b, high_pass_a, np.zeros((2, self.channels))),
        )

        self._momentary_samples = np.empty((0, self.channels))
        self._short_term_samples = np.empty((0, self.channels))
        self._block_samples = np.empty((0, self.channels))
        self._block_energies = deque(maxlen=12 * 60 * 60 * 10)

    def reset_integrated(self):
        """Clear only the Integrated LUFS programme measurement."""
        self._block_samples = np.empty((0, self.channels))
        self._block_energies.clear()

    def process(self, samples):
        """Process one floating-point block and return M/S/I LUFS."""
        data = np.asarray(samples, dtype=np.float64)

        if data.size == 0:
            return SILENCE_LUFS, SILENCE_LUFS, SILENCE_LUFS

        if data.ndim == 1:
            data = data[:, np.newaxis]

        if data.shape[1] != self.channels:
            self.reset(channels=data.shape[1])

        weighted = data
        updated_filters = []

        for b, a, state in self._filters:
            weighted, new_state = lfilter(
                b,
                a,
                weighted,
                axis=0,
                zi=state
            )
            updated_filters.append((b, a, new_state))

        self._filters = tuple(updated_filters)

        self._momentary_samples = self._append_window(
            self._momentary_samples,
            weighted,
            0.4
        )

        self._short_term_samples = self._append_window(
            self._short_term_samples,
            weighted,
            3.0
        )

        self._block_samples = np.vstack((
            self._block_samples,
            weighted
        ))

        self._store_complete_blocks()

        return (
            energy_to_lufs(self._energy(self._momentary_samples)),
            energy_to_lufs(self._energy(self._short_term_samples)),
            self._integrated_lufs(),
        )

    def _append_window(self, existing, new_samples, seconds):
        maximum = max(1, round(self.sample_rate * seconds))

        return np.vstack((
            existing,
            new_samples
        ))[-maximum:]

    @staticmethod
    def _energy(samples):
        if len(samples) == 0:
            return 0.0

        return float(
            np.sum(
                np.mean(
                    np.square(samples),
                    axis=0
                )
            )
        )

    def _store_complete_blocks(self):
        block_size = max(1, round(self.sample_rate * 0.1))

        while len(self._block_samples) >= block_size:
            block = self._block_samples[:block_size]

            self._block_energies.append(
                self._energy(block)
            )

            self._block_samples = self._block_samples[
                block_size:
            ]

    def _integrated_lufs(self):
        if len(self._block_energies) < 4:
            return SILENCE_LUFS

        energies = np.asarray(self._block_energies)

        blocks = np.convolve(
            energies,
            np.ones(4) / 4.0,
            mode="valid"
        )

        block_lufs = np.array([
            energy_to_lufs(value)
            for value in blocks
        ])

        absolute_gated = blocks[
            block_lufs > SILENCE_LUFS
        ]

        if len(absolute_gated) == 0:
            return SILENCE_LUFS

        relative_gate = (
            energy_to_lufs(
                float(np.mean(absolute_gated))
            )
            - 10.0
        )

        gated_lufs = np.array([
            energy_to_lufs(value)
            for value in absolute_gated
        ])

        gated = absolute_gated[
            gated_lufs > relative_gate
        ]

        if len(gated) == 0:
            return SILENCE_LUFS

        return energy_to_lufs(
            float(np.mean(gated))
        )
import time
import sounddevice as sd

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QFrame, QHBoxLayout,
    QLabel, QMainWindow, QPushButton, QVBoxLayout, QWidget,
)

from audio_state import audio_state
from settings import load_settings, save_settings
from themes import apply_theme, theme_names
from widgets import (
    AudioMeter, CorrelationWidget, PhaseScopeWidget,
    SpectrumWidget, WaveformWidget,
)


class MainWindow(QMainWindow):
    def __init__(self, start_stream, stop_stream):
        super().__init__()

        self.start_stream = start_stream
        self.stop_stream = stop_stream

        self.input_devices = []
        self.output_devices = []

        self.rate_values = [44100, 48000, 96000]
        self.buffer_values = [256, 512, 1024, 2048, 4096]
        self.opus_bitrate_values = [96, 128, 160]
        self.limiter_ceiling_values = [-1.0, -2.0, -3.0]
        self.normalizer_target_values = [-14.0, -16.0, -23.0]

        self.setWindowTitle("Stream Audio Monitor")
        self.resize(1100, 1200)

        apply_theme(self, "Studio Dark")

        central = QWidget()
        self.setCentralWidget(central)

        layout = QVBoxLayout(central)
        layout.setSpacing(12)

        title = QLabel("Stream Audio Monitor")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 22pt; font-weight: bold;")

        layout.addWidget(title)
        layout.addWidget(self.create_settings_panel())

        self.create_meters(layout)

        status_row = QHBoxLayout()

        self.status = QLabel("Status: Ready")

        self.normalizer_gain_indicator = QLabel("Normalize: 0.0 dB")
        self.normalizer_gain_indicator.setStyleSheet(
            """
            background: #203a4a; color: #b8e8ff;
            padding: 6px; border-radius: 4px;
            """
        )

        self.headroom_indicator = QLabel("Headroom: 60.0 dB")

        self.clip_indicator = QLabel("CLIP: 0")
        self.clip_indicator.setStyleSheet(
            """
            background: #304030; color: #baffba;
            padding: 6px; border-radius: 4px;
            """
        )

        self.clear_clip_button = QPushButton("Clear Clip")
        self.clear_clip_button.clicked.connect(self.clear_clip)

        self.reset_lufs_button = QPushButton("Reset LUFS-I")
        self.reset_lufs_button.clicked.connect(
            self.reset_integrated_loudness
        )

        self.youtube_preset_button = QPushButton("YouTube")
        self.youtube_preset_button.clicked.connect(
            self.apply_youtube_preset
        )

        self.podcast_preset_button = QPushButton("Podcast")
        self.podcast_preset_button.clicked.connect(
            self.apply_podcast_preset
        )

        self.broadcast_preset_button = QPushButton("Broadcast")
        self.broadcast_preset_button.clicked.connect(
            self.apply_broadcast_preset
        )

        status_row.addWidget(self.status)
        status_row.addStretch()
        status_row.addWidget(self.normalizer_gain_indicator)
        status_row.addWidget(self.headroom_indicator)
        status_row.addWidget(self.clip_indicator)
        status_row.addWidget(self.clear_clip_button)
        status_row.addWidget(self.reset_lufs_button)
        status_row.addWidget(self.youtube_preset_button)
        status_row.addWidget(self.podcast_preset_button)
        status_row.addWidget(self.broadcast_preset_button)

        layout.addLayout(status_row)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_gui)
        self.timer.start(16)

        QTimer.singleShot(500, self.start_audio)

    def create_settings_panel(self):
        frame = QFrame()
        layout = QHBoxLayout(frame)

        self.input_box = QComboBox()
        self.output_box = QComboBox()

        self.rate_box = QComboBox()
        self.buffer_box = QComboBox()

        self.opus_bitrate_box = QComboBox()
        self.limiter_ceiling_box = QComboBox()
        self.theme_box = QComboBox()
        self.normalizer_target_box = QComboBox()

        for value in self.rate_values:
            self.rate_box.addItem(f"{value} Hz")

        for value in self.buffer_values:
            self.buffer_box.addItem(str(value))

        for value in self.opus_bitrate_values:
            self.opus_bitrate_box.addItem(f"{value} kbps")

        for value in self.limiter_ceiling_values:
            self.limiter_ceiling_box.addItem(f"{value:.0f} dBFS")

        self.theme_box.addItems(theme_names())

        for value in self.normalizer_target_values:
            self.normalizer_target_box.addItem(f"{value:.0f} LUFS")

        self.start_button = QPushButton("Start")
        self.stop_button = QPushButton("Stop")

        self.youtube_checkbox = QCheckBox("YouTube Opus Preview")
        self.aac_checkbox = QCheckBox("AAC Preview")
        self.limiter_checkbox = QCheckBox("Safety Limiter")
        self.normalizer_checkbox = QCheckBox("Loudness Normalize")

        self.load_devices()

        self.opus_bitrate_box.setCurrentIndex(
            self.opus_bitrate_values.index(128)
        )

        for label, widget, stretch in (
            ("Input", self.input_box, 2),
            ("Output", self.output_box, 2),
            ("Rate", self.rate_box, 0),
            ("Buffer", self.buffer_box, 0),
        ):
            layout.addWidget(QLabel(label))
            layout.addWidget(widget, stretch)

        layout.addWidget(self.start_button)
        layout.addWidget(self.stop_button)

        layout.addWidget(self.youtube_checkbox)
        layout.addWidget(self.aac_checkbox)

        layout.addWidget(QLabel("Opus"))
        layout.addWidget(self.opus_bitrate_box)

        layout.addWidget(self.limiter_checkbox)

        layout.addWidget(self.normalizer_checkbox)
        layout.addWidget(QLabel("Target"))
        layout.addWidget(self.normalizer_target_box)

        layout.addWidget(QLabel("Ceiling"))
        layout.addWidget(self.limiter_ceiling_box)

        layout.addWidget(QLabel("Skin"))
        layout.addWidget(self.theme_box)

        self.start_button.clicked.connect(self.start_audio)
        self.stop_button.clicked.connect(self.stop_audio)

        self.youtube_checkbox.toggled.connect(self.toggle_opus)
        self.aac_checkbox.toggled.connect(self.toggle_aac)

        self.opus_bitrate_box.currentIndexChanged.connect(
            self.change_opus_bitrate
        )

        self.limiter_checkbox.toggled.connect(
            self.toggle_limiter
        )

        self.limiter_ceiling_box.currentIndexChanged.connect(
            self.change_limiter_ceiling
        )

        self.normalizer_checkbox.toggled.connect(
            self.toggle_normalizer
        )

        self.normalizer_target_box.currentIndexChanged.connect(
            self.change_normalizer_target
        )

        self.theme_box.currentTextChanged.connect(
            self.change_theme
        )

        return frame

    def create_meters(self, layout):
        self.peak_meter = AudioMeter("Peak")
        self.true_peak_meter = AudioMeter("True Peak")
        self.rms_meter = AudioMeter("RMS")

        self.lufs_m_meter = AudioMeter("LUFS-M")
        self.lufs_s_meter = AudioMeter("LUFS-S")
        self.lufs_i_meter = AudioMeter("LUFS-I")

        self.correlation_meter = CorrelationWidget()
        self.phase_scope = PhaseScopeWidget()
        self.waveform = WaveformWidget()
        self.spectrum = SpectrumWidget()

        for widget in (
            self.peak_meter,
            self.true_peak_meter,
            self.rms_meter,
            self.lufs_m_meter,
            self.lufs_s_meter,
            self.lufs_i_meter,
            self.correlation_meter,
            self.phase_scope,
            self.waveform,
            self.spectrum,
        ):
            layout.addWidget(widget)

    def load_devices(self):
        devices = sd.query_devices()

        for index, device in enumerate(devices):
            name = device["name"]

            if device["max_input_channels"] > 0:
                self.input_devices.append(index)
                self.input_box.addItem(f"{index}: {name}")

            if device["max_output_channels"] > 0:
                self.output_devices.append(index)
                self.output_box.addItem(f"{index}: {name}")

        saved = load_settings()

        if not saved:
            return

        if saved.get("input_device") in self.input_devices:
            self.input_box.setCurrentIndex(
                self.input_devices.index(saved["input_device"])
            )

        if saved.get("output_device") in self.output_devices:
            self.output_box.setCurrentIndex(
                self.output_devices.index(saved["output_device"])
            )

        if saved.get("samplerate") in self.rate_values:
            self.rate_box.setCurrentIndex(
                self.rate_values.index(saved["samplerate"])
            )

        if saved.get("blocksize") in self.buffer_values:
            self.buffer_box.setCurrentIndex(
                self.buffer_values.index(saved["blocksize"])
            )

    def start_audio(self):
        if not self.input_devices or not self.output_devices:
            self.status.setText("Status: No usable audio device found")
            return

        input_device = self.input_devices[
            self.input_box.currentIndex()
        ]

        output_device = self.output_devices[
            self.output_box.currentIndex()
        ]

        samplerate = self.rate_values[
            self.rate_box.currentIndex()
        ]

        blocksize = self.buffer_values[
            self.buffer_box.currentIndex()
        ]

        save_settings(
            input_device,
            output_device,
            samplerate,
            blocksize
        )

        started = self.start_stream(
            input_device,
            output_device,
            samplerate,
            blocksize,
        )

        self.status.setText(
            "Status: Running" if started else "Status: Audio error"
        )

    def stop_audio(self):
        self.stop_stream()
        self.status.setText("Status: Stopped")

    def toggle_opus(self, enabled):
        import audio

        audio.opus_simulation = enabled

        if enabled:
            audio.set_aac_simulation(False)

            self.aac_checkbox.blockSignals(True)
            self.aac_checkbox.setChecked(False)
            self.aac_checkbox.blockSignals(False)

            bitrate = self.current_opus_bitrate()

            print(
                f"YouTube Opus Preview: ON ({bitrate} kbps)"
            )

            self.status.setText(
                f"Status: YouTube Opus Preview ({bitrate} kbps)"
            )

        else:
            print("YouTube Opus Preview: OFF")
            self.status.setText("Status: Running")

    def toggle_aac(self, enabled):
        import audio

        audio.set_aac_simulation(enabled)

        if enabled:
            self.youtube_checkbox.blockSignals(True)
            self.youtube_checkbox.setChecked(False)
            self.youtube_checkbox.blockSignals(False)

            print("AAC Preview: ON")

            self.status.setText(
                "Status: AAC Preview (Approximate)"
            )

        else:
            print("AAC Preview: OFF")
            self.status.setText("Status: Running")

    def change_opus_bitrate(self, _index=None):
        import audio

        bitrate = self.current_opus_bitrate()

        audio.set_opus_bitrate(bitrate)

        print(
            f"YouTube Opus Preview bitrate: {bitrate} kbps"
        )

    def current_opus_bitrate(self):
        return self.opus_bitrate_values[
            self.opus_bitrate_box.currentIndex()
        ]

    def toggle_limiter(self, enabled):
        import audio

        audio.set_limiter_enabled(enabled)

        state = "ON" if enabled else "OFF"

        print(
            f"Safety Limiter: {state} "
            f"({self.current_limiter_ceiling():.0f} dBFS)"
        )

    def change_limiter_ceiling(self, _index=None):
        import audio

        ceiling = self.current_limiter_ceiling()

        audio.set_limiter_ceiling(ceiling)

        print(
            f"Safety Limiter ceiling: {ceiling:.0f} dBFS"
        )

    def current_limiter_ceiling(self):
        return self.limiter_ceiling_values[
            self.limiter_ceiling_box.currentIndex()
        ]

    def toggle_normalizer(self, enabled):
        import audio

        audio.set_normalizer_enabled(enabled)

        state = "ON" if enabled else "OFF"
        target = self.current_normalizer_target()

        print(
            f"Loudness Normalize: {state} ({target:.0f} LUFS)"
        )

    def change_normalizer_target(self, _index=None):
        import audio

        target = self.current_normalizer_target()

        audio.set_normalizer_target(target)

        print(
            f"Loudness Normalize target: {target:.0f} LUFS"
        )

    def current_normalizer_target(self):
        return self.normalizer_target_values[
            self.normalizer_target_box.currentIndex()
        ]

    def change_theme(self, name):
        apply_theme(self, name)

    def clear_clip(self):
        import audio

        audio.reset_clip_counter()
        self.clip_indicator.setText("CLIP: 0")

    def reset_integrated_loudness(self):
        import audio

        audio.reset_integrated_loudness()
        self.lufs_i_meter.set_level(-70.0)
        self.status.setText("Status: Integrated LUFS reset")

        print("Integrated LUFS: RESET")

    def apply_youtube_preset(self):
        self.apply_loudness_preset(
            name="YouTube",
            target_lufs=-14.0,
            limiter_ceiling=-1.0,
            opus_preview=True,
        )

    def apply_podcast_preset(self):
        self.apply_loudness_preset(
            name="Podcast",
            target_lufs=-16.0,
            limiter_ceiling=-1.0,
            opus_preview=False,
        )

    def apply_broadcast_preset(self):
        self.apply_loudness_preset(
            name="Broadcast",
            target_lufs=-23.0,
            limiter_ceiling=-1.0,
            opus_preview=False,
        )

    def apply_loudness_preset(
        self,
        name,
        target_lufs,
        limiter_ceiling,
        opus_preview,
    ):
        self.normalizer_target_box.setCurrentIndex(
            self.normalizer_target_values.index(target_lufs)
        )

        self.limiter_ceiling_box.setCurrentIndex(
            self.limiter_ceiling_values.index(limiter_ceiling)
        )

        self.normalizer_checkbox.setChecked(True)
        self.limiter_checkbox.setChecked(True)
        self.youtube_checkbox.setChecked(opus_preview)

        if not opus_preview:
            self.aac_checkbox.setChecked(False)

        self.status.setText(f"Status: {name} preset applied")

        print(
            f"Preset: {name} "
            f"({target_lufs:.0f} LUFS, {limiter_ceiling:.0f} dBFS)"
        )

    def update_headroom_indicator(self):
        headroom_db = -audio_state.true_peak_db

        self.headroom_indicator.setText(
            f"Headroom: {headroom_db:.1f} dB"
        )

        if headroom_db < 0.0:
            style = """
                background: #8b1e1e; color: white;
                padding: 6px; border-radius: 4px;
            """
        elif headroom_db < 3.0:
            style = """
                background: #66520e; color: #fff3b0;
                padding: 6px; border-radius: 4px;
            """
        else:
            style = """
                background: #304030; color: #baffba;
                padding: 6px; border-radius: 4px;
            """

        self.headroom_indicator.setStyleSheet(style)

    def update_gui(self):
        self.peak_meter.set_level(audio_state.peak_db)
        self.true_peak_meter.set_level(audio_state.true_peak_db)
        self.rms_meter.set_level(audio_state.rms_db)

        self.lufs_m_meter.set_level(audio_state.lufs_m)
        self.lufs_s_meter.set_level(audio_state.lufs_s)
        self.lufs_i_meter.set_level(audio_state.lufs_i)

        self.correlation_meter.set_correlation(
            audio_state.correlation
        )

        self.phase_scope.set_samples(
            audio_state.last_audio
        )

        self.waveform.set_samples(
            audio_state.last_audio
        )

        self.spectrum.set_spectrum(
            audio_state.spectrum
        )

        self.clip_indicator.setText(
            f"CLIP: {audio_state.clip_count}"
        )

        self.normalizer_gain_indicator.setText(
            f"Normalize: {audio_state.normalizer_gain_db:+.1f} dB"
        )

        self.update_headroom_indicator()

        if time.monotonic() < audio_state.clip_hold_until:
            self.clip_indicator.setStyleSheet(
                """
                background: #8b1e1e; color: white;
                padding: 6px; border-radius: 4px;
                """
            )
        else:
            self.clip_indicator.setStyleSheet(
                """
                background: #304030; color: #baffba;
                padding: 6px; border-radius: 4px;
                """
            )
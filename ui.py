import time
import sounddevice as sd

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QFrame, QFileDialog, QGridLayout, QHBoxLayout,
    QLabel, QMainWindow, QMessageBox, QPushButton, QScrollArea,
    QVBoxLayout, QWidget,
)

from audio_state import audio_state
from aac_exporter import export_aac_preview
from file_analyzer import analyze_wav, compare_wavs
from opus_exporter import export_opus_preview, export_youtube_ab_previews
from preview_pack import export_codec_pack
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
        self.saved_settings = {}

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

        status_row = QGridLayout()
        status_row.setHorizontalSpacing(8)
        status_row.setVerticalSpacing(6)

        self.status = QLabel("Status: Ready")

        self.input_signal_indicator = QLabel("INPUT: SILENT")

        self.lufs_time_indicator = QLabel("LUFS: 00:00")

        self.codec_indicator = QLabel("CODEC: OFF")

        self.normalizer_gain_indicator = QLabel("Normalize: 0.0 dB")
        self.normalizer_gain_indicator.setStyleSheet(
            """
            background: #203a4a; color: #b8e8ff;
            padding: 6px; border-radius: 4px;
            """
        )

        self.youtube_gain_indicator = QLabel("YT: 0.0 dB / 100%")
        self.youtube_gain_indicator.setStyleSheet(
            """
            background: #3b263f; color: #ffd1ff;
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

        status_row.addWidget(self.status, 0, 0, 1, 2)
        status_row.addWidget(self.input_signal_indicator, 0, 2)
        status_row.addWidget(self.lufs_time_indicator, 0, 3)
        status_row.addWidget(self.codec_indicator, 0, 4)
        status_row.addWidget(self.normalizer_gain_indicator, 0, 5)
        status_row.addWidget(self.youtube_gain_indicator, 0, 6)
        status_row.addWidget(self.headroom_indicator, 0, 7)
        status_row.addWidget(self.clip_indicator, 0, 8)
        status_row.addWidget(self.clear_clip_button, 1, 0)
        status_row.addWidget(self.reset_lufs_button, 1, 1)
        status_row.addWidget(self.youtube_preset_button, 1, 2)
        status_row.addWidget(self.podcast_preset_button, 1, 3)
        status_row.addWidget(self.broadcast_preset_button, 1, 4)

        layout.addLayout(status_row)

        self.create_meters(layout)

        self.restore_preview_settings()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_gui)
        self.timer.start(16)

        QTimer.singleShot(500, self.start_audio)

    def create_settings_panel(self):
        frame = QFrame()
        layout = QVBoxLayout(frame)
        layout.setSpacing(6)

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
        self.analyze_wav_button = QPushButton("Analyze WAV")
        self.compare_wav_button = QPushButton("Compare WAV")
        self.export_opus_button = QPushButton("Export Opus WAV")
        self.export_aac_button = QPushButton("Export AAC WAV")
        self.export_youtube_ab_button = QPushButton("Export YouTube A/B")
        self.export_codec_pack_button = QPushButton("Export Codec Pack")
        self.youtube_volume_export_checkbox = QCheckBox(
            "Apply YouTube Volume"
        )
        self.youtube_volume_export_checkbox.setChecked(True)

        self.youtube_checkbox = QCheckBox("YouTube Opus Preview")
        self.aac_checkbox = QCheckBox("AAC Preview")
        self.mono_checkbox = QCheckBox("Mono Preview")
        self.bass_mono_checkbox = QCheckBox("Bass Mono (150 Hz)")
        self.phone_speaker_checkbox = QCheckBox("Phone Speaker Preview")
        self.mute_monitor_checkbox = QCheckBox("Mute Monitor")
        self.bypass_checkbox = QCheckBox("Bypass Effects")
        self.limiter_checkbox = QCheckBox("Safety Limiter")
        self.normalizer_checkbox = QCheckBox("Loudness Normalize")
        self.youtube_normalize_checkbox = QCheckBox(
            "YouTube Playback Normalize"
        )

        self.load_devices()

        self.opus_bitrate_box.setCurrentIndex(
            self.opus_bitrate_values.index(128)
        )

        device_row = QHBoxLayout()
        device_row.addWidget(QLabel("Input"))
        device_row.addWidget(self.input_box, 2)
        device_row.addWidget(QLabel("Output"))
        device_row.addWidget(self.output_box, 2)
        device_row.addWidget(QLabel("Rate"))
        device_row.addWidget(self.rate_box)
        device_row.addWidget(QLabel("Buffer"))
        device_row.addWidget(self.buffer_box)
        device_row.addWidget(self.start_button)
        device_row.addWidget(self.stop_button)
        layout.addLayout(device_row)

        export_row = QHBoxLayout()
        export_row.addWidget(self.analyze_wav_button)
        export_row.addWidget(self.compare_wav_button)
        export_row.addWidget(self.export_opus_button)
        export_row.addWidget(self.export_aac_button)
        export_row.addWidget(self.export_youtube_ab_button)
        export_row.addWidget(self.export_codec_pack_button)
        export_row.addWidget(self.youtube_volume_export_checkbox)
        export_row.addStretch()
        layout.addLayout(export_row)

        preview_row = QHBoxLayout()
        preview_row.addWidget(self.youtube_checkbox)
        preview_row.addWidget(self.aac_checkbox)
        preview_row.addWidget(self.mono_checkbox)
        preview_row.addWidget(self.bass_mono_checkbox)
        preview_row.addWidget(self.phone_speaker_checkbox)
        preview_row.addWidget(QLabel("Opus"))
        preview_row.addWidget(self.opus_bitrate_box)
        preview_row.addStretch()
        layout.addLayout(preview_row)

        monitor_row = QHBoxLayout()
        monitor_row.addWidget(self.mute_monitor_checkbox)
        monitor_row.addWidget(self.bypass_checkbox)
        monitor_row.addWidget(QLabel("Mute keeps meters running. Bypass plays the raw input."))
        monitor_row.addStretch()
        layout.addLayout(monitor_row)

        processing_row = QHBoxLayout()
        processing_row.addWidget(self.limiter_checkbox)
        processing_row.addWidget(QLabel("Ceiling"))
        processing_row.addWidget(self.limiter_ceiling_box)
        processing_row.addWidget(self.normalizer_checkbox)
        processing_row.addWidget(self.youtube_normalize_checkbox)
        processing_row.addWidget(QLabel("Target"))
        processing_row.addWidget(self.normalizer_target_box)
        processing_row.addWidget(QLabel("Skin"))
        processing_row.addWidget(self.theme_box)
        processing_row.addStretch()
        layout.addLayout(processing_row)

        self.start_button.clicked.connect(self.start_audio)
        self.stop_button.clicked.connect(self.stop_audio)
        self.analyze_wav_button.clicked.connect(self.analyze_wav_file)
        self.compare_wav_button.clicked.connect(self.compare_wav_files)
        self.export_opus_button.clicked.connect(self.export_opus_wav)
        self.export_aac_button.clicked.connect(self.export_aac_wav)
        self.export_youtube_ab_button.clicked.connect(
            self.export_youtube_ab_wavs
        )
        self.export_codec_pack_button.clicked.connect(
            self.export_codec_pack_wavs
        )

        self.youtube_checkbox.toggled.connect(self.toggle_opus)
        self.aac_checkbox.toggled.connect(self.toggle_aac)
        self.mono_checkbox.toggled.connect(self.toggle_mono_preview)
        self.bass_mono_checkbox.toggled.connect(
            self.toggle_bass_mono_preview
        )
        self.phone_speaker_checkbox.toggled.connect(
            self.toggle_phone_speaker_preview
        )
        self.mute_monitor_checkbox.toggled.connect(
            self.toggle_mute_monitor
        )
        self.bypass_checkbox.toggled.connect(self.toggle_bypass_effects)

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

        self.youtube_normalize_checkbox.toggled.connect(
            self.toggle_youtube_normalizer
        )

        self.normalizer_target_box.currentIndexChanged.connect(
            self.change_normalizer_target
        )

        self.theme_box.currentTextChanged.connect(
            self.change_theme
        )

        return frame

    def create_meters(self, layout):
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        meter_container = QWidget()
        meter_layout = QVBoxLayout(meter_container)
        meter_layout.setContentsMargins(0, 0, 0, 0)
        meter_layout.setSpacing(10)

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
            meter_layout.addWidget(widget)

        meter_layout.addStretch()
        scroll_area.setWidget(meter_container)
        layout.addWidget(scroll_area, 1)

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

        saved = load_settings() or {}
        self.saved_settings = saved

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

        self.save_current_settings()

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

    def restore_preview_settings(self):
        """Restore monitor choices saved when the app was last closed."""
        saved = self.saved_settings.get("preview_settings", {})
        if not saved:
            return

        theme = saved.get("theme")
        if theme in theme_names():
            self.theme_box.setCurrentText(theme)

        bitrate = saved.get("opus_bitrate")
        if bitrate in self.opus_bitrate_values:
            self.opus_bitrate_box.setCurrentIndex(
                self.opus_bitrate_values.index(bitrate)
            )

        target = saved.get("normalizer_target")
        if target in self.normalizer_target_values:
            self.normalizer_target_box.setCurrentIndex(
                self.normalizer_target_values.index(target)
            )

        ceiling = saved.get("limiter_ceiling")
        if ceiling in self.limiter_ceiling_values:
            self.limiter_ceiling_box.setCurrentIndex(
                self.limiter_ceiling_values.index(ceiling)
            )

        self.youtube_volume_export_checkbox.setChecked(
            saved.get("apply_youtube_volume", True)
        )
        self.limiter_checkbox.setChecked(saved.get("limiter_enabled", False))
        self.normalizer_checkbox.setChecked(
            saved.get("normalizer_enabled", False)
        )
        self.youtube_normalize_checkbox.setChecked(
            saved.get("youtube_normalize_enabled", False)
        )
        self.mono_checkbox.setChecked(saved.get("mono_preview", False))
        self.bass_mono_checkbox.setChecked(
            saved.get("bass_mono_preview", False)
        )
        self.phone_speaker_checkbox.setChecked(
            saved.get("phone_speaker_preview", False)
        )
        self.bypass_checkbox.setChecked(saved.get("bypass_effects", False))

        # AAC is restored first because enabling the YouTube preview turns it
        # off automatically; only one real-time codec preview can be active.
        self.aac_checkbox.setChecked(saved.get("aac_preview", False))
        self.youtube_checkbox.setChecked(saved.get("youtube_preview", False))

    def save_current_settings(self):
        """Save devices and all monitor choices for the next launch."""
        if not self.input_devices or not self.output_devices:
            return

        preview_settings = {
            "theme": self.theme_box.currentText(),
            "opus_bitrate": self.current_opus_bitrate(),
            "limiter_ceiling": self.current_limiter_ceiling(),
            "normalizer_target": self.current_normalizer_target(),
            "apply_youtube_volume": self.youtube_volume_export_checkbox.isChecked(),
            "youtube_preview": self.youtube_checkbox.isChecked(),
            "aac_preview": self.aac_checkbox.isChecked(),
            "mono_preview": self.mono_checkbox.isChecked(),
            "bass_mono_preview": self.bass_mono_checkbox.isChecked(),
            "phone_speaker_preview": self.phone_speaker_checkbox.isChecked(),
            "bypass_effects": self.bypass_checkbox.isChecked(),
            "limiter_enabled": self.limiter_checkbox.isChecked(),
            "normalizer_enabled": self.normalizer_checkbox.isChecked(),
            "youtube_normalize_enabled": (
                self.youtube_normalize_checkbox.isChecked()
            ),
        }

        save_settings(
            self.input_devices[self.input_box.currentIndex()],
            self.output_devices[self.output_box.currentIndex()],
            self.rate_values[self.rate_box.currentIndex()],
            self.buffer_values[self.buffer_box.currentIndex()],
            preview_settings=preview_settings,
        )

    def closeEvent(self, event):
        self.save_current_settings()
        super().closeEvent(event)

    def analyze_wav_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Analyze WAV file",
            "",
            "WAV files (*.wav)",
        )

        if not path:
            return

        try:
            self.status.setText("Status: Analyzing WAV...")
            result = analyze_wav(path)
        except (OSError, ValueError) as error:
            self.status.setText("Status: WAV analysis error")
            QMessageBox.warning(self, "WAV Analysis", str(error))
            return

        minutes, seconds = divmod(int(result["duration_seconds"]), 60)
        message = (
            f"File: {result['name']}\n"
            f"Duration: {minutes:02d}:{seconds:02d}\n"
            f"Integrated LUFS: {result['lufs_i']:.1f}\n"
            f"Sample Peak: {result['peak_db']:.1f} dBFS\n\n"
            f"Estimated True Peak: {result['true_peak_db']:.1f} dBTP\n\n"
            "YouTube playback estimate\n"
            f"Gain: {result['youtube_gain_db']:+.1f} dB\n"
            f"Volume: {result['youtube_percent']:.0f}%\n\n"
            "YouTube mix check\n"
            f"{result['youtube_advice']}"
        )

        self.status.setText("Status: WAV analysis complete")
        print(message.replace("\n", " | "))
        QMessageBox.information(self, "WAV Analysis", message)

    def compare_wav_files(self):
        reference_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select original WAV",
            "",
            "WAV files (*.wav)",
        )

        if not reference_path:
            return

        preview_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Opus or YouTube preview WAV",
            "",
            "WAV files (*.wav)",
        )

        if not preview_path:
            return

        try:
            self.status.setText("Status: Comparing WAV files...")
            result = compare_wavs(reference_path, preview_path)
        except (OSError, ValueError) as error:
            self.status.setText("Status: WAV comparison error")
            QMessageBox.warning(self, "WAV Comparison", str(error))
            return

        reference = result["reference"]
        preview = result["preview"]
        message = (
            "WAV comparison\n\n"
            f"Original: {reference['name']}\n"
            f"Preview: {preview['name']}\n\n"
            f"Integrated LUFS difference: {result['lufs_difference_db']:+.1f} dB\n"
            f"Peak difference: {result['peak_difference_db']:+.1f} dB\n"
            f"Presence (4–8 kHz): {result['presence_difference_db']:+.1f} dB\n"
            f"High range (8–16 kHz): {result['high_band_difference_db']:+.1f} dB\n"
            f"Duration difference: {result['duration_difference_seconds']:+.3f} sec\n\n"
            "A negative high-range value means the preview contains less "
            "energy in that band. Use it as a comparison guide, not a score."
        )

        self.status.setText("Status: WAV comparison complete")
        print(message.replace("\n", " | "))
        QMessageBox.information(self, "WAV Comparison", message)

    def export_opus_wav(self):
        source_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select source WAV",
            "",
            "WAV files (*.wav)",
        )

        if not source_path:
            return

        default_path = source_path.rsplit(".", 1)[0]
        default_path += f"_opus_{self.current_opus_bitrate()}k.wav"

        destination_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Opus preview WAV",
            default_path,
            "WAV files (*.wav)",
        )

        if not destination_path:
            return

        try:
            bitrate = self.current_opus_bitrate()
            analysis = analyze_wav(source_path)
            playback_gain_db = (
                analysis["youtube_gain_db"]
                if self.youtube_volume_export_checkbox.isChecked()
                else 0.0
            )
            self.status.setText("Status: Exporting Opus preview...")
            output_path = export_opus_preview(
                source_path,
                destination_path,
                bitrate,
                playback_gain_db,
            )
        except (OSError, RuntimeError, ValueError) as error:
            self.status.setText("Status: Opus export error")
            QMessageBox.warning(self, "Opus Export", str(error))
            return

        self.status.setText("Status: Opus preview exported")
        message = (
            f"Created Opus preview WAV\n\n"
            f"Bitrate: {bitrate} kbps\n"
            f"YouTube gain: {playback_gain_db:+.1f} dB\n"
            f"File: {output_path}"
        )
        print(message.replace("\n", " | "))
        QMessageBox.information(self, "Opus Export", message)

    def export_aac_wav(self):
        source_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select source WAV",
            "",
            "WAV files (*.wav)",
        )

        if not source_path:
            return

        default_path = source_path.rsplit(".", 1)[0] + "_aac_128k.wav"
        destination_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save AAC preview WAV",
            default_path,
            "WAV files (*.wav)",
        )

        if not destination_path:
            return

        try:
            analysis = analyze_wav(source_path)
            playback_gain_db = (
                analysis["youtube_gain_db"]
                if self.youtube_volume_export_checkbox.isChecked()
                else 0.0
            )
            self.status.setText("Status: Exporting AAC preview...")
            output_path = export_aac_preview(
                source_path,
                destination_path,
                bitrate_kbps=128,
                playback_gain_db=playback_gain_db,
            )
        except (OSError, RuntimeError, ValueError) as error:
            self.status.setText("Status: AAC export error")
            QMessageBox.warning(self, "AAC Export", str(error))
            return

        self.status.setText("Status: AAC preview exported")
        message = (
            "Created AAC preview WAV\n\n"
            "Bitrate: 128 kbps\n"
            f"YouTube gain: {playback_gain_db:+.1f} dB\n"
            f"File: {output_path}"
        )
        print(message.replace("\n", " | "))
        QMessageBox.information(self, "AAC Export", message)

    def export_youtube_ab_wavs(self):
        source_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select source WAV",
            "",
            "WAV files (*.wav)",
        )

        if not source_path:
            return

        destination_folder = QFileDialog.getExistingDirectory(
            self,
            "Select output folder for YouTube A/B files",
        )

        if not destination_folder:
            return

        try:
            bitrate = self.current_opus_bitrate()
            analysis = analyze_wav(source_path)
            playback_gain_db = analysis["youtube_gain_db"]
            self.status.setText("Status: Exporting YouTube A/B previews...")
            output_paths = export_youtube_ab_previews(
                source_path,
                destination_folder,
                bitrate,
                playback_gain_db,
            )
        except (OSError, RuntimeError, ValueError) as error:
            self.status.setText("Status: YouTube A/B export error")
            QMessageBox.warning(self, "YouTube A/B Export", str(error))
            return

        self.status.setText("Status: YouTube A/B previews exported")
        message = (
            "Created matched YouTube A/B preview WAVs\n\n"
            f"Bitrate: {bitrate} kbps\n"
            f"YouTube gain: {playback_gain_db:+.1f} dB\n\n"
            "A — Opus codec only\n"
            f"{output_paths['opus']}\n\n"
            "B — Opus + YouTube playback volume\n"
            f"{output_paths['youtube']}"
        )
        print(message.replace("\n", " | "))
        QMessageBox.information(self, "YouTube A/B Export", message)

    def export_codec_pack_wavs(self):
        source_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select source WAV",
            "",
            "WAV files (*.wav)",
        )

        if not source_path:
            return

        destination_folder = QFileDialog.getExistingDirectory(
            self,
            "Select output folder for codec preview pack",
        )

        if not destination_folder:
            return

        try:
            opus_bitrate = self.current_opus_bitrate()
            analysis = analyze_wav(source_path)
            playback_gain_db = analysis["youtube_gain_db"]
            self.status.setText("Status: Exporting codec preview pack...")
            paths = export_codec_pack(
                source_path,
                destination_folder,
                opus_bitrate_kbps=opus_bitrate,
                aac_bitrate_kbps=128,
                youtube_gain_db=playback_gain_db,
            )
        except (OSError, RuntimeError, ValueError) as error:
            self.status.setText("Status: Codec pack export error")
            QMessageBox.warning(self, "Codec Pack Export", str(error))
            return

        self.status.setText("Status: Codec preview pack exported")
        message = (
            "Created YouTube codec preview pack\n\n"
            f"YouTube gain: {playback_gain_db:+.1f} dB\n\n"
            f"Opus + YouTube volume\n{paths['opus_youtube']}\n\n"
            f"AAC + YouTube volume\n{paths['aac_youtube']}"
        )
        print(message.replace("\n", " | "))
        QMessageBox.information(self, "Codec Pack Export", message)

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

            self.status.setText("Status: AAC Preview (128 kbps)")

        else:
            print("AAC Preview: OFF")
            self.status.setText("Status: Running")

    def toggle_mono_preview(self, enabled):
        import audio

        audio.set_mono_preview(enabled)
        state = "ON" if enabled else "OFF"
        print(f"Mono Preview: {state}")

    def toggle_bass_mono_preview(self, enabled):
        import audio

        audio.set_bass_mono_preview(enabled)
        state = "ON" if enabled else "OFF"
        print(f"Bass Mono Preview (150 Hz): {state}")

    def toggle_phone_speaker_preview(self, enabled):
        import audio

        audio.set_phone_speaker_preview(enabled)
        state = "ON" if enabled else "OFF"
        print(f"Phone Speaker Preview: {state}")

        if enabled:
            self.status.setText("Status: Phone Speaker Preview")
        else:
            self.status.setText("Status: Running")

    def toggle_mute_monitor(self, enabled):
        import audio

        audio.set_monitor_muted(enabled)
        self.status.setText(
            "Status: Monitor muted (analysis continues)"
            if enabled
            else "Status: Running"
        )

    def toggle_bypass_effects(self, enabled):
        import audio

        audio.set_bypass_effects(enabled)
        self.status.setText(
            "Status: Bypass — raw input"
            if enabled
            else "Status: Running"
        )

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

    def toggle_youtube_normalizer(self, enabled):
        import audio

        audio.set_youtube_normalizer_enabled(enabled)
        state = "ON" if enabled else "OFF"
        print(f"YouTube Playback Normalize: {state}")

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
            youtube_normalize=True,
        )

    def apply_podcast_preset(self):
        self.apply_loudness_preset(
            name="Podcast",
            target_lufs=-16.0,
            limiter_ceiling=-1.0,
            opus_preview=False,
            youtube_normalize=False,
        )

    def apply_broadcast_preset(self):
        self.apply_loudness_preset(
            name="Broadcast",
            target_lufs=-23.0,
            limiter_ceiling=-1.0,
            opus_preview=False,
            youtube_normalize=False,
        )

    def apply_loudness_preset(
        self,
        name,
        target_lufs,
        limiter_ceiling,
        opus_preview,
        youtube_normalize,
    ):
        self.normalizer_target_box.setCurrentIndex(
            self.normalizer_target_values.index(target_lufs)
        )

        self.limiter_ceiling_box.setCurrentIndex(
            self.limiter_ceiling_values.index(limiter_ceiling)
        )

        self.normalizer_checkbox.setChecked(not youtube_normalize)
        self.youtube_normalize_checkbox.setChecked(youtube_normalize)
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

    def update_input_signal_indicator(self):
        input_peak_db = audio_state.input_peak_db

        if input_peak_db >= -40.0:
            text = "INPUT: SIGNAL"
            style = """
                background: #1f5637; color: #d4ffdf;
                padding: 6px; border-radius: 4px;
            """
        elif input_peak_db > -60.0:
            text = "INPUT: LOW"
            style = """
                background: #66520e; color: #fff3b0;
                padding: 6px; border-radius: 4px;
            """
        else:
            text = "INPUT: SILENT"
            style = """
                background: #4a2525; color: #ffd6d6;
                padding: 6px; border-radius: 4px;
            """

        self.input_signal_indicator.setText(text)
        self.input_signal_indicator.setStyleSheet(style)

    def update_lufs_time_indicator(self):
        total_seconds = int(audio_state.lufs_measurement_seconds)
        minutes, seconds = divmod(total_seconds, 60)

        if total_seconds < 30:
            progress = "START"
        elif total_seconds < 120:
            progress = "MEASURING"
        else:
            progress = "LONG"

        self.lufs_time_indicator.setText(
            f"LUFS: {minutes:02d}:{seconds:02d} {progress}"
        )

    def update_codec_indicator(self):
        mode = audio_state.codec_preview_mode
        self.codec_indicator.setText(f"CODEC: {mode}")

        if mode == "REAL OPUS":
            style = """
                background: #1f5637; color: #d4ffdf;
                padding: 6px; border-radius: 4px;
            """
        elif mode == "OPUS APPROX":
            style = """
                background: #66520e; color: #fff3b0;
                padding: 6px; border-radius: 4px;
            """
        elif mode == "REAL AAC":
            style = """
                background: #1f5637; color: #d4ffdf;
                padding: 6px; border-radius: 4px;
            """
        elif mode == "AAC APPROX":
            style = """
                background: #203a4a; color: #b8e8ff;
                padding: 6px; border-radius: 4px;
            """
        elif mode == "BYPASS":
            style = """
                background: #66520e; color: #fff3b0;
                padding: 6px; border-radius: 4px;
            """
        else:
            style = """
                background: #303030; color: #d0d0d0;
                padding: 6px; border-radius: 4px;
            """

        self.codec_indicator.setStyleSheet(style)

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

        youtube_volume_percent = 100.0 * (
            10.0 ** (audio_state.youtube_gain_db / 20.0)
        )

        self.youtube_gain_indicator.setText(
            f"YT: {audio_state.youtube_gain_db:+.1f} dB "
            f"/ {youtube_volume_percent:.0f}%"
        )

        self.update_headroom_indicator()
        self.update_input_signal_indicator()
        self.update_lufs_time_indicator()
        self.update_codec_indicator()

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

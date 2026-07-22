import math
import time
from datetime import datetime
import sounddevice as sd

from PyQt6.QtCore import QByteArray, QEvent, Qt, QTimer
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QFrame, QFileDialog, QGridLayout, QHBoxLayout,
    QInputDialog, QLabel, QMainWindow, QMessageBox, QPushButton, QScrollArea,
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
        self.saved_settings = load_settings() or {}
        self.last_candidate_report = ""
        self.current_language = self.saved_settings.get(
            "preview_settings", {}
        ).get("language", "ja")

        self.rate_values = [44100, 48000, 96000]
        self.buffer_values = [256, 512, 1024, 2048, 4096]
        self.opus_bitrate_values = [96, 128, 160]
        self.limiter_ceiling_values = [-1.0, -2.0, -3.0]
        self.normalizer_target_values = [-14.0, -16.0, -23.0]
        self.youtube_target_lufs = -14.0

        self.setWindowTitle("Stream Audio Monitor")
        self.resize(1100, 1200)

        apply_theme(self, "Studio Dark")

        central = QWidget()
        self.setCentralWidget(central)

        layout = QVBoxLayout(central)
        layout.setSpacing(12)

        self.title_label = QLabel("Stream Audio Monitor")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setStyleSheet("font-size: 22pt; font-weight: bold;")
        self.language_button = QPushButton()
        self.language_button.clicked.connect(self.toggle_language)

        title_row = QHBoxLayout()
        title_row.addStretch()
        title_row.addWidget(self.title_label, 1)
        title_row.addWidget(self.language_button)
        layout.addLayout(title_row)
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

        self.youtube_readiness_indicator = QLabel(
            "YouTube Check: measuring..."
        )
        self.youtube_readiness_indicator.setStyleSheet(
            """
            background: #303030; color: #d0d0d0;
            padding: 6px; border-radius: 4px;
            """
        )

        self.hover_help_indicator = QLabel(
            "Help: Move the cursor over a control for an explanation."
        )
        self.hover_help_indicator.setWordWrap(True)
        self.hover_help_indicator.setStyleSheet(
            """
            background: #202a34; color: #c8e5ff;
            padding: 7px; border-radius: 4px;
            """
        )

        self.clear_clip_button = QPushButton("Clear Clip")
        self.clear_clip_button.clicked.connect(self.clear_clip)

        self.reset_lufs_button = QPushButton("Reset LUFS-I")
        self.reset_lufs_button.clicked.connect(
            self.reset_integrated_loudness
        )

        self.youtube_preset_button = QPushButton("YouTube")
        self.browser_sample_button = QPushButton("Browser Sample")
        self.browser_sample_button.clicked.connect(self.apply_browser_sample_preset)
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
        status_row.addWidget(self.browser_sample_button, 1, 5)
        status_row.addWidget(self.podcast_preset_button, 1, 3)
        status_row.addWidget(self.broadcast_preset_button, 1, 4)
        status_row.addWidget(self.youtube_readiness_indicator, 1, 6, 1, 3)
        status_row.addWidget(self.hover_help_indicator, 2, 0, 1, 9)

        layout.addLayout(status_row)
        self.configure_tooltips()
        self.apply_language()

        self.create_meters(layout)

        self.restore_preview_settings()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_gui)
        self.timer.start(16)

        QTimer.singleShot(500, self.start_audio)

    def configure_tooltips(self):
        """Keep the compact controls understandable without changing labels."""
        self.input_box.setToolTip("音を取り込む入力デバイスを選びます。")
        self.output_box.setToolTip("モニター音を出す出力デバイスを選びます。")
        self.rate_box.setToolTip("音声処理に使うサンプリングレートです。")
        self.buffer_box.setToolTip(
            "小さいほど遅延は減りますが、音が途切れる場合があります。"
        )
        self.start_button.setToolTip("音声入力・モニター・メーターを開始します。")
        self.stop_button.setToolTip("音声エンジンを完全に停止します。")
        self.clear_clip_button.setToolTip(
            "クリップ検出回数だけを 0 に戻します。"
        )
        self.reset_lufs_button.setToolTip(
            "新しい曲を測る前に押します。\n"
            "LUFS-I、CLIP、最大 True Peak の記録をリセットします。"
        )
        self.youtube_preset_button.setToolTip(
            "YouTube向けのモニター設定をまとめてONにします。\n"
            "Opus Preview、YouTube Playback Normalize、Safety Limiterを設定します。"
        )
        self.analyze_wav_button.setToolTip(
            "WAVファイル全体のLUFS、True Peak、YouTubeでの音量変化を確認します。"
        )
        self.analyze_candidates_button.setToolTip(
            "複数の候補WAVを一度に解析し、YouTube投稿時の変化を比較します。"
        )
        self.compare_wav_button.setToolTip(
            "元のWAVと書き出したプレビューWAVの測定値を比較します。"
        )
        self.export_youtube_ab_button.setToolTip(
            "元の音量に近いOpus版と、YouTube音量調整後のOpus版を2つ書き出します。"
        )
        self.export_opus_button.setToolTip(
            "Opus圧縮後のWAVを書き出します。必要ならYouTube音量調整も加えます。"
        )
        self.export_aac_button.setToolTip(
            "AAC 128 kbps圧縮後のWAVを書き出します。"
        )
        self.youtube_volume_export_checkbox.setToolTip(
            "個別のOpus/AAC書き出しに、YouTube想定の音量低下を反映します。"
        )
        self.export_codec_pack_button.setToolTip(
            "YouTube想定のOpus版とAAC版をまとめて書き出します。"
        )
        self.youtube_checkbox.setToolTip(
            "ブラウザのサンプルにはON。YouTubeの参考曲は既に圧縮済みなので通常はOFFにします。"
        )
        self.aac_checkbox.setToolTip(
            "再生中の音をAAC 128 kbps相当で聴きます。Opus Previewとは同時に使えません。"
        )
        self.mono_checkbox.setToolTip(
            "左右を中央にまとめ、モノラル再生時の聴こえ方を確認します。"
        )
        self.bass_mono_checkbox.setToolTip(
            "150 Hzより低い帯域だけをモノラルにして、低音の安定性を確認します。"
        )
        self.phone_speaker_checkbox.setToolTip(
            "スマホの小型スピーカーに近い帯域で確認します。"
        )
        self.opus_bitrate_box.setToolTip(
            "YouTube Opus Previewで使うビットレートを選びます。"
        )
        self.mute_monitor_checkbox.setToolTip(
            "音だけを消します。メーターと測定は続きます。"
        )
        self.bypass_checkbox.setToolTip(
            "プレビュー・音量調整・リミッターを通さない元の入力音を聴きます。"
        )
        self.youtube_normalize_checkbox.setToolTip(
            "YouTube基準より大きい音だけを、再生中に下げて確認します。"
        )
        self.limiter_checkbox.setToolTip(
            "設定した上限を超えないように、音のピークを抑えます。"
        )
        self.limiter_ceiling_box.setToolTip(
            "Safety Limiterの上限です。YouTube用途では -1 dBFS が目安です。"
        )
        self.normalizer_checkbox.setToolTip(
            "ライブ入力の音量を目標LUFSへ近づけるプレビューです。"
        )
        self.normalizer_target_box.setToolTip(
            "Loudness Normalizeの目標ラウドネスを選びます。"
        )
        self.theme_box.setToolTip("画面の配色を変更します。音声処理には影響しません。")
        self.calibrate_youtube_button.setToolTip(
            "実際に投稿した動画の統計情報を使い、YouTubeの音量基準をあなたの投稿に合わせます。"
        )
        self.reset_youtube_target_button.setToolTip(
            "YouTubeの基準を標準の -14 LUFS に戻します。"
        )
        self.input_signal_indicator.setToolTip("現在、入力デバイスから音が届いているかを示します。")
        self.lufs_time_indicator.setToolTip("Integrated LUFSを測定している時間です。")
        self.codec_indicator.setToolTip("現在有効な圧縮プレビューの状態です。")
        self.normalizer_gain_indicator.setToolTip("Loudness Normalizeが現在加えている音量変化です。")
        self.youtube_gain_indicator.setToolTip("YouTube Playback Normalizeの現在の音量変化と予想音量です。")
        self.headroom_indicator.setToolTip("現在のTrue Peakから0 dBTPまでに残る余裕です。")
        self.clip_indicator.setToolTip("測定開始後に検出したクリップ回数です。")
        self.youtube_readiness_indicator.setToolTip(
            "30秒以上の測定結果から、LUFS・最大True Peak・クリップを投稿前に確認します。"
        )

        hover_targets = (
            self.input_box,
            self.output_box,
            self.rate_box,
            self.buffer_box,
            self.start_button,
            self.stop_button,
            self.clear_clip_button,
            self.reset_lufs_button,
            self.youtube_preset_button,
            self.podcast_preset_button,
            self.broadcast_preset_button,
            self.analyze_wav_button,
            self.analyze_candidates_button,
            self.compare_wav_button,
            self.export_opus_button,
            self.export_aac_button,
            self.export_youtube_ab_button,
            self.export_codec_pack_button,
            self.youtube_volume_export_checkbox,
            self.youtube_checkbox,
            self.aac_checkbox,
            self.mono_checkbox,
            self.bass_mono_checkbox,
            self.phone_speaker_checkbox,
            self.opus_bitrate_box,
            self.mute_monitor_checkbox,
            self.bypass_checkbox,
            self.limiter_checkbox,
            self.limiter_ceiling_box,
            self.normalizer_checkbox,
            self.youtube_normalize_checkbox,
            self.normalizer_target_box,
            self.theme_box,
            self.calibrate_youtube_button,
            self.reset_youtube_target_button,
            self.input_signal_indicator,
            self.lufs_time_indicator,
            self.codec_indicator,
            self.normalizer_gain_indicator,
            self.youtube_gain_indicator,
            self.headroom_indicator,
            self.clip_indicator,
            self.youtube_readiness_indicator,
        )

        for widget in hover_targets:
            widget.installEventFilter(self)

    def toggle_language(self):
        language = "en" if self.current_language == "ja" else "ja"
        self.current_language = language
        self.apply_language()
        self.save_current_settings()

    def apply_language(self):
        japanese = self.current_language == "ja"

        texts = {
            "title": "ストリーム音声モニター" if japanese else "Stream Audio Monitor",
            "language": "Language: 日本語" if japanese else "Language: English",
            "start": "開始" if japanese else "Start",
            "stop": "停止" if japanese else "Stop",
            "analyze": "WAVを解析" if japanese else "Analyze WAV",
            "candidates": "候補WAVを比較" if japanese else "Analyze Candidates",
            "compare": "WAVを比較" if japanese else "Compare WAV",
            "opus_export": "Opus WAVを書き出す" if japanese else "Export Opus WAV",
            "aac_export": "AAC WAVを書き出す" if japanese else "Export AAC WAV",
            "ab_export": "YouTube A/Bを書き出す" if japanese else "Export YouTube A/B",
            "pack_export": "コーデックパックを書き出す" if japanese else "Export Codec Pack",
            "youtube_volume": "YouTube音量を反映" if japanese else "Apply YouTube Volume",
            "opus_preview": "YouTube Opusプレビュー" if japanese else "YouTube Opus Preview",
            "aac_preview": "AACプレビュー" if japanese else "AAC Preview",
            "mono": "モノラルプレビュー" if japanese else "Mono Preview",
            "bass_mono": "低音をモノラル化 (150 Hz)" if japanese else "Bass Mono (150 Hz)",
            "phone": "スマホスピーカープレビュー" if japanese else "Phone Speaker Preview",
            "mute": "モニターをミュート" if japanese else "Mute Monitor",
            "bypass": "エフェクトをバイパス" if japanese else "Bypass Effects",
            "limiter": "セーフティリミッター" if japanese else "Safety Limiter",
            "normalize": "ラウドネスノーマライズ" if japanese else "Loudness Normalize",
            "youtube_normalize": "YouTube再生ノーマライズ" if japanese else "YouTube Playback Normalize",
            "clear_clip": "クリップを消去" if japanese else "Clear Clip",
            "reset_lufs": "LUFS-Iをリセット" if japanese else "Reset LUFS-I",
            "youtube": "YouTube" if japanese else "YouTube",
            "podcast": "ポッドキャスト" if japanese else "Podcast",
            "broadcast": "放送" if japanese else "Broadcast",
            "calibrate": "YouTubeを調整" if japanese else "Calibrate YouTube",
            "reset_yt": "YT基準をリセット" if japanese else "Reset YT Ref",
            "input": "入力" if japanese else "Input",
            "output": "出力" if japanese else "Output",
            "rate": "レート" if japanese else "Rate",
            "buffer": "バッファ" if japanese else "Buffer",
            "opus": "Opus" if japanese else "Opus",
            "ceiling": "上限" if japanese else "Ceiling",
            "target": "目標" if japanese else "Target",
            "skin": "スキン" if japanese else "Skin",
            "monitor_note": (
                "ミュート中もメーターは動作します。バイパスは元の入力音を再生します。"
                if japanese else "Mute keeps meters running. Bypass plays the raw input."
            ),
            "youtube_note": (
                "YouTubeの詳細統計にある正規化音量の％を使います。"
                if japanese else "Use the normalized volume % from YouTube Stats for Nerds."
            ),
            "help": (
                "ヘルプ: 操作項目にカーソルを合わせると説明を表示します。"
                if japanese else "Help: Move the cursor over a control for an explanation."
            ),
        }

        self.title_label.setText(texts["title"])
        self.language_button.setText(texts["language"])
        self.start_button.setText(texts["start"])
        self.stop_button.setText(texts["stop"])
        self.analyze_wav_button.setText(texts["analyze"])
        self.analyze_candidates_button.setText(texts["candidates"])
        self.compare_wav_button.setText(texts["compare"])
        self.export_opus_button.setText(texts["opus_export"])
        self.export_aac_button.setText(texts["aac_export"])
        self.export_youtube_ab_button.setText(texts["ab_export"])
        self.export_codec_pack_button.setText(texts["pack_export"])
        self.youtube_volume_export_checkbox.setText(texts["youtube_volume"])
        self.youtube_checkbox.setText(texts["opus_preview"])
        if not japanese:
            self.youtube_checkbox.setText("Opus Preview (YouTube)")
        self.aac_checkbox.setText(texts["aac_preview"])
        self.mono_checkbox.setText(texts["mono"])
        self.bass_mono_checkbox.setText(texts["bass_mono"])
        self.phone_speaker_checkbox.setText(texts["phone"])
        self.mute_monitor_checkbox.setText(texts["mute"])
        self.bypass_checkbox.setText(texts["bypass"])
        self.limiter_checkbox.setText(texts["limiter"])
        self.normalizer_checkbox.setText(texts["normalize"])
        self.youtube_normalize_checkbox.setText(texts["youtube_normalize"])
        self.clear_clip_button.setText(texts["clear_clip"])
        self.reset_lufs_button.setText(texts["reset_lufs"])
        self.youtube_preset_button.setText(texts["youtube"])
        self.podcast_preset_button.setText(texts["podcast"])
        self.broadcast_preset_button.setText(texts["broadcast"])
        self.calibrate_youtube_button.setText(texts["calibrate"])
        self.reset_youtube_target_button.setText(texts["reset_yt"])
        self.input_label.setText(texts["input"])
        self.output_label.setText(texts["output"])
        self.rate_label.setText(texts["rate"])
        self.buffer_label.setText(texts["buffer"])
        self.opus_label.setText(texts["opus"])
        self.ceiling_label.setText(texts["ceiling"])
        self.target_label.setText(texts["target"])
        self.skin_label.setText(texts["skin"])
        self.monitor_note_label.setText(texts["monitor_note"])
        self.youtube_note_label.setText(texts["youtube_note"])
        self.default_help_text = texts["help"]
        self.hover_help_indicator.setText(self.default_help_text)

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.Enter:
            description = watched.toolTip()
            if description:
                self.hover_help_indicator.setText(f"Help: {description}")
        elif event.type() == QEvent.Type.Leave:
            self.hover_help_indicator.setText(self.default_help_text)

        return super().eventFilter(watched, event)

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
        self.analyze_candidates_button = QPushButton("Analyze Candidates")
        self.compare_wav_button = QPushButton("Compare WAV")
        self.export_opus_button = QPushButton("Export Opus WAV")
        self.export_aac_button = QPushButton("Export AAC WAV")
        self.export_youtube_ab_button = QPushButton("Export YouTube A/B")
        self.export_codec_pack_button = QPushButton("Export Codec Pack")
        self.youtube_volume_export_checkbox = QCheckBox(
            "Apply YouTube Volume"
        )
        self.youtube_volume_export_checkbox.setChecked(True)

        self.youtube_checkbox = QCheckBox("Opus Preview (YouTube)")
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
        self.youtube_target_label = QLabel("YT Ref: -14.0 LUFS")
        self.calibrate_youtube_button = QPushButton("Calibrate YouTube")
        self.reset_youtube_target_button = QPushButton("Reset YT Ref")

        self.load_devices()

        self.opus_bitrate_box.setCurrentIndex(
            self.opus_bitrate_values.index(128)
        )

        device_row = QHBoxLayout()
        self.input_label = QLabel("Input")
        self.output_label = QLabel("Output")
        self.rate_label = QLabel("Rate")
        self.buffer_label = QLabel("Buffer")
        device_row.addWidget(self.input_label)
        device_row.addWidget(self.input_box, 2)
        device_row.addWidget(self.output_label)
        device_row.addWidget(self.output_box, 2)
        device_row.addWidget(self.rate_label)
        device_row.addWidget(self.rate_box)
        device_row.addWidget(self.buffer_label)
        device_row.addWidget(self.buffer_box)
        device_row.addWidget(self.start_button)
        device_row.addWidget(self.stop_button)
        layout.addLayout(device_row)

        export_row = QHBoxLayout()
        export_row.addWidget(self.analyze_wav_button)
        export_row.addWidget(self.analyze_candidates_button)
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
        self.opus_label = QLabel("Opus")
        preview_row.addWidget(self.opus_label)
        preview_row.addWidget(self.opus_bitrate_box)
        preview_row.addStretch()
        layout.addLayout(preview_row)

        monitor_row = QHBoxLayout()
        monitor_row.addWidget(self.mute_monitor_checkbox)
        monitor_row.addWidget(self.bypass_checkbox)
        self.monitor_note_label = QLabel(
            "Mute keeps meters running. Bypass plays the raw input."
        )
        monitor_row.addWidget(self.monitor_note_label)
        monitor_row.addStretch()
        layout.addLayout(monitor_row)

        processing_row = QHBoxLayout()
        processing_row.addWidget(self.limiter_checkbox)
        self.ceiling_label = QLabel("Ceiling")
        self.target_label = QLabel("Target")
        self.skin_label = QLabel("Skin")
        processing_row.addWidget(self.ceiling_label)
        processing_row.addWidget(self.limiter_ceiling_box)
        processing_row.addWidget(self.normalizer_checkbox)
        processing_row.addWidget(self.youtube_normalize_checkbox)
        processing_row.addWidget(self.target_label)
        processing_row.addWidget(self.normalizer_target_box)
        processing_row.addWidget(self.skin_label)
        processing_row.addWidget(self.theme_box)
        processing_row.addStretch()
        layout.addLayout(processing_row)

        youtube_row = QHBoxLayout()
        youtube_row.addWidget(self.youtube_target_label)
        youtube_row.addWidget(self.calibrate_youtube_button)
        youtube_row.addWidget(self.reset_youtube_target_button)
        self.youtube_note_label = QLabel(
            "Use the normalized volume % from YouTube Stats for Nerds."
        )
        youtube_row.addWidget(self.youtube_note_label)
        youtube_row.addStretch()
        layout.addLayout(youtube_row)

        self.start_button.clicked.connect(self.start_audio)
        self.stop_button.clicked.connect(self.stop_audio)
        self.analyze_wav_button.clicked.connect(self.analyze_wav_file)
        self.analyze_candidates_button.clicked.connect(
            self.analyze_candidate_wavs
        )
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
        self.bypass_checkbox.toggled.connect(self.update_bypass_status)
        self.calibrate_youtube_button.clicked.connect(self.calibrate_youtube)
        self.reset_youtube_target_button.clicked.connect(
            self.reset_youtube_target
        )

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
            self.set_status(
                "No usable audio device found",
                "使用できる音声デバイスがありません",
            )
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

        if started:
            self.set_status("Running", "動作中")
            self.set_audio_running_state(True)
        else:
            self.set_status("Audio error", "音声エラー")
            self.set_audio_running_state(False)

    def stop_audio(self):
        self.stop_stream()
        self.set_status("Stopped", "停止しました")
        self.set_audio_running_state(False)

    def set_audio_running_state(self, running):
        if running:
            self.start_button.setStyleSheet(
                "background: #1f7a45; color: white; font-weight: bold;"
            )
            self.stop_button.setStyleSheet("")
        else:
            self.start_button.setStyleSheet("")
            self.stop_button.setStyleSheet(
                "background: #8b1e1e; color: white; font-weight: bold;"
            )

    def set_status(self, english, japanese):
        if self.current_language == "ja":
            self.status.setText(f"状態: {japanese}")
        else:
            self.status.setText(f"Status: {english}")

    def restore_preview_settings(self):
        """Restore monitor choices saved when the app was last closed."""
        saved = self.saved_settings.get("preview_settings", {})
        if not saved:
            self.apply_language()
            return

        self.current_language = saved.get(
            "language", self.current_language
        )

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

        self.set_youtube_target(
            saved.get("youtube_target_lufs", -14.0)
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
        self.apply_language()

        geometry = saved.get("window_geometry")
        if isinstance(geometry, str):
            try:
                self.restoreGeometry(
                    QByteArray.fromBase64(geometry.encode("ascii"))
                )
            except (TypeError, ValueError):
                pass

        if saved.get("window_maximized", False):
            QTimer.singleShot(0, self.showMaximized)

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
            "youtube_target_lufs": self.youtube_target_lufs,
            "language": self.current_language,
            "window_geometry": self.saveGeometry().toBase64().data().decode(
                "ascii"
            ),
            "window_maximized": self.isMaximized(),
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
            self.set_status("Analyzing WAV...", "WAVを解析中...")
            result = analyze_wav(path, self.youtube_target_lufs)
        except (OSError, ValueError) as error:
            self.set_status("WAV analysis error", "WAV解析エラー")
            QMessageBox.warning(self, "WAV Analysis", str(error))
            return

        minutes, seconds = divmod(int(result["duration_seconds"]), 60)
        readiness = self.format_offline_youtube_readiness(result)
        message = (
            f"File: {result['name']}\n"
            f"Duration: {minutes:02d}:{seconds:02d}\n"
            f"Integrated LUFS: {result['lufs_i']:.1f}\n"
            f"Sample Peak: {result['peak_db']:.1f} dBFS\n\n"
            f"Estimated True Peak: {result['true_peak_db']:.1f} dBTP\n\n"
            f"Stereo Correlation: {result['stereo_correlation']:+.2f}\n\n"
            f"Mono Check: {self.format_stereo_check(result)}\n\n"
            "YouTube playback estimate\n"
            f"Gain: {result['youtube_gain_db']:+.1f} dB\n"
            f"Volume: {result['youtube_percent']:.0f}%\n\n"
            f"YouTube Check: {readiness}\n\n"
            "YouTube mix check\n"
            f"{result['youtube_advice']}"
        )

        self.set_status("WAV analysis complete", "WAV解析が完了しました")
        print(message.replace("\n", " | "))
        QMessageBox.information(self, "WAV Analysis", message)

    def analyze_candidate_wavs(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Select candidate WAV files",
            "",
            "WAV files (*.wav)",
        )

        if not paths:
            return

        japanese = self.current_language == "ja"
        self.set_status(
            "Analyzing candidate WAV files...",
            "候補WAVを解析中...",
        )
        results = []
        errors = []

        for path in paths:
            try:
                result = analyze_wav(path, self.youtube_target_lufs)
                results.append(result)
            except (OSError, ValueError) as error:
                errors.append(f"{path}: {error}")

        if not results:
            self.set_status("Candidate analysis error", "候補WAVの解析エラー")
            QMessageBox.warning(
                self,
                "Candidate Analysis",
                "No WAV files could be analyzed.",
            )
            return

        rows = []
        for result in results:
            readiness = self.format_offline_youtube_readiness(result)
            stereo_check = self.format_stereo_check(result)
            rows.append(
                f"{result['name']}\n"
                f"  LUFS-I: {result['lufs_i']:.1f} | "
                f"True Peak: {result['true_peak_db']:.1f} dBTP | "
                f"Correlation: {result['stereo_correlation']:+.2f}\n"
                f"  Mono Check: {stereo_check}\n"
                f"  YouTube: {result['youtube_gain_db']:+.1f} dB "
                f"({result['youtube_percent']:.0f}%) | {readiness}"
            )

        title = "候補WAVの比較" if japanese else "Candidate WAV Comparison"
        message = "\n\n".join(rows)
        if errors:
            error_title = "解析できなかったファイル" if japanese else "Files not analyzed"
            message += f"\n\n{error_title}\n" + "\n".join(errors)

        self.set_status(
            "Candidate WAV analysis complete",
            "候補WAVの解析が完了しました",
        )
        self.last_candidate_report = message
        print(message.replace("\n", " | "))
        dialog = QMessageBox(self)
        dialog.setWindowTitle(title)
        dialog.setText(message)
        save_button = dialog.addButton(
            "Save Candidate Report",
            QMessageBox.ButtonRole.ActionRole,
        )
        dialog.addButton(QMessageBox.StandardButton.Close)
        dialog.exec()
        if dialog.clickedButton() is save_button:
            self.save_candidate_report()

    def save_candidate_report(self):
        if not self.last_candidate_report:
            return

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save candidate report",
            "candidate_wav_report.txt",
            "Text files (*.txt)",
        )
        if not path:
            return

        try:
            with open(path, "w", encoding="utf-8") as report_file:
                report_file.write(
                    "Stream Audio Monitor - Candidate WAV Report\n"
                    f"Created: {datetime.now():%Y-%m-%d %H:%M:%S}\n"
                    f"YouTube Reference: {self.youtube_target_lufs:.1f} LUFS\n"
                    "=" * 60 + "\n\n"
                    + self.last_candidate_report
                )
        except OSError as error:
            QMessageBox.warning(self, "Candidate Report", str(error))
            return

        self.set_status("Candidate report saved", "候補レポートを保存しました")

    def format_offline_youtube_readiness(self, result):
        code = result["youtube_readiness"]
        japanese = self.current_language == "ja"

        if code == "TRUE_PEAK":
            return (
                f"True Peakを下げる ({result['true_peak_db']:.1f} dBTP)"
                if japanese
                else f"Lower True Peak ({result['true_peak_db']:.1f} dBTP)"
            )
        if code == "VOLUME_REDUCTION":
            gain_db = abs(result["youtube_gain_db"])
            return (
                f"音量が {gain_db:.1f} dB 下がる見込み"
                if japanese
                else f"Volume expected to decrease by {gain_db:.1f} dB"
            )
        if code == "QUIET":
            return "基準より小さめ" if japanese else "Quieter than reference"

        return "準備完了" if japanese else "READY"

    def format_stereo_check(self, result):
        check = result["stereo_check"]
        japanese = self.current_language == "ja"

        if check == "MONO":
            return "モノラル音源" if japanese else "Mono source"
        if check == "STABLE":
            return "安定" if japanese else "Stable"
        if check == "CHECK_MONO":
            return "モノラルで要確認" if japanese else "Check in mono"
        return "位相に注意" if japanese else "Phase risk"

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
            self.set_status("Comparing WAV files...", "WAVファイルを比較中...")
            result = compare_wavs(reference_path, preview_path)
        except (OSError, ValueError) as error:
            self.set_status("WAV comparison error", "WAV比較エラー")
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
            f"Stereo correlation difference: {result['correlation_difference']:+.2f}\n"
            f"Presence (4–8 kHz): {result['presence_difference_db']:+.1f} dB\n"
            f"High range (8–16 kHz): {result['high_band_difference_db']:+.1f} dB\n"
            f"Duration difference: {result['duration_difference_seconds']:+.3f} sec\n\n"
            "A negative high-range value means the preview contains less "
            "energy in that band. Use it as a comparison guide, not a score."
        )

        self.set_status("WAV comparison complete", "WAV比較が完了しました")
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
            analysis = analyze_wav(source_path, self.youtube_target_lufs)
            playback_gain_db = (
                analysis["youtube_gain_db"]
                if self.youtube_volume_export_checkbox.isChecked()
                else 0.0
            )
            self.set_status("Exporting Opus preview...", "Opusプレビューを書き出し中...")
            output_path = export_opus_preview(
                source_path,
                destination_path,
                bitrate,
                playback_gain_db,
            )
        except (OSError, RuntimeError, ValueError) as error:
            self.set_status("Opus export error", "Opus書き出しエラー")
            QMessageBox.warning(self, "Opus Export", str(error))
            return

        self.set_status("Opus preview exported", "Opusプレビューを書き出しました")
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
            analysis = analyze_wav(source_path, self.youtube_target_lufs)
            playback_gain_db = (
                analysis["youtube_gain_db"]
                if self.youtube_volume_export_checkbox.isChecked()
                else 0.0
            )
            self.set_status("Exporting AAC preview...", "AACプレビューを書き出し中...")
            output_path = export_aac_preview(
                source_path,
                destination_path,
                bitrate_kbps=128,
                playback_gain_db=playback_gain_db,
            )
        except (OSError, RuntimeError, ValueError) as error:
            self.set_status("AAC export error", "AAC書き出しエラー")
            QMessageBox.warning(self, "AAC Export", str(error))
            return

        self.set_status("AAC preview exported", "AACプレビューを書き出しました")
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
            analysis = analyze_wav(source_path, self.youtube_target_lufs)
            playback_gain_db = analysis["youtube_gain_db"]
            self.set_status(
                "Exporting YouTube A/B previews...",
                "YouTube A/Bプレビューを書き出し中...",
            )
            output_paths = export_youtube_ab_previews(
                source_path,
                destination_folder,
                bitrate,
                playback_gain_db,
            )
        except (OSError, RuntimeError, ValueError) as error:
            self.set_status("YouTube A/B export error", "YouTube A/B書き出しエラー")
            QMessageBox.warning(self, "YouTube A/B Export", str(error))
            return

        self.set_status(
            "YouTube A/B previews exported",
            "YouTube A/Bプレビューを書き出しました",
        )
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
            analysis = analyze_wav(source_path, self.youtube_target_lufs)
            playback_gain_db = analysis["youtube_gain_db"]
            self.set_status(
                "Exporting codec preview pack...",
                "コーデックプレビューパックを書き出し中...",
            )
            paths = export_codec_pack(
                source_path,
                destination_folder,
                opus_bitrate_kbps=opus_bitrate,
                aac_bitrate_kbps=128,
                youtube_gain_db=playback_gain_db,
                analysis=analysis,
                youtube_target_lufs=self.youtube_target_lufs,
            )
        except (OSError, RuntimeError, ValueError) as error:
            self.set_status("Codec pack export error", "コーデックパック書き出しエラー")
            QMessageBox.warning(self, "Codec Pack Export", str(error))
            return

        self.set_status(
            "Codec preview pack exported",
            "コーデックプレビューパックを書き出しました",
        )
        message = (
            "Created YouTube codec preview pack\n\n"
            f"YouTube gain: {playback_gain_db:+.1f} dB\n\n"
            f"Opus + YouTube volume\n{paths['opus_youtube']}\n\n"
            f"AAC + YouTube volume\n{paths['aac_youtube']}\n\n"
            f"Report\n{paths['report']}"
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

            self.set_status(
                f"YouTube Opus Preview ({bitrate} kbps)",
                f"YouTube Opusプレビュー ({bitrate} kbps)",
            )

        else:
            print("YouTube Opus Preview: OFF")
            self.set_status("Running", "動作中")

    def toggle_aac(self, enabled):
        import audio

        audio.set_aac_simulation(enabled)

        if enabled:
            self.youtube_checkbox.blockSignals(True)
            self.youtube_checkbox.setChecked(False)
            self.youtube_checkbox.blockSignals(False)

            print("AAC Preview: ON")

            self.set_status("AAC Preview (128 kbps)", "AACプレビュー (128 kbps)")

        else:
            print("AAC Preview: OFF")
            self.set_status("Running", "動作中")

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
            self.set_status("Phone Speaker Preview", "スマホスピーカープレビュー")
        else:
            self.set_status("Running", "動作中")

    def toggle_mute_monitor(self, enabled):
        import audio

        audio.set_monitor_muted(enabled)
        if enabled:
            self.set_status(
                "Monitor muted (analysis continues)",
                "モニターをミュート中（解析は続きます）",
            )
        else:
            self.set_status("Running", "動作中")

    def toggle_bypass_effects(self, enabled):
        import audio

        audio.set_bypass_effects(enabled)
        self.status.setText(
            "Status: Bypass — raw input"
            if enabled
            else "Status: Running"
        )

    def update_bypass_status(self, enabled):
        if enabled:
            self.set_status("Bypass raw input", "バイパス中 - 元の入力音")
        else:
            self.set_status("Running", "動作中")

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

    def set_youtube_target(self, target_lufs):
        import audio

        self.youtube_target_lufs = float(
            max(-24.0, min(-8.0, target_lufs))
        )
        audio.set_youtube_target(self.youtube_target_lufs)
        self.youtube_target_label.setText(
            f"YT Ref: {self.youtube_target_lufs:.1f} LUFS"
        )

    def calibrate_youtube(self):
        source_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select the WAV used in your uploaded YouTube video",
            "",
            "WAV files (*.wav)",
        )

        if not source_path:
            return

        percent, accepted = QInputDialog.getDouble(
            self,
            "YouTube normalized volume",
            "Enter the second value from 100% / XX%:",
            100.0,
            1.0,
            100.0,
            1,
        )

        if not accepted:
            return

        try:
            self.set_status(
                "Calibrating YouTube reference...",
                "YouTube基準を調整中...",
            )
            analysis = analyze_wav(source_path)
        except (OSError, ValueError) as error:
            self.set_status("YouTube calibration error", "YouTube調整エラー")
            QMessageBox.warning(self, "YouTube Calibration", str(error))
            return

        observed_gain_db = 20.0 * math.log10(percent / 100.0)
        calibrated_target = analysis["lufs_i"] + observed_gain_db
        self.set_youtube_target(calibrated_target)
        self.set_status("YouTube reference calibrated", "YouTube基準を調整しました")

        message = (
            "YouTube reference updated\n\n"
            f"Source Integrated LUFS: {analysis['lufs_i']:.1f}\n"
            f"Observed normalized volume: {percent:.0f}%\n"
            f"Observed gain: {observed_gain_db:+.1f} dB\n\n"
            f"New YouTube reference: {self.youtube_target_lufs:.1f} LUFS"
        )
        print(message.replace("\n", " | "))
        QMessageBox.information(self, "YouTube Calibration", message)

    def reset_youtube_target(self):
        self.set_youtube_target(-14.0)
        self.set_status(
            "YouTube reference reset to -14 LUFS",
            "YouTube基準を -14 LUFS に戻しました",
        )
        print("YouTube reference: RESET to -14.0 LUFS")

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
        audio.reset_clip_counter()
        self.lufs_i_meter.set_level(-70.0)
        self.clip_indicator.setText("CLIP: 0")
        self.set_status("Integrated LUFS reset", "Integrated LUFSをリセットしました")

        print("Integrated LUFS and clip counter: RESET")

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

        japanese_names = {
            "YouTube": "YouTube",
            "Podcast": "ポッドキャスト",
            "Broadcast": "放送",
        }
        self.set_status(
            f"{name} preset applied",
            f"{japanese_names.get(name, name)}プリセットを適用しました",
        )
        print(
            f"Preset: {name} "
            f"({target_lufs:.0f} LUFS, {limiter_ceiling:.0f} dBFS)"
        )

    def apply_browser_sample_preset(self):
        self.youtube_normalize_checkbox.setChecked(False)
        self.normalizer_checkbox.setChecked(False)
        self.youtube_checkbox.setChecked(True)
        self.aac_checkbox.setChecked(False)
        self.set_status("Browser sample Opus preview", "ブラウザサンプル用Opusプレビュー")

    def update_headroom_indicator(self):
        headroom_db = -audio_state.true_peak_db
        label = "余裕" if self.current_language == "ja" else "Headroom"

        self.headroom_indicator.setText(
            f"{label}: {headroom_db:.1f} dB"
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
        japanese = self.current_language == "ja"

        if input_peak_db >= -40.0:
            text = "入力: 信号あり" if japanese else "INPUT: SIGNAL"
            style = """
                background: #1f5637; color: #d4ffdf;
                padding: 6px; border-radius: 4px;
            """
        elif input_peak_db > -60.0:
            text = "入力: 小さい" if japanese else "INPUT: LOW"
            style = """
                background: #66520e; color: #fff3b0;
                padding: 6px; border-radius: 4px;
            """
        else:
            text = "入力: 無音" if japanese else "INPUT: SILENT"
            style = """
                background: #4a2525; color: #ffd6d6;
                padding: 6px; border-radius: 4px;
            """

        self.input_signal_indicator.setText(text)
        self.input_signal_indicator.setStyleSheet(style)

    def update_lufs_time_indicator(self):
        total_seconds = int(audio_state.lufs_measurement_seconds)
        minutes, seconds = divmod(total_seconds, 60)
        japanese = self.current_language == "ja"

        if total_seconds < 30:
            progress = "開始" if japanese else "START"
        elif total_seconds < 120:
            progress = "測定中" if japanese else "MEASURING"
        else:
            progress = "長時間" if japanese else "LONG"

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

    def update_youtube_readiness_indicator(self):
        """Show a simple posting check from the live measurements."""
        measured_seconds = audio_state.lufs_measurement_seconds
        max_true_peak_db = audio_state.max_true_peak_db
        lufs_i = audio_state.lufs_i
        japanese = self.current_language == "ja"
        title = "YouTube確認" if japanese else "YouTube Check"

        if measured_seconds < 30.0:
            remaining = max(0, int(30.0 - measured_seconds))
            progress = "測定中" if japanese else "measuring"
            text = f"{title}: {progress} ({remaining}s)"
            style = """
                background: #303030; color: #d0d0d0;
                padding: 6px; border-radius: 4px;
            """
        elif audio_state.clip_count > 0:
            result = "クリップを修正" if japanese else "FIX CLIP"
            text = f"{title}: {result}"
            style = """
                background: #8b1e1e; color: white;
                padding: 6px; border-radius: 4px;
            """
        elif max_true_peak_db > -1.0:
            result = "True Peakを下げる" if japanese else "lower true peak"
            text = (
                f"{title}: {result} "
                f"(max {max_true_peak_db:.1f} dBTP)"
            )
            style = """
                background: #8b1e1e; color: white;
                padding: 6px; border-radius: 4px;
            """
        elif lufs_i > self.youtube_target_lufs + 0.5:
            gain_db = self.youtube_target_lufs - lufs_i
            volume = "音量" if japanese else "volume"
            text = f"{title}: {volume} -{abs(gain_db):.1f} dB"
            style = """
                background: #66520e; color: #fff3b0;
                padding: 6px; border-radius: 4px;
            """
        elif lufs_i < self.youtube_target_lufs - 3.0:
            result = "基準より小さめ" if japanese else "quieter than reference"
            text = f"{title}: {result}"
            style = """
                background: #203a4a; color: #b8e8ff;
                padding: 6px; border-radius: 4px;
            """
        else:
            result = "準備完了" if japanese else "READY"
            text = f"{title}: {result}"
            style = """
                background: #1f5637; color: #d4ffdf;
                padding: 6px; border-radius: 4px;
            """

        self.youtube_readiness_indicator.setText(text)
        self.youtube_readiness_indicator.setStyleSheet(style)

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

        clip_label = "クリップ" if self.current_language == "ja" else "CLIP"
        self.clip_indicator.setText(f"{clip_label}: {audio_state.clip_count}")

        normalize_label = (
            "正規化" if self.current_language == "ja" else "Normalize"
        )
        self.normalizer_gain_indicator.setText(
            f"{normalize_label}: {audio_state.normalizer_gain_db:+.1f} dB"
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
        self.update_youtube_readiness_indicator()

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

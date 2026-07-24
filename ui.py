import math
import time
from datetime import datetime
from pathlib import Path
import sounddevice as sd

from PyQt6.QtCore import QByteArray, QEvent, Qt, QTimer
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFrame,
    QFileDialog, QGridLayout, QHBoxLayout, QInputDialog, QLabel, QMainWindow,
    QLineEdit, QMessageBox, QPlainTextEdit, QProgressDialog, QPushButton, QScrollArea,
    QVBoxLayout, QWidget,
)

from app_info import support_environment_text
from audio_state import audio_state
from aac_exporter import aac_support_error, export_aac_preview
from file_analyzer import analyze_opus_impact, analyze_wav, compare_wavs
from ffmpeg_tools import describe_ffmpeg_source
from opus_exporter import (
    export_opus_delta, export_opus_preview, export_youtube_ab_previews,
    opus_support_error,
)
from preview_pack import export_codec_pack
from settings import load_settings, save_settings
from themes import apply_theme, theme_names
from widgets import (
    AudioMeter, CorrelationWidget, PhaseScopeWidget,
    CodecDifferenceWidget, SpectrumWidget, WaveformWidget,
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
        self.debug_events = []
        self.last_debug_status = ""
        self.last_support_error_code = ""
        self.last_support_error_detail = ""
        self.last_runtime_error_count = 0
        self.audio_engine_started = False
        self.active_audio_config = None
        self.codec_focus_enabled = False
        self.developer_mode = self.saved_settings.get(
            "preview_settings", {}
        ).get("developer_mode", False)
        self.last_file_tools_output_folder = self.saved_settings.get(
            "preview_settings", {}
        ).get("file_tools_output_folder", "")
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
        self.resize(1480, 960)
        self.setMinimumSize(1060, 760)

        apply_theme(self, "Stream Neon")

        central = QWidget()
        central.setObjectName("appShell")
        self.setCentralWidget(central)

        layout = QVBoxLayout(central)
        layout.setContentsMargins(24, 20, 24, 18)
        layout.setSpacing(14)

        self.title_label = QLabel("Stream Audio Monitor")
        self.title_label.setObjectName("productTitle")
        self.subtitle_label = QLabel("REAL-TIME CODEC PREVIEW & MONITORING")
        self.subtitle_label.setObjectName("productSubtitle")
        self.brand_badge = QLabel("SAM")
        self.brand_badge.setObjectName("brandBadge")
        self.brand_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ready_label = QLabel("●  READY\nMonitoring Idle")
        self.ready_label.setObjectName("readyLabel")
        self.language_button = QPushButton()
        self.language_button.clicked.connect(self.toggle_language)
        self.developer_mode_button = QPushButton()
        self.developer_mode_button.clicked.connect(self.toggle_developer_mode)
        self.debug_log_button = QPushButton()
        self.debug_log_button.clicked.connect(self.show_debug_log)
        self.debug_log_placeholder = QWidget()

        header_frame = QFrame()
        header_frame.setObjectName("appHeader")
        title_row = QHBoxLayout(header_frame)
        title_row.setContentsMargins(16, 12, 16, 12)
        title_row.setSpacing(14)
        title_row.addWidget(self.brand_badge)
        title_stack = QVBoxLayout()
        title_stack.setSpacing(1)
        title_stack.addWidget(self.title_label)
        title_stack.addWidget(self.subtitle_label)
        title_row.addLayout(title_stack, 1)
        title_row.addWidget(self.ready_label)
        title_row.addWidget(self.developer_mode_button)
        title_row.addWidget(self.debug_log_button)
        title_row.addWidget(self.debug_log_placeholder)
        title_row.addWidget(self.language_button)
        layout.addWidget(header_frame)
        layout.addWidget(self.create_settings_panel())

        status_row = QGridLayout()
        status_row.setHorizontalSpacing(8)
        status_row.setVerticalSpacing(6)

        self.status = QLabel("Status: Ready")
        self.latency_indicator = QLabel("Base latency: -- ms")

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

        self.issue_indicator = QLabel()
        self.issue_indicator.setStyleSheet(
            "background: #6e2020; color: #ffe0e0; padding: 6px; border-radius: 4px;"
        )
        self.issue_indicator.setVisible(False)
        self.copy_support_button = QPushButton()
        self.copy_support_button.setVisible(False)
        self.copy_support_button.clicked.connect(self.copy_support_info)

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
        status_row.addWidget(self.latency_indicator, 0, 9)
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
        status_row.addWidget(self.issue_indicator, 2, 0, 1, 3)
        status_row.addWidget(self.copy_support_button, 2, 3)
        status_row.addWidget(self.hover_help_indicator, 3, 0, 1, 9)

        layout.addLayout(status_row)
        self.configure_tooltips()
        self.apply_language()

        self.create_meters(layout)

        self.set_developer_mode(self.developer_mode)
        self.restore_preview_settings()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_gui)
        self.timer.start(16)

        QTimer.singleShot(0, self.check_opus_support_at_startup)
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
        self.stop_button.setToolTip(
            "SAMの処理を外し、元の入力音をそのまま再生します。"
        )
        self.refresh_devices_button.setToolTip(
            "USBオーディオ機器やVB-CABLEを抜き差しした後、デバイス一覧を更新します。"
        )
        self.routing_help_button.setToolTip(
            "ブラウザ、SAM、DAW、オーディオインターフェースの音の通り道を表示します。"
        )
        self.system_check_button.setToolTip(
            "現在の音声設定とコーデック対応状況を確認・コピーします。"
        )
        self.file_tools_button.setToolTip(
            "WAVの解析とプレビュー書き出しを、元ファイルと保存先を指定して行います。"
        )
        self.copy_support_button.setToolTip(
            "エラーコード、音声設定、直近の操作履歴をコピーして報告できます。"
        )
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
        self.youtube_reference_button.setToolTip(
            "すでに圧縮済みのYouTube参考曲を聴く時に押します。\n"
            "Opus/AACとYouTube音量シミュレーションをOFFにして二重処理を防ぎます。"
        )
        self.analyze_wav_button.setToolTip(
            "WAVファイル全体のLUFS、True Peak、YouTubeでの音量変化を確認します。"
        )
        self.analyze_candidates_button.setToolTip(
            "複数の候補WAVを一度に解析し、YouTube投稿時の変化を比較します。"
        )
        self.analyze_candidate_folder_button.setToolTip(
            "フォルダ内のWAVをまとめて解析します。サブフォルダは含みません。"
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
        self.export_delta_button.setToolTip(
            "Export only the sound changed by Opus, for offline listening."
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
        self.codec_delta_checkbox.setToolTip(
            "Hear only the sound changed by Opus or AAC. Use with a codec preview."
        )
        self.codec_focus_button.setToolTip(
            "Hide general meters and focus on the spectrum and codec difference."
        )
        self.reset_codec_difference_button.setToolTip(
            "Clear the held codec-difference graph before comparing a new sound."
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
            self.developer_mode_button,
            self.debug_log_button,
            self.copy_support_button,
            self.input_box,
            self.output_box,
            self.rate_box,
            self.buffer_box,
            self.start_button,
            self.stop_button,
            self.refresh_devices_button,
            self.routing_help_button,
            self.system_check_button,
            self.file_tools_button,
            self.clear_clip_button,
            self.reset_lufs_button,
            self.youtube_preset_button,
            self.youtube_reference_button,
            self.podcast_preset_button,
            self.broadcast_preset_button,
            self.analyze_wav_button,
            self.analyze_candidates_button,
            self.analyze_candidate_folder_button,
            self.compare_wav_button,
            self.export_opus_button,
            self.export_delta_button,
            self.export_aac_button,
            self.export_youtube_ab_button,
            self.export_codec_pack_button,
            self.youtube_volume_export_checkbox,
            self.youtube_checkbox,
            self.aac_checkbox,
            self.codec_delta_checkbox,
            self.codec_focus_button,
            self.reset_codec_difference_button,
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

    def toggle_developer_mode(self):
        self.set_developer_mode(not self.developer_mode)
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
            "youtube_volume": (
                "書き出しにYouTubeノーマライズを反映"
                if japanese else "Apply YouTube normalization to exports"
            ),
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
        mode_text = "開発者" if japanese else "Developer"
        mode_state = "ON" if self.developer_mode else "OFF"
        self.developer_mode_button.setText(f"{mode_text}: {mode_state}")
        self.debug_log_button.setText(
            "デバッグログ" if japanese else "Debug Log"
        )
        self.debug_log_placeholder.setFixedWidth(
            self.debug_log_button.sizeHint().width()
        )
        self.copy_support_button.setText(
            "サポート情報をコピー" if japanese else "Copy Support Info"
        )
        if self.last_support_error_code:
            issue_label = "問題" if japanese else "Issue"
            self.issue_indicator.setText(
                f"{issue_label}: {self.last_support_error_code}"
            )
        self.developer_mode_button.setToolTip(
            "WAV解析・書き出し・詳細メーターなど、開発・確認用の表示を切り替えます。"
            if japanese else
            "Show development displays such as WAV analysis, exports, and detailed meters."
        )
        self.debug_log_button.setToolTip(
            "操作履歴、音声設定、コーデック状態を表示・コピーします。"
            if japanese else
            "Show and copy the operation history, audio settings, and codec state."
        )
        self.start_button.setText("ENGAGE")
        self.stop_button.setText(
            "DISENGAGE" if not japanese else "DISENGAGE / バイパス"
        )
        self.refresh_devices_button.setText(
            "デバイス更新" if japanese else "Refresh Devices"
        )
        self.routing_help_button.setText(
            "音の経路" if japanese else "Routing Help"
        )
        self.system_check_button.setText(
            "システム確認" if japanese else "System Check"
        )
        self.file_tools_button.setText(
            "解析 / 書き出し" if japanese else "Analyze / Export"
        )
        self.analyze_wav_button.setText(texts["analyze"])
        self.analyze_candidates_button.setText(texts["candidates"])
        self.analyze_candidate_folder_button.setText(
            "候補フォルダを比較" if japanese else "Analyze Folder"
        )
        self.analysis_label.setText(
            "WAV解析" if japanese else "WAV Analysis"
        )
        self.export_label.setText(
            "プレビュー書き出し" if japanese else "Preview Exports"
        )
        self.youtube_export_label.setText(
            "YouTube書き出し" if japanese else "YouTube Exports"
        )
        self.compare_wav_button.setText(texts["compare"])
        self.export_opus_button.setText(texts["opus_export"])
        self.export_delta_button.setText(
            "Opus差分を書き出す" if japanese else "Export Opus Delta"
        )
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
        self.youtube_reference_button.setText(
            "YouTube 参考曲" if japanese else "YouTube Reference"
        )
        self.podcast_preset_button.setText(texts["podcast"])
        self.broadcast_preset_button.setText(texts["broadcast"])
        self.calibrate_youtube_button.setText(texts["calibrate"])
        self.reset_youtube_target_button.setText(texts["reset_yt"])
        self.input_label.setText(texts["input"])
        self.output_label.setText(texts["output"])
        self.rate_label.setText(texts["rate"])
        self.buffer_label.setText(texts["buffer"])
        self.opus_label.setText(texts["opus"])
        self.engage_opus_label.setText("OPUS PREVIEW")
        self.ceiling_label.setText(texts["ceiling"])
        self.target_label.setText(texts["target"])
        self.skin_label.setText(texts["skin"])
        self.monitor_note_label.setText(texts["monitor_note"])
        self.youtube_note_label.setText(texts["youtube_note"])
        self.default_help_text = texts["help"]
        self.hover_help_indicator.setText(self.default_help_text)
        self.subtitle_label.setText(
            "REAL-TIME CODEC PREVIEW & MONITORING"
            if not japanese else "リアルタイム・コーデック・プレビュー"
        )

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.Enter:
            description = watched.toolTip()
            if description:
                self.hover_help_indicator.setText(f"Help: {description}")
        elif event.type() == QEvent.Type.Leave:
            self.hover_help_indicator.setText(self.default_help_text)

        return super().eventFilter(watched, event)

    def create_settings_panel(self):
        frame = QWidget()
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

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
        self.refresh_devices_button = QPushButton("Refresh Devices")
        self.routing_help_button = QPushButton("Routing Help")
        self.system_check_button = QPushButton("System Check")
        self.file_tools_button = QPushButton("File Tools")
        self.analyze_wav_button = QPushButton("Analyze WAV")
        self.analyze_candidates_button = QPushButton("Analyze Candidates")
        self.analyze_candidate_folder_button = QPushButton("Analyze Folder")
        self.compare_wav_button = QPushButton("Compare WAV")
        self.export_opus_button = QPushButton("Export Opus WAV")
        self.export_delta_button = QPushButton("Export Opus Delta")
        self.export_aac_button = QPushButton("Export AAC WAV")
        self.export_youtube_ab_button = QPushButton("Export YouTube A/B")
        self.export_codec_pack_button = QPushButton("Export Codec Pack")
        self.youtube_volume_export_checkbox = QCheckBox(
            "Apply YouTube Volume"
        )
        self.youtube_volume_export_checkbox.setChecked(True)

        self.youtube_checkbox = QCheckBox("Opus Preview (YouTube)")
        self.aac_checkbox = QCheckBox("AAC Preview")
        self.codec_delta_checkbox = QCheckBox("Codec Delta Monitor")
        self.codec_focus_button = QPushButton("Codec Focus: OFF")
        self.codec_focus_button.clicked.connect(self.toggle_codec_focus)
        self.reset_codec_difference_button = QPushButton("Reset Codec Diff")
        self.reset_codec_difference_button.clicked.connect(
            self.reset_codec_difference
        )
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
        self.opus_label = QLabel("Opus")
        self.youtube_target_label = QLabel("YT Ref: -14.0 LUFS")
        self.calibrate_youtube_button = QPushButton("Calibrate YouTube")
        self.reset_youtube_target_button = QPushButton("Reset YT Ref")
        self.youtube_reference_button = QPushButton("YouTube Reference")

        self.load_devices()

        self.opus_bitrate_box.setCurrentIndex(
            self.opus_bitrate_values.index(128)
        )

        self.input_label = QLabel("Input")
        self.output_label = QLabel("Output")
        self.rate_label = QLabel("Rate")
        self.buffer_label = QLabel("Buffer")
        self.analysis_label = QLabel("WAV Analysis")
        self.export_label = QLabel("Preview Exports")
        self.youtube_export_label = QLabel("YouTube Exports")
        self.monitor_note_label = QLabel(
            "Mute keeps meters running. Bypass plays the raw input."
        )
        self.ceiling_label = QLabel("Ceiling")
        self.target_label = QLabel("Target")
        self.skin_label = QLabel("Skin")
        self.youtube_note_label = QLabel(
            "Use the normalized volume % from YouTube Stats for Nerds."
        )

        def make_card(title, accent, description=""):
            card = QFrame()
            card.setObjectName(f"{accent}Card")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(18, 16, 18, 16)
            card_layout.setSpacing(10)
            title_label = QLabel(title)
            title_label.setObjectName("cardTitle")
            if accent == "purple":
                title_label.setObjectName("purpleTitle")
            elif accent == "pink":
                title_label.setObjectName("pinkTitle")
            card_layout.addWidget(title_label)
            if description:
                description_label = QLabel(description)
                description_label.setObjectName("cardDescription")
                description_label.setWordWrap(True)
                card_layout.addWidget(description_label)
            return card, card_layout

        cards = QGridLayout()
        cards.setHorizontalSpacing(16)
        cards.setVerticalSpacing(16)
        cards.setColumnStretch(0, 1)
        cards.setColumnStretch(1, 1)
        cards.setColumnStretch(2, 1)

        preview_card, preview_layout = make_card(
            "AAC PREVIEW", "cyan", "AAC圧縮をリアルタイムでシミュレート"
        )
        self.aac_checkbox.setObjectName("accentButton")
        preview_layout.addWidget(self.aac_checkbox)
        preview_layout.addStretch()
        cards.addWidget(preview_card, 0, 0)

        delta_card, delta_layout = make_card(
            "DELTA MONITOR", "purple",
            "変化した部分（差分）だけを聴く"
        )
        self.codec_delta_checkbox.setObjectName("accentButton")
        delta_layout.addWidget(self.codec_delta_checkbox)
        delta_layout.addStretch()
        cards.addWidget(delta_card, 0, 1)

        tools_card, tools_layout = make_card(
            "ANALYZE / EXPORT", "pink",
            "解析・比較・書き出しをまとめて実行"
        )
        self.file_tools_button.setObjectName("accentButton")
        tools_layout.addStretch()
        tools_layout.addWidget(self.file_tools_button)
        tools_layout.addStretch()
        cards.addWidget(tools_card, 0, 2)

        input_card, input_layout = make_card("AUDIO INPUT", "cyan")
        input_layout.addWidget(self.input_label)
        input_layout.addWidget(self.input_box)
        input_options = QGridLayout()
        input_options.addWidget(self.rate_label, 0, 0)
        input_options.addWidget(self.buffer_label, 0, 1)
        input_options.addWidget(self.rate_box, 1, 0)
        input_options.addWidget(self.buffer_box, 1, 1)
        input_layout.addLayout(input_options)
        input_layout.addWidget(self.refresh_devices_button)
        cards.addWidget(input_card, 1, 0)

        engage_card = QFrame()
        engage_card.setObjectName("engageCard")
        engage_layout = QVBoxLayout(engage_card)
        engage_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        engage_layout.setSpacing(5)
        self.engage_opus_label = QLabel("OPUS PREVIEW")
        self.engage_opus_label.setObjectName("purpleTitle")
        self.engage_opus_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.youtube_checkbox.setObjectName("accentButton")
        self.youtube_checkbox.setText("Opus Preview")
        opus_controls = QHBoxLayout()
        opus_controls.addWidget(self.opus_label)
        opus_controls.addWidget(self.opus_bitrate_box)
        engage_layout.addWidget(
            self.engage_opus_label, 0, Qt.AlignmentFlag.AlignCenter
        )
        engage_layout.addWidget(
            self.youtube_checkbox, 0, Qt.AlignmentFlag.AlignCenter
        )
        engage_layout.addLayout(opus_controls)
        self.start_button.setObjectName("engageButton")
        self.start_button.setFixedSize(300, 300)
        self.stop_button.setObjectName("secondaryButton")
        self.stop_button.setMaximumWidth(180)
        engage_layout.addWidget(
            self.start_button, 0, Qt.AlignmentFlag.AlignCenter
        )
        engage_layout.addWidget(
            self.stop_button, 0, Qt.AlignmentFlag.AlignCenter
        )
        cards.addWidget(engage_card, 1, 1)

        output_card, output_layout = make_card("AUDIO OUTPUT", "cyan")
        output_layout.addWidget(self.output_label)
        output_layout.addWidget(self.output_box)
        output_layout.addWidget(self.routing_help_button)
        output_layout.addWidget(self.system_check_button)
        output_layout.addStretch()
        cards.addWidget(output_card, 1, 2)

        layout.addLayout(cards)

        self.developer_panel = QFrame()
        self.developer_panel.setObjectName("neonCard")
        developer_layout = QVBoxLayout(self.developer_panel)
        developer_layout.setContentsMargins(14, 12, 14, 12)
        developer_layout.setSpacing(8)
        developer_title = QLabel("DEVELOPER CONTROLS")
        developer_title.setObjectName("purpleTitle")
        developer_layout.addWidget(developer_title)

        preview_row = QHBoxLayout()
        for widget in (
            self.mono_checkbox, self.bass_mono_checkbox,
            self.phone_speaker_checkbox, self.mute_monitor_checkbox,
            self.bypass_checkbox, self.codec_focus_button,
            self.reset_codec_difference_button,
        ):
            preview_row.addWidget(widget)
        preview_row.addStretch()
        developer_layout.addLayout(preview_row)

        processing_row = QHBoxLayout()
        for widget in (
            self.limiter_checkbox, self.ceiling_label, self.limiter_ceiling_box,
            self.normalizer_checkbox, self.youtube_normalize_checkbox,
            self.target_label, self.normalizer_target_box, self.skin_label,
            self.theme_box,
        ):
            processing_row.addWidget(widget)
        processing_row.addStretch()
        developer_layout.addLayout(processing_row)

        youtube_row = QHBoxLayout()
        for widget in (
            self.youtube_target_label, self.calibrate_youtube_button,
            self.reset_youtube_target_button, self.youtube_reference_button,
            self.monitor_note_label, self.youtube_note_label,
        ):
            youtube_row.addWidget(widget)
        youtube_row.addStretch()
        developer_layout.addLayout(youtube_row)

        analysis_row = QHBoxLayout()
        for widget in (
            self.analyze_wav_button, self.analyze_candidates_button,
            self.analyze_candidate_folder_button, self.compare_wav_button,
            self.export_opus_button, self.export_delta_button,
            self.export_aac_button, self.export_youtube_ab_button,
            self.export_codec_pack_button, self.youtube_volume_export_checkbox,
        ):
            analysis_row.addWidget(widget)
        analysis_row.addStretch()
        developer_layout.addLayout(analysis_row)
        layout.addWidget(self.developer_panel)

        self.start_button.clicked.connect(self.start_audio)
        self.stop_button.clicked.connect(self.stop_audio)
        self.refresh_devices_button.clicked.connect(self.refresh_devices)
        self.routing_help_button.clicked.connect(self.show_routing_guide)
        self.system_check_button.clicked.connect(self.show_system_check)
        self.file_tools_button.clicked.connect(self.show_file_tools)
        self.analyze_wav_button.clicked.connect(self.analyze_wav_file)
        self.analyze_candidates_button.clicked.connect(
            self.analyze_candidate_wavs
        )
        self.analyze_candidate_folder_button.clicked.connect(
            self.analyze_candidate_folder
        )
        self.compare_wav_button.clicked.connect(self.compare_wav_files)
        self.export_opus_button.clicked.connect(self.export_opus_wav)
        self.export_delta_button.clicked.connect(self.export_opus_delta_wav)
        self.export_aac_button.clicked.connect(self.export_aac_wav)
        self.export_youtube_ab_button.clicked.connect(
            self.export_youtube_ab_wavs
        )
        self.export_codec_pack_button.clicked.connect(
            self.export_codec_pack_wavs
        )

        self.youtube_checkbox.toggled.connect(self.toggle_opus)
        self.aac_checkbox.toggled.connect(self.toggle_aac)
        self.codec_delta_checkbox.toggled.connect(self.toggle_codec_delta)
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
        self.youtube_reference_button.clicked.connect(
            self.apply_youtube_reference_preset
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

        # Make the transport state obvious before the first Start click.
        self.set_audio_running_state(False)

        return frame

    def create_meters(self, layout):
        scroll_area = QScrollArea()
        self.meter_scroll_area = scroll_area
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
        self.codec_difference = CodecDifferenceWidget()

        self.detail_meter_widgets = (
            self.peak_meter,
            self.true_peak_meter,
            self.rms_meter,
            self.lufs_m_meter,
            self.lufs_s_meter,
            self.lufs_i_meter,
            self.correlation_meter,
            self.phase_scope,
            self.waveform,
        )

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
            self.codec_difference,
        ):
            meter_layout.addWidget(widget)

        meter_layout.addStretch()
        scroll_area.setWidget(meter_container)
        layout.addWidget(scroll_area, 1)

    def load_devices(self, preferred_input=None, preferred_output=None):
        restore_audio_settings = (
            preferred_input is None and preferred_output is None
        )
        if preferred_input is None and self.input_devices:
            preferred_input = self.input_devices[self.input_box.currentIndex()]
        if preferred_output is None and self.output_devices:
            preferred_output = self.output_devices[self.output_box.currentIndex()]

        self.input_devices.clear()
        self.output_devices.clear()
        self.input_box.clear()
        self.output_box.clear()
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

        selected_input = preferred_input
        if selected_input is None:
            selected_input = saved.get("input_device")
        selected_output = preferred_output
        if selected_output is None:
            selected_output = saved.get("output_device")

        if selected_input in self.input_devices:
            self.input_box.setCurrentIndex(
                self.input_devices.index(selected_input)
            )

        if selected_output in self.output_devices:
            self.output_box.setCurrentIndex(
                self.output_devices.index(selected_output)
            )

        if restore_audio_settings and saved.get("samplerate") in self.rate_values:
            self.rate_box.setCurrentIndex(
                self.rate_values.index(saved["samplerate"])
            )

        if restore_audio_settings and saved.get("blocksize") in self.buffer_values:
            self.buffer_box.setCurrentIndex(
                self.buffer_values.index(saved["blocksize"])
            )

    def refresh_devices(self):
        preferred_input = (
            self.input_devices[self.input_box.currentIndex()]
            if self.input_devices and self.input_box.currentIndex() >= 0
            else None
        )
        preferred_output = (
            self.output_devices[self.output_box.currentIndex()]
            if self.output_devices and self.output_box.currentIndex() >= 0
            else None
        )
        self.load_devices(preferred_input, preferred_output)
        self.set_status(
            "Audio device list refreshed",
            "音声デバイス一覧を更新しました",
        )

    def show_routing_guide(self):
        japanese = self.current_language == "ja"
        if japanese:
            title = "SAM 音の経路"
            message = (
                "ブラウザの音\n"
                "Windows出力 → 仮想ケーブル入力 → SAM入力 → "
                "SAM処理 → オーディオインターフェース出力 → スピーカー\n\n"
                "DAWの音\n"
                "通常は DAW → オーディオインターフェース → スピーカーです。\n"
                "この経路ではSAMを通りません。DAWをSAMで確認するには、"
                "DAWの出力を仮想ケーブルへ送ります。その場合は遅延が増えます。"
            )
        else:
            title = "SAM Audio Routing"
            message = (
                "Browser audio\n"
                "Windows output → virtual cable input → SAM input → "
                "SAM processing → audio interface output → speakers\n\n"
                "DAW audio\n"
                "Normally: DAW → audio interface → speakers.\n"
                "This route does not use SAM. Route the DAW output to a virtual "
                "cable to monitor it through SAM; this adds latency."
            )

        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.resize(720, 390)
        layout = QVBoxLayout(dialog)

        guide_text = QPlainTextEdit()
        guide_text.setReadOnly(True)
        guide_text.setPlainText(message)
        layout.addWidget(guide_text)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        copy_button = buttons.addButton(
            "Copy",
            QDialogButtonBox.ButtonRole.ActionRole,
        )
        copy_button.clicked.connect(
            lambda _checked=False: self.copy_routing_guide(message)
        )
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.exec()

    def copy_routing_guide(self, message):
        QApplication.clipboard().setText(message)
        self.set_status(
            "Routing guide copied",
            "音の経路をコピーしました",
        )

    def show_system_check(self):
        rate = self.rate_values[self.rate_box.currentIndex()]
        buffer_size = self.buffer_values[self.buffer_box.currentIndex()]
        latency_ms = 2000.0 * buffer_size / rate
        input_name = self.input_box.currentText() or "(not selected)"
        output_name = self.output_box.currentText() or "(not selected)"
        opus_status = opus_support_error() or "Ready"
        aac_status = aac_support_error() or "Ready"
        japanese = self.current_language == "ja"
        if japanese:
            title = "システム確認"
            copy_label = "コピー"
            message = (
                "Stream Audio Monitor - システム確認\n\n"
                f"入力: {input_name}\n"
                f"出力: {output_name}\n"
                f"サンプルレート: {rate} Hz\n"
                f"バッファ: {buffer_size} samples\n"
                f"基本I/Oバッファ遅延: ~{latency_ms:.0f} ms\n"
                f"コーデックプレビュー: {audio_state.codec_preview_mode}\n"
                "注意: Real Opus/AACプレビューでは、コーデックの追加遅延が発生します。\n\n"
                f"FFmpeg: {describe_ffmpeg_source()}\n"
                f"Opus: {opus_status}\n"
                f"AAC: {aac_status}"
            )
        else:
            title = "System Check"
            copy_label = "Copy"
            message = (
                "Stream Audio Monitor - System Check\n\n"
                f"Input: {input_name}\n"
                f"Output: {output_name}\n"
                f"Sample rate: {rate} Hz\n"
                f"Buffer: {buffer_size} samples\n"
                f"Base I/O buffer latency: ~{latency_ms:.0f} ms\n"
                f"Codec preview: {audio_state.codec_preview_mode}\n"
                "Note: Real Opus/AAC preview adds extra codec buffering latency.\n\n"
                f"FFmpeg: {describe_ffmpeg_source()}\n"
                f"Opus: {opus_status}\n"
                f"AAC: {aac_status}"
            )

        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.resize(760, 430)
        layout = QVBoxLayout(dialog)
        check_text = QPlainTextEdit()
        check_text.setReadOnly(True)
        check_text.setPlainText(message)
        layout.addWidget(check_text)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        copy_button = buttons.addButton(
            copy_label,
            QDialogButtonBox.ButtonRole.ActionRole,
        )
        copy_button.clicked.connect(
            lambda _checked=False: self.copy_system_check(message)
        )
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.exec()

    def copy_system_check(self, message):
        QApplication.clipboard().setText(message)
        self.set_status(
            "System check copied",
            "システム確認をコピーしました",
        )

    def show_file_tools(self):
        """Queue offline analysis and exports from one compact dialog."""
        japanese = self.current_language == "ja"
        dialog = QDialog(self)
        dialog.setWindowTitle(
            "解析 / 書き出し" if japanese else "Analyze / Export"
        )
        dialog.resize(760, 420)
        layout = QVBoxLayout(dialog)

        guide = QLabel(
            "元WAVと保存先を選び、実行したい処理を複数選択してからOKを押してください。"
            if japanese else
            "Choose a source WAV and output folder, select one or more actions, then press OK."
        )
        guide.setWordWrap(True)
        layout.addWidget(guide)

        paths = QGridLayout()
        source_label = QLabel("元WAV" if japanese else "Source WAV")
        source_edit = QLineEdit()
        source_edit.setReadOnly(True)
        source_button = QPushButton("選択" if japanese else "Browse")
        destination_label = QLabel("保存先" if japanese else "Output folder")
        destination_edit = QLineEdit()
        destination_edit.setReadOnly(True)
        destination_edit.setText(self.last_file_tools_output_folder)
        destination_button = QPushButton("選択" if japanese else "Browse")
        paths.addWidget(source_label, 0, 0)
        paths.addWidget(source_edit, 0, 1)
        paths.addWidget(source_button, 0, 2)
        paths.addWidget(destination_label, 1, 0)
        paths.addWidget(destination_edit, 1, 1)
        paths.addWidget(destination_button, 1, 2)
        layout.addLayout(paths)

        apply_youtube_volume = QCheckBox(
            "書き出しにYouTubeノーマライズを反映"
            if japanese else "Apply YouTube normalization to exports"
        )
        apply_youtube_volume.setChecked(
            self.youtube_volume_export_checkbox.isChecked()
        )
        layout.addWidget(apply_youtube_volume)

        def choose_source():
            path, _ = QFileDialog.getOpenFileName(
                dialog,
                "元のWAVを選択" if japanese else "Select source WAV",
                "",
                "WAV files (*.wav)",
            )
            if path:
                source_edit.setText(path)

        def choose_destination():
            folder = QFileDialog.getExistingDirectory(
                dialog,
                "保存先フォルダを選択" if japanese else "Select output folder",
                destination_edit.text(),
            )
            if folder:
                destination_edit.setText(folder)
                self.last_file_tools_output_folder = folder
                self.save_current_settings()

        def source_path():
            path = source_edit.text().strip()
            if Path(path).is_file():
                return path
            QMessageBox.warning(
                dialog,
                "ファイルツール" if japanese else "File Tools",
                "元WAVを選択してください。"
                if japanese else "Select a source WAV file first.",
            )
            return None

        def output_folder():
            folder = destination_edit.text().strip()
            if Path(folder).is_dir():
                return Path(folder)
            QMessageBox.warning(
                dialog,
                "ファイルツール" if japanese else "File Tools",
                "保存先フォルダを選択してください。"
                if japanese else "Select an output folder first.",
            )
            return None

        actions = QGridLayout()
        analyze_button = QPushButton("解析結果を表示" if japanese else "Show Analysis")
        opus_button = QPushButton("Opusを書き出す" if japanese else "Export Opus")
        aac_button = QPushButton("AACを書き出す" if japanese else "Export AAC")
        delta_button = QPushButton("Opus差分を書き出す" if japanese else "Export Opus Delta")
        ab_button = QPushButton("YouTube A/Bを書き出す" if japanese else "Export YouTube A/B")
        pack_button = QPushButton("コーデックパックを書き出す" if japanese else "Export Codec Pack")
        action_buttons = (
            analyze_button,
            opus_button,
            aac_button,
            delta_button,
            ab_button,
            pack_button,
        )
        for button in action_buttons:
            button.setCheckable(True)
            button.setStyleSheet(
                "QPushButton:checked {"
                "background: #1f5637; color: #d4ffdf; font-weight: bold;"
                "}"
            )

        actions.addWidget(analyze_button, 0, 0)
        actions.addWidget(opus_button, 0, 1)
        actions.addWidget(aac_button, 0, 2)
        actions.addWidget(delta_button, 1, 0)
        actions.addWidget(ab_button, 1, 1)
        actions.addWidget(pack_button, 1, 2)
        layout.addLayout(actions)

        source_button.clicked.connect(choose_source)
        destination_button.clicked.connect(choose_destination)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(
            "OK（選択した処理を実行）" if japanese else "OK (Run selected actions)"
        )

        def run_selected_actions():
            path = source_path()
            selected_exports = any(
                button.isChecked() for button in action_buttons[1:]
            )
            folder = output_folder() if selected_exports else None
            if not path or (selected_exports and folder is None):
                return

            selected = [button for button in action_buttons if button.isChecked()]
            if not selected:
                QMessageBox.information(
                    dialog,
                    "ファイルツール" if japanese else "File Tools",
                    "実行する処理を1つ以上選択してください。"
                    if japanese else "Select at least one action to run.",
                )
                return

            self.youtube_volume_export_checkbox.setChecked(
                apply_youtube_volume.isChecked()
            )
            dialog.accept()
            results = []
            source = Path(path)

            def add_result(name, result):
                success = bool(result) and not result.startswith("ERROR: ")
                results.append((name, success, result))

            if analyze_button.isChecked():
                result = self.analyze_wav_file(path, show_result=False)
                add_result("WAV解析", result)
            if opus_button.isChecked():
                destination = folder / f"{source.stem}_opus_{self.current_opus_bitrate()}k.wav"
                result = self.export_opus_wav(
                    path, str(destination), show_result=False
                )
                add_result("Opus WAV", result)
            if aac_button.isChecked():
                destination = folder / f"{source.stem}_aac_128k.wav"
                result = self.export_aac_wav(
                    path, str(destination), show_result=False
                )
                add_result("AAC WAV", result)
            if delta_button.isChecked():
                destination = folder / f"{source.stem}_opus_{self.current_opus_bitrate()}k_delta.wav"
                result = self.export_opus_delta_wav(
                    path, str(destination), show_result=False
                )
                add_result("Opus差分WAV", result)
            if ab_button.isChecked():
                result = self.export_youtube_ab_wavs(
                    path, str(folder), show_result=False
                )
                add_result("YouTube A/B", result)
            if pack_button.isChecked():
                result = self.export_codec_pack_wavs(
                    path, str(folder), show_result=False
                )
                add_result("コーデックパック", result)

            self.show_file_tools_report(path, folder, results)

        buttons.accepted.connect(run_selected_actions)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.exec()

    def show_file_tools_report(self, source_path, destination_folder, results):
        japanese = self.current_language == "ja"
        title = "ファイルツールの実行結果" if japanese else "File Tools Results"
        lines = [
            f"元WAV: {source_path}" if japanese else f"Source WAV: {source_path}",
        ]
        if destination_folder:
            lines.append(
                f"保存先: {destination_folder}"
                if japanese else f"Output folder: {destination_folder}"
            )
        lines.append("")
        lines.append("実行結果:" if japanese else "Results:")
        for name, success, result in results:
            status = "完了" if success else "失敗"
            if not japanese:
                status = "Completed" if success else "Failed"
            lines.append(f"• {name}: {status}")
            if result:
                lines.extend(
                    f"  {line}" for line in result.splitlines() if line
                )

        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.resize(680, 300)
        layout = QVBoxLayout(dialog)
        report = QPlainTextEdit()
        report.setReadOnly(True)
        report.setPlainText("\n".join(lines))
        layout.addWidget(report)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.exec()

    def check_opus_support_at_startup(self):
        """Warn early when codec previews are unavailable in a SAM install."""
        opus_error = opus_support_error()
        aac_error = aac_support_error()
        errors = []
        if opus_error:
            errors.append(f"Opus: {opus_error}")
        if aac_error:
            errors.append(f"AAC: {aac_error}")

        if errors:
            message = "\n".join(errors)
            print(f"Codec support: UNAVAILABLE - {message}")
            self.set_status(
                "Codec setup error",
                "コーデック設定エラー",
                error_code="SAM-E-CODEC-SETUP",
                error_detail=message,
            )
            QMessageBox.warning(
                self,
                "Codec Setup Check",
                "Some codec previews or exports are unavailable.\n\n" + message,
            )
            return

        print("Codec support: FFmpeg, Opus, and AAC ready.")
        print(describe_ffmpeg_source())

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

        audio_config = (
            input_device,
            output_device,
            samplerate,
            blocksize,
        )
        if self.audio_engine_started and audio_config == self.active_audio_config:
            self.bypass_checkbox.setChecked(False)
            self.set_status("Running", "動作中")
            self.set_audio_running_state(True)
            return

        self.save_current_settings()

        started = self.start_stream(
            input_device,
            output_device,
            samplerate,
            blocksize,
        )

        if started:
            self.audio_engine_started = True
            self.active_audio_config = audio_config
            self.bypass_checkbox.setChecked(False)
            self.set_status("Running", "動作中")
            self.set_audio_running_state(True)
        else:
            self.audio_engine_started = False
            self.active_audio_config = None
            error_detail = getattr(self.start_stream, "last_error", "")
            self.set_status(
                "Audio error",
                "音声エラー",
                error_detail=error_detail,
            )
            self.set_audio_running_state(False)

    def stop_audio(self):
        if not self.audio_engine_started:
            self.set_status("Stopped", "停止しました")
            self.set_audio_running_state(False)
            return

        self.bypass_checkbox.setChecked(True)
        self.set_status("Bypass raw input", "SAM停止: 元の入力音を再生中")
        self.set_audio_running_state(False)

    def set_audio_running_state(self, running):
        if running:
            self.start_button.setStyleSheet(
                "background: #1b715f; color: white; font-weight: bold;"
            )
            self.stop_button.setStyleSheet(
                "background: #4a2525; color: #ffd6d6; font-weight: bold;"
            )
        else:
            self.start_button.setStyleSheet("")
            self.stop_button.setStyleSheet(
                "background: #6b2424; color: #ffd6d6; font-weight: bold;"
            )

    def add_debug_event(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.debug_events.append(f"[{timestamp}] {message}")
        self.debug_events = self.debug_events[-200:]

    def show_debug_log(self):
        japanese = self.current_language == "ja"
        title = "デバッグログ" if japanese else "Debug Log"
        input_name = self.input_box.currentText() or "(not selected)"
        output_name = self.output_box.currentText() or "(not selected)"
        rate = self.rate_values[self.rate_box.currentIndex()]
        buffer_size = self.buffer_values[self.buffer_box.currentIndex()]
        header = (
            "SAM デバッグ情報\n\n"
            f"入力: {input_name}\n"
            f"出力: {output_name}\n"
            f"サンプルレート: {rate} Hz\n"
            f"バッファ: {buffer_size} samples\n"
            f"コーデック: {audio_state.codec_preview_mode}\n"
            f"開発者モード: {'ON' if self.developer_mode else 'OFF'}\n"
            f"FFmpeg: {describe_ffmpeg_source()}\n\n"
            "操作履歴\n"
            if japanese else
            "SAM Debug Information\n\n"
            f"Input: {input_name}\n"
            f"Output: {output_name}\n"
            f"Sample rate: {rate} Hz\n"
            f"Buffer: {buffer_size} samples\n"
            f"Codec: {audio_state.codec_preview_mode}\n"
            f"Developer mode: {'ON' if self.developer_mode else 'OFF'}\n"
            f"FFmpeg: {describe_ffmpeg_source()}\n\n"
            "Operation history\n"
        )
        message = header + ("\n".join(self.debug_events) or "(no events)")

        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.resize(820, 560)
        layout = QVBoxLayout(dialog)
        log_text = QPlainTextEdit()
        log_text.setReadOnly(True)
        log_text.setPlainText(message)
        layout.addWidget(log_text)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        copy_button = buttons.addButton(
            "コピー" if japanese else "Copy",
            QDialogButtonBox.ButtonRole.ActionRole,
        )
        clear_button = buttons.addButton(
            "履歴を消去" if japanese else "Clear history",
            QDialogButtonBox.ButtonRole.ActionRole,
        )
        copy_button.clicked.connect(
            lambda _checked=False: QApplication.clipboard().setText(
                log_text.toPlainText()
            )
        )

        def clear_history():
            self.debug_events.clear()
            log_text.setPlainText(
                header + ("(履歴はありません)" if japanese else "(no events)")
            )

        clear_button.clicked.connect(clear_history)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.exec()

    def set_support_error(self, code, detail=""):
        self.last_support_error_code = code
        self.last_support_error_detail = detail
        label = "問題" if self.current_language == "ja" else "Issue"
        self.issue_indicator.setText(f"{label}: {code}")
        self.issue_indicator.setVisible(True)
        self.copy_support_button.setVisible(True)
        self.add_debug_event(f"Issue: {code} - {detail}".rstrip(" - "))

    def clear_support_error(self):
        self.last_support_error_code = ""
        self.last_support_error_detail = ""
        self.issue_indicator.setVisible(False)
        self.copy_support_button.setVisible(False)

    def copy_support_info(self):
        japanese = self.current_language == "ja"
        input_name = self.input_box.currentText() or "(not selected)"
        output_name = self.output_box.currentText() or "(not selected)"
        rate = self.rate_values[self.rate_box.currentIndex()]
        buffer_size = self.buffer_values[self.buffer_box.currentIndex()]
        message = (
            "SAM サポート情報\n\n"
            f"エラーコード: {self.last_support_error_code}\n"
            f"内容: {self.last_support_error_detail or '(詳細なし)'}\n\n"
            f"入力: {input_name}\n"
            f"出力: {output_name}\n"
            f"サンプルレート: {rate} Hz\n"
            f"バッファ: {buffer_size} samples\n"
            f"コーデック: {audio_state.codec_preview_mode}\n"
            f"FFmpeg: {describe_ffmpeg_source()}\n\n"
            "環境情報\n"
            f"{support_environment_text()}\n\n"
            "直近の操作履歴\n"
            if japanese else
            "SAM Support Information\n\n"
            f"Error code: {self.last_support_error_code}\n"
            f"Details: {self.last_support_error_detail or '(no details)'}\n\n"
            f"Input: {input_name}\n"
            f"Output: {output_name}\n"
            f"Sample rate: {rate} Hz\n"
            f"Buffer: {buffer_size} samples\n"
            f"Codec: {audio_state.codec_preview_mode}\n"
            f"FFmpeg: {describe_ffmpeg_source()}\n\n"
            "Environment\n"
            f"{support_environment_text()}\n\n"
            "Recent operation history\n"
        )
        message += "\n".join(self.debug_events[-20:]) or "(no events)"
        QApplication.clipboard().setText(message)
        self.add_debug_event("Support information copied")

    def set_status(self, english, japanese, error_code=None, error_detail=""):
        if self.current_language == "ja":
            self.status.setText(f"状態: {japanese}")
        else:
            self.status.setText(f"Status: {english}")

        if english == "Running":
            self.ready_label.setText("●  ACTIVE\nMonitoring Live")
            self.ready_label.setStyleSheet("color: #38f29a; font-size: 10pt;")
        elif "error" in english.lower() or error_code:
            self.ready_label.setText("●  ERROR\nCheck details")
            self.ready_label.setStyleSheet("color: #ff628f; font-size: 10pt;")
        else:
            self.ready_label.setText("●  READY\nMonitoring Idle")
            self.ready_label.setStyleSheet("color: #b7c8ef; font-size: 10pt;")

        if english != self.last_debug_status:
            self.last_debug_status = english
            self.add_debug_event(f"Status: {english}")

        default_codes = {
            "No usable audio device found": "SAM-E-AUDIO-DEVICE",
            "Audio error": "SAM-E-AUDIO-START",
            "Audio runtime warning": "SAM-E-AUDIO-RUNTIME",
            "WAV analysis error": "SAM-E-WAV-ANALYSIS",
            "Opus export error": "SAM-E-OPUS-EXPORT",
            "Opus Delta export error": "SAM-E-DELTA-EXPORT",
            "AAC export error": "SAM-E-AAC-EXPORT",
            "YouTube A/B export error": "SAM-E-YT-AB-EXPORT",
            "Codec pack export error": "SAM-E-CODEC-PACK",
            "YouTube calibration error": "SAM-E-YT-CALIBRATION",
        }
        code = error_code or default_codes.get(english)
        if code:
            self.set_support_error(code, error_detail)
        elif english == "Running":
            self.clear_support_error()

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
        if self.developer_mode and theme in theme_names():
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
        self.codec_delta_checkbox.setChecked(
            saved.get("codec_delta_monitor", False)
        )
        self.set_codec_focus(saved.get("codec_focus", False))
        self.set_developer_mode(saved.get("developer_mode", False))
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
            "codec_delta_monitor": self.codec_delta_checkbox.isChecked(),
            "codec_focus": self.codec_focus_enabled,
            "developer_mode": self.developer_mode,
            "file_tools_output_folder": self.last_file_tools_output_folder,
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

    def analyze_wav_file(self, path=None, show_result=True):
        japanese = self.current_language == "ja"
        if path is None:
            path, _ = QFileDialog.getOpenFileName(
                self,
                "WAVを解析" if japanese else "Analyze WAV file",
                "",
                "WAV files (*.wav)",
            )

        if not path:
            return

        try:
            self.set_status("Analyzing WAV...", "WAVを解析中...")
            result = analyze_wav(path, self.youtube_target_lufs)
        except (OSError, ValueError) as error:
            self.set_status(
                "WAV analysis error", "WAV解析エラー", error_detail=str(error)
            )
            if show_result:
                QMessageBox.warning(
                    self,
                    "WAV解析" if japanese else "WAV Analysis",
                    str(error),
                )
            return f"ERROR: {error}"

        minutes, seconds = divmod(int(result["duration_seconds"]), 60)
        readiness = self.format_offline_youtube_readiness(result)
        if japanese:
            message = (
                f"ファイル: {result['name']}\n"
                f"長さ: {minutes:02d}:{seconds:02d}\n"
                f"統合LUFS: {result['lufs_i']:.1f}\n"
                f"サンプルピーク: {result['peak_db']:.1f} dBFS\n\n"
                f"推定True Peak: {result['true_peak_db']:.1f} dBTP\n\n"
                f"ステレオ相関: {result['stereo_correlation']:+.2f}\n\n"
                f"モノラル確認: {self.format_stereo_check(result)}\n\n"
                "YouTube再生の想定\n"
                f"ゲイン: {result['youtube_gain_db']:+.1f} dB\n"
                f"音量: {result['youtube_percent']:.0f}%\n\n"
                f"YouTube確認: {readiness}\n\n"
                "YouTubeミックス確認\n"
                f"{result['youtube_advice']}"
            )
        else:
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
        if show_result:
            QMessageBox.information(
                self,
                "WAV解析" if japanese else "WAV Analysis",
                message,
            )
        return message

    def analyze_candidate_wavs(self):
        japanese = self.current_language == "ja"
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "候補WAVを選択" if japanese else "Select candidate WAV files",
            "",
            "WAV files (*.wav)",
        )

        if not paths:
            return

        self.analyze_candidate_paths(paths)

    def analyze_candidate_folder(self):
        japanese = self.current_language == "ja"
        folder = QFileDialog.getExistingDirectory(
            self,
            "候補WAVフォルダを選択" if japanese else "Select candidate WAV folder",
        )
        if not folder:
            return

        paths = sorted(
            str(path)
            for path in Path(folder).iterdir()
            if path.is_file() and path.suffix.lower() == ".wav"
        )
        if not paths:
            QMessageBox.information(
                self,
                "候補WAVの比較" if japanese else "Candidate Analysis",
                "このフォルダにはWAVファイルがありません。"
                if japanese else "No WAV files were found in this folder.",
            )
            return

        self.analyze_candidate_paths(paths)

    def analyze_candidate_paths(self, paths):
        japanese = self.current_language == "ja"
        measure_opus_impact = (
            QMessageBox.question(
                self,
                "Opus影響測定" if japanese else "Opus Impact",
                "Opus圧縮による変化も測定しますか？\n"
                "WAVごとに時間が追加でかかります。"
                if japanese else "Also measure Opus codec impact? This takes longer for each WAV.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            == QMessageBox.StandardButton.Yes
        )
        if measure_opus_impact:
            error = opus_support_error()
            if error:
                QMessageBox.warning(
                    self,
                    "Opus影響測定" if japanese else "Opus Impact",
                    error,
                )
                return

        self.set_status(
            "Analyzing candidate WAV files...",
            "候補WAVを解析中...",
        )
        results = []
        errors = []
        progress = QProgressDialog(
            "候補WAVを解析中..." if japanese else "Analyzing candidate WAV files...",
            "中止" if japanese else "Cancel",
            0,
            len(paths),
            self,
        )
        progress.setWindowTitle(
            "候補WAVの比較" if japanese else "Candidate Analysis"
        )
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.setValue(0)
        cancelled = False

        for index, path in enumerate(paths, start=1):
            if progress.wasCanceled():
                cancelled = True
                break

            progress.setLabelText(
                f"{index}/{len(paths)} を解析中\n{Path(path).name}"
                if japanese else f"Analyzing {index}/{len(paths)}\n{Path(path).name}"
            )
            try:
                result = analyze_wav(path, self.youtube_target_lufs)
                if measure_opus_impact:
                    try:
                        result["opus_impact"] = analyze_opus_impact(
                            path,
                            self.current_opus_bitrate(),
                        )
                    except (OSError, RuntimeError, ValueError) as error:
                        result["opus_impact_error"] = str(error)
                results.append(result)
            except (OSError, ValueError) as error:
                errors.append(f"{path}: {error}")
            progress.setValue(index)

        progress.close()

        if not results:
            self.set_status("Candidate analysis error", "候補WAVの解析エラー")
            QMessageBox.warning(
                self,
                "候補WAVの比較" if japanese else "Candidate Analysis",
                "解析できるWAVファイルがありませんでした。"
                if japanese else "No WAV files could be analyzed.",
            )
            return

        rows = []
        mono_label = "モノラル確認" if japanese else "Mono Check"
        youtube_label = "YouTube想定" if japanese else "YouTube"
        opus_delta_label = "Opus変化" if japanese else "Opus Delta"
        strongest_label = "高域で最も変化" if japanese else "Strongest high-frequency delta"
        for result in results:
            readiness = self.format_offline_youtube_readiness(result)
            stereo_check = self.format_stereo_check(result)
            rows.append(
                f"{result['name']}\n"
                f"  LUFS-I: {result['lufs_i']:.1f} | "
                f"True Peak: {result['true_peak_db']:.1f} dBTP | "
                f"Correlation: {result['stereo_correlation']:+.2f}\n"
                f"  {mono_label}: {stereo_check}\n"
                f"  {youtube_label}: {result['youtube_gain_db']:+.1f} dB "
                f"({result['youtube_percent']:.0f}%) | {readiness}"
            )

            if measure_opus_impact:
                impact = result.get("opus_impact")
                if impact:
                    rows[-1] += (
                        f"\n  {opus_delta_label}: {impact['relative_lufs_db']:.1f} dB "
                        f"vs source | Delta LUFS: {impact['delta_lufs_i']:.1f}\n"
                        f"  {strongest_label}: "
                        f"{self.format_opus_delta_band(impact)}"
                    )
                else:
                    rows[-1] += (
                        f"\n  {opus_delta_label}: "
                        + ("利用不可 - " if japanese else "unavailable - ")
                        + result.get("opus_impact_error", "unknown error")
                    )

        title = "候補WAVの比較" if japanese else "Candidate WAV Comparison"
        conditions = [
            "測定条件" if japanese else "Analysis settings",
            f"解析ファイル数: {len(results)}" if japanese else f"Files analyzed: {len(results)}",
            f"YouTube基準: {self.youtube_target_lufs:.1f} LUFS"
            if japanese else f"YouTube reference: {self.youtube_target_lufs:.1f} LUFS",
        ]
        if measure_opus_impact:
            conditions.append(
                f"Opus影響測定: {self.current_opus_bitrate()} kbps"
                if japanese else f"Opus impact: {self.current_opus_bitrate()} kbps"
            )
        else:
            conditions.append("Opus影響測定: 実行しない" if japanese else "Opus impact: skipped")

        message = "\n".join(conditions) + "\n\n" + "\n\n".join(rows)
        if measure_opus_impact:
            ranked_impacts = sorted(
                (
                    result
                    for result in results
                    if result.get("opus_impact") is not None
                ),
                key=lambda result: result["opus_impact"]["relative_lufs_db"],
            )
            if ranked_impacts:
                ranking_rows = []
                for position, result in enumerate(ranked_impacts, start=1):
                    relative_delta = result["opus_impact"]["relative_lufs_db"]
                    ranking_rows.append(
                        f"{position}. {result['name']} ({relative_delta:.1f} dB)"
                    )

                winner = ranked_impacts[0]
                if japanese:
                    message += (
                        "\n\nOpus安定性順位（変化が少ない順）\n"
                        + "\n".join(ranking_rows)
                        + "\n\n最初に確認する候補: "
                        + winner["name"]
                    )
                else:
                    message += (
                        "\n\nOpus stability ranking (less changed first)\n"
                        + "\n".join(ranking_rows)
                        + "\n\nRecommended first check: "
                        + winner["name"]
                    )
            if japanese:
                message += (
                    "\n\nOpus変化の見方: 元音に対する数値がよりマイナスなら、"
                    "コーデックによる変化エネルギーが少ない目安です。\n"
                    "高域で最も変化は、4-8 kHz と 8-16 kHz のどちらで"
                    "相対的な変化が大きいかを示します。"
                )
            else:
                message += (
                    "\n\nOpus Delta guide: a more negative value versus source "
                    "means less changed codec-difference energy.\n"
                    "The strongest high-frequency delta identifies whether 4-8 kHz "
                    "or 8-16 kHz changed more relative to the source."
                )
        if errors:
            error_title = "解析できなかったファイル" if japanese else "Files not analyzed"
            message += f"\n\n{error_title}\n" + "\n".join(errors)
        if cancelled:
            message += (
                f"\n\n解析を中止しました: {len(paths)} 個中 {len(results)} 個を表示しています。"
                if japanese else
                f"\n\nAnalysis cancelled: showing {len(results)} of {len(paths)} files."
            )

        self.set_status(
            "Candidate WAV analysis complete",
            "候補WAVの解析が完了しました",
        )
        self.last_candidate_report = message
        print(message.replace("\n", " | "))
        self.show_candidate_report(title, message)

    def show_candidate_report(self, title, message):
        """Display long candidate comparisons without clipping the results."""
        japanese = self.current_language == "ja"
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.resize(820, 620)

        layout = QVBoxLayout(dialog)
        report_text = QPlainTextEdit()
        report_text.setReadOnly(True)
        report_text.setPlainText(message)
        layout.addWidget(report_text)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        copy_button = buttons.addButton(
            "結果をコピー" if japanese else "Copy Results",
            QDialogButtonBox.ButtonRole.ActionRole,
        )
        save_button = buttons.addButton(
            "候補レポートを保存" if japanese else "Save Candidate Report",
            QDialogButtonBox.ButtonRole.ActionRole,
        )
        copy_button.clicked.connect(
            lambda _checked=False: self.copy_candidate_report(message)
        )
        save_button.clicked.connect(self.save_candidate_report)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.exec()

    @staticmethod
    def format_opus_delta_band(impact):
        band_names = {
            "presence": "4-8 kHz",
            "high": "8-16 kHz",
        }
        band = band_names.get(impact["strongest_band"], "unknown")
        return (
            f"{band} "
            f"({impact['strongest_band_relative_db']:.1f} dB vs source)"
        )

    def copy_candidate_report(self, message):
        QApplication.clipboard().setText(message)
        self.set_status(
            "Candidate report copied",
            "候補レポートをコピーしました",
        )

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

    def export_opus_wav(self, source_path=None, destination_path=None, show_result=True):
        japanese = self.current_language == "ja"
        if source_path is None:
            source_path, _ = QFileDialog.getOpenFileName(
                self,
                "元のWAVを選択" if japanese else "Select source WAV",
                "",
                "WAV files (*.wav)",
            )

        if not source_path:
            return

        default_path = source_path.rsplit(".", 1)[0]
        default_path += f"_opus_{self.current_opus_bitrate()}k.wav"

        if destination_path is None:
            destination_path, _ = QFileDialog.getSaveFileName(
                self,
                "OpusプレビューWAVを保存" if japanese else "Save Opus preview WAV",
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
            self.set_status(
                "Opus export error", "Opus書き出しエラー", error_detail=str(error)
            )
            if show_result:
                QMessageBox.warning(
                    self,
                    "Opus書き出し" if japanese else "Opus Export",
                    str(error),
                )
            return f"ERROR: {error}"

        self.set_status("Opus preview exported", "Opusプレビューを書き出しました")
        if japanese:
            message = (
                "OpusプレビューWAVを作成しました\n\n"
                f"ビットレート: {bitrate} kbps\n"
                f"YouTubeゲイン: {playback_gain_db:+.1f} dB\n"
                f"ファイル: {output_path}"
            )
        else:
            message = (
                "Created Opus preview WAV\n\n"
                f"Bitrate: {bitrate} kbps\n"
                f"YouTube gain: {playback_gain_db:+.1f} dB\n"
                f"File: {output_path}"
            )
        print(message.replace("\n", " | "))
        if show_result:
            QMessageBox.information(
                self,
                "Opus書き出し" if japanese else "Opus Export",
                message,
            )
        return message

    def export_opus_delta_wav(
        self, source_path=None, destination_path=None, show_result=True
    ):
        japanese = self.current_language == "ja"
        if source_path is None:
            source_path, _ = QFileDialog.getOpenFileName(
                self,
                "元のWAVを選択" if japanese else "Select source WAV",
                "",
                "WAV files (*.wav)",
            )

        if not source_path:
            return

        default_path = source_path.rsplit(".", 1)[0]
        default_path += f"_opus_{self.current_opus_bitrate()}k_delta.wav"
        if destination_path is None:
            destination_path, _ = QFileDialog.getSaveFileName(
                self,
                "Opus差分WAVを保存" if japanese else "Save Opus Delta WAV",
                default_path,
                "WAV files (*.wav)",
            )

        if not destination_path:
            return

        gain_text, accepted = QInputDialog.getItem(
            self,
            "差分ゲイン" if japanese else "Delta Gain",
            "差分WAVのゲイン:" if japanese else "Delta WAV gain:",
            ["+0 dB", "+6 dB", "+12 dB"],
            1,
            False,
        )
        if not accepted:
            return

        delta_gain_db = float(gain_text.split()[0])

        try:
            bitrate = self.current_opus_bitrate()
            self.set_status(
                "Exporting Opus Delta...",
                "Opus差分を書き出し中...",
            )
            output_path = export_opus_delta(
                source_path,
                destination_path,
                bitrate,
                delta_gain_db,
            )
        except (OSError, RuntimeError, ValueError) as error:
            self.set_status(
                "Opus Delta export error",
                "Opus差分の書き出しエラー",
                error_detail=str(error),
            )
            if show_result:
                QMessageBox.warning(
                    self,
                    "Opus差分の書き出し" if japanese else "Opus Delta Export",
                    str(error),
                )
            return f"ERROR: {error}"

        self.set_status("Opus Delta exported", "Opus差分を書き出しました")
        if japanese:
            message = (
                "Opus差分WAVを作成しました\n\n"
                "このファイルには、Opus圧縮によって変化した音だけが入っています。\n"
                f"ビットレート: {bitrate} kbps\n"
                f"差分ゲイン: {delta_gain_db:+.1f} dB\n"
                f"ファイル: {output_path}"
            )
        else:
            message = (
                "Created Opus Delta WAV\n\n"
                "This file contains only the sound changed by Opus.\n"
                f"Bitrate: {bitrate} kbps\n"
                f"Delta gain: {delta_gain_db:+.1f} dB\n"
                f"File: {output_path}"
            )
        print(message.replace("\n", " | "))
        if show_result:
            QMessageBox.information(
                self,
                "Opus差分の書き出し" if japanese else "Opus Delta Export",
                message,
            )
        return message

    def export_aac_wav(self, source_path=None, destination_path=None, show_result=True):
        japanese = self.current_language == "ja"
        if source_path is None:
            source_path, _ = QFileDialog.getOpenFileName(
                self,
                "元のWAVを選択" if japanese else "Select source WAV",
                "",
                "WAV files (*.wav)",
            )

        if not source_path:
            return

        default_path = source_path.rsplit(".", 1)[0] + "_aac_128k.wav"
        if destination_path is None:
            destination_path, _ = QFileDialog.getSaveFileName(
                self,
                "AACプレビューWAVを保存" if japanese else "Save AAC preview WAV",
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
            self.set_status(
                "AAC export error", "AAC書き出しエラー", error_detail=str(error)
            )
            if show_result:
                QMessageBox.warning(
                    self,
                    "AAC書き出し" if japanese else "AAC Export",
                    str(error),
                )
            return f"ERROR: {error}"

        self.set_status("AAC preview exported", "AACプレビューを書き出しました")
        if japanese:
            message = (
                "AACプレビューWAVを作成しました\n\n"
                "ビットレート: 128 kbps\n"
                f"YouTubeゲイン: {playback_gain_db:+.1f} dB\n"
                f"ファイル: {output_path}"
            )
        else:
            message = (
                "Created AAC preview WAV\n\n"
                "Bitrate: 128 kbps\n"
                f"YouTube gain: {playback_gain_db:+.1f} dB\n"
                f"File: {output_path}"
            )
        print(message.replace("\n", " | "))
        if show_result:
            QMessageBox.information(
                self,
                "AAC書き出し" if japanese else "AAC Export",
                message,
            )
        return message

    def export_youtube_ab_wavs(
        self, source_path=None, destination_folder=None, show_result=True
    ):
        japanese = self.current_language == "ja"
        if source_path is None:
            source_path, _ = QFileDialog.getOpenFileName(
                self,
                "元のWAVを選択" if japanese else "Select source WAV",
                "",
                "WAV files (*.wav)",
            )

        if not source_path:
            return

        if destination_folder is None:
            destination_folder = QFileDialog.getExistingDirectory(
                self,
                "YouTube A/Bファイルの保存フォルダを選択"
                if japanese else "Select output folder for YouTube A/B files",
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
            self.set_status(
                "YouTube A/B export error",
                "YouTube A/B書き出しエラー",
                error_detail=str(error),
            )
            if show_result:
                QMessageBox.warning(
                    self,
                    "YouTube A/B書き出し" if japanese else "YouTube A/B Export",
                    str(error),
                )
            return f"ERROR: {error}"

        self.set_status(
            "YouTube A/B previews exported",
            "YouTube A/Bプレビューを書き出しました",
        )
        if japanese:
            message = (
                "音量を揃えたYouTube A/BプレビューWAVを作成しました\n\n"
                f"ビットレート: {bitrate} kbps\n"
                f"YouTubeゲイン: {playback_gain_db:+.1f} dB\n\n"
                "A — Opus圧縮のみ\n"
                f"{output_paths['opus']}\n\n"
                "B — Opus圧縮 + YouTube再生音量\n"
                f"{output_paths['youtube']}"
            )
        else:
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
        if show_result:
            QMessageBox.information(
                self,
                "YouTube A/B書き出し" if japanese else "YouTube A/B Export",
                message,
            )
        return message

    def export_codec_pack_wavs(
        self, source_path=None, destination_folder=None, show_result=True
    ):
        japanese = self.current_language == "ja"
        if source_path is None:
            source_path, _ = QFileDialog.getOpenFileName(
                self,
                "元のWAVを選択" if japanese else "Select source WAV",
                "",
                "WAV files (*.wav)",
            )

        if not source_path:
            return

        if destination_folder is None:
            destination_folder = QFileDialog.getExistingDirectory(
                self,
                "コーデックプレビューパックの保存フォルダを選択"
                if japanese else "Select output folder for codec preview pack",
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
            self.set_status(
                "Codec pack export error",
                "コーデックパック書き出しエラー",
                error_detail=str(error),
            )
            if show_result:
                QMessageBox.warning(
                    self,
                    "コーデックパック書き出し" if japanese else "Codec Pack Export",
                    str(error),
                )
            return f"ERROR: {error}"

        self.set_status(
            "Codec preview pack exported",
            "コーデックプレビューパックを書き出しました",
        )
        if japanese:
            message = (
                "YouTubeコーデックプレビューパックを作成しました\n\n"
                f"YouTubeゲイン: {playback_gain_db:+.1f} dB\n\n"
                f"Opus + YouTube音量\n{paths['opus_youtube']}\n\n"
                f"AAC + YouTube音量\n{paths['aac_youtube']}\n\n"
                f"レポート\n{paths['report']}"
            )
        else:
            message = (
                "Created YouTube codec preview pack\n\n"
                f"YouTube gain: {playback_gain_db:+.1f} dB\n\n"
                f"Opus + YouTube volume\n{paths['opus_youtube']}\n\n"
                f"AAC + YouTube volume\n{paths['aac_youtube']}\n\n"
                f"Report\n{paths['report']}"
            )
        print(message.replace("\n", " | "))
        if show_result:
            QMessageBox.information(
                self,
                "コーデックパック書き出し" if japanese else "Codec Pack Export",
                message,
            )
        return message

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

    def toggle_codec_delta(self, enabled):
        import audio

        audio.set_codec_delta_monitor(enabled)
        state = "ON" if enabled else "OFF"
        print(f"Codec Delta Monitor: {state}")

        if enabled:
            self.set_status(
                "Codec Delta Monitor: changed sound only",
                "Codec Delta Monitor: changed sound only",
            )

    def toggle_codec_focus(self):
        self.set_codec_focus(not self.codec_focus_enabled)
        self.save_current_settings()

    def reset_codec_difference(self):
        self.codec_difference.reset_history()
        self.set_status("Codec difference reset", "Codec difference reset")

    def set_codec_focus(self, enabled):
        self.codec_focus_enabled = bool(enabled)
        self.update_detail_meter_visibility()

        if self.codec_focus_enabled:
            self.codec_focus_button.setText("Codec Focus: ON")
            self.codec_focus_button.setStyleSheet(
                "background: #1f5637; color: #d4ffdf; font-weight: bold;"
            )
        else:
            self.codec_focus_button.setText("Codec Focus: OFF")
            self.codec_focus_button.setStyleSheet("")

    def set_developer_mode(self, enabled):
        import audio

        self.developer_mode = bool(enabled)
        audio.set_live_loudness_measurement_enabled(self.developer_mode)
        self.update_detail_meter_visibility()
        self.debug_log_button.setVisible(self.developer_mode)
        self.debug_log_placeholder.setVisible(not self.developer_mode)
        self.update_production_control_visibility()

        if self.developer_mode:
            self.developer_mode_button.setStyleSheet(
                "background: #1f5637; color: #d4ffdf; font-weight: bold;"
            )
        else:
            self.developer_mode_button.setStyleSheet("")

        self.apply_language()

    def update_production_control_visibility(self):
        """Keep advanced processing available only in Developer mode."""
        show_developer_controls = self.developer_mode
        developer_only_widgets = (
            self.developer_panel,
            self.clip_indicator,
            self.clear_clip_button,
            self.lufs_time_indicator,
            self.normalizer_gain_indicator,
            self.youtube_gain_indicator,
            self.reset_lufs_button,
            self.youtube_preset_button,
            self.browser_sample_button,
            self.podcast_preset_button,
            self.broadcast_preset_button,
            self.youtube_readiness_indicator,
            self.mute_monitor_checkbox,
            self.bypass_checkbox,
            self.limiter_checkbox,
            self.ceiling_label,
            self.limiter_ceiling_box,
            self.normalizer_checkbox,
            self.youtube_normalize_checkbox,
            self.target_label,
            self.normalizer_target_box,
            self.skin_label,
            self.theme_box,
            self.youtube_target_label,
            self.calibrate_youtube_button,
            self.reset_youtube_target_button,
            self.youtube_reference_button,
        )
        for widget in developer_only_widgets:
            widget.setVisible(show_developer_controls)

        if not show_developer_controls:
            self.limiter_ceiling_box.setCurrentIndex(
                self.limiter_ceiling_values.index(-1.0)
            )
            self.limiter_checkbox.setChecked(True)
            self.normalizer_checkbox.setChecked(False)
            self.youtube_normalize_checkbox.setChecked(False)
            self.mute_monitor_checkbox.setChecked(False)

    def update_detail_meter_visibility(self):
        """Keep detailed metering available without crowding production view."""
        show_details = self.developer_mode and not self.codec_focus_enabled
        self.meter_scroll_area.setVisible(self.developer_mode)
        for widget in self.detail_meter_widgets:
            widget.setVisible(show_details)

        # Codec Delta Monitor remains available in production view, but the
        # detailed difference graph is reserved for development checks.
        self.codec_difference.setVisible(self.developer_mode)
        self.codec_focus_button.setVisible(self.developer_mode)
        self.reset_codec_difference_button.setVisible(self.developer_mode)

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
            self.set_status(
                "YouTube calibration error",
                "YouTube調整エラー",
                error_detail=str(error),
            )
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

    def apply_youtube_reference_preset(self):
        """Avoid double codec and volume processing for an existing YouTube track."""
        self.youtube_checkbox.setChecked(False)
        self.aac_checkbox.setChecked(False)
        self.codec_delta_checkbox.setChecked(False)
        self.youtube_normalize_checkbox.setChecked(False)
        self.normalizer_checkbox.setChecked(False)
        self.set_status(
            "YouTube reference: codec bypass",
            "YouTube参考曲: 二重圧縮をOFFにしました",
        )

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
        delta_active = audio_state.codec_delta_active
        suffix = " + DELTA" if delta_active else ""
        self.codec_indicator.setText(f"CODEC: {mode}{suffix}")

        if delta_active:
            style = """
                background: #4a245c; color: #ffd8ff;
                padding: 6px; border-radius: 4px;
            """
        elif mode == "REAL OPUS":
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
        if audio_state.runtime_error_count != self.last_runtime_error_count:
            self.last_runtime_error_count = audio_state.runtime_error_count
            self.set_status(
                "Audio runtime warning",
                "再生中の音声エラー",
                error_detail=audio_state.runtime_error_message,
            )

        rate = self.rate_values[self.rate_box.currentIndex()]
        buffer_size = self.buffer_values[self.buffer_box.currentIndex()]
        latency_ms = 2000.0 * buffer_size / rate
        codec_active = audio_state.codec_preview_mode not in {"OFF", "BYPASS"}
        if codec_active:
            self.latency_indicator.setText(
                f"Base: ~{latency_ms:.0f} ms + codec delay"
            )
        else:
            self.latency_indicator.setText(
                f"Base latency: ~{latency_ms:.0f} ms"
            )
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

        self.codec_difference.set_difference(
            audio_state.codec_difference,
            audio_state.codec_difference_active,
            audio_state.sample_rate,
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

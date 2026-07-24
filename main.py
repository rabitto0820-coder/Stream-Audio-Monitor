import os
import sys
import traceback
from datetime import datetime
from pathlib import Path

import sounddevice as sd

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import (
    QApplication, QDialog, QDialogButtonBox, QPlainTextEdit, QVBoxLayout,
)

from app_info import (
    APP_NAME, APP_VERSION, saved_audio_setup_text, support_environment_text,
)
from audio import callback, configure_audio
from audio_state import audio_state
from check_devices import validate_audio_settings
from settings import load_settings
from ui import MainWindow


stream = None


def handle_unexpected_error(error_type, error, error_traceback):
    """Create a report that testers can send after an unexpected crash."""
    if issubclass(error_type, KeyboardInterrupt):
        sys.__excepthook__(error_type, error, error_traceback)
        return

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    try:
        saved_audio_settings = load_settings()
    except Exception as settings_error:
        saved_audio_settings = {}
        print(f"Could not read saved audio settings: {settings_error}")

    report_text = (
        f"{APP_NAME} crash report\n"
        f"SAM version: {APP_VERSION}\n"
        "Error code: SAM-E-UNEXPECTED\n"
        f"Time: {datetime.now().isoformat(timespec='seconds')}\n\n"
        "Environment\n"
        f"{support_environment_text()}\n\n"
        "Last saved audio setup\n"
        f"{saved_audio_setup_text(saved_audio_settings)}\n\n"
        + "".join(traceback.format_exception(error_type, error, error_traceback))
    )
    print(report_text)

    report_path = None
    try:
        local_data = Path(os.environ.get("LOCALAPPDATA", Path.home()))
        report_folder = local_data / "Stream Audio Monitor" / "logs"
        report_folder.mkdir(parents=True, exist_ok=True)
        report_path = report_folder / f"sam_crash_{timestamp}.txt"
        report_path.write_text(report_text, encoding="utf-8")
    except OSError as write_error:
        print(f"Could not write crash report: {write_error}")

    message = (
        "予期しないエラーが発生しました。\n"
        "An unexpected error occurred.\n\n"
        "エラーコード / Error code: SAM-E-UNEXPECTED\n\n"
        "このコードとクラッシュレポートを開発者へ送ってください。\n"
        "Please send this code and the crash report file to the developer."
    )
    if report_path:
        message += f"\n\nCrash report:\n{report_path}"

    try:
        dialog = QDialog()
        dialog.setWindowTitle("Stream Audio Monitor Error")
        dialog.resize(760, 360)
        dialog.setStyleSheet(
            "QDialog { background: #111111; }"
            "QPlainTextEdit {"
            "background: #111111; color: #f2f2f2;"
            "border: 2px solid #e04b4b; padding: 10px;"
            "font-weight: bold;"
            "}"
        )
        layout = QVBoxLayout(dialog)
        error_text = QPlainTextEdit()
        error_text.setReadOnly(True)
        error_text.setPlainText(
            "⚠ ERROR / エラー\n\n"
            + message
            + "\n\n────────────────────\n"
            "Crash report / クラッシュレポート\n"
            "────────────────────\n\n"
            + report_text
        )
        layout.addWidget(error_text)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        copy_button = buttons.addButton(
            "コピー / Copy",
            QDialogButtonBox.ButtonRole.ActionRole,
        )
        copy_button.clicked.connect(
            lambda _checked=False: QApplication.clipboard().setText(
                error_text.toPlainText()
            )
        )
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.exec()
    except Exception:
        pass


sys.excepthook = handle_unexpected_error


def start_stream(
    input_device,
    output_device,
    samplerate,
    blocksize
):
    global stream
    start_stream.last_error = ""

    try:
        if stream is not None:
            stream.stop()
            stream.close()
            stream = None

        print("====================")
        print("Audio Check")
        print("Input:", input_device)
        print("Output:", output_device)
        print("Sample Rate:", samplerate)

        valid, error = validate_audio_settings(
            input_device,
            output_device,
            samplerate
        )

        if not valid:
            print("====================")
            print("AUDIO SETTING ERROR")
            print(error)
            print("====================")
            start_stream.last_error = str(error)
            return False

        print("Audio Check OK")
        print("====================")
        print("Audio Start")
        print("Buffer:", blocksize)
        print("====================")

        # 新しいストリーム用にLUFS・Peakなどのメーターをリセット
        configure_audio(samplerate, channels=2)

        stream = sd.Stream(
            device=(
                input_device,
                output_device
            ),
            samplerate=samplerate,
            channels=2,
            blocksize=blocksize,
            latency="high",
            callback=callback
        )

        stream.start()
        return True

    except Exception as error:
        print("====================")
        print("AUDIO ERROR")
        print(error)
        print("====================")

        start_stream.last_error = str(error)
        stream = None
        return False


def stop_stream():
    global stream

    if stream is not None:
        try:
            stream.stop()
            stream.close()
        except Exception:
            pass

        stream = None


print("======================================")
print(f" {APP_NAME}")
print("======================================")
print(f"Version {APP_VERSION}")

app = QApplication(sys.argv)

if "--test-crash" in sys.argv:
    raise RuntimeError("Intentional SAM crash test requested")

window = MainWindow(
    start_stream,
    stop_stream
)

window.show()

if "--test-runtime-audio-error" in sys.argv:
    QTimer.singleShot(
        800,
        lambda: audio_state.report_runtime_error(
            "Intentional runtime audio warning test requested"
        ),
    )

try:
    sys.exit(app.exec())
finally:
    stop_stream()

import sounddevice as sd



def validate_audio_settings(
    input_device,
    output_device,
    samplerate
):
    """
    オーディオ設定チェック

    OK:
        True, None

    NG:
        False, エラーメッセージ
    """

    try:

        devices = sd.query_devices()


        # ==========================
        # デバイス存在確認
        # ==========================

        if input_device >= len(devices):

            return (
                False,
                f"Input device not found:\n{input_device}"
            )


        if output_device >= len(devices):

            return (
                False,
                f"Output device not found:\n{output_device}"
            )



        # ==========================
        # Inputチェック
        # ==========================

        try:

            sd.check_input_settings(
                device=input_device,
                channels=2,
                samplerate=samplerate
            )


        except Exception as e:

            return (
                False,
                "Input device error:\n\n"
                + str(e)
            )



        # ==========================
        # Outputチェック
        # ==========================

        try:

            sd.check_output_settings(
                device=output_device,
                channels=2,
                samplerate=samplerate
            )


        except Exception as e:

            return (
                False,
                "Output device error:\n\n"
                + str(e)
            )



        return (
            True,
            None
        )



    except Exception as e:

        return (
            False,
            str(e)
        )



# ==========================
# デバッグ用
# ==========================

if __name__ == "__main__":


    print(
        "=== Audio Devices ==="
    )

    print(
        sd.query_devices()
    )


    print(
        "\nDefault:"
    )

    print(
        sd.default.device
    )
import json
import os


SETTINGS_FILE = "settings.json"



def save_settings(
    input_device,
    output_device
):

    data = {
        "input_device": input_device,
        "output_device": output_device
    }


    with open(
        SETTINGS_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            data,
            f,
            indent=4
        )



def load_settings():

    if not os.path.exists(
        SETTINGS_FILE
    ):

        return None



    with open(
        SETTINGS_FILE,
        "r",
        encoding="utf-8"
    ) as f:

        return json.load(f)
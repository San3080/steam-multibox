"""Entry point Steam Multi-Box Launcher."""
import os
import shutil

import customtkinter as ctk

from src.config import load_config
from src.logbus import LogBus
from src.ui.main_window import MainWindow

CONFIG_PATH = "config.json"
CONFIG_EXAMPLE = "config.example.json"
DATA_DIR = "data"


def main():
    # buat config.json dari contoh saat pertama kali dijalankan
    if not os.path.exists(CONFIG_PATH) and os.path.exists(CONFIG_EXAMPLE):
        shutil.copyfile(CONFIG_EXAMPLE, CONFIG_PATH)

    # pastikan folder data/ untuk accounts.txt & fail.txt selalu ada
    os.makedirs(DATA_DIR, exist_ok=True)

    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    config = load_config(CONFIG_PATH)
    logbus = LogBus()
    app = MainWindow(config, CONFIG_PATH, logbus)
    logbus.log("aplikasi siap.", "", "ok")
    app.mainloop()


if __name__ == "__main__":
    main()

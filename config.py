"""
Application configuration and user settings persistence.
"""
import os
import json
from pathlib import Path

DEFAULT_DOWNLOAD_DIR = str(Path.home() / "Music" / "LosslessMusic")
CONFIG_FILE = os.path.join(os.path.dirname(__file__), "settings.json")


def load_config() -> dict:
    default_cfg = {
        "download_dir": DEFAULT_DOWNLOAD_DIR,
        "target_format": "alac",  # "alac" or "flac"
        "only_lossless": False,
        "max_results_per_source": 10,
        "embed_cover_art": True,
        "auto_open_folder": False,
    }
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                default_cfg.update(saved)
        except Exception:
            pass
    return default_cfg


def save_config(cfg: dict):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

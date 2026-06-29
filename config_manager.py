import json
from pathlib import Path

from translations import DEFAULT_LANGUAGE, TRANSLATIONS

import sys

if getattr(sys, "frozen", False):
    PROJECT_DIR = Path(sys.executable).parent
else:
    PROJECT_DIR = Path(__file__).resolve().parent

DEFAULT_OUTPUT_DIR = PROJECT_DIR / "outputs"
CONFIG_FILE = PROJECT_DIR / "config.json"


def load_config():
    if not CONFIG_FILE.exists():
        return {}

    try:
        with CONFIG_FILE.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def save_config(config):
    with CONFIG_FILE.open("w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def load_output_dir():
    DEFAULT_OUTPUT_DIR.mkdir(exist_ok=True)
    config = load_config()

    saved_path = Path(config.get("output_dir", ""))
    if not saved_path:
        return DEFAULT_OUTPUT_DIR

    try:
        saved_path.mkdir(exist_ok=True)
    except OSError:
        return DEFAULT_OUTPUT_DIR

    return saved_path


def save_output_dir(output_dir):
    config = load_config()
    config["output_dir"] = str(output_dir)
    save_config(config)


def load_language():
    language = load_config().get("language", "English")
    if language not in TRANSLATIONS:
        return "English"
    return language


def save_language(language):
    config = load_config()
    config["language"] = language
    save_config(config)


def load_fetch_pages():
    try:
        pages = int(load_config().get("fetch_pages", 1))
    except (TypeError, ValueError):
        return 1
    return max(1, pages)


def save_fetch_pages(pages):
    config = load_config()
    config["fetch_pages"] = int(pages)
    save_config(config)


def load_window_size():
    config = load_config()
    mode = config.get("window_size_mode", "Standard")
    if mode == "Maximized":
        return mode, 1280, 850

    try:
        width = int(config.get("window_width"))
        height = int(config.get("window_height"))
    except (TypeError, ValueError):
        size = config.get("window_size", {})
        try:
            width = int(size.get("width", 900))
            height = int(size.get("height", 620))
        except (AttributeError, TypeError, ValueError):
            return "Standard", 1280, 850
    except AttributeError:
        return "Standard", 1280, 850
    return mode, max(1000, width), max(700, height)


def save_window_size(mode, width, height):
    config = load_config()
    config["window_size_mode"] = mode
    config["window_width"] = int(width)
    config["window_height"] = int(height)
    save_config(config)

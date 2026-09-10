"""Project configuration: docshot.config.json plus its defaults."""

import json
import os
from typing import Dict

CONFIG_NAME = "docshot.config.json"

DEFAULTS = {
    "template": "",
    "sourceDir": "source",
    "shotsDir": "shots",
    "outDir": "build",
    "lang": "pt-BR",
    "maxImageWidthIn": 0,
    "cover": True,
    "revisionHistory": True,
    "approval": True,
    "document": {},
    "labels": {},
    "consolidated": {},
}


def find(start: str = ".") -> str:
    """Nearest docshot.config.json, walking up from `start`."""
    current = os.path.abspath(start)
    while True:
        candidate = os.path.join(current, CONFIG_NAME)
        if os.path.exists(candidate):
            return candidate
        parent = os.path.dirname(current)
        if parent == current:
            raise SystemExit(
                "no %s found (looked from %s upwards)" % (CONFIG_NAME, os.path.abspath(start))
            )
        current = parent


def load(path: str) -> Dict:
    with open(path, encoding="utf-8") as fh:
        raw = json.load(fh)

    config = dict(DEFAULTS)
    config.update(raw)

    root = os.path.dirname(os.path.abspath(path))
    config["root"] = root
    for key in ("sourceDir", "shotsDir", "outDir", "template"):
        if config[key]:
            config[key] = os.path.join(root, os.path.expanduser(config[key]))
    return config

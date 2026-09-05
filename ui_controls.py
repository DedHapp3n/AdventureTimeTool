"""Small shared visual controls; actions stay with their callers."""

import json
from functools import lru_cache

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QPushButton

from app_paths import resource_path, ui_icon_path


@lru_cache(maxsize=1)
def stepper_config():
    """Universal settings live once in the default dialog layout, across themes."""
    defaults = {
        "minus_asset": "ui_elements/icons/minus.jpg",
        "plus_asset": "ui_elements/icons/plus.jpg",
        "w": 32,
        "h": 32,
    }
    try:
        config = json.loads(resource_path("assets/themes/diablo/roll_dialog_layout.json").read_text(encoding="utf-8"))
        defaults.update(config.get("shared_ui", {}).get("stepper", {}))
    except (OSError, ValueError, AttributeError, TypeError):
        pass
    return defaults


def create_step_button(parent, direction, tooltip=None):
    cfg = stepper_config()
    button = QPushButton(parent)
    button.setFixedSize(int(cfg["w"]), int(cfg["h"]))
    button.setCursor(Qt.PointingHandCursor)
    description = tooltip or ("Erhöhen" if direction == "+" else "Verringern")
    button.setToolTip(description)
    button.setAccessibleName(description)
    button.setStyleSheet(
        "QPushButton { background: transparent; border: none; padding: 0px; }"
        "QPushButton:hover, QPushButton:pressed { background: transparent; border: none; }"
    )
    pixmap = QPixmap(str(ui_icon_path(cfg["plus_asset" if direction == "+" else "minus_asset"])))
    if not pixmap.isNull():
        pixmap = pixmap.scaled(button.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        button.setIcon(QIcon(pixmap))
        button.setIconSize(pixmap.size())
    return button

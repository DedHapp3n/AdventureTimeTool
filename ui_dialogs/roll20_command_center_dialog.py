import json

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app_logger import log_warning_once
from app_paths import load_settings, save_settings
from ui_dialogs.window_chrome import install_frameless_dialog_chrome


HISTORY_KEY = "roll20_command_center"
MAX_HISTORY = 40
MODES = ["Schnellbefehl", "Chat", "Würfel", "Makro", "Verlauf"]
GOLD = "#f2d28b"
GOLD_DARK = "#d8aa4c"
TEXT = "#eadfca"
MUTED = "#c8c0aa"
VALUE_BLUE = "#7fd0ff"


class Roll20CommandCenterDialog(QDialog):
    def __init__(self, parent=None, insert_callback=None, show_browser_callback=None):
        super().__init__(parent)
        self.insert_callback = insert_callback
        self.show_browser_callback = show_browser_callback
        self.history = _load_history()
        self.mode_buttons = []
        self.setWindowTitle("Roll20 Command Center")
        self.setModal(False)
        install_frameless_dialog_chrome(self)

        self.ui_cfg = _command_center_cfg(parent)
        dialog_w = _safe_int(self.ui_cfg.get("w", 680), 680)
        dialog_h = _safe_int(self.ui_cfg.get("h", 600), 600)
        self.resize(dialog_w, dialog_h)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAutoFillBackground(False)
        self.setStyleSheet(_tool_stylesheet(parent, self.ui_cfg))
        _add_dialog_background(self, parent, dialog_w, dialog_h)

        close_button = _make_close_button(self, parent)
        if close_button is not None:
            close_button.clicked.connect(self.close)

        margins = _margins(self.ui_cfg.get("margins", [30, 24, 30, 24]), [30, 24, 30, 24])
        root = QVBoxLayout(self)
        root.setContentsMargins(*margins)
        root.setSpacing(_safe_int(self.ui_cfg.get("spacing", 9), 9))

        title = QLabel("Roll20 Command Center")
        title.setObjectName("DialogTitle")
        title.setAlignment(Qt.AlignCenter)
        title.installEventFilter(self._frameless_drag_filter)
        root.addWidget(title)

        nav = QHBoxLayout()
        nav.setSpacing(_safe_int(self.ui_cfg.get("nav_spacing", 6), 6))
        for index, mode in enumerate(MODES):
            button = _make_nav_button(mode, parent, self.ui_cfg)
            button.clicked.connect(lambda _checked=False, idx=index: self._set_mode(idx))
            self.mode_buttons.append(button)
            nav.addWidget(button)
        root.addLayout(nav)

        self.pages = QStackedWidget(self)
        root.addWidget(self.pages, 1)
        self._build_quick_page()
        self._build_chat_page()
        self._build_dice_page()
        self._build_macro_page()
        self._build_history_page()

        preview_label = QLabel("Roll20-Befehl")
        preview_label.setObjectName("SectionTitle")
        root.addWidget(preview_label)

        self.preview = QTextEdit()
        self.preview.setObjectName("CommandPreview")
        self.preview.setFixedHeight(_safe_int(self.ui_cfg.get("preview_h", 82), 82))
        self.preview.setAcceptRichText(False)
        root.addWidget(self.preview)

        self.status = QLabel("")
        self.status.setObjectName("Status")
        self.status.setWordWrap(True)
        root.addWidget(self.status)

        actions = QHBoxLayout()
        actions.setSpacing(_safe_int(self.ui_cfg.get("action_spacing", 10), 10))
        actions.addStretch()
        self.copy_button = _make_action_button("Kopieren", parent, self.ui_cfg)
        self.insert_button = _make_action_button("In Roll20-Chat einsetzen", parent, self.ui_cfg, wide=True)
        self.close_button = _make_action_button("Schließen", parent, self.ui_cfg)
        for button in (self.copy_button, self.insert_button, self.close_button):
            actions.addWidget(button)
        actions.addStretch()
        self.copy_button.clicked.connect(self.copy_command)
        self.insert_button.clicked.connect(self.insert_command)
        self.close_button.clicked.connect(self.close)
        root.addLayout(actions)

        if close_button is not None:
            close_button.raise_()
        self._set_mode(0)
        self.update_preview()
        self._refresh_history()

    def _build_quick_page(self):
        page, layout = _page()
        self.quick_type = QComboBox()
        self.quick_type.addItems(["Normaler Wurf", "GM-Wurf", "Emote", "OOC", "Whisper", "Beschreibung", "Freier Befehl"])
        self.quick_dice = QLineEdit("1d20")
        self.quick_recipient = QLineEdit("gm")
        self.quick_text = QTextEdit()
        self.quick_text.setAcceptRichText(False)
        self.quick_text.setPlaceholderText("Text, Würfelausdruck oder freier Befehl")
        self.quick_text.setFixedHeight(_safe_int(self.ui_cfg.get("text_h", 96), 96))
        _add_labeled(layout, "Typ", self.quick_type)
        _add_labeled(layout, "Würfel", self.quick_dice)
        _add_labeled(layout, "Empfänger", self.quick_recipient)
        _add_labeled(layout, "Text", self.quick_text)
        self.pages.addWidget(page)
        self.quick_type.currentIndexChanged.connect(self.update_preview)
        self.quick_dice.textChanged.connect(self.update_preview)
        self.quick_recipient.textChanged.connect(self.update_preview)
        self.quick_text.textChanged.connect(self.update_preview)

    def _build_chat_page(self):
        page, layout = _page()
        self.chat_type = QComboBox()
        self.chat_type.addItems(["Chat", "Emote", "OOC", "Beschreibung"])
        self.chat_text = QTextEdit()
        self.chat_text.setAcceptRichText(False)
        self.chat_text.setFixedHeight(_safe_int(self.ui_cfg.get("large_text_h", 150), 150))
        self.chat_text.setPlaceholderText("Text mit optionalen Roll20 Inline Rolls wie [[3d10+4]]")
        _add_labeled(layout, "Format", self.chat_type)
        _add_labeled(layout, "Text", self.chat_text)
        self.pages.addWidget(page)
        self.chat_type.currentIndexChanged.connect(self.update_preview)
        self.chat_text.textChanged.connect(self.update_preview)

    def _build_dice_page(self):
        page, layout = _page()
        self.dice_gm = QCheckBox("GM-Wurf")
        self.dice_gm.setObjectName("AssetCheckbox")
        self.dice_expr = QLineEdit("1d20")
        self.dice_expr.setPlaceholderText("z.B. 3d20kh1+11")
        _add_labeled(layout, "Ausdruck", self.dice_expr)
        layout.addWidget(self.dice_gm)
        dice_buttons = QHBoxLayout()
        dice_buttons.setSpacing(6)
        for die in ("d4", "d6", "d8", "d10", "d12", "d20", "d100"):
            button = _make_dice_button(die, self.parent(), self.ui_cfg)
            button.clicked.connect(lambda _checked=False, value=die: self._append_die(value))
            dice_buttons.addWidget(button)
        layout.addLayout(dice_buttons)
        self.pages.addWidget(page)
        self.dice_gm.stateChanged.connect(self.update_preview)
        self.dice_expr.textChanged.connect(self.update_preview)

    def _build_macro_page(self):
        page, layout = _page()
        self.macro_text = QTextEdit()
        self.macro_text.setAcceptRichText(False)
        self.macro_text.setFixedHeight(_safe_int(self.ui_cfg.get("large_text_h", 150), 150))
        self.macro_text.setPlaceholderText("#MeinMakro oder %{Character|Ability} oder ein anderer Roll20-Befehl")
        _add_labeled(layout, "Makro / Freier Befehl", self.macro_text)
        self.pages.addWidget(page)
        self.macro_text.textChanged.connect(self.update_preview)

    def _build_history_page(self):
        page, layout = _page()
        self.history_list = QListWidget()
        self.history_list.setObjectName("HistoryList")
        self.history_list.itemClicked.connect(self._history_clicked)
        layout.addWidget(self.history_list)
        self.pages.addWidget(page)

    def _set_mode(self, index):
        self.pages.setCurrentIndex(index)
        for button_index, button in enumerate(self.mode_buttons):
            _set_nav_button_active(button, button_index == index, self.parent(), self.ui_cfg)
        self.update_preview()

    def _append_die(self, die):
        text = self.dice_expr.text().strip()
        self.dice_expr.setText((text + "+" if text else "1") + die)

    def _history_clicked(self, item):
        command = item.data(Qt.UserRole) or item.text()
        self.macro_text.setPlainText(str(command))
        self._set_mode(3)

    def current_command(self):
        index = self.pages.currentIndex()
        if index == 0:
            return self._quick_command()
        if index == 1:
            return self._chat_command()
        if index == 2:
            prefix = "/gmroll" if self.dice_gm.isChecked() else "/r"
            return _join_command(prefix, self.dice_expr.text())
        if index == 3:
            return self.macro_text.toPlainText().strip()
        item = self.history_list.currentItem()
        return str(item.data(Qt.UserRole) if item is not None else "").strip()

    def _quick_command(self):
        kind = self.quick_type.currentText()
        text = self.quick_text.toPlainText().strip()
        dice = self.quick_dice.text().strip()
        if kind == "Normaler Wurf":
            return _join_command("/r", dice or text)
        if kind == "GM-Wurf":
            return _join_command("/gmroll", dice or text)
        if kind == "Emote":
            return _join_command("/em", text)
        if kind == "OOC":
            return _join_command("/ooc", text)
        if kind == "Whisper":
            return f"/w {self.quick_recipient.text().strip()} {text}".strip()
        if kind == "Beschreibung":
            return _join_command("/desc", text)
        return text

    def _chat_command(self):
        kind = self.chat_type.currentText()
        text = self.chat_text.toPlainText().strip()
        if kind == "Emote":
            return _join_command("/em", text)
        if kind == "OOC":
            return _join_command("/ooc", text)
        if kind == "Beschreibung":
            return _join_command("/desc", text)
        return text

    def update_preview(self):
        self.preview.setPlainText(self.current_command())

    def copy_command(self):
        command = self.current_command()
        if not command:
            self.status.setText("Kein Befehl vorhanden.")
            return
        QApplication.clipboard().setText(command)
        self._remember(command)
        self.status.setText("Befehl kopiert.")

    def insert_command(self):
        command = self.current_command()
        if not command:
            self.status.setText("Kein Befehl vorhanden.")
            return
        self._remember(command)
        if callable(self.show_browser_callback):
            self.show_browser_callback()
        if not callable(self.insert_callback):
            QApplication.clipboard().setText(command)
            self.status.setText("Roll20-Chatfeld nicht gefunden. Befehl wurde kopiert.")
            return

        def done(success):
            if success:
                self.status.setText("Befehl in Roll20-Chat eingesetzt. Nicht gesendet.")
            else:
                QApplication.clipboard().setText(command)
                self.status.setText("Roll20-Chatfeld nicht gefunden. Befehl wurde kopiert.")

        self.insert_callback(command, done)

    def _remember(self, command):
        command = str(command or "").strip()
        if not command:
            return
        self.history = [item for item in self.history if item != command]
        self.history.insert(0, command)
        self.history = self.history[:MAX_HISTORY]
        _save_history(self.history)
        self._refresh_history()

    def _refresh_history(self):
        if not hasattr(self, "history_list"):
            return
        self.history_list.clear()
        for command in self.history:
            label = command if len(command) <= 92 else command[:89] + "..."
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, command)
            self.history_list.addItem(item)


def _page():
    page = QWidget()
    page.setObjectName("TransparentPage")
    layout = QVBoxLayout(page)
    layout.setContentsMargins(4, 8, 4, 8)
    layout.setSpacing(8)
    return page, layout


def _add_labeled(layout, label_text, widget):
    label = QLabel(label_text)
    label.setObjectName("SectionTitle")
    layout.addWidget(label)
    layout.addWidget(widget)


def _join_command(prefix, body):
    body = str(body or "").strip()
    return f"{prefix} {body}".strip()


def _load_history():
    try:
        settings, _created = load_settings()
        data = settings.get(HISTORY_KEY, {})
        history = data.get("history", []) if isinstance(data, dict) else []
        return [str(item) for item in history if str(item or "").strip()][:MAX_HISTORY]
    except Exception as exc:
        log_warning_once("roll20_command_center", "history-load", f"roll20 command history load failed: {exc}")
        return []


def _save_history(history):
    try:
        settings, _created = load_settings()
        data = settings.setdefault(HISTORY_KEY, {})
        if not isinstance(data, dict):
            data = {}
            settings[HISTORY_KEY] = data
        data["history"] = list(history)[:MAX_HISTORY]
        save_settings(settings)
    except Exception as exc:
        log_warning_once("roll20_command_center", "history-save", f"roll20 command history save failed: {exc}")


def _command_center_cfg(window):
    roll_layout = _load_roll_dialog_layout(window)
    resource_dialog = _dict(roll_layout.get("resource_dialog"))
    return {
        "w": 680,
        "h": 600,
        "margins": [30, 24, 30, 24],
        "spacing": _safe_int(resource_dialog.get("spacing", 8), 8),
        "nav_spacing": 6,
        "text_h": 96,
        "large_text_h": 150,
        "preview_h": _safe_int(_dict(resource_dialog.get("command")).get("h", 40), 40) + 38,
        "background_asset": resource_dialog.get("background_asset", "panels/main_Frame.png"),
        "button_asset": _dict(resource_dialog.get("buttons")).get("asset", "buttons/menu_button_medium.png"),
        "small_button_asset": "buttons/menu_button_small.png",
        "input_frame": _dict(resource_dialog.get("value")).get("frame", "frames/256x122_box.png"),
        "preview_frame": _dict(resource_dialog.get("command")).get("frame", "frames/1024x122_box.png"),
        "close_asset": _dict(resource_dialog.get("close_button")).get("asset", "ui_elements/icons/x.jpg"),
        "check_true": "ui_elements/icons/checkmark_true.png",
        "check_false": "ui_elements/icons/checkmark_false.png",
    }


def _load_roll_dialog_layout(window):
    if window is None:
        return {}
    try:
        active_theme = window.get_active_theme() if hasattr(window, "get_active_theme") else "diablo"
        assets_dir = window.assets_dir
        for path in (
            assets_dir / "themes" / active_theme / "roll_dialog_layout.json",
            assets_dir / "themes" / "diablo" / "roll_dialog_layout.json",
        ):
            if path.exists():
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    return data
    except Exception as exc:
        log_warning_once("roll20_command_center", "layout-load", f"roll20 command center layout load failed: {exc}")
    return {}


def _dict(value):
    return value if isinstance(value, dict) else {}


def _safe_int(value, default):
    try:
        return int(value)
    except Exception:
        return default


def _margins(value, default):
    if isinstance(value, (list, tuple)) and len(value) == 4:
        return tuple(_safe_int(item, default[index]) for index, item in enumerate(value))
    return tuple(default)


def _asset_path(window, relative_path):
    rel = str(relative_path or "").strip().replace("\\", "/").lstrip("/")
    if not rel or window is None:
        return None
    candidates = []
    try:
        theme_base = window.theme_asset_base_path
        assets_dir = window.assets_dir
        candidates.extend([
            theme_base / rel,
            theme_base / "ui" / rel,
            assets_dir / "themes" / "diablo" / rel,
            assets_dir / "themes" / "diablo" / "ui" / rel,
            assets_dir / rel,
        ])
    except Exception:
        return None
    for candidate in candidates:
        try:
            if candidate.exists():
                return candidate
        except Exception:
            continue
    return None


def _asset_url(window, relative_path):
    path = _asset_path(window, relative_path)
    return path.as_posix() if path is not None else ""


def _asset_background(window, relative_path, fallback):
    url = _asset_url(window, relative_path)
    if url:
        return f"border-image: url({url}) 0 0 0 0 stretch stretch;"
    return fallback


def _add_dialog_background(dialog, window, width, height):
    path = _asset_path(window, dialog.ui_cfg.get("background_asset", "panels/main_Frame.png"))
    if path is None:
        return
    pixmap = QPixmap(str(path))
    if pixmap.isNull():
        return
    label = QLabel(dialog)
    label.setGeometry(0, 0, width, height)
    label.setPixmap(pixmap.scaled(width, height, Qt.IgnoreAspectRatio, Qt.SmoothTransformation))
    label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
    label.lower()


def _make_close_button(dialog, window):
    path = _asset_path(window, dialog.ui_cfg.get("close_asset", "ui_elements/icons/x.jpg"))
    if path is None:
        return None
    button = QPushButton(dialog)
    button.setGeometry(dialog.width() - 44, 16, 24, 24)
    button.setIcon(QIcon(str(path)))
    button.setIconSize(button.size())
    button.setCursor(Qt.PointingHandCursor)
    button.setStyleSheet("QPushButton { background: transparent; border: none; padding: 0px; }")
    return button


def _make_nav_button(text, window, cfg):
    button = QPushButton(text)
    button.setObjectName("ModeButton")
    button.setCursor(Qt.PointingHandCursor)
    button.setMinimumHeight(34)
    button.setMinimumWidth(112)
    icon_path = _asset_path(window, cfg.get("check_false", "ui_elements/icons/checkmark_false.png"))
    if icon_path is not None:
        button.setIcon(QIcon(str(icon_path)))
        button.setIconSize(QSize(16, 16))
    return button


def _set_nav_button_active(button, active, window, cfg):
    button.setProperty("active", "true" if active else "false")
    icon_path = _asset_path(window, cfg.get("check_true" if active else "check_false"))
    if icon_path is not None:
        button.setIcon(QIcon(str(icon_path)))
    button.style().unpolish(button)
    button.style().polish(button)


def _make_action_button(text, window, cfg, wide=False):
    button = QPushButton(text)
    button.setObjectName("ActionButton")
    button.setCursor(Qt.PointingHandCursor)
    button.setFixedHeight(36)
    button.setMinimumWidth(220 if wide else 126)
    return button


def _make_dice_button(text, window, cfg):
    button = QPushButton(text)
    button.setObjectName("DiceButton")
    button.setCursor(Qt.PointingHandCursor)
    button.setFixedHeight(30)
    return button


def _tool_stylesheet(window, cfg):
    button_bg = _asset_background(window, cfg.get("button_asset"), "background: rgba(30, 22, 14, 230);")
    small_button_bg = _asset_background(window, cfg.get("small_button_asset"), button_bg)
    input_bg = _asset_background(window, cfg.get("input_frame"), "background: rgba(0, 0, 0, 145);")
    preview_bg = _asset_background(window, cfg.get("preview_frame"), "background: rgba(0, 0, 0, 170);")
    checked = _asset_url(window, cfg.get("check_true"))
    unchecked = _asset_url(window, cfg.get("check_false"))
    checkbox_style = ""
    if checked and unchecked:
        checkbox_style = (
            "QCheckBox::indicator { width: 18px; height: 18px; }"
            f"QCheckBox::indicator:checked {{ image: url({checked}); }}"
            f"QCheckBox::indicator:unchecked {{ image: url({unchecked}); }}"
        )
    return f"""
QDialog {{
    background: transparent;
    color: {TEXT};
    border: none;
    font-size: 13px;
}}
QWidget#TransparentPage {{
    background: transparent;
}}
QLabel {{
    background: transparent;
    color: {TEXT};
}}
QLabel#DialogTitle {{
    color: {GOLD};
    font-size: 21px;
    font-weight: 800;
    padding: 0px 36px 3px 36px;
}}
QLabel#SectionTitle {{
    color: {GOLD_DARK};
    font-weight: 700;
}}
QLabel#Status {{
    color: {MUTED};
    min-height: 20px;
}}
QPushButton#ModeButton, QPushButton#ActionButton {{
    {button_bg}
    border: none;
    color: {GOLD};
    font-weight: 700;
    padding: 5px 10px;
}}
QPushButton#ModeButton[active="false"] {{
    color: {MUTED};
}}
QPushButton#ModeButton[active="true"] {{
    color: #ffffff;
}}
QPushButton#ModeButton:hover, QPushButton#ActionButton:hover {{
    color: #fff1be;
}}
QPushButton#DiceButton {{
    {small_button_bg}
    border: none;
    color: {GOLD};
    font-weight: 700;
    padding: 3px 8px;
}}
QPushButton#DiceButton:hover {{
    color: #ffffff;
}}
QLineEdit, QTextEdit, QComboBox {{
    {input_bg}
    border: none;
    color: {TEXT};
    padding: 7px 9px;
    selection-background-color: rgba(95, 69, 30, 180);
    selection-color: #ffffff;
}}
QComboBox QAbstractItemView {{
    background: #211812;
    color: {TEXT};
    selection-background-color: rgba(95, 69, 30, 220);
}}
QTextEdit#CommandPreview {{
    {preview_bg}
    border: none;
    color: {VALUE_BLUE};
    font-size: 16px;
    font-weight: 700;
}}
QListWidget#HistoryList {{
    {preview_bg}
    border: none;
    color: {TEXT};
    padding: 8px;
}}
QListWidget#HistoryList::item {{
    padding: 5px 8px;
}}
QListWidget#HistoryList::item:selected {{
    color: #ffffff;
    background: rgba(95, 69, 30, 180);
}}
QCheckBox#AssetCheckbox {{
    color: {TEXT};
    spacing: 7px;
    background: transparent;
}}
{checkbox_style}
"""

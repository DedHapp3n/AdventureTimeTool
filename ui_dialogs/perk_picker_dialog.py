from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from game_rules_loader import get_perks_by_type, load_perk_catalog


def _get_perk_catalog(window):
    catalog = getattr(window, "_perk_catalog", None)
    if isinstance(catalog, dict):
        return catalog
    catalog = load_perk_catalog()
    window._perk_catalog = catalog if isinstance(catalog, dict) else {}
    return window._perk_catalog


def _button_asset_url(window, asset_name):
    try:
        primary = window.theme_asset_base_path / "buttons" / asset_name
        if primary.exists():
            return primary.as_posix()
        fallback = window.assets_dir / "themes" / "diablo" / "ui" / "buttons" / asset_name
        if fallback.exists():
            return fallback.as_posix()
    except Exception:
        return ""
    return ""


def _frame_asset_url(window, asset_name):
    candidates = []
    try:
        theme_base = window.theme_asset_base_path
        assets_dir = window.assets_dir
        candidates = [
            theme_base / "frames" / asset_name,
            theme_base / "boxes" / asset_name,
            theme_base / "ui" / "frames" / asset_name,
            theme_base / "ui" / "boxes" / asset_name,
            assets_dir / "themes" / "diablo" / "ui" / "frames" / asset_name,
            assets_dir / "themes" / "diablo" / "ui" / "boxes" / asset_name,
            assets_dir / "themes" / "diablo" / "frames" / asset_name,
            assets_dir / "themes" / "diablo" / "boxes" / asset_name,
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate.as_posix()
    except Exception:
        return ""
    try:
        if not getattr(window, "_perk_picker_frame_asset_missing_logged", False):
            window._perk_picker_frame_asset_missing_logged = True
            if hasattr(window, "_character_debug"):
                window._character_debug(f"[PERK PICKER] missing row frame asset: {asset_name}")
    except Exception:
        pass
    return ""


def _dialog_stylesheet(window):
    button_asset = _button_asset_url(window, "menu_button_medium.png")
    button_style = (
        f"border-image: url({button_asset}) 16 18 16 18 stretch stretch;"
        if button_asset
        else "background: #3a2019; border: 1px solid #8a642c;"
    )
    return f"""
    QDialog {{
        background: #140f0c;
        color: #eadfca;
    }}
    QLabel {{
        color: #eadfca;
    }}
    QLabel#PickerTitle {{
        color: #d8aa4c;
        font-size: 19px;
        font-weight: 700;
    }}
    QLineEdit, QListWidget, QTextEdit {{
        background: #211812;
        color: #eadfca;
        border: 1px solid #6b4a22;
        selection-background-color: transparent;
        selection-color: #eadfca;
    }}
    QListWidget::item {{
        background: transparent;
        border: none;
        padding: 1px 0px;
    }}
    QListWidget::item:selected {{
        background: transparent;
        border: none;
    }}
    QPushButton {{
        {button_style}
        color: #f3dfb2;
        font-size: 13px;
        min-width: 104px;
        min-height: 30px;
        max-height: 38px;
        padding: 1px 10px;
        font-weight: 700;
    }}
    QPushButton:hover {{
        color: #fff3d6;
    }}
    QPushButton:disabled {{
        color: #8c8170;
    }}
    """


def _entries_for_type(window, perk_type):
    requested_type = "disadvantage" if str(perk_type) == "disadvantage" else "perk"
    return requested_type, get_perks_by_type(_get_perk_catalog(window), requested_type)


def _entry_search_text(entry):
    parts = [
        entry.get("name", ""),
        entry.get("effect", ""),
        entry.get("description", ""),
        " ".join(str(item) for item in entry.get("tags", []) if item),
        " ".join(str(item) for item in entry.get("species", []) if item),
    ]
    return " ".join(str(part) for part in parts).casefold()


def _format_detail(entry):
    if not isinstance(entry, dict):
        return "Keine Einträge gefunden"
    rows = [
        f"Name: {entry.get('name', '')}",
        f"Typ: {entry.get('type', '')}",
        f"Kategorie: {entry.get('category', '')}",
        f"BP: {entry.get('bp', 0)}",
        "",
        f"Effekt: {entry.get('effect', '')}",
        f"Beschreibung: {entry.get('description', '')}",
    ]
    species = entry.get("species", [])
    requirements = entry.get("requirements", [])
    tags = entry.get("tags", [])
    if species:
        rows.append(f"Spezies: {', '.join(str(item) for item in species)}")
    if requirements:
        rows.append(f"Voraussetzungen: {', '.join(str(item) for item in requirements)}")
    if tags:
        rows.append(f"Tags: {', '.join(str(item) for item in tags)}")
    return "\n".join(rows)


def _entry_row_frame_pixmap(window):
    pixmap = getattr(window, "_perk_picker_row_frame_pixmap", None)
    if isinstance(pixmap, QPixmap):
        return pixmap
    frame_asset = _frame_asset_url(window, "512x122_box.png")
    pixmap = QPixmap(frame_asset) if frame_asset else QPixmap()
    window._perk_picker_row_frame_pixmap = pixmap
    return pixmap


class PerkPickerRowWidget(QWidget):
    def __init__(self, window, entry, list_widget, item, on_activate):
        super().__init__()
        self._window = window
        self._entry = entry
        self._list_widget = list_widget
        self._item = item
        self._on_activate = on_activate
        self._hovered = False
        self._selected = False
        self.setObjectName("PerkPickerRow")
        self.setMinimumHeight(42)
        self.setMaximumHeight(48)
        self.setMouseTracking(True)
        self.setStyleSheet("background: transparent; border: none;")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 5, 16, 5)
        layout.setSpacing(8)

        self.name_label = QLabel(str(entry.get("name", "")), self)
        self.name_label.setStyleSheet("color: #f0d38a; font-size: 13px; font-weight: 700; background: transparent;")
        self.name_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        layout.addWidget(self.name_label, 1)

        self.bp_label = QLabel(f"BP {entry.get('bp', 0)}", self)
        self.bp_label.setStyleSheet("color: #39b8ff; font-size: 13px; font-weight: 700; background: transparent;")
        self.bp_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        layout.addWidget(self.bp_label, 0)

        self.category_label = QLabel(str(entry.get("category", "")), self)
        self.category_label.setStyleSheet("color: #bfa77c; font-size: 12px; background: transparent;")
        self.category_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.category_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(self.category_label, 0)
        self.set_selected(False)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        painter.fillRect(self.rect(), QColor(14, 10, 7, 235))

        frame = _entry_row_frame_pixmap(self._window)
        if not frame.isNull():
            painter.drawPixmap(self.rect(), frame)

        if self._selected:
            painter.fillRect(self.rect().adjusted(3, 3, -3, -3), QColor(130, 82, 25, 86))
            painter.setPen(QColor(235, 178, 66, 235))
        elif self._hovered:
            painter.fillRect(self.rect().adjusted(3, 3, -3, -3), QColor(92, 58, 22, 65))
            painter.setPen(QColor(205, 148, 58, 210))
        else:
            painter.fillRect(self.rect().adjusted(3, 3, -3, -3), QColor(20, 14, 10, 72))
            painter.setPen(QColor(145, 102, 45, 180))
        painter.drawRect(self.rect().adjusted(1, 1, -2, -2))

    def _refresh_style(self):
        if self._selected:
            self.name_label.setStyleSheet("color: #ffe6a6; font-size: 13px; font-weight: 700; background: transparent;")
            self.category_label.setStyleSheet("color: #d6be8e; font-size: 12px; background: transparent;")
        elif self._hovered:
            self.name_label.setStyleSheet("color: #f8dda0; font-size: 13px; font-weight: 700; background: transparent;")
            self.category_label.setStyleSheet("color: #ccb383; font-size: 12px; background: transparent;")
        else:
            self.name_label.setStyleSheet("color: #f0d38a; font-size: 13px; font-weight: 700; background: transparent;")
            self.category_label.setStyleSheet("color: #bfa77c; font-size: 12px; background: transparent;")
        self.update()

    def set_selected(self, selected):
        self._selected = bool(selected)
        self._refresh_style()

    def enterEvent(self, event):
        self._hovered = True
        self._refresh_style()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self._refresh_style()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        self._list_widget.setCurrentItem(self._item)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        self._list_widget.setCurrentItem(self._item)
        self._on_activate()
        super().mouseDoubleClickEvent(event)


def open_perk_picker(window, perk_type, current_entry=None):
    requested_type, entries = _entries_for_type(window, perk_type)
    dialog = QDialog(window)
    dialog.setWindowTitle("Nachteil auswählen" if requested_type == "disadvantage" else "Perk auswählen")
    dialog.resize(760, 540)
    dialog.setStyleSheet(_dialog_stylesheet(window))

    result = {"value": None}
    selected_entry = {"value": current_entry if isinstance(current_entry, dict) else None}

    root = QVBoxLayout(dialog)
    root.setContentsMargins(16, 14, 16, 14)
    root.setSpacing(10)

    title = QLabel("Nachteil-Katalog" if requested_type == "disadvantage" else "Perk-Katalog", dialog)
    title.setObjectName("PickerTitle")
    root.addWidget(title)

    search = QLineEdit(dialog)
    search.setPlaceholderText("Suchen...")
    root.addWidget(search)

    body = QHBoxLayout()
    body.setSpacing(10)
    root.addLayout(body, 1)

    list_widget = QListWidget(dialog)
    list_widget.setSpacing(3)
    list_widget.setUniformItemSizes(False)
    body.addWidget(list_widget, 2)

    detail = QTextEdit(dialog)
    detail.setReadOnly(True)
    body.addWidget(detail, 3)

    buttons = QHBoxLayout()
    buttons.addStretch(1)
    delete_button = QPushButton("Löschen", dialog)
    cancel_button = QPushButton("Abbrechen", dialog)
    select_button = QPushButton("Auswählen", dialog)
    select_button.setEnabled(False)
    for button in (delete_button, cancel_button, select_button):
        button.setFixedHeight(36)
    buttons.addWidget(delete_button)
    buttons.addWidget(cancel_button)
    buttons.addWidget(select_button)
    root.addLayout(buttons)

    def refresh_list():
        query = search.text().strip().casefold()
        list_widget.clear()
        selected_entry["value"] = None
        select_button.setEnabled(False)
        detail.setPlainText("")
        filtered = [entry for entry in entries if not query or query in _entry_search_text(entry)]
        for entry in filtered:
            item = QListWidgetItem()
            item.setSizeHint(QSize(0, 48))
            item.setData(Qt.UserRole, entry)
            list_widget.addItem(item)
            list_widget.setItemWidget(item, PerkPickerRowWidget(window, entry, list_widget, item, confirm_selection))
        if not filtered:
            detail.setPlainText("Keine Einträge gefunden")

    def refresh_row_selection():
        current = list_widget.currentItem()
        for index in range(list_widget.count()):
            item = list_widget.item(index)
            row = list_widget.itemWidget(item)
            if isinstance(row, PerkPickerRowWidget):
                row.set_selected(item is current)

    def on_current_changed(current, _previous):
        entry = current.data(Qt.UserRole) if current is not None else None
        selected_entry["value"] = entry if isinstance(entry, dict) else None
        select_button.setEnabled(isinstance(entry, dict))
        detail.setPlainText(_format_detail(entry))
        refresh_row_selection()

    def confirm_selection():
        entry = selected_entry.get("value")
        if isinstance(entry, dict):
            result["value"] = {"action": "select", "entry": entry}
            dialog.accept()

    def delete_row():
        result["value"] = {"action": "delete"}
        dialog.accept()

    search.textChanged.connect(refresh_list)
    list_widget.currentItemChanged.connect(on_current_changed)
    list_widget.itemDoubleClicked.connect(lambda _item: confirm_selection())
    select_button.clicked.connect(confirm_selection)
    delete_button.clicked.connect(delete_row)
    cancel_button.clicked.connect(dialog.reject)

    refresh_list()
    if dialog.exec() == QDialog.Accepted:
        return result["value"]
    return None

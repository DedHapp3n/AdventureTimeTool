from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import QInputDialog


class _EditablePanelTextFilter(QObject):
    def __init__(self, label, value, title, on_save, dialog_opener=None):
        super().__init__(label)
        self.label = label
        self.value = "" if value is None else str(value)
        self.title = str(title or "Feld bearbeiten")
        self.on_save = on_save
        self.dialog_opener = dialog_opener

    def eventFilter(self, watched, event):
        if watched is self.label and event.type() == QEvent.MouseButtonDblClick and event.button() == Qt.LeftButton:
            if callable(self.dialog_opener):
                new_value, accepted = self.dialog_opener(self.title, self.value)
            else:
                new_value, accepted = QInputDialog.getText(self.label, self.title, "Wert:", text=self.value)
            if accepted and callable(self.on_save):
                self.on_save(str(new_value))
            return True
        return False


def create_editable_panel_text(window, parent, rect_cfg, value, font_size, color, on_save, *, title="Feld bearbeiten", bold=True, align="left"):
    display_value = "" if value is None else str(value)
    label = window.create_panel_text(parent, rect_cfg, display_value, font_size, color, bold=bold, align=align)
    opener = getattr(window, "_open_character_field_dialog", None)
    event_filter = _EditablePanelTextFilter(label, display_value, title, on_save, opener if callable(opener) else None)
    label.installEventFilter(event_filter)
    label.setCursor(Qt.IBeamCursor)
    label.setProperty("panel_text_editable", True)
    return label

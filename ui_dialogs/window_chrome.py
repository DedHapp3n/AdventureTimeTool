from PySide6.QtCore import QObject, QEvent, Qt


class FramelessDialogDragFilter(QObject):
    def __init__(self, dialog):
        super().__init__(dialog)
        self._dialog = dialog
        self._drag_offset = None

    def eventFilter(self, obj, event):
        if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self._dialog.frameGeometry().topLeft()
            return False
        if event.type() == QEvent.MouseMove and self._drag_offset is not None:
            if event.buttons() & Qt.LeftButton:
                self._dialog.move(event.globalPosition().toPoint() - self._drag_offset)
                return True
        if event.type() == QEvent.MouseButtonRelease and event.button() == Qt.LeftButton:
            self._drag_offset = None
            return False
        return False


def install_frameless_dialog_chrome(dialog, *drag_widgets):
    dialog.setWindowFlag(Qt.FramelessWindowHint, True)
    drag_filter = FramelessDialogDragFilter(dialog)
    dialog._frameless_drag_filter = drag_filter
    dialog.installEventFilter(drag_filter)
    for widget in drag_widgets:
        if widget is not None:
            widget.installEventFilter(drag_filter)
    return drag_filter

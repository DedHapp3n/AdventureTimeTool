from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel


def render_start_section(window):
    if window.content_layer is None:
        return

    content_w = window.content_layer.width()
    content_h = window.content_layer.height()
    title_w = 520
    button_w = 300
    button_h = 58
    gap = 18
    title_h = 48
    block_h = title_h + 28 + button_h + gap + button_h + 38
    block_x = max(0, (content_w - button_w) // 2)
    block_y = max(0, (content_h - block_h) // 2)

    title = QLabel(window.content_layer)
    title.setGeometry(max(0, (content_w - title_w) // 2), block_y, title_w, title_h)
    title.setText("Kein Charakter geladen")
    title.setAlignment(Qt.AlignCenter)
    title.setStyleSheet(
        "background: transparent; color: #f2d28b; font-size: 30px; font-weight: 700;"
    )
    title.show()

    load_y = block_y + title_h + 28
    window.create_asset_text_button(
        window.content_layer,
        {
            "x": block_x,
            "y": load_y,
            "w": button_w,
            "h": button_h,
            "text": "Charakter laden",
            "asset": "buttons/menu_button_medium.png",
            "font_size": 22,
            "color": "#f2d28b",
        },
        "Charakter laden",
        window.on_settings_load_character_clicked,
    )

    placeholder = QLabel(window.content_layer)
    placeholder.setGeometry(max(0, (content_w - title_w) // 2), load_y + button_h + gap + button_h + 12, title_w, 26)
    placeholder.setText("")
    placeholder.setAlignment(Qt.AlignCenter)
    placeholder.setStyleSheet(
        "background: transparent; color: #cdbb8a; font-size: 16px; font-weight: 600;"
    )
    placeholder.show()

    def show_create_placeholder():
        placeholder.setText("Charakter erstellen kommt später.")

    window.create_asset_text_button(
        window.content_layer,
        {
            "x": block_x,
            "y": load_y + button_h + gap,
            "w": button_w,
            "h": button_h,
            "text": "Charakter erstellen",
            "asset": "buttons/menu_button_medium.png",
            "font_size": 22,
            "color": "#f2d28b",
        },
        "Charakter erstellen",
        show_create_placeholder,
    )

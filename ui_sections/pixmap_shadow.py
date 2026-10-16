from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import QLabel


def alpha_shadow_padding(safe_int, shadow_cfg):
    offset_x = safe_int(shadow_cfg.get("offset_x", shadow_cfg.get("x", 3)), 3)
    offset_y = safe_int(shadow_cfg.get("offset_y", shadow_cfg.get("y", 4)), 4)
    blur_radius = max(0, safe_int(shadow_cfg.get("blur_radius", 18), 18))
    spread = max(1, blur_radius // 3)
    return (
        max(spread, spread - offset_x),
        max(spread, spread - offset_y),
        max(spread, spread + offset_x),
        max(spread, spread + offset_y),
    )


def create_alpha_pixmap_shadow(window, parent, source, rect_cfg, shadow_cfg):
    if source is None or source.isNull() or not isinstance(shadow_cfg, dict) or not bool(shadow_cfg.get("enabled", False)):
        return None
    safe_int = getattr(window, "_safe_int", lambda value, default=0: int(value if value is not None else default))
    x = safe_int(rect_cfg.get("x", 0), 0)
    y = safe_int(rect_cfg.get("y", 0), 0)
    width = max(1, safe_int(rect_cfg.get("w", 1), 1))
    height = max(1, safe_int(rect_cfg.get("h", 1), 1))
    offset_x = safe_int(shadow_cfg.get("offset_x", shadow_cfg.get("x", 3)), 3)
    offset_y = safe_int(shadow_cfg.get("offset_y", shadow_cfg.get("y", 4)), 4)
    blur_radius = max(0, safe_int(shadow_cfg.get("blur_radius", 18), 18))
    spread = max(1, blur_radius // 3)
    scaled = source.scaled(width, height, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)

    color = QColor(0, 0, 0, 160)
    if hasattr(window, "parse_layout_color"):
        parsed, ok = window.parse_layout_color(str(shadow_cfg.get("color", "rgba(0, 0, 0, 160)")), color)
        if ok:
            color = parsed

    mask = QPixmap(width, height)
    mask.fill(Qt.transparent)
    mask_painter = QPainter(mask)
    mask_painter.drawPixmap(0, 0, scaled)
    mask_painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
    mask_painter.fillRect(mask.rect(), color)
    mask_painter.end()

    pad_left, pad_top, pad_right, pad_bottom = alpha_shadow_padding(safe_int, shadow_cfg)
    rendered = QPixmap(width + pad_left + pad_right, height + pad_top + pad_bottom)
    rendered.fill(Qt.transparent)
    painter = QPainter(rendered)
    if blur_radius > 0:
        for distance in range(spread, 0, -1):
            painter.setOpacity(0.10 * (spread - distance + 1) / spread)
            for dx, dy in ((-distance, 0), (distance, 0), (0, -distance), (0, distance), (-distance, -distance), (distance, -distance), (-distance, distance), (distance, distance)):
                painter.drawPixmap(pad_left + offset_x + dx, pad_top + offset_y + dy, mask)
    painter.setOpacity(0.55)
    painter.drawPixmap(pad_left + offset_x, pad_top + offset_y, mask)
    painter.end()

    shadow = QLabel(parent)
    shadow.setObjectName("alphaPixmapShadow")
    shadow.setGeometry(x - pad_left, y - pad_top, rendered.width(), rendered.height())
    shadow.setAttribute(Qt.WA_TranslucentBackground, True)
    shadow.setAutoFillBackground(False)
    shadow.setStyleSheet("background: transparent; border: none;")
    shadow.setAttribute(Qt.WA_TransparentForMouseEvents, True)
    shadow.setPixmap(rendered)
    shadow.show()
    shadow.lower()
    return shadow

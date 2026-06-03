import json
import re

from PySide6.QtCore import QUrl, Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QFrame, QLabel, QLineEdit, QWidget

from app_logger import log_debug, log_warning
from app_paths import data_path, load_settings, resource_path, save_settings

try:
    from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile
    from PySide6.QtWebEngineWidgets import QWebEngineView
except Exception:
    QWebEnginePage = None
    QWebEngineProfile = None
    QWebEngineView = None


BROWSER_SETTINGS_KEY = "browser"
DEFAULT_URL = "https://app.roll20.net/login"
DEFAULT_BROWSER_LAYOUT = {
    "browser_screen": {
        "enabled": True,
        "fill_content_area": True,
        "margin": 8,
        "default_url": DEFAULT_URL,
        "show_url_bar": True,
        "url_bar_h": 36,
        "gap": 8,
        "inner_margin": 10,
        "background": "rgba(5, 5, 5, 125)",
        "border_color": "rgba(242, 210, 139, 95)",
        "debug": {
            "enabled": False,
            "console_messages": False,
        },
    }
}


class BrowserPage(QWebEnginePage if QWebEnginePage is not None else object):
    def __init__(self, profile, window):
        super().__init__(profile)
        self.window = window

    def javaScriptConsoleMessage(self, level, message, line_number, source_id):
        cfg = _browser_cfg(self.window).get("debug", {})
        if not isinstance(cfg, dict) or not bool(cfg.get("console_messages", False)):
            return
        log_debug("browser", f"console[{level}] {source_id}:{line_number}: {message}")

    def createWindow(self, _type):
        view = getattr(self.window, "_browser_web_view", None)
        if _is_qt_widget_alive(view):
            return view.page()
        return self


def _is_qt_widget_alive(widget):
    if widget is None:
        return False
    try:
        widget.objectName()
        return True
    except RuntimeError:
        return False


def _browser_cfg(window):
    return load_browser_layout_config(window).get("browser_screen", {})


def load_browser_layout_config(window):
    main_cfg = getattr(window, "main_ui_layout_config", {}).get("browser_screen", {})
    if not isinstance(main_cfg, dict):
        main_cfg = {}
    layout_file = str(main_cfg.get("layout_file", "") or "").strip() or "browser_layout.json"
    active_theme = window.get_active_theme() if hasattr(window, "get_active_theme") else "diablo"
    assets_dir = getattr(window, "assets_dir", resource_path("assets"))
    candidates = [
        assets_dir / "themes" / active_theme / layout_file,
        assets_dir / "themes" / "diablo" / "browser_layout.json",
    ]
    for layout_path in candidates:
        try:
            if not layout_path.exists():
                continue
            with open(layout_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and isinstance(data.get("browser_screen"), dict):
                return data
        except Exception as exc:
            log_warning("browser", f"browser layout load failed: {layout_path}: {exc}")
    return DEFAULT_BROWSER_LAYOUT


def _safe_int(window, value, default):
    safe_int = getattr(window, "_safe_int", None)
    if callable(safe_int):
        return safe_int(value, default)
    try:
        return int(value)
    except Exception:
        return default


def _remember_url(window, url):
    url_text = url.toString() if isinstance(url, QUrl) else str(url or "")
    url_text = url_text.strip()
    if not url_text:
        return
    window._browser_last_url = url_text
    try:
        settings, _created = load_settings()
        browser = settings.setdefault(BROWSER_SETTINGS_KEY, {})
        if not isinstance(browser, dict):
            browser = {}
            settings[BROWSER_SETTINGS_KEY] = browser
        browser["last_url"] = url_text
        save_settings(settings)
        window.settings = settings
    except Exception as exc:
        log_warning("browser", f"browser url save failed: {exc}")


def _normalize_url(url_edit, fallback_url):
    text = str(url_edit.text() or "").strip()
    if not text:
        text = fallback_url
    if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", text):
        text = "https://" + text
    url_edit.setText(text)
    return QUrl(text)


def _initial_url(window, cfg):
    configured_url = str(cfg.get("default_url", DEFAULT_URL) or DEFAULT_URL)
    browser_settings = getattr(window, "settings", {}).get(BROWSER_SETTINGS_KEY, {})
    saved_url = ""
    if isinstance(browser_settings, dict):
        saved_url = str(browser_settings.get("last_url", "") or "").strip()
    return saved_url or str(getattr(window, "_browser_last_url", "") or "").strip() or configured_url


def _ensure_profile_paths():
    if QWebEngineProfile is None:
        return None
    profile = QWebEngineProfile.defaultProfile()
    try:
        profile.setPersistentStoragePath(str(data_path("browser/profile")))
        profile.setCachePath(str(data_path("browser/cache")))
    except Exception as exc:
        log_warning("browser", f"browser profile path setup failed: {exc}")
    return profile


def _browser_geometry(window, cfg):
    margin = _safe_int(window, cfg.get("margin", 8), 8)
    if bool(cfg.get("fill_content_area", True)):
        return (
            margin,
            margin,
            max(1, window.content_layer.width() - (margin * 2)),
            max(1, window.content_layer.height() - (margin * 2)),
        )
    return (
        _safe_int(window, cfg.get("x", margin), margin),
        _safe_int(window, cfg.get("y", margin), margin),
        _safe_int(window, cfg.get("w", window.content_layer.width() - (margin * 2)), window.content_layer.width() - (margin * 2)),
        _safe_int(window, cfg.get("h", window.content_layer.height() - (margin * 2)), window.content_layer.height() - (margin * 2)),
    )


def _apply_browser_geometry(window, cfg):
    container = window._browser_container
    if not _is_qt_widget_alive(container):
        return
    x, y, w, h = _browser_geometry(window, cfg)
    container.setGeometry(x, y, w, h)

    show_url_bar = bool(cfg.get("show_url_bar", True))
    url_bar_h = _safe_int(window, cfg.get("url_bar_h", 36), 36)
    gap = _safe_int(window, cfg.get("gap", 8), 8)
    inner_margin = _safe_int(window, cfg.get("inner_margin", 10), 10)

    url_edit = window._browser_url_edit
    if _is_qt_widget_alive(url_edit):
        url_edit.setVisible(show_url_bar)
        if show_url_bar:
            url_edit.setGeometry(inner_margin, inner_margin, max(1, w - (inner_margin * 2)), url_bar_h)

    web_y = inner_margin
    if show_url_bar:
        web_y = inner_margin + url_bar_h + gap
    web_h = max(1, h - web_y - inner_margin)
    web_w = max(1, w - (inner_margin * 2))

    if _is_qt_widget_alive(window._browser_web_view):
        window._browser_web_view.setGeometry(inner_margin, web_y, web_w, web_h)

    fallback = getattr(window, "_browser_fallback_label", None)
    if _is_qt_widget_alive(fallback):
        fallback.setGeometry(inner_margin, web_y, web_w, min(140, web_h))


def render_browser_section(window):
    if getattr(window, "content_layer", None) is None:
        return

    if getattr(window, "_browser_container", None) is not None and not _is_qt_widget_alive(window._browser_container):
        window._browser_container = None
        window._browser_web_view = None
        window._browser_url_edit = None
        window._browser_fallback_label = None
        window._browser_initialized = False

    cfg = _browser_cfg(window)
    default_url = _initial_url(window, cfg)
    background = str(cfg.get("background", "rgba(5, 5, 5, 125)"))
    border_color = str(cfg.get("border_color", "rgba(242, 210, 139, 95)"))

    if getattr(window, "_browser_container", None) is None:
        container = QFrame(window.content_layer)
        container.setStyleSheet(
            f"QFrame {{ background: {background}; border: 1px solid {border_color}; }}"
        )
        window._browser_container = container

        url_edit = QLineEdit(container)
        url_edit.setText(default_url)
        url_edit.setStyleSheet(
            "QLineEdit { background: rgba(0, 0, 0, 150); color: #ffffff; "
            "border: 1px solid rgba(242, 210, 139, 120); padding: 5px 8px; font-size: 14px; }"
        )
        window._browser_url_edit = url_edit

        if QWebEngineView is not None:
            profile = _ensure_profile_paths()
            web_view = QWebEngineView(container)
            if profile is not None and QWebEnginePage is not None:
                web_view.setPage(BrowserPage(profile, window))
            web_view.urlChanged.connect(
                lambda url: (
                    window._browser_url_edit.setText(url.toString()) if _is_qt_widget_alive(window._browser_url_edit) else None,
                    _remember_url(window, url),
                )
            )
            web_view.setUrl(QUrl(default_url))
            window._browser_web_view = web_view

            def load_url():
                url = _normalize_url(url_edit, default_url)
                _remember_url(window, url)
                web_view.setUrl(url)

            url_edit.returnPressed.connect(load_url)
        else:
            fallback = QLabel(container)
            fallback.setWordWrap(True)
            fallback.setAlignment(Qt.AlignCenter)
            fallback.setText(
                "QtWebEngine ist in dieser PySide6-Installation nicht verfuegbar. "
                "Enter in der Adresszeile oeffnet die Adresse extern."
            )
            fallback.setStyleSheet(
                "background: transparent; border: none; color: #e8e0c8; font-size: 18px;"
            )
            window._browser_fallback_label = fallback

            def open_external_url():
                url = _normalize_url(url_edit, default_url)
                _remember_url(window, url)
                QDesktopServices.openUrl(url)

            url_edit.returnPressed.connect(open_external_url)

        window._browser_initialized = True

    if _is_qt_widget_alive(window._browser_container) and window._browser_container.parent() is not window.content_layer:
        window._browser_container.setParent(window.content_layer)

    _apply_browser_geometry(window, cfg)
    if _is_qt_widget_alive(window._browser_container):
        window._browser_container.show()
        window._browser_container.raise_()

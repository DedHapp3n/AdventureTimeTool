import json
import re
import shutil
import html

from PySide6.QtCore import QDateTime, QUrl, Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QApplication, QFrame, QLabel, QLineEdit, QWidget

from app_logger import log_debug, log_warning_once
from app_paths import data_path, load_settings, resource_path, save_settings

try:
    from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile
    from PySide6.QtWebEngineWidgets import QWebEngineView
except Exception:
    QWebEnginePage = None
    QWebEngineProfile = None
    QWebEngineView = None

try:
    from PySide6.QtNetwork import QNetworkCookie
except Exception:
    QNetworkCookie = None


BROWSER_SETTINGS_KEY = "browser"
DEFAULT_URL = "https://app.roll20.net/login"
DEFAULT_BROWSER_LAYOUT = {
    "browser_screen": {
        "enabled": True,
        "fill_content_area": True,
        "preload_on_start": True,
        "show_on_start": False,
        "external_links": False,
        "allow_new_windows": False,
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
            "navigation": False,
            "suppress_engine_noise": True,
            "persistence_test_enabled": False,
            "persistence_test_url_keyword": "persistence-test",
        },
        "profile": {
            "enabled": True,
            "name": "roll20",
            "use_default_profile": True,
            "persistent_cookies": True,
            "cache_enabled": True,
            "storage_subdir": "browser_profiles/roll20_default",
            "encrypt_at_rest": False,
            "cookie_backup": {
                "enabled": True,
                "file": "browser_profiles/roll20_cookie_backup.json",
                "domains": [
                    "roll20.net",
                    ".roll20.net",
                    "app.roll20.net",
                ],
            },
        },
    }
}


class BrowserConsolePage(QWebEnginePage if QWebEnginePage is not None else object):
    def __init__(self, profile, window):
        super().__init__(profile)
        self.window = window

    def javaScriptConsoleMessage(self, *args):
        cfg = _browser_cfg(self.window).get("debug", {})
        if not isinstance(cfg, dict) or not bool(cfg.get("console_messages", False)):
            return
        level = args[0] if len(args) > 0 else "-"
        message = args[1] if len(args) > 1 else ""
        line_number = args[2] if len(args) > 2 else "-"
        source_id = args[3] if len(args) > 3 else ""
        log_debug("browser", f"console[{level}] {source_id}:{line_number}: {message}")


class BrowserPage(BrowserConsolePage):
    def createWindow(self, _type):
        cfg = _browser_cfg(self.window)
        if bool(cfg.get("allow_new_windows", False)):
            return super().createWindow(_type)
        if QWebEngineProfile is not None:
            popup_page = PopupRedirectPage(self.profile(), self.window)
            popup_pages = getattr(self.window, "_browser_popup_pages", None)
            if not isinstance(popup_pages, list):
                popup_pages = []
                self.window._browser_popup_pages = popup_pages
            popup_pages.append(popup_page)
            popup_page.destroyed.connect(lambda _obj=None, page=popup_page: _forget_popup_page(self.window, page))
            return popup_page
        return self


class PopupRedirectPage(BrowserConsolePage):
    def __init__(self, profile, window):
        super().__init__(profile, window)
        self.urlChanged.connect(self._redirect)

    def _redirect(self, url):
        if not isinstance(url, QUrl) or not url.isValid() or url.isEmpty():
            return
        view = getattr(self.window, "_browser_web_view", None)
        if _is_qt_widget_alive(view):
            view.setUrl(url)
        self.deleteLater()


def _forget_popup_page(window, page):
    popup_pages = getattr(window, "_browser_popup_pages", None)
    if isinstance(popup_pages, list) and page in popup_pages:
        popup_pages.remove(page)


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


def _browser_debug_enabled(window):
    cfg = _browser_cfg(window).get("debug", {})
    return isinstance(cfg, dict) and bool(cfg.get("enabled", False))


def _browser_debug_cfg(window):
    cfg = _browser_cfg(window).get("debug", {})
    return cfg if isinstance(cfg, dict) else {}


def load_browser_layout_config(window):
    main_cfg = getattr(window, "main_ui_layout_config", {}).get("browser_screen", {})
    if not isinstance(main_cfg, dict):
        log_warning_once("browser", "invalid-browser-screen-config", "invalid browser_screen config, using defaults")
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
            log_warning_once("browser", f"layout:{layout_path}", f"browser layout load failed: {layout_path}: {exc}")
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
    if not _is_storable_browser_url(url):
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
        log_warning_once("browser", "url-save-failed", f"browser url save failed: {exc}")


def _on_url_changed(window, url):
    if getattr(window, "_browser_shutdown_in_progress", False):
        return
    if _is_internal_persistence_test_url(url):
        if _is_qt_widget_alive(getattr(window, "_browser_url_edit", None)):
            window._browser_url_edit.setText(_persistence_test_display_text())
        return
    if _is_qt_widget_alive(getattr(window, "_browser_url_edit", None)):
        window._browser_url_edit.setText(url.toString())
    cfg = _browser_cfg(window).get("debug", {})
    if isinstance(cfg, dict) and bool(cfg.get("navigation", False)):
        log_debug("browser", f"navigation: {url.toString()}")
    _remember_url(window, url)


def _normalize_url(url_edit, fallback_url):
    text = str(url_edit.text() or "").strip()
    if not text:
        text = fallback_url
    if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", text):
        text = "https://" + text
    url_edit.setText(text)
    return QUrl(text)


def _persistence_test_display_text():
    return "persistence-test"


def _is_persistence_test_requested(window, text):
    raw = str(text or "").strip().lower()
    return raw in {"persistence-test", "local://persistence-test", "app://persistence-test"}


def _is_internal_persistence_test_url(url):
    try:
        return url.host().lower() == "adventure.local" and url.path().startswith("/persistence-test")
    except Exception:
        return False


def _is_storable_browser_url(url):
    url_text = url.toString() if isinstance(url, QUrl) else str(url or "")
    url_text = url_text.strip()
    if not url_text or url_text.lower() == _persistence_test_display_text():
        return False
    qurl = url if isinstance(url, QUrl) else QUrl(url_text)
    scheme = str(qurl.scheme() or "").lower()
    if scheme == "about":
        return False
    if _is_internal_persistence_test_url(qurl):
        return False
    return scheme in {"http", "https"}


def _profile_summary_lines(window, reason):
    profile = getattr(window, "_roll20_web_profile", None)
    profile_path = getattr(window, "_roll20_profile_path", None)
    cache_path = getattr(window, "_roll20_cache_path", None)
    return [
        f"reason={reason}",
        f"off_the_record={_read_profile_value(profile, 'isOffTheRecord') if profile is not None else None}",
        f"persistentStoragePath={_read_profile_value(profile, 'persistentStoragePath') if profile is not None else None}",
        f"cachePath={_read_profile_value(profile, 'cachePath') if profile is not None else None}",
        f"profile_exists={bool(profile_path and profile_path.exists())} profile_count={_path_child_count(profile_path)}",
        f"cache_exists={bool(cache_path and cache_path.exists())} cache_count={_path_child_count(cache_path)}",
        f"cookie_added_count={int(getattr(window, '_roll20_cookie_added_count', 0) or 0)}",
    ]


def _log_browser_profile_summary(window, reason):
    if not _browser_debug_enabled(window):
        return
    for line in _profile_summary_lines(window, reason):
        log_debug("browser", f"BROWSER PROFILE {line}")


def _persistence_test_html(window):
    summary = "\n".join(html.escape(line) for line in _profile_summary_lines(window, "persistence-test"))
    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Adventure Browser Persistence Test</title>
  <style>
    body {{ background:#111; color:#eee; font:14px sans-serif; margin:24px; }}
    pre {{ background:#1d1d1d; border:1px solid #555; padding:12px; white-space:pre-wrap; }}
    button {{ padding:8px 12px; }}
  </style>
</head>
<body>
  <h1>Browser Persistence Test</h1>
  <p>This page uses the same embedded QWebEngineView and profile as Roll20.</p>
  <p>This setHtml diagnostic may not perfectly represent real HTTPS persistence.</p>
  <ol>
    <li>Open this page with persistence-test.</li>
    <li>Close the app.</li>
    <li>Restart the app.</li>
    <li>Open persistence-test again.</li>
    <li>The cookie/localStorage values should still be visible.</li>
  </ol>
  <button onclick="location.reload()">Reload test page</button>
  <pre id="out">Running...</pre>
  <h2>Profile Summary</h2>
  <pre>{summary}</pre>
  <script>
    (async function() {{
      const key = "adventure_persistence_test_token";
      const now = new Date().toISOString();
      const cookieBefore = document.cookie || "";
      const localBefore = localStorage.getItem(key) || "";
      const sessionBefore = sessionStorage.getItem(key) || "";

      const token = localBefore || ("token-" + now + "-" + Math.random().toString(36).slice(2));
      document.cookie = key + "=" + encodeURIComponent(token) + "; max-age=31536000; path=/; SameSite=Lax";
      localStorage.setItem(key, token);
      sessionStorage.setItem(key, token);

      const lines = [
        "cookie_before=" + cookieBefore,
        "cookie_after=" + (document.cookie || ""),
        "localStorage_before=" + localBefore,
        "localStorage_after=" + (localStorage.getItem(key) || ""),
        "sessionStorage_before=" + sessionBefore,
        "sessionStorage_after=" + (sessionStorage.getItem(key) || ""),
        "",
        "Expected: cookie/localStorage should survive app restart if the QWebEngine profile persists.",
        "Note: sessionStorage is informational and is not expected to survive app restart."
      ];
      document.getElementById("out").textContent = lines.join("\\n");
    }})();
  </script>
</body>
</html>"""


def _load_persistence_test_page(window, web_view):
    if not _is_qt_widget_alive(web_view):
        return False
    if _is_qt_widget_alive(getattr(window, "_browser_url_edit", None)):
        window._browser_url_edit.setText(_persistence_test_display_text())
    _log_browser_profile_summary(window, "before-persistence-test")
    window._browser_persistence_test_pending = True
    web_view.setHtml(_persistence_test_html(window), QUrl("https://adventure.local/persistence-test"))
    return True


def _initial_url(window, cfg):
    configured_url = str(cfg.get("default_url", DEFAULT_URL) or DEFAULT_URL)
    browser_settings = getattr(window, "settings", {}).get(BROWSER_SETTINGS_KEY, {})
    saved_url = ""
    if isinstance(browser_settings, dict):
        saved_url = str(browser_settings.get("last_url", "") or "").strip()
    if not _is_storable_browser_url(saved_url):
        saved_url = ""
    memory_url = str(getattr(window, "_browser_last_url", "") or "").strip()
    if not _is_storable_browser_url(memory_url):
        memory_url = ""
    return saved_url or memory_url or configured_url


def _persistent_cookie_policy():
    if QWebEngineProfile is None:
        return None
    policy_group = getattr(QWebEngineProfile, "PersistentCookiesPolicy", None)
    if policy_group is not None and hasattr(policy_group, "ForcePersistentCookies"):
        return policy_group.ForcePersistentCookies
    return getattr(QWebEngineProfile, "ForcePersistentCookies", None)


def _disk_http_cache_type():
    if QWebEngineProfile is None:
        return None
    cache_group = getattr(QWebEngineProfile, "HttpCacheType", None)
    if cache_group is not None and hasattr(cache_group, "DiskHttpCache"):
        return cache_group.DiskHttpCache
    return getattr(QWebEngineProfile, "DiskHttpCache", None)


def _read_profile_value(profile, method_name):
    try:
        method = getattr(profile, method_name, None)
        if callable(method):
            return method()
    except Exception:
        return None
    return None


def _path_child_count(path):
    try:
        if path is None or not path.exists():
            return 0
        return sum(1 for _child in path.iterdir())
    except Exception:
        return 0


def _write_test_profile_path(window, path):
    if path is None:
        return
    test_path = path / ".write_test"
    try:
        test_path.write_text("ok", encoding="utf-8")
        test_path.unlink(missing_ok=True)
        if _browser_debug_enabled(window):
            log_debug("browser", f"BROWSER PROFILE write_test=ok path={path}")
    except Exception as exc:
        log_warning_once("browser", "profile-write-test-failed", f"browser profile write test failed: {exc}")


def _connect_cookie_debug_counter(window, profile):
    if not _browser_debug_enabled(window) or getattr(window, "_roll20_cookie_debug_connected", False):
        return
    try:
        cookie_store = profile.cookieStore()
        if cookie_store is None:
            return

        def on_cookie_added(_cookie):
            window._roll20_cookie_added_count = int(getattr(window, "_roll20_cookie_added_count", 0) or 0) + 1

        cookie_store.cookieAdded.connect(on_cookie_added)
        window._roll20_cookie_added_handler = on_cookie_added
        window._roll20_cookie_debug_connected = True
        window._roll20_cookie_added_count = int(getattr(window, "_roll20_cookie_added_count", 0) or 0)
    except Exception as exc:
        log_warning_once("browser", "cookie-debug-counter", f"browser cookie debug counter setup failed: {exc}")


def _cookie_backup_cfg(profile_cfg):
    cfg = profile_cfg.get("cookie_backup", {})
    if not isinstance(cfg, dict):
        cfg = {}
    domains = cfg.get("domains", ["roll20.net", ".roll20.net", "app.roll20.net"])
    if not isinstance(domains, list):
        domains = ["roll20.net", ".roll20.net", "app.roll20.net"]
    return {
        "enabled": bool(cfg.get("enabled", True)),
        "file": str(cfg.get("file", "browser_profiles/roll20_cookie_backup.json") or "browser_profiles/roll20_cookie_backup.json"),
        "domains": [str(domain or "").strip().lower() for domain in domains if str(domain or "").strip()],
    }


def _cookie_backup_path(cfg):
    # Sensitive global browser/app state: this file can contain Roll20 session cookies/tokens.
    # It is intentionally not character data, does not store usernames/passwords, and should be encrypted later.
    return data_path(str(cfg.get("file", "browser_profiles/roll20_cookie_backup.json") or "browser_profiles/roll20_cookie_backup.json"))


def _cookie_text(value):
    try:
        return bytes(value).decode("latin-1")
    except Exception:
        return str(value or "")


def _cookie_bytes(value):
    try:
        return str(value or "").encode("latin-1")
    except Exception:
        return b""


def _cookie_to_dict(cookie):
    data = {
        "name": _cookie_text(cookie.name()),
        "value": _cookie_text(cookie.value()),
        "domain": str(cookie.domain() or ""),
        "path": str(cookie.path() or "/"),
        "secure": bool(cookie.isSecure()),
        "httpOnly": bool(cookie.isHttpOnly()),
    }
    try:
        expiration = cookie.expirationDate()
        if expiration.isValid():
            data["expirationDate"] = expiration.toString(Qt.ISODateWithMs)
    except Exception:
        pass
    try:
        policy = cookie.sameSitePolicy()
        data["sameSitePolicy"] = int(getattr(policy, "value", policy))
    except Exception:
        pass
    return data


def _cookie_from_dict(data):
    if QNetworkCookie is None or not isinstance(data, dict):
        return None
    try:
        cookie = QNetworkCookie(_cookie_bytes(data.get("name", "")), _cookie_bytes(data.get("value", "")))
        cookie.setDomain(str(data.get("domain", "") or ""))
        cookie.setPath(str(data.get("path", "/") or "/"))
        cookie.setSecure(bool(data.get("secure", False)))
        cookie.setHttpOnly(bool(data.get("httpOnly", False)))
        expiration = str(data.get("expirationDate", "") or "")
        if expiration:
            expiration_date = QDateTime.fromString(expiration, Qt.ISODateWithMs)
            if expiration_date.isValid():
                cookie.setExpirationDate(expiration_date)
        return cookie
    except Exception:
        return None


def _cookie_key_from_dict(data):
    return "|".join([
        str(data.get("domain", "") or "").lower(),
        str(data.get("path", "/") or "/"),
        str(data.get("name", "") or ""),
    ])


def _cookie_key(cookie):
    return _cookie_key_from_dict(_cookie_to_dict(cookie))


def _cookie_domain_allowed(cookie, domains):
    try:
        domain = str(cookie.domain() or "").strip().lower()
    except Exception:
        return False
    if not domain:
        return False
    domain_base = domain.lstrip(".")
    for allowed in domains:
        allowed_base = str(allowed or "").strip().lower().lstrip(".")
        if not allowed_base:
            continue
        if domain == allowed or domain_base == allowed_base or domain_base.endswith("." + allowed_base):
            return True
    return False


def _write_cookie_backup(window, cfg):
    backup = getattr(window, "_roll20_cookie_backup", {})
    if not isinstance(backup, dict):
        backup = {}
    path = _cookie_backup_path(cfg)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"cookies": list(backup.values())}, f, ensure_ascii=False, indent=2)
    except Exception as exc:
        log_warning_once("browser", "cookie-backup-save", f"browser cookie backup save failed: {exc}")


def _load_cookie_backup(window, profile, cfg):
    if not bool(cfg.get("enabled", True)):
        return
    if QNetworkCookie is None:
        log_warning_once("browser", "cookie-backup-network-cookie", "browser cookie backup disabled: QNetworkCookie unavailable")
        return
    cookie_store = profile.cookieStore()
    if cookie_store is None:
        return
    path = _cookie_backup_path(cfg)
    backup = {}
    try:
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            cookies = raw.get("cookies", []) if isinstance(raw, dict) else []
            if isinstance(cookies, list):
                for item in cookies:
                    if isinstance(item, dict):
                        backup[_cookie_key_from_dict(item)] = item
    except Exception as exc:
        log_warning_once("browser", "cookie-backup-load", f"browser cookie backup load failed: {exc}")
    window._roll20_cookie_backup = backup
    restore_url = QUrl("https://app.roll20.net/")
    for item in list(backup.values()):
        cookie = _cookie_from_dict(item)
        if cookie is None or not _cookie_domain_allowed(cookie, cfg.get("domains", [])):
            continue
        try:
            cookie_store.setCookie(cookie, restore_url)
        except Exception:
            pass


def _save_cookie_backup(window, profile, cfg):
    if not bool(cfg.get("enabled", True)):
        return
    _write_cookie_backup(window, cfg)


def _connect_cookie_backup(window, profile, cfg):
    if not bool(cfg.get("enabled", True)) or getattr(window, "_roll20_cookie_backup_connected", False):
        return
    if QNetworkCookie is None:
        log_warning_once("browser", "cookie-backup-network-cookie", "browser cookie backup disabled: QNetworkCookie unavailable")
        return
    try:
        cookie_store = profile.cookieStore()
        if cookie_store is None:
            return
        domains = cfg.get("domains", [])

        def on_cookie_added(cookie):
            if not _cookie_domain_allowed(cookie, domains):
                return
            data = _cookie_to_dict(cookie)
            backup = getattr(window, "_roll20_cookie_backup", {})
            if not isinstance(backup, dict):
                backup = {}
            backup[_cookie_key_from_dict(data)] = data
            window._roll20_cookie_backup = backup
            _save_cookie_backup(window, profile, cfg)

        def on_cookie_removed(cookie):
            data = _cookie_to_dict(cookie)
            backup = getattr(window, "_roll20_cookie_backup", {})
            if isinstance(backup, dict):
                backup.pop(_cookie_key_from_dict(data), None)
                window._roll20_cookie_backup = backup
                _save_cookie_backup(window, profile, cfg)

        cookie_store.cookieAdded.connect(on_cookie_added)
        removed_signal = getattr(cookie_store, "cookieRemoved", None)
        if removed_signal is not None:
            removed_signal.connect(on_cookie_removed)
        window._roll20_cookie_backup_added_handler = on_cookie_added
        window._roll20_cookie_backup_removed_handler = on_cookie_removed
        window._roll20_cookie_backup_connected = True
    except Exception as exc:
        log_warning_once("browser", "cookie-backup-connect", f"browser cookie backup setup failed: {exc}")


def _initialize_cookie_store(window, profile):
    try:
        cookie_store = profile.cookieStore()
        load_all = getattr(cookie_store, "loadAllCookies", None) if cookie_store is not None else None
        if callable(load_all):
            load_all()
        if _browser_debug_enabled(window):
            log_debug("browser", f"BROWSER PROFILE cookie_store_initialized={cookie_store is not None}")
    except Exception as exc:
        log_warning_once("browser", "cookie-store-init", f"browser cookie store init failed: {exc}")


def shutdown_roll20_browser(window):
    if getattr(window, "_roll20_browser_shutting_down", False):
        return
    window._roll20_browser_shutting_down = True
    window._browser_shutdown_in_progress = True
    app = QApplication.instance()
    web_view = getattr(window, "_browser_web_view", None)
    page = None
    if _is_qt_widget_alive(web_view):
        try:
            page = web_view.page()
        except Exception:
            page = None
        try:
            web_view.stop()
        except Exception:
            pass
        if app is not None:
            try:
                app.processEvents()
            except Exception:
                pass
        try:
            web_view.setPage(None)
        except Exception:
            pass
        try:
            web_view.deleteLater()
        except Exception:
            pass
        window._browser_web_view = None
    if page is not None:
        try:
            page.deleteLater()
        except Exception:
            pass
    if app is not None:
        try:
            app.processEvents()
        except Exception:
            pass


def _connect_roll20_shutdown_hook(window):
    if getattr(window, "_roll20_shutdown_hook_connected", False):
        return
    app = QApplication.instance()
    if app is None:
        return
    try:
        app.aboutToQuit.connect(lambda: shutdown_roll20_browser(window))
        window._roll20_shutdown_hook_connected = True
    except Exception as exc:
        log_warning_once("browser", "shutdown-hook", f"browser shutdown hook setup failed: {exc}")


def _log_profile_disk_status(window, ok):
    if not _browser_debug_enabled(window):
        return
    log_debug("browser", f"BROWSER PROFILE load_finished={bool(ok)}")
    _log_browser_profile_summary(window, "page-load-finished")
    if getattr(window, "_browser_persistence_test_pending", False):
        window._browser_persistence_test_pending = False
        _log_browser_profile_summary(window, "persistence-test-load-finished")


def _create_web_profile(profile_name, parent, use_default_profile=False):
    if use_default_profile:
        return QWebEngineProfile.defaultProfile()
    try:
        return QWebEngineProfile(str(profile_name or "roll20"), parent)
    except TypeError as exc:
        log_warning_once(
            "browser",
            "profile-constructor-fallback",
            f"browser profile parent constructor unavailable; trying storage-name constructor ({exc})",
        )
    try:
        return QWebEngineProfile(str(profile_name or "roll20"))
    except TypeError as exc:
        log_warning_once(
            "browser",
            "profile-offrecord-fallback",
            f"browser profile fallback created off-the-record profile; cookies may not persist ({exc})",
        )
        return QWebEngineProfile()


def _ensure_roll20_web_profile(window, cfg):
    if QWebEngineProfile is None:
        return None
    existing_profile = getattr(window, "_roll20_web_profile", None)
    if existing_profile is not None:
        _connect_roll20_shutdown_hook(window)
        return existing_profile

    profile_cfg = cfg.get("profile", {})
    if not isinstance(profile_cfg, dict):
        profile_cfg = {}
    profile_name = str(profile_cfg.get("name", "roll20") or "roll20")
    use_default_profile = bool(profile_cfg.get("use_default_profile", False))
    cookie_backup_cfg = _cookie_backup_cfg(profile_cfg)
    storage_subdir = str(profile_cfg.get("storage_subdir", "browser_profiles/roll20") or "browser_profiles/roll20").strip()
    if use_default_profile:
        storage_subdir = "browser_profiles/roll20_default"
    storage_root = data_path(storage_subdir)
    profile_path = storage_root / "current_profile"
    cache_path = storage_root / "cache"

    encrypt_at_rest = bool(profile_cfg.get("encrypt_at_rest", False))
    if encrypt_at_rest:
        log_warning_once(
            "browser",
            "profile-encryption-disabled",
            "browser profile encryption requested but not enabled: no secure keyring/passphrase flow is configured",
        )

    # If the internal persistence test does not persist, likely causes are an off-the-record
    # profile, paths set too late, an unwritable/unstable path, or early profile teardown.
    profile = _create_web_profile(profile_name, window, use_default_profile)
    try:
        profile_path.mkdir(parents=True, exist_ok=True)
        cache_path.mkdir(parents=True, exist_ok=True)
        _write_test_profile_path(window, profile_path)
        profile.setPersistentStoragePath(str(profile_path))
        if bool(profile_cfg.get("cache_enabled", True)):
            profile.setCachePath(str(cache_path))
        cache_maximum_size = profile_cfg.get("http_cache_maximum_size", 0)
        try:
            cache_maximum_size = int(cache_maximum_size)
        except Exception:
            cache_maximum_size = 0
        if cache_maximum_size > 0:
            set_cache_max = getattr(profile, "setHttpCacheMaximumSize", None)
            if callable(set_cache_max):
                set_cache_max(cache_maximum_size)
        if bool(profile_cfg.get("disk_cache", True)):
            cache_type = _disk_http_cache_type()
            if cache_type is not None:
                profile.setHttpCacheType(cache_type)
            else:
                log_warning_once("browser", "disk-cache-unavailable", "browser profile DiskHttpCache enum unavailable")
        persistent_cookies_enabled = bool(profile_cfg.get("persistent_cookies", True))
        force_persistent_cookies = bool(profile_cfg.get("force_persistent_cookies", persistent_cookies_enabled))
        if persistent_cookies_enabled or force_persistent_cookies:
            cookie_policy = _persistent_cookie_policy()
            if cookie_policy is not None:
                profile.setPersistentCookiesPolicy(cookie_policy)
            else:
                log_warning_once("browser", "cookie-policy-unavailable", "browser profile ForcePersistentCookies enum unavailable")
        try:
            if profile.isOffTheRecord():
                log_warning_once("browser", "profile-offrecord", "browser profile is off-the-record; cookies may not persist")
        except Exception:
            pass
        _initialize_cookie_store(window, profile)
        window._roll20_web_profile = profile
        window._roll20_profile_path = profile_path
        window._roll20_cache_path = cache_path
        _load_cookie_backup(window, profile, cookie_backup_cfg)
        _connect_cookie_backup(window, profile, cookie_backup_cfg)
        _initialize_cookie_store(window, profile)
        _connect_cookie_debug_counter(window, profile)
        _connect_roll20_shutdown_hook(window)
        if _browser_debug_enabled(window):
            log_debug("browser", f"BROWSER PROFILE storage_root={storage_root}")
            if profile_path.exists() and _path_child_count(profile_path) > 0:
                log_debug("browser", "BROWSER PROFILE profile folder has previous data")
            _log_browser_profile_summary(window, "after-profile-creation")
            log_debug("browser", f"BROWSER PROFILE use_default_profile={use_default_profile}")
            log_debug("browser", f"BROWSER PROFILE cookie_backup_enabled={bool(cookie_backup_cfg.get('enabled', True))}")
            log_debug("browser", f"BROWSER PROFILE cookie_backup_file={_cookie_backup_path(cookie_backup_cfg)}")
            log_debug("browser", f"BROWSER PROFILE cookie_policy={_read_profile_value(profile, 'persistentCookiesPolicy')}")
            log_debug("browser", f"BROWSER PROFILE http_cache_type={_read_profile_value(profile, 'httpCacheType')}")
            log_debug("browser", "BROWSER PROFILE cookies=persistent")
            log_debug("browser", "BROWSER PROFILE encryption=disabled reason=no_keyring_or_not_configured")
    except Exception as exc:
        log_warning_once("browser", "profile-paths", f"browser profile path setup failed: {exc}")
    return profile


def clear_roll20_browser_profile(window):
    if _is_qt_widget_alive(getattr(window, "_browser_web_view", None)):
        return False
    profile = getattr(window, "_roll20_web_profile", None)
    try:
        if profile is not None:
            cookie_store = profile.cookieStore()
            if cookie_store is not None:
                cookie_store.deleteAllCookies()
            profile.clearHttpCache()
    except RuntimeError:
        pass
    except Exception as exc:
        log_warning_once("browser", "clear-profile-failed", f"browser profile clear failed: {exc}")
        return False

    for attr in ("_roll20_profile_path", "_roll20_cache_path"):
        path = getattr(window, attr, None)
        if path is not None:
            try:
                shutil.rmtree(path, ignore_errors=True)
            except Exception as exc:
                log_warning_once("browser", f"delete-profile-path:{attr}", f"browser profile path delete failed: {exc}")
                return False
    try:
        cfg = _cookie_backup_cfg(_browser_cfg(window).get("profile", {}))
        backup_path = _cookie_backup_path(cfg)
        if backup_path.exists():
            backup_path.unlink()
        window._roll20_cookie_backup = {}
    except Exception as exc:
        log_warning_once("browser", "delete-cookie-backup", f"browser cookie backup delete failed: {exc}")
        return False
    return True


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


def _clear_dead_browser_refs(window):
    if getattr(window, "_browser_container", None) is not None and not _is_qt_widget_alive(window._browser_container):
        window._browser_container = None
        window._browser_web_view = None
        window._browser_url_edit = None
        window._browser_fallback_label = None
        window._browser_initialized = False


def ensure_browser_created(window):
    if getattr(window, "content_layer", None) is None:
        return False

    _clear_dead_browser_refs(window)

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
            profile = _ensure_roll20_web_profile(window, cfg)
            web_view = QWebEngineView(container)
            if profile is not None and QWebEnginePage is not None:
                web_view.setPage(BrowserPage(profile, window))
            web_view.urlChanged.connect(lambda url: _on_url_changed(window, url))
            web_view.loadFinished.connect(lambda ok: _log_profile_disk_status(window, ok))
            web_view.setUrl(QUrl(default_url))
            window._browser_web_view = web_view

            def load_url():
                if _is_persistence_test_requested(window, url_edit.text()):
                    if _load_persistence_test_page(window, web_view):
                        return
                url = _normalize_url(url_edit, default_url)
                _remember_url(window, url)
                web_view.setUrl(url)

            url_edit.returnPressed.connect(load_url)
        else:
            log_warning_once("browser", "webengine-unavailable", "QtWebEngine is unavailable; browser fallback will open URLs externally.")
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
    return _is_qt_widget_alive(window._browser_container)


def show_browser_section(window):
    cfg = _browser_cfg(window)
    _apply_browser_geometry(window, cfg)
    if _is_qt_widget_alive(window._browser_container):
        window._browser_container.show()
        window._browser_container.raise_()


def hide_browser_section(window):
    if _is_qt_widget_alive(getattr(window, "_browser_container", None)):
        window._browser_container.hide()


def render_browser_section(window):
    if ensure_browser_created(window):
        show_browser_section(window)

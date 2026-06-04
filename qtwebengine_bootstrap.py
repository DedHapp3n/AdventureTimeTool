from __future__ import annotations

import os
import sys


def _append_env_tokens(name, tokens):
    current = os.environ.get(name, "").strip()
    parts = current.split() if current else []
    for token in tokens:
        if token not in parts:
            parts.append(token)
    os.environ[name] = " ".join(parts)


def _append_qt_logging_rules(rules):
    current = os.environ.get("QT_LOGGING_RULES", "").strip()
    existing = [item for item in current.split(";") if item] if current else []
    for rule in rules:
        if rule not in existing:
            existing.append(rule)
    os.environ["QT_LOGGING_RULES"] = ";".join(existing)


def configure_qtwebengine_logging():
    _append_env_tokens(
        "QTWEBENGINE_CHROMIUM_FLAGS",
        ["--log-level=3", "--disable-logging"],
    )
    _append_qt_logging_rules(
        [
            "qt.webenginecontext.debug=false",
            "qt.webenginecontext.info=false",
            "qt.webenginecontext.warning=false",
        ]
    )


def _js_stderr_filter_enabled():
    raw_value = os.environ.get("ADVENTURE_SUPPRESS_QTWEBENGINE_JS_STDERR", "")
    return raw_value.strip().lower() not in ("0", "false", "no")


class _JsStderrFilter:
    """Suppress only Chromium/QtWebEngine webpage console lines that start with js:."""

    def __init__(self, wrapped):
        self._wrapped = wrapped
        self._buffer = ""

    def write(self, text):
        if not isinstance(text, str):
            return self._wrapped.write(text)
        self._buffer += text
        written = 0
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            if self._should_forward(line):
                written += self._wrapped.write(line + "\n")
        return written

    def flush(self):
        if self._buffer:
            if self._should_forward(self._buffer):
                self._wrapped.write(self._buffer)
            self._buffer = ""
        return self._wrapped.flush()

    def isatty(self):
        return self._wrapped.isatty()

    def fileno(self):
        return self._wrapped.fileno()

    def writable(self):
        return self._wrapped.writable()

    def __getattr__(self, name):
        return getattr(self._wrapped, name)

    @staticmethod
    def _should_forward(line):
        stripped = str(line or "").strip()
        if stripped.startswith("js:"):
            return False
        return True


def install_qtwebengine_js_stderr_filter():
    if not _js_stderr_filter_enabled():
        return
    if isinstance(sys.stderr, _JsStderrFilter):
        return
    sys.stderr = _JsStderrFilter(sys.stderr)

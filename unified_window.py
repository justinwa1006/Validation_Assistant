"""Unified window class with a position-preserving responsive adapter."""
from __future__ import annotations

import logging
import re

from PySide6.QtCore import QSettings, QTimer, Qt
from PySide6.QtWidgets import QApplication, QLabel

try:
    from .ui_responsive import ResponsiveUiController
except ImportError:
    from ui_responsive import ResponsiveUiController

logger = logging.getLogger("validation_assistant.unified")


def _apply_theme(window, ds, settings_org: str, settings_app: str, theme: str) -> None:
    ds.apply_theme(QApplication.instance(), theme)
    window._ds_theme = theme
    dark = theme == "dark"
    button = getattr(window, "u_theme_switch_btn", None)
    if button is not None:
        button.setText("☀ 밝은 화면" if dark else "☾ 어두운 화면")
    window.setWindowTitle("Validation Assistant Unified - " + ("Professional" if dark else "Bright"))
    ds.set_native_titlebar_dark(window, dark)
    QSettings(settings_org, settings_app).setValue("ui/theme", theme)


def create_window_class(engine, ds, settings_org: str, settings_app: str):
    base = engine.ValidationAssistant

    class UnifiedValidationAssistant(base):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._responsive = ResponsiveUiController(self, settings_org, settings_app)
            QTimer.singleShot(0, self._responsive.setup)

        def _u_theme_css(self):
            return ""

        def switch_unified_theme(self, target=None):
            current = getattr(self, "_ds_theme", "dark")
            theme = ds.normalize_theme(target) if target else ("light" if current == "dark" else "dark")
            if theme == current:
                return
            _apply_theme(self, ds, settings_org, settings_app, theme)
            self._responsive.apply(force=True)
            toast = getattr(self, "_ds_toast", None)
            if toast is not None:
                toast.popup("어두운 화면으로 전환했습니다." if theme == "dark" else "밝은 화면으로 전환했습니다.")

        def _u_show_structured_result(self, key, data):
            super()._u_show_structured_result(key, data)
            if key != "validation" or (isinstance(data, dict) and data):
                return
            layout = getattr(self, "u_structured_layouts", {}).get(key)
            if layout is not None:
                label = QLabel("AI JSON 결과를 Paste하면\n판정과 상세 결과가 여기에 표시됩니다.")
                label.setObjectName("uStructuredEmptyGuide")
                label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                label.setWordWrap(True)
                layout.insertWidget(0, label)
                layout.insertStretch(0, 1)

        def _u_set_result_metric(self, key, value):
            super()._u_set_result_metric(key, value)
            label = getattr(self, "u_validation_metric_label", None)
            if key == "validation" and label is not None:
                match = re.search(r"SCORE\s+(\d{1,3})", label.text())
                state = "guide" if not match else ("high" if int(match.group(1)) >= 80 else "mid" if int(match.group(1)) >= 50 else "low")
                label.setProperty("metricState", state)
                ds.repolish(label)

        def resizeEvent(self, event):
            super().resizeEvent(event)
            if hasattr(self, "_responsive"):
                QTimer.singleShot(0, self._responsive.apply)

        def changeEvent(self, event):
            super().changeEvent(event)
            if hasattr(self, "_responsive") and self._responsive.is_screen_or_font_change(event):
                QTimer.singleShot(0, lambda: self._responsive.apply(force=True))

        def closeEvent(self, event):
            settings = QSettings(settings_org, settings_app)
            settings.setValue("responsive/geometry", self.saveGeometry())
            settings.setValue("responsive/maximized", self.isMaximized())
            super().closeEvent(event)

    UnifiedValidationAssistant._ds_apply_to_window = staticmethod(
        lambda window, theme: _apply_theme(window, ds, settings_org, settings_app, theme)
    )
    return UnifiedValidationAssistant


def install_toast(engine, ds) -> None:
    if hasattr(ds, "install_toast_for_information") and hasattr(engine, "QMessageBox"):
        try:
            ds.install_toast_for_information(engine)
        except Exception:
            logger.warning("토스트 설치에 실패해 기본 메시지박스를 사용합니다.", exc_info=True)

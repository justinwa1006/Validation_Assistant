"""Small, testable responsive-UI service.

The service changes only control heights and overflow behavior. It never moves
result panels, restores splitter positions, or rewrites the engine layout.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from PySide6.QtCore import QEvent, QSettings, Qt
from PySide6.QtWidgets import (
    QAbstractButton, QComboBox, QFrame, QGroupBox, QLineEdit, QScrollArea,
    QSizePolicy, QTabWidget, QTextEdit, QToolButton, QWidget,
)


@dataclass(frozen=True)
class ResponsiveMetrics:
    control_height: int
    editor_height: int


METRICS = {
    "compact": ResponsiveMetrics(32, 82),
    "standard": ResponsiveMetrics(36, 112),
    "wide": ResponsiveMetrics(40, 142),
}


def widget_text(widget: QWidget) -> str:
    for getter in ("title", "text"):
        method = getattr(widget, getter, None)
        if callable(method):
            try:
                return str(method()).strip()
            except (RuntimeError, TypeError):
                return ""
    return ""


class ResponsiveUiController:
    """Apply safe responsiveness without changing panel placement."""

    def __init__(self, window: QWidget, settings_org: str, settings_app: str):
        self.window = window
        self.settings = QSettings(settings_org, settings_app)
        self.right_scroll: QScrollArea | None = None
        self.evidence_group: QGroupBox | None = None
        self.current_mode = ""

    def setup(self) -> None:
        self.wrap_automotive_panel()
        self.configure_evidence_group()
        self.normalize_size_policies()
        self.apply(force=True)

    def find_group(self, phrase: str) -> QGroupBox | None:
        phrase = phrase.lower()
        return next((g for g in self.window.findChildren(QGroupBox)
                     if phrase in widget_text(g).lower()), None)

    def wrap_automotive_panel(self) -> None:
        panel = self.find_group("automotive log analysis")
        if panel is None or isinstance(panel.parentWidget(), QScrollArea):
            return
        parent = panel.parentWidget()
        layout = parent.layout() if parent is not None else None
        if layout is None or layout.indexOf(panel) < 0:
            return
        scroll = QScrollArea(parent)
        scroll.setObjectName("uAutomotivePanelScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        panel.setMinimumSize(0, 0)
        panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout.replaceWidget(panel, scroll)
        panel.setParent(None)
        scroll.setWidget(panel)
        self.right_scroll = scroll

    def configure_evidence_group(self) -> None:
        group = self.find_group("screenshot evidence")
        if group is None:
            return
        self.evidence_group = group
        group.setCheckable(True)
        expanded = self.settings.value("responsive/evidenceExpanded", False, type=bool)
        group.setChecked(expanded)
        group.toggled.connect(self.set_evidence_expanded)
        self.set_evidence_expanded(expanded)

    def set_evidence_expanded(self, expanded: bool) -> None:
        if self.evidence_group is None:
            return
        direct = Qt.FindChildOption.FindDirectChildrenOnly
        for child in self.evidence_group.findChildren(QWidget, options=direct):
            child.setVisible(expanded)
        self.evidence_group.setMinimumHeight(0)
        self.evidence_group.setMaximumHeight(16777215 if expanded else 34)
        self.settings.setValue("responsive/evidenceExpanded", expanded)

    def normalize_size_policies(self) -> None:
        expanding: Iterable[QWidget] = (
            self.window.findChildren(QTextEdit)
            + self.window.findChildren(QTabWidget)
            + self.window.findChildren(QScrollArea)
        )
        for widget in expanding:
            widget.setMinimumSize(0, 0)
            widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        for widget in self.window.findChildren(QLineEdit) + self.window.findChildren(QComboBox):
            widget.setMinimumWidth(0)
            widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def mode(self) -> str:
        screen = self.window.screen()
        dpi = screen.logicalDotsPerInch() if screen else 96.0
        width = self.window.width() * 96.0 / max(dpi, 96.0)
        height = self.window.height() * 96.0 / max(dpi, 96.0)
        if width < 1250 or height < 720:
            return "compact"
        if width < 1700 or height < 900:
            return "standard"
        return "wide"

    def apply(self, force: bool = False) -> None:
        mode = self.mode()
        if not force and mode == self.current_mode:
            return
        self.current_mode = mode
        metric = METRICS[mode]
        self._resize_controls(metric)
        self._resize_input_editors(metric.editor_height)
        if self.evidence_group is not None and not self.evidence_group.isChecked():
            self.evidence_group.setMaximumHeight(34)

    def _resize_controls(self, metric: ResponsiveMetrics) -> None:
        for button in self.window.findChildren(QAbstractButton):
            if not isinstance(button, QToolButton):
                button.setMinimumHeight(metric.control_height)
                button.setMaximumHeight(metric.control_height + 8)
        for widget in self.window.findChildren(QComboBox) + self.window.findChildren(QLineEdit):
            widget.setMinimumHeight(metric.control_height)
            widget.setMaximumHeight(metric.control_height + 6)

    def _resize_input_editors(self, editor_height: int) -> None:
        engine_adjust = getattr(self.window, "apply_responsive_input_heights", None)
        if callable(engine_adjust):
            engine_adjust(self.window.height())
        tokens = ("precondition", "step", "expected", "actual")
        for editor in self.window.findChildren(QTextEdit):
            if any(token in (editor.objectName() or "").lower() for token in tokens):
                editor.setMaximumHeight(editor_height)

    @staticmethod
    def is_screen_or_font_change(event: QEvent) -> bool:
        return event.type() in (QEvent.Type.ScreenChangeInternal, QEvent.Type.FontChange)

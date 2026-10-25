"""
unified_launcher.py  -  Validation Assistant 통합 런처 (디자인 시스템 & 리팩토링 모듈 호환판)
"""
import argparse
import os
import re
import logging
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger("validation_assistant")

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))

SETTINGS_ORG = "ValidationAssistant"
SETTINGS_APP = "AutomotiveValidationAI"

# 모듈 호환 임포트
try:
    import bright_theme as engine
    import ui_design_system as ds
except ImportError:
    try:
        from . import engine, ui_design_system as ds
    except ImportError:
        _project_parent = BASE.parent
        if str(_project_parent) not in sys.path:
            sys.path.insert(0, str(_project_parent))
        from Validation_Assistant_Refactored import engine, ui_design_system as ds

from unified_window import create_window_class, install_toast  # noqa: E402  (BASE 가 sys.path 에 있음)


def _legacy(args) -> int:
    target = BASE / ("bright_theme.py" if args.theme in ("bright", "light") else "professional_theme.py")
    env = os.environ.copy()
    env["VA_UNIFIED_LAUNCHER"] = str(Path(__file__).resolve())
    if args.restore_state:
        env["VA_UNIFIED_RESTORE"] = "1"
    return subprocess.call([sys.executable, str(target)], env=env)


def _log_patch_error(name: str):
    logger.warning("[design-patch skipped] %s", name, exc_info=True)


def finish_window(window, ds, theme):
    """윈도우 생성 직후 마무리 세팅"""
    try:
        window._ds_theme = theme
        if hasattr(ds, "Toast"):
            window._ds_toast = ds.Toast(window)
    except Exception:
        _log_patch_error("toast widget")
        
    try:
        btn = getattr(window, "u_theme_switch_btn", None)
        if btn is not None:
            try:
                btn.clicked.disconnect()
            except (RuntimeError, TypeError):  # 연결된 슬롯이 없으면 PySide6 가 예외를 던진다
                logger.debug("테마 버튼에 끊을 시그널 연결이 없습니다.", exc_info=True)
            btn.clicked.connect(lambda _checked=False: window.switch_unified_theme())
            btn.setText("☀ 밝은 화면" if theme == "dark" else "☾ 어두운 화면")
            btn.setToolTip("화면 테마 전환 (Ctrl+Shift+T). 입력값과 결과는 그대로 유지됩니다.")
    except Exception:
        _log_patch_error("theme button")
        
    try:
        if hasattr(window, "u_shell"):
            ds.normalize_layout(window.u_shell)
    except Exception:
        _log_patch_error("layout normalize")
        
    try:
        if hasattr(ds, "install_shortcuts"):
            ds.install_shortcuts(window, lambda: window.switch_unified_theme())
    except Exception:
        _log_patch_error("shortcuts")
        
    window.setWindowTitle("Validation Assistant Unified - " + ("Professional" if theme == "dark" else "Bright"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--theme", choices=["bright", "professional", "light", "dark"], default=None)
    parser.add_argument("--restore-state", action="store_true")
    parser.add_argument("--legacy", action="store_true", help="이전 방식(서브프로세스)으로 실행")
    args = parser.parse_args()
    logging.basicConfig(level=os.environ.get("VA_LOG_LEVEL", "WARNING"), format="[%(levelname)s] %(name)s: %(message)s")

    os.environ["VA_UNIFIED_LAUNCHER"] = str(Path(__file__).resolve())
    if args.restore_state:
        os.environ["VA_UNIFIED_RESTORE"] = "1"
    if args.legacy:
        return _legacy(args)

    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    saved = QSettings(SETTINGS_ORG, SETTINGS_APP).value("ui/theme", "dark")
    theme = ds.normalize_theme(args.theme or saved)

    if hasattr(ds, "InlineStyleGuard"):
        guard = ds.InlineStyleGuard(app)
        app.installEventFilter(guard)

    ds.apply_theme(app, theme)
    install_toast(engine, ds)

    window_class = create_window_class(engine, ds, SETTINGS_ORG, SETTINGS_APP)
    window = window_class()
    finish_window(window, ds, theme)

    available = app.primaryScreen().availableGeometry()
    window.setMinimumSize(960, 620)

    settings = QSettings(SETTINGS_ORG, SETTINGS_APP)
    stored_geometry = settings.value("responsive/geometry")
    stored_maximized = settings.value("responsive/maximized", True, type=bool)
    if stored_geometry:
        window.restoreGeometry(stored_geometry)

    # Notebook/Full-HD displays use every available pixel. Large displays retain
    # a comfortable centered window unless the user previously maximized it.
    compact_screen = available.width() <= 1920 or available.height() <= 1080
    if compact_screen or stored_maximized:
        window.showMaximized()
    else:
        if not stored_geometry:
            width = max(1200, int(available.width() * 0.90))
            height = max(760, int(available.height() * 0.90))
            window.resize(width, height)
            window.move(
                available.x() + (available.width() - width) // 2,
                available.y() + (available.height() - height) // 2,
            )
        window.show()
    ds.set_native_titlebar_dark(window, theme == "dark")
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

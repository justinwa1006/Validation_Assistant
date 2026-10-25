"""프로젝트 폴더를 스텁 Qt 로 임포트해 init_ui 를 실행하고 호출 기록을 파일로 저장한다.

사용: python tools/record_ui.py <프로젝트 폴더(패키지 부모 기준 이름 지정)> <출력 파일>
"""
from __future__ import annotations

import importlib
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import qt_stub  # noqa: E402

qt_stub.install()


def main(project_dir: str, out_path: str) -> int:
    project_dir = os.path.abspath(project_dir)
    parent, pkg_name = os.path.split(project_dir)
    sys.path.insert(0, parent)
    # 패키지 이름이 폴더 이름과 같아야 하므로, 폴더 이름을 그대로 패키지로 임포트한다
    engine = importlib.import_module(f"{pkg_name}.engine")

    class Harness(engine.ValidationAssistant):
        def __getattr__(self, name):  # 아직 만들어지지 않은 위젯/속성 접근은 기록 객체로 대체
            if name.startswith("__"):
                raise AttributeError(name)
            return qt_stub.Rec(f"self.{name}")

    qt_stub.LOG.clear()
    Harness()  # UiMainMixin.__init__ 이 init_ui 를 호출한다
    text = "\n".join(qt_stub.LOG)
    text = re.sub(r"<function [^>]*>", "<function>", text)
    with open(out_path, "w", encoding="utf-8") as handle:
        handle.write(text + "\n")
    print(f"recorded {len(qt_stub.LOG)} calls -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1], sys.argv[2]))


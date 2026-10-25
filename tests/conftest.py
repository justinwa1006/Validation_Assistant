"""프로젝트 폴더를 sys.path 에 올려 Qt 없이 core/ 와 prompt_data 를 임포트한다.

패키지(__init__.py)는 PySide6 를 임포트하므로, 테스트는 폴더 자체를 모듈 루트로 사용한다.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


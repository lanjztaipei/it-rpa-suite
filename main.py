"""IT RPA Suite 快速直接啟動入口腳本.

可以直接使用 Python 執行此檔案：
    python main.py
或在 IDE 中直接點擊「執行 (Run)」按鈕。
"""

from __future__ import annotations

import sys
from pathlib import Path

# 將 src 目錄加到 sys.path，確保即使未執行 pip install -e . 也能直接引用模組
_SRC_DIR = Path(__file__).resolve().parent / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from it_rpa_suite.app.bootstrap import main  # noqa: E402

if __name__ == "__main__":
    main()

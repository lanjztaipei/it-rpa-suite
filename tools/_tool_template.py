"""Starter Template for Standalone Toolbox Scripts (`_tool_template.py`).

================================================================================
快速開發說明（SDK 與範本分工）
--------------------------------------------------------------------------------
1. `tool_sdk.py`：主程式共用底座（路徑定位、DPAPI 憑證、沙盒探測、Playwright Edge）。
   更新主程式時會自動覆蓋同步，請勿直接修改 `tool_sdk.py`。
2. `_tool_template.py`（本檔）：給開發者與 AI 快速開工的起始範本，不會顯示在工具箱按鈕。
   - 使用方式：複製本檔並重新命名（例如 `tools/my_tool.py` 或 `tools/my_tool/my_tool.py`），
     再請 AI 保留「0. SDK 匯入區」並直接於「1. 業務邏輯實作區」撰寫自動化流程。
   - 若要編譯成獨立 `.exe` 放入 `tools/`，打包時請加上 `--paths tools` 以內嵌 `tool_sdk`：
     `uv run pyinstaller --noconfirm --onefile --paths tools tools/my_tool.py`
================================================================================
"""

from __future__ import annotations

import sys
from pathlib import Path

# ==============================================================================
# 0. SDK 匯入區（請保留此區，勿任意刪除；同時支援 tools/ 與 tools/<子資料夾>/）
# ==============================================================================
_TOOLS_DIR = next(
    (
        parent
        for parent in (Path(__file__).resolve().parent, *Path(__file__).resolve().parents)
        if (parent / "tool_sdk.py").is_file()
    ),
    Path(__file__).resolve().parent,
)
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

from tool_sdk import (  # noqa: E402
    BASE_DIR,
    ensure_sandbox_server,
    open_browser,
    read_credentials,
)


# ==============================================================================
# 1. 業務邏輯實作區（請 AI 直接在此撰寫需求流程）
# ==============================================================================
def main() -> None:
    """Entry point for the standalone toolbox script."""
    creds = read_credentials()
    print(f"[SDK] 專案根目錄：{BASE_DIR}")
    print(f"[SDK] 已載入憑證：{creds['email']} (Portal 帳號：{creds['portal_account']})")

    with (
        ensure_sandbox_server() as sandbox_url,
        open_browser(headless=False, downloads_path=None, dialog_action="accept") as page,
    ):
        target_url = f"{sandbox_url.rstrip('/')}/portal/directory"
        print(f"[Demo] 正在開啟目標頁面：{target_url}")
        page.goto(target_url, wait_until="domcontentloaded")

        # TODO: 在此撰寫 Playwright 自動化步驟
        if sys.stdin and sys.stdin.isatty():
            input("\n請確認瀏覽器畫面結果，按 Enter 後關閉瀏覽器...")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"\n[錯誤] 執行過程發生異常：{exc}")
    if sys.stdin and sys.stdin.isatty():
        input("\n按 Enter 鍵結束程式...")

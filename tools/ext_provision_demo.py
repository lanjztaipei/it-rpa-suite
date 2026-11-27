"""Standalone Telecom Extension Provisioning Demo Tool (`ext_provision_demo.py`).

Demonstrates how external scripts in `tools/` leverage `tool_sdk.py` to:
1. Share DPAPI credentials and discover the active local Enterprise Sandbox URL
2. Search area prefix `502` on `/portal/telecom/extensions`
3. Scan available extension rows and select the first extension whose last two digits do NOT repeat
4. Fill out the extension provisioning form (auto-enabling Softphone when MAC is omitted)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

# Ensure `tools/` is on sys.path whether run from `tools/` or `tools/<subdir>/`
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
    ensure_sandbox_server,
    open_browser,
    read_credentials,
)

DEFAULT_EMP_ID = "EMP104"
DEFAULT_EMP_NAME = "張心怡 (Claire Chang)"
DEFAULT_AREA_CODE = "502"
DEFAULT_SITE_LOCATION = "HQ-Taipei"


def is_last_two_digits_repeated(ext_text: str) -> bool:
    """Return True if the last two numeric digits of `ext_text` are identical.

    Examples:
        - `"50200"` -> last two digits `"00"` -> True (repeated, skip)
        - `"50222"` -> last two digits `"22"` -> True (repeated, skip)
        - `"50234"` -> last two digits `"34"` -> False (valid candidate)
    """
    digits = "".join(ch for ch in ext_text if ch.isdigit())
    if len(digits) < 2:
        return True
    return digits[-1] == digits[-2]


def normalize_emp_id(value: str) -> str:
    """Normalize an employee ID to include the 'EMP' prefix (e.g. '104' -> 'EMP104')."""
    cleaned = (value or "").strip().upper()
    if not cleaned:
        return DEFAULT_EMP_ID
    if cleaned.startswith("EMP-"):
        body = cleaned[4:].strip()
    elif cleaned.startswith("EMP"):
        body = cleaned[3:].strip()
    else:
        body = cleaned
    return f"EMP{body}" if body else DEFAULT_EMP_ID


def ask_user_inputs() -> tuple[str, str, str, str]:
    """Prompt the engineer for employee ID, name, optional MAC, and area prefix in CLI."""
    print("=" * 68)
    print("  企業電信分機自動選號與配發工具 (Telecom Extension Provisioning)")
    print("  提示：直接按 Enter 可快速套用預設測試員工資料進行展示")
    print("=" * 68)

    raw_emp_id = input(f"請輸入配發員工工號 [可省略 EMP，預設 {DEFAULT_EMP_ID}]：").strip()
    emp_id = normalize_emp_id(raw_emp_id) if raw_emp_id else DEFAULT_EMP_ID

    raw_emp_name = input(f"請輸入配發員工姓名 [預設 {DEFAULT_EMP_NAME}]：").strip()
    emp_name = raw_emp_name if raw_emp_name else DEFAULT_EMP_NAME

    mac_addr = input("請輸入話機 MAC 位址 [選填，直接按 Enter 留白則啟用 Softphone]：").strip()

    raw_area = input(f"請輸入搜尋分機區碼 [預設 {DEFAULT_AREA_CODE}]：").strip()
    area_code = raw_area if raw_area else DEFAULT_AREA_CODE

    return emp_id, emp_name, mac_addr, area_code


def find_and_click_available_extension(page: Any) -> str:
    """Scan `#telecom-extensions-tbody` and click the first available extension with non-repeating last 2 digits."""
    rows = page.locator("#telecom-extensions-tbody tr.telecom-ext-row")
    row_count = rows.count()

    if row_count == 0:
        raise RuntimeError("查無符合條件的分機資料列")

    for idx in range(row_count):
        row = rows.nth(idx)
        button = row.locator("button.btn-select-ext")
        ext_value = (button.get_attribute("data-ext") or button.inner_text()).strip()
        status_value = (row.get_attribute("data-status") or "").strip()

        print(f"  [掃描第 {idx + 1} 列] 分機：{ext_value} (狀態：{status_value})")

        if status_value and status_value.lower() != "available":
            print(f"    -> 略過：狀態非 Available ({status_value})")
            continue

        if is_last_two_digits_repeated(ext_value):
            print(f"    -> 略過：尾碼後兩位數字重複 ({ext_value[-2:]})")
            continue

        print(f"  [OK] 找到符合規則之可用分機：{ext_value}，正在開啟配號設定面板...")
        button.click()
        return ext_value

    raise RuntimeError("已掃描所有分機列，未找到尾碼後兩位不重複的可用分機")


def run_provision_flow(
    page: Any,
    sandbox_url: str,
    emp_id: str,
    emp_name: str,
    mac_addr: str = "",
    area_code: str = DEFAULT_AREA_CODE,
    site_location: str = DEFAULT_SITE_LOCATION,
) -> str:
    """Execute the end-to-end extension search, selection, and provisioning form fill."""
    target_url = f"{sandbox_url.rstrip('/')}/portal/telecom/extensions"
    print(f"\n1. 正在連線至電信分機管理系統：{target_url}")
    page.goto(target_url, wait_until="domcontentloaded")

    print(f"2. 輸入分機區碼「{area_code}」並篩選「未配發可用 (Available)」...")
    page.locator("#input-area-code").fill(area_code)
    page.locator("#select-ext-status").select_option("Available")
    page.locator("#btn-telecom-search").click()

    print("3. 開始掃描分機清單（規則：排除尾碼後兩位重複之預留號）...")
    selected_ext = find_and_click_available_extension(page)

    panel = page.locator("#telecom-provision-panel")
    panel.wait_for(state="visible", timeout=10000)

    print(f"4. 正在填寫分機 {selected_ext} 配號表單...")
    page.locator("#select-telecom-company").select_option("Enterprise-HQ")
    page.locator("#select-telecom-user-type").select_option("Regular")
    page.locator("#select-telecom-status").select_option("Active")

    if mac_addr:
        page.locator("#select-telecom-phone-type").select_option("IP-Phone")
    else:
        page.locator("#select-telecom-phone-type").select_option("Softphone")

    normalized_emp_id = normalize_emp_id(emp_id)
    page.locator("#input-telecom-site").fill(site_location)
    page.locator("#input-telecom-assign-emp-id").fill(normalized_emp_id)
    page.locator("#input-telecom-assign-emp-name").fill(emp_name)

    mac_input = page.locator("#input-telecom-mac")
    mac_input.fill("")

    softphone_checkbox = page.locator("#chk-telecom-softphone")
    if mac_addr == "":
        softphone_checkbox.check()
    else:
        if softphone_checkbox.is_checked():
            softphone_checkbox.uncheck()
        mac_input.fill(mac_addr)

    page.locator("#btn-telecom-save-provision").click()
    return selected_ext


def main() -> None:
    creds = read_credentials()
    print(f"[SDK] 已載入工程師憑證：{creds['email']} (Portal 帳號: {creds['portal_account']})")

    emp_id, emp_name, mac_addr, area_code = ask_user_inputs()

    with ensure_sandbox_server() as sandbox_url:
        try:
            with open_browser(
                headless=False,
                downloads_path=None,
                dialog_action="accept",
            ) as page:
                try:
                    selected_ext = run_provision_flow(
                        page=page,
                        sandbox_url=sandbox_url,
                        emp_id=emp_id,
                        emp_name=emp_name,
                        mac_addr=mac_addr,
                        area_code=area_code,
                    )

                    print("\n" + "=" * 68)
                    print("[OK] 分機配號資料已自動填寫並預覽完成！")
                    print(f"  - 配發員工工號：{emp_id}")
                    print(f"  - 配發員工姓名：{emp_name}")
                    print(f"  - 選取可用分機：{selected_ext}")
                    print(
                        f"  - 話機配置模式：{'桌面 Softphone (無實體 MAC)' if not mac_addr else f'實體話機 MAC ({mac_addr})'}"
                    )
                    print("=" * 68)
                    print("請於瀏覽器確認畫面結果。")

                    if sys.stdin and sys.stdin.isatty():
                        input("\n按 Enter 後關閉瀏覽器...")
                except Exception as exc:
                    print(f"\n[錯誤] 執行過程發生異常：{exc}")
                    if sys.stdin and sys.stdin.isatty():
                        input("按 Enter 後關閉瀏覽器...")
        except Exception as exc:
            print(f"\n[錯誤] 啟動瀏覽器過程發生異常：{exc}")
            if sys.stdin and sys.stdin.isatty():
                input("按 Enter 後繼續...")


def restart_program() -> None:
    """Restart the current script or frozen executable."""
    os.execv(sys.executable, [sys.executable, *sys.argv])


if __name__ == "__main__":
    while True:
        main()
        if not (sys.stdin and sys.stdin.isatty()):
            break
        print("")
        choice = input("按 Enter 重新啟動分機配號工具，或輸入 Q 離開：").strip().lower()
        if choice == "q":
            print("程式已結束。")
            break
        restart_program()

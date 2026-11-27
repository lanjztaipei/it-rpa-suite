"""Standalone Async Form Audit Crawler Demo (`async_form_audit_demo.py`).

Demonstrates high-concurrency Playwright automation for Toolbox scripts:
1. Single login sharing one authenticated `BrowserContext` across all worker tabs
2. `asyncio.Queue` + configurable multi-tab Worker Pool (1-10 concurrent tabs)
3. Cross-`iframe` form field extraction (`<select>` + `<textarea>`)
4. Single-line terminal progress bar guarded by `asyncio.Lock`
5. Pure `openpyxl` read/write outputting a new `.xlsx` file into `data/downloads/`
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote

from openpyxl import load_workbook

# Ensure tools/ directory is on sys.path when invoked from any working directory
_TOOLS_DIR = Path(__file__).resolve().parent
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

from tool_sdk import (  # noqa: E402
    BASE_DIR,
    ensure_sandbox_server,
    read_credentials,
    setup_async_browser,
)

SAMPLE_REPORT_FILENAME = "sample_form_audit_report.xlsx"
DEFAULT_CONCURRENCY = 5
MIN_CONCURRENCY = 1
MAX_CONCURRENCY = 10


def resolve_sample_workbook_path(base_dir: Path | None = None) -> Path:
    """Locate the bundled sample audit workbook in source or packaged mode."""
    root = (base_dir or BASE_DIR).resolve()
    candidates = (
        root / "assets" / SAMPLE_REPORT_FILENAME,
        root / "_internal" / "assets" / SAMPLE_REPORT_FILENAME,
    )
    for path in candidates:
        if path.is_file():
            return path
    raise FileNotFoundError(f"找不到內建範例 Excel：{candidates[0]}（請確認 assets 目錄完整）")


def make_output_path(input_path: Path, output_dir: Path) -> Path:
    """Return a non-overwriting output path inside `output_dir` (e.g. `data/downloads/`)."""
    output_dir.mkdir(parents=True, exist_ok=True)
    candidate = output_dir / f"{input_path.stem}_updated{input_path.suffix}"
    counter = 2
    while candidate.exists():
        candidate = output_dir / f"{input_path.stem}_updated_{counter}{input_path.suffix}"
        counter += 1
    return candidate


def load_form_numbers(excel_path: Path) -> list[str]:
    """Read non-empty form IDs from column A (`Form No`) using pure `openpyxl`."""
    wb = load_workbook(excel_path, read_only=True, data_only=True)
    try:
        ws = wb.active
        if ws is None:
            return []
        form_numbers: list[str] = []
        for row in ws.iter_rows(min_row=2, max_col=1, values_only=True):
            raw = row[0]
            if raw is None:
                continue
            cleaned = str(raw).strip()
            if cleaned:
                form_numbers.append(cleaned)
        return form_numbers
    finally:
        wb.close()


def write_results_to_excel(
    input_path: Path,
    output_path: Path,
    results: dict[str, dict[str, str]],
) -> int:
    """Write crawled `request_type` and `review_comment` into columns E & F and save a new copy."""
    wb = load_workbook(input_path)
    try:
        ws = wb.active
        if ws is None:
            raise ValueError("範例 Excel 缺少有效工作表")

        updated_count = 0
        for row_idx in range(2, ws.max_row + 1):
            raw_no = ws.cell(row=row_idx, column=1).value
            form_no = str(raw_no).strip() if raw_no is not None else ""
            if not form_no or form_no not in results:
                continue
            item = results[form_no]
            ws.cell(row=row_idx, column=5).value = item.get("request_type", "")
            ws.cell(row=row_idx, column=6).value = item.get("review_comment", "")
            updated_count += 1

        output_path.parent.mkdir(parents=True, exist_ok=True)
        wb.save(output_path)
        return updated_count
    finally:
        wb.close()


def show_progress(
    current: int,
    total: int,
    label: str = "非同步爬取",
    detail: str = "",
    width: int = 28,
) -> None:
    """Render an in-place single-line progress bar in the terminal."""
    if total <= 0:
        percent = 100
        filled = width
    else:
        percent = int(current * 100 / total)
        filled = int(width * current / total)

    bar = "#" * filled + "-" * (width - filled)
    detail_text = f" | {detail}" if detail else ""
    message = f"\r{label} [{bar}] {current}/{total} ({percent:3d}%){detail_text}"
    print(message.ljust(96), end="", flush=True)
    if current >= total:
        print()


def ask_concurrency(
    default: int = DEFAULT_CONCURRENCY,
    minimum: int = MIN_CONCURRENCY,
    maximum: int = MAX_CONCURRENCY,
) -> int:
    """Prompt the user for concurrent worker tab count."""
    print("=" * 68)
    print("  高併發電子表單逾期稽核工具 (Async Playwright Worker Pool Demo)")
    print("  特色：單次登入共享 Context ｜ asyncio.Queue 多分頁併發 ｜ 跨 iframe 擷取")
    print("=" * 68)

    if not (sys.stdin and sys.stdin.isatty()):
        return default

    while True:
        raw = input(
            f"請輸入同時開啟的工作分頁數量（{minimum}-{maximum}，直接按 Enter 預設 {default}）："
        ).strip()
        if not raw:
            return default
        try:
            value = int(raw)
        except ValueError:
            print("錯誤：請輸入整數。")
            continue
        if minimum <= value <= maximum:
            return value
        print(f"錯誤：請輸入 {minimum} 到 {maximum} 之間的數字。")


async def login_once(context: Any, sandbox_url: str, creds: dict[str, str]) -> None:
    """Authenticate once in a temporary tab so all worker tabs share the session cookie."""
    login_page = await context.new_page()
    login_page.set_default_timeout(30000)
    try:
        login_url = f"{sandbox_url.rstrip('/')}/portal/forms/login"
        await login_page.goto(login_url, wait_until="domcontentloaded")
        await login_page.locator("#login-username").fill(creds["portal_account"])
        await login_page.locator("#login-password").fill(creds["portal_password"])
        await login_page.locator("#btn-login").click()
        await login_page.locator("#portal-workspace").wait_for(state="visible", timeout=10000)
    finally:
        await login_page.close()


async def fetch_form_from_iframe(
    page: Any,
    sandbox_url: str,
    form_no: str,
) -> dict[str, str]:
    """Open a form view page and extract `<select>` + `<textarea>` values from `iframe#form-frame`."""
    target_url = f"{sandbox_url.rstrip('/')}/portal/forms/view?id={quote(form_no)}"
    await page.goto(target_url, wait_until="domcontentloaded")

    frame = page.frame_locator("iframe#form-frame")
    select_el = frame.locator("#request-type")
    comment_el = frame.locator("#review-comment")

    await select_el.wait_for(state="attached", timeout=15000)
    request_type: str = await select_el.evaluate(
        """(el) => {
            const opt = el.options && el.selectedIndex >= 0 ? el.options[el.selectedIndex] : null;
            return opt ? (opt.textContent || opt.value || '').trim() : (el.value || '').trim();
        }"""
    )
    review_comment = (await comment_el.input_value()).strip()
    return {
        "request_type": request_type,
        "review_comment": review_comment,
    }


async def crawl_forms_concurrently(
    sandbox_url: str,
    form_numbers: list[str],
    creds: dict[str, str],
    concurrency: int = DEFAULT_CONCURRENCY,
    headless: bool = False,
) -> tuple[dict[str, dict[str, str]], float]:
    """Run single login + `asyncio.Queue` multi-tab worker pool and return `(results, elapsed_sec)`."""
    results: dict[str, dict[str, str]] = {}
    total_jobs = len(form_numbers)
    if total_jobs == 0:
        return results, 0.0

    queue: asyncio.Queue[str] = asyncio.Queue()
    for form_no in form_numbers:
        queue.put_nowait(form_no)

    progress_lock = asyncio.Lock()
    completed = 0
    playwright = browser = context = None

    try:
        playwright, browser, context = await setup_async_browser(headless=headless)

        print("1. 正在執行單次登入（共享 BrowserContext Session）...")
        await login_once(context, sandbox_url, creds)

        actual_workers = max(1, min(concurrency, total_jobs))
        print(f"2. 啟動 {actual_workers} 個併發工作分頁，開始讀取 {total_jobs} 筆表單...")
        show_progress(0, total_jobs, detail="準備開始")
        start_time = time.perf_counter()

        async def worker(worker_id: int) -> None:
            nonlocal completed
            page = await context.new_page()
            page.set_default_timeout(30000)
            try:
                while True:
                    try:
                        form_no = queue.get_nowait()
                    except asyncio.QueueEmpty:
                        break
                    try:
                        results[form_no] = await fetch_form_from_iframe(page, sandbox_url, form_no)
                    finally:
                        queue.task_done()
                        async with progress_lock:
                            completed += 1
                            show_progress(
                                completed,
                                total_jobs,
                                detail=f"Tab-{worker_id} 完成 {form_no}",
                            )
            finally:
                await page.close()

        await asyncio.gather(*(worker(idx + 1) for idx in range(actual_workers)))
        elapsed = time.perf_counter() - start_time
        return results, elapsed
    finally:
        if context is not None:
            await context.close()
        if browser is not None:
            await browser.close()
        if playwright is not None:
            await playwright.stop()


async def main() -> None:
    creds = read_credentials()
    print(f"[SDK] 已載入工程師憑證：{creds['email']} (Portal 帳號: {creds['portal_account']})")

    concurrency = ask_concurrency()
    input_path = resolve_sample_workbook_path()
    output_dir = BASE_DIR / "data" / "downloads"
    output_path = make_output_path(input_path, output_dir)

    form_numbers = load_form_numbers(input_path)
    print(f"\n讀取範例報表：{input_path.name}（共 {len(form_numbers)} 筆表單）")

    with ensure_sandbox_server() as sandbox_url:
        results, elapsed = await crawl_forms_concurrently(
            sandbox_url=sandbox_url,
            form_numbers=form_numbers,
            creds=creds,
            concurrency=concurrency,
            headless=False,
        )

    updated_count = write_results_to_excel(input_path, output_path, results)
    throughput = updated_count / elapsed if elapsed > 0 else 0.0

    print("\n" + "=" * 68)
    print("[OK] 非同步併發爬取與 Excel 回填完成！")
    print(f"  - 併發工作分頁：{min(concurrency, len(form_numbers))} 個")
    print(f"  - 完成表單筆數：{updated_count}/{len(form_numbers)} 筆")
    print(f"  - 總爬取耗時  ：{elapsed:.2f} 秒（平均 {throughput:.1f} 筆/秒）")
    print(f"  - 輸出檔案路徑：{output_path}")
    print("=" * 68)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as exc:
        print(f"\n[錯誤] 執行過程發生異常：{exc}")
    if sys.stdin and sys.stdin.isatty():
        input("\n按 Enter 鍵結束程式...")

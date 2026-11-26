"""Playwright report download, pure-openpyxl parsing, and BCC email draft generation."""

from __future__ import annotations

import html
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from it_rpa_suite.adapters.excel import parse_overdue_borrow_recipients
from it_rpa_suite.adapters.logger import get_logger
from it_rpa_suite.adapters.mailer import compose_or_preview_email
from it_rpa_suite.adapters.paths import AppPaths, get_app_paths
from it_rpa_suite.adapters.result import ServiceResult
from it_rpa_suite.adapters.storage import AppStorage
from it_rpa_suite.features.asset_loan.service import login_portal_if_needed

logger = get_logger(__name__)

FEATURE_KEY_OVERDUE_BORROW = "overdue_borrow_notify"
BORROW_REPORT_FILENAME = "sample_borrow_report.xlsx"

SITE_OPTIONS: tuple[str, ...] = (
    "台中總部",
    "台北廠",
    "新北廠",
    "桃園廠",
    "台南廠",
    "高雄廠",
)


@dataclass(frozen=True)
class NotificationActionSpec:
    """Declarative metadata for batch notification buttons."""

    key: str
    title: str
    enabled: bool


NOTIFICATION_ACTIONS: tuple[NotificationActionSpec, ...] = (
    NotificationActionSpec(
        key="overdue_borrow",
        title="短期借用逾期催還",
        enabled=True,
    ),
    NotificationActionSpec(
        key="endpoint_antivirus",
        title="端點防毒合規提醒",
        enabled=False,
    ),
    NotificationActionSpec(
        key="warranty_expiring",
        title="設備保固即將到期",
        enabled=False,
    ),
)


def build_overdue_borrow_email(site: str, recipients: list[str]) -> tuple[str, str, str]:
    """Build sanitized plain-text style overdue laptop reminder email with BCC recipients."""
    safe_site = html.escape(site.strip())
    subject = f"短期借用設備逾期歸還提醒（{site.strip()}）"
    bcc = "; ".join(recipients)
    html_body = (
        "<html><body>"
        "<p>您好：</p>"
        "<p>短期借用筆電期限為 3 天，您借用的設備目前已超過歸還期限。</p>"
        f"<p>請儘速將設備與配件歸還至 {safe_site} IT 服務中心；"
        "若因業務需求需延長使用，請先聯繫服務台辦理展延手續。</p>"
        "<p>感謝您的配合。</p>"
        "<p>IT Service Center</p>"
        "</body></html>"
    )
    return subject, html_body, bcc


def _remove_stale_file(filepath: Path) -> None:
    if not filepath.exists():
        return
    try:
        filepath.unlink()
    except PermissionError as exc:
        raise PermissionError(f"無法覆蓋舊報表，請先關閉開啟中的 Excel 檔案：{filepath}") from exc


def download_borrow_overdue_report(
    page: Any,
    base_url: str,
    credentials: dict[str, str] | None,
    destination: Path,
) -> Path:
    """Navigate to the report portal, trigger Excel export, and save the downloaded file."""
    url = f"{base_url.rstrip('/')}/portal/reports/borrow-overdue"
    logger.info("前往逾期借用報表中心下載報表：%s", url)

    page.goto(url, wait_until="domcontentloaded")
    login_portal_if_needed(page, credentials)

    export_btn = page.locator("#btn-export-excel")
    export_btn.wait_for(state="visible", timeout=15000)

    destination.parent.mkdir(parents=True, exist_ok=True)
    _remove_stale_file(destination)

    with page.expect_download(timeout=30000) as download_info:
        export_btn.click()

    download = download_info.value
    download.save_as(str(destination))

    if not destination.is_file() or destination.stat().st_size == 0:
        raise RuntimeError(f"報表下載異常或檔案為空：{destination}")

    logger.info("Excel 報表已下載至：%s", destination)
    return destination


def run_overdue_borrow_notify(
    browser_session: Any,
    site: str,
    base_url: str,
    credentials: dict[str, str] | None = None,
    storage: AppStorage | None = None,
    paths: AppPaths | None = None,
    *,
    force_email_fallback: bool = False,
) -> ServiceResult:
    """Download overdue loan Excel report, parse recipients via openpyxl, and open BCC draft."""
    normalized_site = (site or "").strip()
    if not normalized_site:
        return ServiceResult.failed(message="請先選擇所在廠區")

    app_paths = paths or get_app_paths()
    report_path = app_paths.downloads_dir / BORROW_REPORT_FILENAME
    page: Any = None

    try:
        page = browser_session.new_page(timeout=30000)
        download_borrow_overdue_report(
            page=page,
            base_url=base_url,
            credentials=credentials,
            destination=report_path,
        )
    except Exception as exc:
        logger.exception("下載逾期借用報表失敗")
        return ServiceResult.failed(
            message="報表下載失敗",
            error=str(exc),
        )
    finally:
        if page is not None:
            browser_session.close_page(page)

    try:
        recipients = parse_overdue_borrow_recipients(
            filepath=report_path,
            site=normalized_site,
        )
        subject, html_body, bcc = build_overdue_borrow_email(normalized_site, recipients)
        draft = compose_or_preview_email(
            to="",
            subject=subject,
            html_body=html_body,
            bcc=bcc,
            force_fallback=force_email_fallback,
        )
        if storage is not None:
            storage.record_usage(FEATURE_KEY_OVERDUE_BORROW)

        return ServiceResult.success(
            message=f"已生成 {normalized_site} 逾期催還郵件草稿",
            data={
                "operation": FEATURE_KEY_OVERDUE_BORROW,
                "site": normalized_site,
                "recipients": recipients,
                "report_path": str(report_path),
                "draft_email": draft.to_dict(),
            },
        )
    except Exception as exc:
        logger.exception("解析逾期借用報表或建立郵件草稿失敗")
        return ServiceResult.failed(
            message="報表解析或郵件建立失敗",
            error=str(exc),
        )

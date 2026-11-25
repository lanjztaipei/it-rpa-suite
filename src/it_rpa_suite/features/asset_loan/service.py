"""Playwright automation workflows and input validation for asset loan, project loan, and return lookup."""

from __future__ import annotations

from typing import Any

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from it_rpa_suite.adapters.credentials_dpapi import resolve_login_credentials
from it_rpa_suite.adapters.logger import get_logger
from it_rpa_suite.adapters.result import (
    ServiceResult,
    ValidationResult,
    validate_employee_id,
    validate_request_no,
)
from it_rpa_suite.adapters.storage import AppStorage

logger = get_logger(__name__)

OPERATION_SHORT_LOAN = "short_loan"
OPERATION_PROJECT_LOAN = "project_loan"
OPERATION_RETURN_LOOKUP = "return_and_lookup"


def detect_loan_operation(
    asset_tags: list[tuple[str, str]],
    borrower_or_request: str,
) -> ValidationResult:
    """Classify the operation mode based on validated asset tags and borrower/request input.

    Rules:
    - Asset tag(s) + empty borrower/request -> Return & Custodian Lookup (limited to 1 asset tag)
    - Asset tag(s) + 6-digit number or REQ-xxxxxx -> Project Loan (long-term borrow)
    - Asset tag(s) + alphanumeric employee ID -> Short Term Loan (short borrow)
    """
    if not asset_tags:
        return ValidationResult(valid=False, message="請至少輸入一筆資產編號")

    target = (borrower_or_request or "").strip().upper()
    if not target:
        if len(asset_tags) != 1:
            return ValidationResult(
                valid=False,
                message="歸還與保管人聯查限單筆資產編號，請先刪除多餘項目",
            )
        return ValidationResult(
            valid=True,
            value={
                "operation": OPERATION_RETURN_LOOKUP,
                "asset_tags": list(asset_tags),
            },
        )

    is_request_candidate = (target.isdigit() and len(target) == 6) or target.startswith("REQ-")
    if is_request_candidate:
        req_result = validate_request_no(target)
        if not req_result.valid:
            return req_result
        return ValidationResult(
            valid=True,
            value={
                "operation": OPERATION_PROJECT_LOAN,
                "asset_tags": list(asset_tags),
                "request_no": req_result.value,
            },
        )

    emp_result = validate_employee_id(target)
    if not emp_result.valid:
        return emp_result

    return ValidationResult(
        valid=True,
        value={
            "operation": OPERATION_SHORT_LOAN,
            "asset_tags": list(asset_tags),
            "employee_id": emp_result.value,
        },
    )


def login_portal_if_needed(
    page: Any,
    credentials: dict[str, str] | None = None,
) -> None:
    """Authenticate on the Enterprise IT Portal if the login gate is visible."""
    login_input = page.locator("#login-username")
    try:
        login_visible = bool(login_input.is_visible(timeout=800))
    except PlaywrightTimeoutError:
        login_visible = False

    if not login_visible:
        logger.debug("Enterprise Portal 已處於登入狀態")
        return

    username, password = resolve_login_credentials(
        credentials,
        account_keys=("portal_account",),
        password_keys=("portal_password",),
        default_account="it.admin",
        default_password="Sandbox@2026",
        system_name="企業入口網",
    )
    login_input.fill(username)
    page.locator("#login-password").fill(password)
    page.locator("#btn-login").click()
    page.locator("#portal-workspace").wait_for(state="visible", timeout=5000)


def select_searchable_employee(
    page: Any,
    trigger_selector: str,
    input_selector: str,
    employee_id: str,
) -> None:
    """Interact with a custom searchable select dropdown to choose an employee by ID."""
    page.locator(trigger_selector).click()
    search_box = page.locator(input_selector)
    search_box.wait_for(state="visible", timeout=3000)
    search_box.fill(employee_id)
    page.wait_for_timeout(120)
    search_box.press("Enter")


def add_asset_to_issue_table(
    page: Any,
    employee_id: str | None,
    asset_tag: str,
    usage_type: str = "Loan",
) -> None:
    """Select borrower (if provided), verify asset tag, choose usage type, and add row."""
    if employee_id:
        select_searchable_employee(
            page,
            "#borrower-select-trigger",
            "#borrower-select-input",
            employee_id,
        )

    page.locator("#input-asset-tag").fill(asset_tag)
    page.locator("#btn-search-asset").click()
    page.wait_for_timeout(100)
    page.locator("#select-usage-type").select_option(value=usage_type)
    page.wait_for_timeout(100)
    page.locator("#btn-add-asset-row").click()


def fill_computer_security_fields(
    page: Any,
    asset_tags: list[tuple[str, str]],
) -> None:
    """Populate hostname, Corporate-LAN network zone, and EDR status for computer assets."""
    for index, (full_tag, digits) in enumerate(asset_tags):
        if not (digits.startswith("1") or digits.startswith("3")):
            continue

        page.locator(f"#input-hostname-{index}").fill(full_tag)
        page.locator(f"#select-network-zone-{index}").select_option(value="Corporate-LAN")
        page.locator(f"#select-endpoint-edr-{index}").select_option(value="Enabled")


def run_short_loan(
    browser_session: Any,
    asset_tags: list[tuple[str, str]],
    employee_id: str,
    base_url: str = "http://127.0.0.1:8000",
    credentials: dict[str, str] | None = None,
    storage: AppStorage | None = None,
) -> ServiceResult:
    """Automate short-term equipment loan form filling on the Asset Portal."""
    logger.info("開始執行短期借用自動化: emp=%s, count=%d", employee_id, len(asset_tags))
    page = None
    store = storage or AppStorage()

    try:
        page = browser_session.new_page()
        page.goto(f"{base_url.rstrip('/')}/portal/assets/issue")
        login_portal_if_needed(page, credentials)

        page.locator("#select-issue-purpose").select_option(value="Short Term Loan")
        page.locator("#btn-load-purpose").click()

        for index, (full_tag, _) in enumerate(asset_tags):
            emp_arg = employee_id if index == 0 else None
            add_asset_to_issue_table(page, emp_arg, full_tag, usage_type="Loan")
            page.wait_for_timeout(150)
            store.record_usage("short_loan")

        fill_computer_security_fields(page, asset_tags)
        page.evaluate("window.scrollTo(0, document.body.scrollHeight);")

        return ServiceResult.manual_confirmation(
            message="短期借用資料已自動填入 Asset Portal，請於 Edge 確認明細後點擊送出。",
            data={
                "operation": OPERATION_SHORT_LOAN,
                "asset_count": len(asset_tags),
                "employee_id": employee_id,
            },
        )
    except Exception as exc:
        logger.exception("短期借用自動化執行失敗")
        return ServiceResult.failed(
            message="短期借用自動填單發生錯誤，已保留目前瀏覽器分頁供手動確認。",
            error=str(exc),
            data={"keep_browser_page": page is not None},
        )


def run_project_loan(
    browser_session: Any,
    asset_tags: list[tuple[str, str]],
    request_no: str,
    base_url: str = "http://127.0.0.1:8000",
    credentials: dict[str, str] | None = None,
    storage: AppStorage | None = None,
) -> ServiceResult:
    """Automate project long-term equipment loan form filling by request number."""
    logger.info("開始執行專案長借自動化: req=%s, count=%d", request_no, len(asset_tags))
    page = None
    store = storage or AppStorage()

    try:
        page = browser_session.new_page()
        page.goto(f"{base_url.rstrip('/')}/portal/assets/issue")
        login_portal_if_needed(page, credentials)

        page.locator("#select-issue-purpose").select_option(value="Project Loan")
        page.locator("#input-request-no").fill(request_no)
        page.locator("#btn-load-purpose").click()

        for full_tag, _ in asset_tags:
            add_asset_to_issue_table(page, None, full_tag, usage_type="Loan")
            page.wait_for_timeout(150)
            store.record_usage("project_loan")

        fill_computer_security_fields(page, asset_tags)
        page.evaluate("window.scrollTo(0, document.body.scrollHeight);")

        return ServiceResult.manual_confirmation(
            message="專案長借資料已自動填入 Asset Portal，請於 Edge 確認明細後點擊送出。",
            data={
                "operation": OPERATION_PROJECT_LOAN,
                "asset_count": len(asset_tags),
                "request_no": request_no,
            },
        )
    except Exception as exc:
        logger.exception("專案長借自動化執行失敗")
        return ServiceResult.failed(
            message="專案長借自動填單發生錯誤，已保留目前瀏覽器分頁供手動確認。",
            error=str(exc),
            data={"keep_browser_page": page is not None},
        )


def run_return_and_lookup(
    browser_session: Any,
    asset_tags: list[tuple[str, str]],
    base_url: str = "http://127.0.0.1:8000",
    credentials: dict[str, str] | None = None,
    storage: AppStorage | None = None,
) -> ServiceResult:
    """Cross-tab workflow: look up asset custodian -> search Directory extension -> prepare Return page."""
    asset_tag, _ = asset_tags[0]
    logger.info("開始執行歸還與保管人聯查自動化: tag=%s", asset_tag)
    lookup_page = None
    detail_page = None
    directory_page = None
    return_page = None
    store = storage or AppStorage()
    clean_base = base_url.rstrip("/")

    try:
        # 1. Search asset in Asset Portal and intercept target="_blank" detail tab
        lookup_page = browser_session.new_page()
        lookup_page.goto(f"{clean_base}/portal/assets/search")
        login_portal_if_needed(lookup_page, credentials)

        lookup_page.locator("#input-search-tag").fill(asset_tag)
        lookup_page.locator("#btn-query-asset").click()

        with lookup_page.context.expect_page() as new_page_info:
            lookup_page.locator("#asset-link-0").click()
        detail_page = new_page_info.value
        detail_page.wait_for_load_state()

        owner_id = detail_page.locator("#holder-emp-id").inner_text().strip()

        # 2. Query custodian contact extension in Enterprise Directory
        directory_page = browser_session.new_page()
        directory_page.goto(f"{clean_base}/portal/directory")
        directory_page.locator("#input-directory-query").fill(owner_id)
        directory_page.locator("#btn-directory-search").click()
        store.record_usage("holder_lookup")

        # 3. Prepare Asset Return page for custodian
        return_page = browser_session.new_page()
        return_page.goto(f"{clean_base}/portal/assets/return")
        login_portal_if_needed(return_page, credentials)

        return_page.locator("#select-return-purpose").select_option(value="Loan Return")
        select_searchable_employee(
            return_page,
            "#returner-select-trigger",
            "#returner-select-input",
            owner_id,
        )
        return_page.locator("#btn-load-return-list").click()
        return_page.wait_for_timeout(200)
        return_page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
        store.record_usage("asset_return")

        # 4. Close the transient detail tab
        browser_session.close_page(detail_page)
        detail_page = None

        return ServiceResult.manual_confirmation(
            message=(
                f"已查出資產 {asset_tag} 保管人為「{owner_id}」，"
                "並已開啟企業通訊錄與完成歸還頁面準備。"
            ),
            data={
                "operation": OPERATION_RETURN_LOOKUP,
                "asset_tag": asset_tag,
                "owner_id": owner_id,
            },
        )
    except Exception as exc:
        logger.exception("歸還與保管人聯查自動化執行失敗")
        return ServiceResult.failed(
            message="歸還與保管人聯查發生錯誤，已保留瀏覽器分頁供手動接續處理。",
            error=str(exc),
            data={
                "keep_browser_page": any(
                    p is not None for p in (lookup_page, detail_page, directory_page, return_page)
                )
            },
        )

"""Playwright workflows and input validation for employee onboarding and offboarding clearance."""

from __future__ import annotations

from typing import Any

from it_rpa_suite.adapters.credentials_dpapi import CredentialStore
from it_rpa_suite.adapters.logger import get_logger
from it_rpa_suite.adapters.mailer import compose_or_preview_email
from it_rpa_suite.adapters.result import (
    ServiceResult,
    ValidationResult,
    validate_asset_tag,
    validate_device_type,
    validate_employee_id,
    validate_request_no,
    validate_yes_no,
)
from it_rpa_suite.adapters.storage import AppStorage
from it_rpa_suite.features.asset_loan.service import (
    add_asset_to_issue_table,
    fill_computer_security_fields,
    login_portal_if_needed,
    select_searchable_employee,
)

logger = get_logger(__name__)

ACTION_ONBOARDING = "onboarding_issue"
ACTION_OFFBOARDING = "offboarding_clearance"

STANDARD_ACCESSORY_TAGS = (
    "ACC-MOUSE-USB",
    "ACC-HEADSET-USB",
    "ACC-CABLE-CAT6",
)
KEYBOARD_ACCESSORY_TAG = "ACC-KEYBOARD-USB"
DESKPHONE_ACCESSORY_TAG = "ACC-PHONE-IP"


def validate_onboarding_inputs(
    request_no: str,
    employee_id: str,
    computer_tag: str,
    monitor_tag: str = "",
    deskphone: str = "N",
) -> ValidationResult:
    """Validate all inputs required for new hire equipment provisioning."""
    req_res = validate_request_no(request_no)
    if not req_res.valid:
        return ValidationResult(valid=False, message=req_res.message, value="request_no")

    emp_res = validate_employee_id(employee_id)
    if not emp_res.valid:
        return ValidationResult(valid=False, message=emp_res.message, value="employee_id")

    comp_res = validate_asset_tag(computer_tag)
    if not comp_res.valid:
        return ValidationResult(
            valid=False,
            message=f"電腦資產編號錯誤：{comp_res.message}",
            value="computer_tag",
        )

    comp_full_tag, comp_digits = comp_res.value
    mon_full_tag: str | None = None

    if comp_digits.startswith("1"):
        mon_res = validate_asset_tag(monitor_tag)
        if not mon_res.valid:
            return ValidationResult(
                valid=False,
                message=f"桌機配發需填寫螢幕資產編號：{mon_res.message}",
                value="monitor_tag",
            )
        mon_full_tag, _ = mon_res.value
        if mon_full_tag == comp_full_tag:
            return ValidationResult(
                valid=False,
                message="電腦資產編號與螢幕資產編號不可相同",
                value="monitor_tag",
            )

    phone_res = validate_yes_no(deskphone, "是否配發實體話機")
    if not phone_res.valid:
        return ValidationResult(valid=False, message=phone_res.message, value="deskphone")

    return ValidationResult(
        valid=True,
        value={
            "request_no": req_res.value,
            "employee_id": emp_res.value,
            "computer_tag": comp_full_tag,
            "computer_digits": comp_digits,
            "monitor_tag": mon_full_tag,
            "deskphone": phone_res.value,
        },
    )


def validate_offboarding_inputs(
    employee_id: str,
    device_type: str = "PC",
    deskphone: str = "N",
) -> ValidationResult:
    """Validate all inputs required for employee offboarding multi-system clearance."""
    emp_res = validate_employee_id(employee_id)
    if not emp_res.valid:
        return ValidationResult(valid=False, message=emp_res.message, value="employee_id")

    dev_res = validate_device_type(device_type)
    if not dev_res.valid:
        return ValidationResult(valid=False, message=dev_res.message, value="device_type")

    phone_res = validate_yes_no(deskphone, "是否繳回實體話機")
    if not phone_res.valid:
        return ValidationResult(valid=False, message=phone_res.message, value="deskphone")

    return ValidationResult(
        valid=True,
        value={
            "employee_id": emp_res.value,
            "device_type": dev_res.value,
            "deskphone": phone_res.value,
        },
    )


def _remove_default_redundant_rows(page: Any) -> int:
    """Remove pre-populated redundant rows (e.g., default bag/lock) on New Hire Assignment."""
    removed = 0
    for _ in range(5):
        remove_buttons = page.locator(".btn-remove-row")
        if remove_buttons.count() == 0:
            break
        remove_buttons.first.click()
        page.wait_for_timeout(80)
        removed += 1
    return removed


def _add_return_accessory(page: Any, accessory_tag: str) -> None:
    """Select and append a standard accessory row on the Asset Return page."""
    page.locator("#select-return-accessory").select_option(value=accessory_tag)
    page.wait_for_timeout(60)
    page.locator("#btn-add-return-accessory").click()
    page.wait_for_timeout(80)


def run_onboarding_issue(
    browser_session: Any,
    request_no: str,
    employee_id: str,
    computer_tag: str,
    computer_digits: str,
    monitor_tag: str | None = None,
    deskphone: str = "N",
    base_url: str = "http://127.0.0.1:8000",
    credentials: dict[str, str] | None = None,
    storage: AppStorage | None = None,
) -> ServiceResult:
    """Automate new hire equipment provisioning on the Asset Portal.

    Steps:
    1. Open `/portal/assets/issue`, authenticate if needed, select `New Hire Assignment` and load request.
    2. Remove default redundant rows (`ACC-DEFAULT-BAG`, `ACC-DEFAULT-LOCK`).
    3. Add primary computer (`computer_tag`) assigned to `employee_id`.
    4. If Desktop (`1` prefix), add monitor (`monitor_tag`) and standard USB Keyboard.
    5. Add standard accessories (Mouse, Headset, Ethernet Cable) and optional IP Desk Phone.
    6. Populate computer security fields (Hostname, Corporate-LAN, EDR Enabled).
    """
    logger.info(
        "開始執行新人入職配發自動化: req=%s, emp=%s, comp=%s, mon=%s, phone=%s",
        request_no,
        employee_id,
        computer_tag,
        monitor_tag,
        deskphone,
    )
    page = None
    store = storage or AppStorage()

    try:
        page = browser_session.new_page()
        page.goto(f"{base_url.rstrip('/')}/portal/assets/issue")
        login_portal_if_needed(page, credentials)

        page.locator("#select-issue-purpose").select_option(value="New Hire Assignment")
        page.locator("#input-request-no").fill(request_no)
        page.locator("#btn-load-purpose").click()
        page.wait_for_timeout(120)

        removed_count = _remove_default_redundant_rows(page)
        logger.info("已自動清除新人配發預設冗餘項目: %d 筆", removed_count)

        # Add primary computer
        add_asset_to_issue_table(
            page,
            employee_id=employee_id,
            asset_tag=computer_tag,
            usage_type="Assign",
        )
        page.wait_for_timeout(100)

        # Desktop requires monitor + keyboard
        if computer_digits.startswith("1"):
            if not monitor_tag:
                raise ValueError("桌機配發缺少螢幕資產編號")
            add_asset_to_issue_table(
                page,
                employee_id=None,
                asset_tag=monitor_tag,
                usage_type="Assign",
            )
            add_asset_to_issue_table(
                page,
                employee_id=None,
                asset_tag=KEYBOARD_ACCESSORY_TAG,
                usage_type="Assign",
            )

        # Standard accessories (Mouse, Headset, Ethernet cable)
        for acc_tag in STANDARD_ACCESSORY_TAGS:
            add_asset_to_issue_table(
                page,
                employee_id=None,
                asset_tag=acc_tag,
                usage_type="Assign",
            )

        if deskphone.upper() == "Y":
            add_asset_to_issue_table(
                page,
                employee_id=None,
                asset_tag=DESKPHONE_ACCESSORY_TAG,
                usage_type="Assign",
            )

        fill_computer_security_fields(page, [(computer_tag, computer_digits)])
        page.evaluate("window.scrollTo(0, document.body.scrollHeight);")

        store.record_usage(ACTION_ONBOARDING)

        return ServiceResult.manual_confirmation(
            message=(
                f"新人員工 {employee_id}（單號 {request_no}）設備與標準配件已填入 Asset Portal，"
                "請於 Edge 確認明細後送出。"
            ),
            data={
                "operation": ACTION_ONBOARDING,
                "request_no": request_no,
                "employee_id": employee_id,
                "computer_tag": computer_tag,
                "monitor_tag": monitor_tag,
                "deskphone": deskphone.upper(),
                "removed_redundant_rows": removed_count,
            },
        )
    except Exception as exc:
        logger.exception("新人入職配發自動化執行失敗")
        return ServiceResult.failed(
            message="新人入職配發自動處理發生錯誤，已保留目前瀏覽器分頁供手動接續處理。",
            error=str(exc),
            data={
                "operation": ACTION_ONBOARDING,
                "keep_browser_page": page is not None,
            },
        )


def run_offboarding_clearance(
    browser_session: Any,
    employee_id: str,
    device_type: str = "PC",
    deskphone: str = "N",
    base_url: str = "http://127.0.0.1:8000",
    credentials: dict[str, str] | None = None,
    storage: AppStorage | None = None,
    *,
    force_email_fallback: bool = False,
) -> ServiceResult:
    """Automate multi-system employee offboarding clearance and notification email draft.

    Steps:
    1. Query HR Offboarding system (`/portal/hr/offboarding`) to extract `#offboard-req-no`
       and `#offboard-checklist-table` outerHTML.
    2. Prepare Asset Return page (`/portal/assets/return`) with `Offboarding Return`,
       load employee's held assets, and append returned standard accessories.
    3. Query Telecom Extensions system (`/portal/telecom/extensions`) for extension reclamation.
    4. Compose notification HTML email via `compose_or_preview_email()` (or return fallback draft).
    """
    logger.info(
        "開始執行員工離職跨系統清點自動化: emp=%s, device=%s, phone=%s",
        employee_id,
        device_type,
        deskphone,
    )
    hr_page = None
    return_page = None
    telecom_page = None
    store = storage or AppStorage()
    creds = credentials or CredentialStore().load()
    clean_base = base_url.rstrip("/")

    try:
        # 1. HR Offboarding system: retrieve offboarding request no & checklist HTML table
        hr_page = browser_session.new_page()
        hr_page.goto(f"{clean_base}/portal/hr/offboarding")
        login_portal_if_needed(hr_page, creds)

        hr_page.locator("#input-offboard-emp-id").fill(employee_id)
        hr_page.locator("#btn-query-offboard").click()
        hr_page.locator("#offboard-result-card").wait_for(state="visible", timeout=5000)

        offboard_req_no = hr_page.locator("#offboard-req-no").inner_text().strip()
        if not offboard_req_no:
            raise RuntimeError("無法從 HR 離職系統取得離職單號")

        checklist_html = hr_page.locator("#offboard-checklist-table").evaluate("el => el.outerHTML")
        if not checklist_html:
            raise RuntimeError("無法從 HR 離職系統擷取交接清點表格 HTML")

        # 2. Asset Return page: load employee's assets & append returned accessories
        return_page = browser_session.new_page()
        return_page.goto(f"{clean_base}/portal/assets/return")
        login_portal_if_needed(return_page, creds)

        return_page.locator("#select-return-purpose").select_option(value="Offboarding Return")
        return_page.locator("#input-return-req-no").fill(offboard_req_no)
        select_searchable_employee(
            return_page,
            "#returner-select-trigger",
            "#returner-select-input",
            employee_id,
        )
        return_page.locator("#btn-load-return-list").click()
        return_page.wait_for_timeout(150)

        if device_type.upper() == "PC":
            _add_return_accessory(return_page, KEYBOARD_ACCESSORY_TAG)

        for acc_tag in STANDARD_ACCESSORY_TAGS:
            _add_return_accessory(return_page, acc_tag)

        if deskphone.upper() == "Y":
            _add_return_accessory(return_page, DESKPHONE_ACCESSORY_TAG)

        return_page.evaluate("window.scrollTo(0, document.body.scrollHeight);")

        # 3. Telecom Extensions system: look up employee's assigned extension
        telecom_page = browser_session.new_page()
        telecom_page.goto(f"{clean_base}/portal/telecom/extensions")
        telecom_page.locator("#input-telecom-emp-id").fill(employee_id)
        telecom_page.locator("#btn-telecom-search").click()
        telecom_page.wait_for_timeout(150)

        # 4. Compose IT offboarding permission revocation email (with graceful fallback)
        to_addr = "iam.security@enterprise.local"
        cc_addr = creds.get("email") or "it.servicedesk@enterprise.local"
        subject = f"[IT 離職清點與停權通知] 員工 {employee_id}（離職單號：{offboard_req_no}）"
        phone_text = "有繳回實體話機" if deskphone.upper() == "Y" else "無實體話機 (Softphone)"
        email_html = (
            f"<p>各位好，</p>"
            f"<p>離職人員 <strong>{employee_id}</strong>（離職單號：<strong>{offboard_req_no}</strong>）"
            f"已完成資訊設備繳回預檢（電腦類型：<b>{device_type.upper()}</b>，話機狀態：<b>{phone_text}</b>），"
            f"請協助依下表辦理帳號停權與權限回收，謝謝！</p>"
            f"{checklist_html}"
        )

        draft = compose_or_preview_email(
            to=to_addr,
            subject=subject,
            html_body=email_html,
            cc=cc_addr,
            force_fallback=force_email_fallback,
        )

        store.record_usage(ACTION_OFFBOARDING)

        fallback_note = (
            "（已自動開啟內建 HTML 郵件草稿預覽視窗）"
            if draft.used_fallback
            else "（已建立 Outlook 郵件草稿）"
        )
        return ServiceResult.manual_confirmation(
            message=(
                f"員工 {employee_id} 離職跨系統清點完成（單號：{offboard_req_no}）{fallback_note}，"
                "請於 Edge 確認資產歸還與分機狀態。"
            ),
            data={
                "operation": ACTION_OFFBOARDING,
                "employee_id": employee_id,
                "offboard_req_no": offboard_req_no,
                "device_type": device_type.upper(),
                "deskphone": deskphone.upper(),
                "draft_email": draft.to_dict(),
            },
        )
    except Exception as exc:
        logger.exception("員工離職跨系統清點自動化執行失敗")
        return ServiceResult.failed(
            message="員工離職跨系統清點發生錯誤，已保留瀏覽器分頁供手動接續處理。",
            error=str(exc),
            data={
                "operation": ACTION_OFFBOARDING,
                "keep_browser_page": any(
                    p is not None for p in (hr_page, return_page, telecom_page)
                ),
            },
        )

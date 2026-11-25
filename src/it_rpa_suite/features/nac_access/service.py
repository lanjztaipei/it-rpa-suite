"""Playwright workflow for cross-tab MAC lookup and dual-iframe + popup network policy unlock."""

from __future__ import annotations

from typing import Any

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from it_rpa_suite.adapters.credentials_dpapi import (
    CredentialStore,
    is_sandbox_mode,
    resolve_login_credentials,
)
from it_rpa_suite.adapters.logger import get_logger
from it_rpa_suite.adapters.result import (
    ServiceResult,
    ValidationResult,
    normalize_asset_tag,
    validate_asset_tag,
)
from it_rpa_suite.adapters.storage import AppStorage
from it_rpa_suite.features.asset_loan.service import login_portal_if_needed

logger = get_logger(__name__)


def normalize_mac(mac: str | None) -> str:
    """Normalize a MAC address string to uppercase trimmed text."""
    return (mac or "").strip().upper()


def preview_nac_unlock_mode(raw_asset_tag: str) -> tuple[str, str]:
    """Return (preview_label, color_role) based on asset tag prefix.

    Rules:
    - 3xxxxx (Laptop) -> Dual NIC (`雙網卡 (Wired + Wi-Fi MAC)`)
    - 1xxxxx (Desktop) -> Single NIC (`單網卡 (Wired MAC)`)
    """
    cleaned = (raw_asset_tag or "").strip()
    if not cleaned:
        return "等待輸入設備資產編號", "muted"

    _, digits = normalize_asset_tag(cleaned)
    if not digits:
        return "等待輸入完整資產編號", "muted"
    if not digits.isdigit():
        return "資產編號格式不正確", "error"
    if digits.startswith("3"):
        return "雙網卡 (Wired + Wi-Fi MAC)", "success"
    return "單網卡 (Wired MAC)", "info"


def validate_nac_asset_input(raw_asset_tag: str) -> ValidationResult:
    """Validate an asset tag for network access unlock."""
    return validate_asset_tag(raw_asset_tag)


def login_nac_if_needed(
    nac_page: Any,
    credentials: dict[str, str] | None = None,
) -> None:
    """Authenticate on the network console if the login gate is visible."""
    login_input = nac_page.locator("#nac-login-username")
    try:
        login_visible = bool(login_input.is_visible(timeout=800))
    except PlaywrightTimeoutError:
        login_visible = False

    if not login_visible:
        logger.debug("網管控制台已處於登入狀態")
        return

    username, password = resolve_login_credentials(
        credentials,
        account_keys=("nac_account", "portal_account"),
        password_keys=("nac_password", "portal_password"),
        default_account="nac.admin",
        default_password="Sandbox@2026",
        system_name="網管控制台",
    )
    login_input.fill(username)
    nac_page.locator("#nac-login-password").fill(password)
    nac_page.locator("#btn-nac-login").click()
    nac_page.locator("#nac-frames-container").wait_for(state="visible", timeout=5000)


def _get_required_frame(page: Any, frame_name: str) -> Any:
    """Locate a named iframe (`navFrame` or `mainFrame`) on the network console page."""
    frame = page.frame(name=frame_name)
    if frame is None:
        raise RuntimeError(f"網管控制台找不到頁框 {frame_name}")
    return frame


def unlock_mac_in_nac(
    mac_address: str,
    browser_session: Any,
    base_url: str = "http://127.0.0.1:8000",
    credentials: dict[str, str] | None = None,
) -> str:
    """Penetrate `navFrame` + `mainFrame` and intercept `expect_popup` to apply Repair Access."""
    normalized_mac = normalize_mac(mac_address)
    if not normalized_mac:
        raise RuntimeError("Asset Portal 資產明細中未提供網卡 MAC 位址")

    nac_page = browser_session.new_page(timeout=30000)
    nac_page.goto(f"{base_url.rstrip('/')}/network/console")
    nac_page.wait_for_load_state("load")

    login_nac_if_needed(nac_page, credentials)

    nac_page.wait_for_timeout(150)

    # 1. Penetrate navFrame to query the target MAC address
    nav_frame = _get_required_frame(nac_page, "navFrame")
    mac_input = nav_frame.locator("#input-mac-query")
    mac_input.wait_for(state="visible", timeout=10000)
    mac_input.fill(normalized_mac)
    nav_frame.locator("#btn-mac-search").click()
    nac_page.wait_for_timeout(250)

    # 2. Penetrate mainFrame and click policy edit link while intercepting popup
    main_frame = _get_required_frame(nac_page, "mainFrame")
    open_policy_btn = main_frame.locator("a.btn-open-policy").first
    open_policy_btn.wait_for(state="visible", timeout=10000)

    with nac_page.expect_popup(timeout=10000) as popup_info:
        open_policy_btn.click()

    popup_page = popup_info.value
    popup_page.set_default_timeout(30000)
    popup_page.wait_for_load_state("load")

    # 3. Select Repair Access radio and submit in the popup window
    popup_page.locator("#radio-access-repair").click()
    popup_page.locator("#btn-apply-policy").click()

    try:
        popup_page.wait_for_event("close", timeout=5000)
    except PlaywrightTimeoutError:
        logger.debug("權限設定彈出視窗未自動關閉，保留目前狀態")

    logger.info("網路維修放行已套用: mac=%s", normalized_mac)
    return normalized_mac


def run_nac_unlock(
    browser_session: Any,
    asset_tag: str,
    asset_digits: str,
    base_url: str = "http://127.0.0.1:8000",
    credentials: dict[str, str] | None = None,
    storage: AppStorage | None = None,
) -> ServiceResult:
    """End-to-end network unlock workflow:
    1. Search asset in Asset Portal (`/portal/assets/search`).
    2. Intercept `target="_blank"` detail tab (`expect_page`) to extract `mac_wired` and `mac_wifi`.
    3. Close transient detail tab (`browser_session.close_page`).
    4. Penetrate Network Console dual frames (`navFrame` + `mainFrame`) and `expect_popup` for each MAC.
    """
    logger.info("開始執行網路存取開通: tag=%s", asset_tag)
    search_page = None
    detail_page = None
    mac_wired = ""
    mac_wifi = ""
    processed_macs: list[str] = []
    store = storage or AppStorage()
    clean_base = base_url.rstrip("/")

    try:
        creds = (
            credentials
            if credentials is not None
            else CredentialStore().load(raise_on_error=not is_sandbox_mode())
        )
        # 1. Query Asset Portal and intercept detail tab
        search_page = browser_session.new_page()
        search_page.goto(f"{clean_base}/portal/assets/search")
        login_portal_if_needed(search_page, creds)

        search_page.locator("#input-search-tag").fill(asset_tag)
        search_page.locator("#btn-query-asset").click()

        asset_link = search_page.locator("#asset-link-0")
        asset_link.wait_for(state="visible", timeout=10000)

        with search_page.context.expect_page(timeout=10000) as new_page_info:
            asset_link.click()

        detail_page = new_page_info.value
        detail_page.wait_for_load_state()

        mac_wired = normalize_mac(detail_page.locator("#input-mac-wired").input_value())
        if not mac_wired:
            raise RuntimeError(f"資產 {asset_tag} 明細中找不到有線網卡 MAC (Wired MAC)")

        if asset_digits.startswith("3"):
            mac_wifi = normalize_mac(detail_page.locator("#input-mac-wifi").input_value())

        # 2. Close transient detail tab while keeping search page open
        browser_session.close_page(detail_page)
        detail_page = None

        # 3. Unlock Wired MAC in Network Console
        processed_wired = unlock_mac_in_nac(
            mac_wired,
            browser_session,
            base_url=clean_base,
            credentials=creds,
        )
        processed_macs.append(processed_wired)

        # 4. Unlock Wi-Fi MAC if Laptop (3 prefix)
        if asset_digits.startswith("3") and mac_wifi:
            processed_wifi = unlock_mac_in_nac(
                mac_wifi,
                browser_session,
                base_url=clean_base,
                credentials=creds,
            )
            processed_macs.append(processed_wifi)
            store.record_usage("nac_dual_mac")
            message = (
                f"筆電資產 {asset_tag} 雙網卡網路維修放行已完成！"
                f"（Wired: {mac_wired} / Wi-Fi: {mac_wifi}）"
            )
        else:
            store.record_usage("nac_single_mac")
            message = f"設備資產 {asset_tag} 單網卡網路維修放行已完成！（Wired: {mac_wired}）"

        return ServiceResult.success(
            message=message,
            data={
                "operation": "nac_unlock",
                "asset_tag": asset_tag,
                "asset_digits": asset_digits,
                "mac_wired": mac_wired,
                "mac_wifi": mac_wifi,
                "processed_macs": processed_macs,
            },
        )
    except Exception as exc:
        logger.exception("網路存取開通執行失敗")
        return ServiceResult.failed(
            message="網路存取開通發生錯誤，已保留瀏覽器分頁供手動確認。",
            error=str(exc),
            data={
                "operation": "nac_unlock",
                "asset_tag": asset_tag,
                "mac_wired": mac_wired,
                "mac_wifi": mac_wifi,
                "processed_macs": processed_macs,
                "keep_browser_page": any(p is not None for p in (search_page, detail_page)),
            },
        )

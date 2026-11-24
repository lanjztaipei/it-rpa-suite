"""Unit and integration tests for asset tag normalization, duplicate prevention, and loan operation detection."""

from __future__ import annotations

from pathlib import Path

from it_rpa_suite.adapters.browser_worker import AutomationWorker
from it_rpa_suite.adapters.result import (
    normalize_asset_tag,
    normalize_employee_id,
    validate_asset_tag,
    validate_asset_tag_lines,
    validate_employee_id,
)
from it_rpa_suite.adapters.storage import AppStorage
from it_rpa_suite.features.asset_loan.service import (
    OPERATION_PROJECT_LOAN,
    OPERATION_RETURN_LOOKUP,
    OPERATION_SHORT_LOAN,
    detect_loan_operation,
    run_project_loan,
    run_return_and_lookup,
    run_short_loan,
)
from it_rpa_suite.mock_server.server import MockEnterpriseServer


def test_normalize_and_validate_asset_tag() -> None:
    """Verify IT-xxxxxx normalization from shorthand and case-insensitive inputs."""
    assert normalize_asset_tag("100001") == ("IT-100001", "100001")
    assert normalize_asset_tag("it-300002") == ("IT-300002", "300002")
    assert normalize_asset_tag("IT200005") == ("IT-200005", "200005")

    res_ok = validate_asset_tag("300001")
    assert res_ok.valid is True
    assert res_ok.value == ("IT-300001", "300001")

    res_short = validate_asset_tag("12345")
    assert res_short.valid is False

    res_alpha = validate_asset_tag("IT-12345A")
    assert res_alpha.valid is False


def test_normalize_and_validate_employee_id() -> None:
    """Verify EMP prefix auto-completion from shorthand and case-insensitive employee IDs."""
    assert normalize_employee_id("101") == "EMP101"
    assert normalize_employee_id("emp102") == "EMP102"
    assert normalize_employee_id("EMP-103") == "EMP103"
    assert normalize_employee_id("EMP104") == "EMP104"

    res_shorthand = validate_employee_id("101")
    assert res_shorthand.valid is True
    assert res_shorthand.value == "EMP101"

    res_lower = validate_employee_id("emp104")
    assert res_lower.valid is True
    assert res_lower.value == "EMP104"

    res_hyphen = validate_employee_id("emp-102")
    assert res_hyphen.valid is True
    assert res_hyphen.value == "EMP102"

    assert validate_employee_id("").valid is False
    assert validate_employee_id("EMP").valid is False
    assert validate_employee_id("EMP-").valid is False


def test_validate_asset_tag_lines_duplicate_and_count_limits() -> None:
    """Verify multiline validation rejects duplicate asset tags and enforces count bounds."""
    dup_input = "100001\nIT-100001\n"
    dup_result = validate_asset_tag_lines(dup_input)
    assert dup_result.valid is False
    assert "重複輸入" in dup_result.message

    valid_multi = "100001\nit-300002\n"
    ok_result = validate_asset_tag_lines(valid_multi, minimum_count=1, maximum_count=2)
    assert ok_result.valid is True
    assert ok_result.value == [("IT-100001", "100001"), ("IT-300002", "300002")]

    too_many = validate_asset_tag_lines(valid_multi, minimum_count=1, maximum_count=1)
    assert too_many.valid is False


def test_detect_loan_operation_modes() -> None:
    """Verify automatic classification into short_loan, project_loan, and return_and_lookup."""
    single_asset = [("IT-300001", "300001")]
    two_assets = [("IT-100002", "100002"), ("IT-300002", "300002")]

    # 1. Alphanumeric or shorthand employee ID -> short_loan (auto-prefixed with EMP)
    short_res = detect_loan_operation(two_assets, "emp101")
    assert short_res.valid is True
    assert short_res.value["operation"] == OPERATION_SHORT_LOAN
    assert short_res.value["employee_id"] == "EMP101"

    short_no_prefix = detect_loan_operation(single_asset, "104")
    assert short_no_prefix.valid is True
    assert short_no_prefix.value["operation"] == OPERATION_SHORT_LOAN
    assert short_no_prefix.value["employee_id"] == "EMP104"

    # 2. 6-digit number or REQ-xxxxxx -> project_loan
    proj_res = detect_loan_operation(two_assets, "260101")
    assert proj_res.valid is True
    assert proj_res.value["operation"] == OPERATION_PROJECT_LOAN
    assert proj_res.value["request_no"] == "260101"

    proj_prefixed = detect_loan_operation(single_asset, "REQ-260105")
    assert proj_prefixed.valid is True
    assert proj_prefixed.value["operation"] == OPERATION_PROJECT_LOAN
    assert proj_prefixed.value["request_no"] == "260105"

    # 3. Blank borrower/request with 1 asset -> return_and_lookup
    ret_res = detect_loan_operation(single_asset, "")
    assert ret_res.valid is True
    assert ret_res.value["operation"] == OPERATION_RETURN_LOOKUP

    # 4. Blank borrower/request with multiple assets -> invalid for return
    ret_multi_err = detect_loan_operation(two_assets, "   ")
    assert ret_multi_err.valid is False
    assert "限單筆" in ret_multi_err.message


def test_lazy_worker_and_asset_loan_end_to_end(tmp_path: Path) -> None:
    """Verify lazy AutomationWorker initialization and end-to-end Asset Portal workflows."""
    storage = AppStorage(base_dir=tmp_path)
    server = MockEnterpriseServer(preferred_port=8010)
    base_url = server.start()
    worker = AutomationWorker(headless=True)

    try:
        worker.start()
        # Lazy check: Worker is running, but browser is NOT initialized before first task
        assert worker.is_running is True
        assert worker.is_browser_initialized is False

        # 1. Short Loan
        f1 = worker.submit(
            run_short_loan,
            [("IT-300002", "300002")],
            "EMP101",
            base_url,
            None,
            storage,
        )
        res1 = f1.result(timeout=30)
        assert res1.is_success is True
        assert worker.is_browser_initialized is True

        # 2. Project Loan
        f2 = worker.submit(
            run_project_loan,
            [("IT-100002", "100002"), ("IT-200002", "200002")],
            "260101",
            base_url,
            None,
            storage,
        )
        res2 = f2.result(timeout=30)
        assert res2.is_success is True

        # 3. Return & Custodian Lookup (expect_page on target="_blank" detail link)
        f3 = worker.submit(
            run_return_and_lookup,
            [("IT-300001", "300001")],
            base_url,
            None,
            storage,
        )
        res3 = f3.result(timeout=30)
        assert res3.is_success is True
        assert res3.data["owner_id"] == "EMP102"

        # Verify KPI stats were updated in SQLite
        stats = storage.get_usage_stats()
        # 1 * short_loan (1.5) + 2 * project_loan (4.0) + 1 * holder_lookup (1.5) + 1 * asset_return (2.0) = 9.0
        assert stats["this_month_saved_minutes"] == 9
    finally:
        worker.shutdown(wait=True, timeout=10)
        server.stop()


def test_onboarding_and_nac_validation_and_mailer_fallback() -> None:
    """Verify input validations, NAC mode preview, and Mailer graceful fallback."""
    from it_rpa_suite.adapters.mailer import (
        compose_or_preview_email,
        render_standalone_email_html,
    )
    from it_rpa_suite.features.nac_access.service import (
        preview_nac_unlock_mode,
    )
    from it_rpa_suite.features.onboarding.service import (
        validate_offboarding_inputs,
        validate_onboarding_inputs,
    )

    # 1. Desktop (1xxxxx) requires monitor asset tag
    missing_mon = validate_onboarding_inputs("260201", "EMP104", "100002", "", "Y")
    assert missing_mon.valid is False
    assert "螢幕" in missing_mon.message

    same_mon = validate_onboarding_inputs("260201", "EMP104", "100002", "IT-100002", "Y")
    assert same_mon.valid is False
    assert "不可相同" in same_mon.message

    ok_pc = validate_onboarding_inputs("260201", "EMP104", "100002", "200002", "Y")
    assert ok_pc.valid is True
    assert ok_pc.value["computer_tag"] == "IT-100002"
    assert ok_pc.value["monitor_tag"] == "IT-200002"

    # 2. Laptop (3xxxxx) does not require monitor tag, and shorthand employee ID is normalized
    ok_nb = validate_onboarding_inputs("REQ-260202", "101", "300002", "", "n")
    assert ok_nb.valid is True
    assert ok_nb.value["employee_id"] == "EMP101"
    assert ok_nb.value["computer_tag"] == "IT-300002"
    assert ok_nb.value["monitor_tag"] is None

    # 3. Offboarding validation (supports omitting EMP prefix)
    ok_quit = validate_offboarding_inputs("103", "nb", "y")
    assert ok_quit.valid is True
    assert ok_quit.value == {
        "employee_id": "EMP103",
        "device_type": "NB",
        "deskphone": "Y",
    }

    # 4. NAC preview modes
    assert preview_nac_unlock_mode("100001")[0] == "單網卡 (Wired MAC)"
    assert preview_nac_unlock_mode("IT-300001")[0] == "雙網卡 (Wired + Wi-Fi MAC)"

    # 5. Mailer graceful fallback
    draft = compose_or_preview_email(
        to="iam.security@enterprise.local",
        subject="Test Offboarding",
        html_body="<table><tr><td>EMP103</td></tr></table>",
        cc="alex.chen@enterprise.local",
        force_fallback=True,
    )
    assert draft.used_fallback is True
    rendered = render_standalone_email_html(draft)
    assert "iam.security@enterprise.local" in rendered
    assert "EMP103" in rendered


def test_onboarding_offboarding_and_nac_end_to_end(tmp_path: Path) -> None:
    """Verify end-to-end Playwright execution for Onboarding, Offboarding, and NAC unlock."""
    from it_rpa_suite.features.nac_access.service import run_nac_unlock
    from it_rpa_suite.features.onboarding.service import (
        run_offboarding_clearance,
        run_onboarding_issue,
    )

    storage = AppStorage(base_dir=tmp_path)
    server = MockEnterpriseServer(preferred_port=8012)
    base_url = server.start()
    worker = AutomationWorker(headless=True)

    try:
        worker.start()

        # 1. Onboarding Desktop PC + Monitor + Keyboard + Standard Accessories + DeskPhone
        f_onboard = worker.submit(
            run_onboarding_issue,
            "260201",
            "EMP104",
            "IT-100002",
            "100002",
            "IT-200002",
            "Y",
            base_url,
            None,
            storage,
        )
        res_onboard = f_onboard.result(timeout=30)
        assert res_onboard.is_success is True
        assert res_onboard.data["removed_redundant_rows"] == 2

        # 2. Offboarding multi-system clearance (HR -> Asset Return -> Telecom -> Mailer Fallback)
        f_offboard = worker.submit(
            run_offboarding_clearance,
            "EMP103",
            "NB",
            "N",
            base_url,
            None,
            storage,
            force_email_fallback=True,
        )
        res_offboard = f_offboard.result(timeout=30)
        assert res_offboard.is_success is True
        assert res_offboard.data["offboard_req_no"] == "260103"
        assert res_offboard.data["draft_email"]["used_fallback"] is True
        assert "offboard-checklist-table" in res_offboard.data["draft_email"]["html_body"]

        # 3. NAC Dual-MAC Unlock (Asset Detail expect_page -> navFrame/mainFrame -> expect_popup)
        f_nac = worker.submit(
            run_nac_unlock,
            "IT-300001",
            "300001",
            base_url,
            None,
            storage,
        )
        res_nac = f_nac.result(timeout=30)
        assert res_nac.is_success is True
        assert res_nac.data["processed_macs"] == [
            "00:1A:2B:30:00:01",
            "00:1A:2B:30:FF:01",
        ]
        assert server.state.nac_policies.get("00:1A:2B:30:00:01") == "Repair Access"
        assert server.state.nac_policies.get("00:1A:2B:30:FF:01") == "Repair Access"

        # Verify KPI stats: onboarding_issue (5.0) + offboarding_clearance (10.0) + nac_dual_mac (2.0) = 17.0
        stats = storage.get_usage_stats()
        assert stats["this_month_saved_minutes"] == 17
    finally:
        worker.shutdown(wait=True, timeout=10)
        server.stop()

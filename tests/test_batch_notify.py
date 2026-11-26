"""Unit, GUI, and E2E tests for batch notification (Excel download, openpyxl filter, BCC draft)."""

from __future__ import annotations

import tkinter as tk
from concurrent.futures import Future
from pathlib import Path
from typing import Any

import pytest

from it_rpa_suite.adapters.browser_worker import AutomationWorker
from it_rpa_suite.adapters.credentials_dpapi import CredentialStore
from it_rpa_suite.adapters.excel import parse_overdue_borrow_recipients, read_sheet_records
from it_rpa_suite.adapters.paths import AppPaths
from it_rpa_suite.adapters.storage import AppStorage
from it_rpa_suite.features.batch_notify.service import (
    FEATURE_KEY_OVERDUE_BORROW,
    NOTIFICATION_ACTIONS,
    SITE_OPTIONS,
    build_overdue_borrow_email,
    run_overdue_borrow_notify,
)
from it_rpa_suite.features.batch_notify.view import SITE_PLACEHOLDER, BatchNotifyView
from it_rpa_suite.mock_server.server import MockEnterpriseServer


@pytest.mark.unit
def test_sample_borrow_report_filtering_across_six_sites() -> None:
    """Verify pure-openpyxl filtering, deduplication, whitespace trimming, and boundary rules."""
    sample_path = AppPaths().sample_borrow_report_file
    assert sample_path.is_file()

    # 台中總部: irene.lin appears twice (deduped), DELAY_DAY=2/PROJECT_LOAN/DT excluded
    assert parse_overdue_borrow_recipients(sample_path, "台中總部") == [
        "irene.lin@enterprise.local",
        "brian.wang@enterprise.local",
    ]
    # 台北廠: DELAY_DAY=3 boundary excluded
    assert parse_overdue_borrow_recipients(sample_path, "台北廠") == [
        "mingde.chou@enterprise.local",
        "jiaying.huang@enterprise.local",
    ]
    # 新北廠: MON category excluded
    assert parse_overdue_borrow_recipients(sample_path, "新北廠") == [
        "junjie.liu@enterprise.local",
        "yijun.hsu@enterprise.local",
    ]
    # 桃園廠: PROJECT_LOAN excluded
    assert parse_overdue_borrow_recipients(sample_path, "桃園廠") == [
        "yawen.cheng@enterprise.local",
        "guanyu.hsieh@enterprise.local",
    ]
    # 台南廠: DELAY_DAY=3 boundary excluded -> 1 recipient
    assert parse_overdue_borrow_recipients(sample_path, "台南廠") == [
        "peishan.hung@enterprise.local",
    ]
    # 高雄廠: handles leading/trailing whitespace & lowercase category/purpose
    assert parse_overdue_borrow_recipients(sample_path, "高雄廠") == [
        "jiahao.su@enterprise.local",
        "wanting.liao@enterprise.local",
    ]


@pytest.mark.unit
def test_excel_adapter_missing_sheet_and_columns(tmp_path: Path) -> None:
    """Verify clear ValueError when worksheet or required headers are missing."""
    sample_path = AppPaths().sample_borrow_report_file
    with pytest.raises(ValueError, match="缺少必要工作表"):
        read_sheet_records(sample_path, sheet_name="NON_EXISTENT")

    with pytest.raises(ValueError, match="缺少必要欄位"):
        read_sheet_records(sample_path, sheet_name="Summary", required_columns={"OWNER_EMAIL"})

    with pytest.raises(FileNotFoundError):
        read_sheet_records(tmp_path / "missing.xlsx")


@pytest.mark.unit
def test_report_site_persistence_and_kpi_coefficient(tmp_path: Path) -> None:
    """Verify report_site persists atomically and overdue_borrow_notify contributes to KPI stats."""
    storage = AppStorage(base_dir=tmp_path)
    assert storage.get_report_site() == ""

    storage.set_report_site("台中總部")
    assert storage.get_report_site() == "台中總部"

    storage.record_usage(FEATURE_KEY_OVERDUE_BORROW)
    stats = storage.get_usage_stats()
    assert stats["this_month_saved_minutes"] == 5


@pytest.mark.unit
def test_build_overdue_borrow_email_uses_bcc_and_plain_text() -> None:
    """Verify overdue recipients are placed in BCC and body contains no HTML table."""
    subject, html_body, bcc = build_overdue_borrow_email(
        "台中總部",
        ["irene.lin@enterprise.local", "brian.wang@enterprise.local"],
    )
    assert "台中總部" in subject
    assert bcc == "irene.lin@enterprise.local; brian.wang@enterprise.local"
    assert "<table" not in html_body.lower()
    assert "台中總部 IT 服務中心" in html_body


@pytest.mark.gui
def test_batch_notify_view_site_persistence_and_action_buttons(
    tmp_path: Path,
    tk_root: tk.Tk,
) -> None:
    """Verify ModernDropdown 6-site persistence, action submission with real CredentialStore, and 1x3 button states."""
    paths = AppPaths(base_dir=tmp_path)
    paths.ensure_directories()
    storage = AppStorage(paths=paths)
    credential_store = CredentialStore(paths=paths)
    submitted_calls: list[tuple[Any, tuple[Any, ...]]] = []

    class _StubWorker:
        def submit(self, fn: Any, *args: Any) -> Future[Any]:
            submitted_calls.append((fn, args))
            fut: Future[Any] = Future()
            return fut

    class _StubApp:
        def __init__(self) -> None:
            self.paths = paths
            self.storage = storage
            self.credential_store = credential_store
            self.scale_factor = 1.0
            self.colors: dict[str, str] = {}
            self.automation_worker = _StubWorker()
            self.sandbox_base_url = "http://127.0.0.1:8000"
            self.closing = False

        def update_browser_status(self, *_args: Any, **_kwargs: Any) -> None:
            pass

        def refresh_usage_stats(self) -> None:
            pass

    app = _StubApp()
    view = BatchNotifyView(tk_root, app)

    # First-time load shows placeholder and 6-municipality ModernDropdown
    assert view.site_dropdown.options == SITE_OPTIONS
    assert "台中總部" in SITE_OPTIONS
    assert len(SITE_OPTIONS) == 6
    assert view.site_var.get() == SITE_PLACEHOLDER
    assert view.get_selected_site() == ""

    # Exactly 1x3 actions, only overdue_borrow enabled
    assert len(NOTIFICATION_ACTIONS) == 3
    assert len(view.action_buttons) == 3
    assert view.action_buttons["overdue_borrow"]["enabled"] is True
    assert view.action_buttons["endpoint_antivirus"]["enabled"] is False
    assert view.action_buttons["warranty_expiring"]["enabled"] is False

    # Clicking before picking a site sets inline error without opening any dialog or submitting
    view._trigger_action("overdue_borrow")
    assert "請先選擇所在廠區" in view.status_var.get()
    assert len(submitted_calls) == 0

    # Open floating dropdown popup, select a site, verify persistence and popup dismissal
    assert callable(view.site_dropdown._root)
    view.site_dropdown.event_generate("<Enter>")
    view.site_dropdown.event_generate("<Leave>")
    tk_root.update()
    view.site_dropdown.open_popup()
    assert view.site_dropdown.is_open is True
    view.site_dropdown._select_option("台中總部")
    assert view.site_dropdown.is_open is False
    assert storage.get_report_site() == "台中總部"
    assert view.status_var.get() == ""

    # Triggering the active action submits to automation_worker using real CredentialStore.load()
    view._trigger_action("overdue_borrow")
    assert len(submitted_calls) == 1
    fn, args = submitted_calls[0]
    assert fn is run_overdue_borrow_notify
    assert args[0] == "台中總部"
    assert args[1] == "http://127.0.0.1:8000"
    assert args[2] == {}
    assert args[3] is storage
    assert args[4] is paths

    view.destroy()
    reopened = BatchNotifyView(tk_root, app)
    assert reopened.site_var.get() == "台中總部"
    assert reopened.get_selected_site() == "台中總部"
    reopened.destroy()


@pytest.mark.e2e
def test_e2e_overdue_borrow_notify_download_parse_and_bcc(tmp_path: Path) -> None:
    """E2E: download sample_borrow_report.xlsx from Mock Server, parse with openpyxl, build BCC draft."""
    server = MockEnterpriseServer(preferred_port=0)
    base_url = server.start()
    paths = AppPaths(base_dir=tmp_path)
    paths.ensure_directories()
    storage = AppStorage(paths=paths)
    worker = AutomationWorker(headless=True)
    worker.start()

    try:
        future = worker.submit(
            run_overdue_borrow_notify,
            "台中總部",
            base_url,
            None,
            storage,
            paths,
            force_email_fallback=True,
        )
        result = future.result(timeout=45)
        assert result.is_success, f"Unexpected failure: {result.message} ({result.error})"

        data = result.data or {}
        assert data["site"] == "台中總部"
        assert data["recipients"] == [
            "irene.lin@enterprise.local",
            "brian.wang@enterprise.local",
        ]
        assert Path(data["report_path"]).is_file()

        draft = data["draft_email"]
        assert draft["to"] == ""
        assert draft["cc"] == ""
        assert draft["bcc"] == "irene.lin@enterprise.local; brian.wang@enterprise.local"
        assert "台中總部" in draft["subject"]
        assert "<table" not in draft["html_body"].lower()
        assert draft["used_fallback"] is True

        # KPI incremented in SQLite
        stats = storage.get_usage_stats()
        assert stats["this_month_saved_minutes"] == 5
    finally:
        worker.shutdown()
        server.stop()

"""Unit and E2E tests for standalone `tools/async_form_audit_demo.py` and mock form endpoints."""

from __future__ import annotations

import asyncio
import importlib.util
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import pytest
from openpyxl import load_workbook

from it_rpa_suite.adapters.paths import AppPaths
from it_rpa_suite.features.toolbox.view import find_tool_files
from it_rpa_suite.mock_server.pages import INITIAL_AUDIT_FORMS
from it_rpa_suite.mock_server.server import MockEnterpriseServer


def _load_tool_module() -> Any:
    """Import `tools/async_form_audit_demo.py` as a module for testing."""
    repo_root = Path(__file__).resolve().parents[1]
    tools_dir = repo_root / "tools"
    if str(tools_dir) not in sys.path:
        sys.path.insert(0, str(tools_dir))

    module_path = tools_dir / "async_form_audit_demo.py"
    spec = importlib.util.spec_from_file_location("async_form_audit_demo", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.unit
def test_sample_form_audit_excel_read_write_and_non_overwrite(tmp_path: Path) -> None:
    """Verify pure-openpyxl reading, non-overwriting output naming, and template preservation."""
    mod = _load_tool_module()
    sample_path = AppPaths().sample_form_audit_report_file
    assert sample_path.is_file()

    form_numbers = mod.load_form_numbers(sample_path)
    assert form_numbers == list(INITIAL_AUDIT_FORMS.keys())
    assert len(form_numbers) == 1000

    downloads_dir = tmp_path / "data" / "downloads"
    out_1 = mod.make_output_path(sample_path, downloads_dir)
    assert out_1 == downloads_dir / "sample_form_audit_report_updated.xlsx"

    mock_results = {
        "FRM-1001": {
            "request_type": "VPN 遠端存取",
            "review_comment": "測試備註 1001",
        },
        "FRM-2000": {
            "request_type": "ERP 模組授權",
            "review_comment": "測試備註 2000",
        },
    }
    updated = mod.write_results_to_excel(sample_path, out_1, mock_results)
    assert updated == 2
    assert out_1.is_file()

    # Second call must not overwrite existing output file
    out_2 = mod.make_output_path(sample_path, downloads_dir)
    assert out_2 == downloads_dir / "sample_form_audit_report_updated_2.xlsx"

    # Original sample file remains untouched (columns E & F still blank)
    orig_wb = load_workbook(sample_path, read_only=True)
    try:
        orig_ws = orig_wb.active
        assert orig_ws is not None
        assert orig_ws["E2"].value is None
        assert orig_ws["F2"].value is None
    finally:
        orig_wb.close()

    # Output workbook has updated columns E & F (first & 1000th data row)
    out_wb = load_workbook(out_1, read_only=True)
    try:
        out_ws = out_wb.active
        assert out_ws is not None
        assert out_ws["E2"].value == "VPN 遠端存取"
        assert out_ws["F2"].value == "測試備註 1001"
        assert out_ws["E1001"].value == "ERP 模組授權"
        assert out_ws["F1001"].value == "測試備註 2000"
    finally:
        out_wb.close()


@pytest.mark.unit
def test_toolbox_scanner_discovers_async_form_audit_demo() -> None:
    """Verify ToolboxView scanner automatically exposes the new standalone script."""
    tools_dir = AppPaths().tools_dir
    discovered_names = [item["name"] for item in find_tool_files(tools_dir)]
    assert "async_form_audit_demo.py" in discovered_names


@pytest.mark.unit
def test_mock_forms_frame_requires_auth_cookie(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify `/portal/forms/frame` enforces the shared `portal_auth=1` session cookie."""
    monkeypatch.setenv("IT_SUITE_MOCK_FORM_DELAY_MS", "0")
    sandbox = MockEnterpriseServer(preferred_port=18310)
    base_url = sandbox.start()
    try:
        frame_url = f"{base_url}/portal/forms/frame?id=FRM-1001"
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(frame_url, timeout=2.0)
        assert exc_info.value.code == 401

        req = urllib.request.Request(frame_url, headers={"Cookie": "portal_auth=1"})
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            body = resp.read().decode("utf-8")
            assert resp.status == 200
            assert "VPN 遠端存取" in body
            assert "review-comment" in body
    finally:
        sandbox.stop()


@pytest.mark.e2e
def test_async_form_audit_worker_pool_e2e(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify single login, shared BrowserContext, multi-tab worker pool, iframe extraction, and Excel output."""
    mod = _load_tool_module()
    monkeypatch.setenv("IT_SUITE_MOCK_FORM_DELAY_MS", "20")

    sample_path = AppPaths().sample_form_audit_report_file
    all_form_numbers = mod.load_form_numbers(sample_path)
    assert len(all_form_numbers) == 1000
    # Sample first 20 + last 4 forms (including FRM-2000) to keep CI fast while testing end-to-end
    target_forms = all_form_numbers[:20] + all_form_numbers[-4:]
    creds = {
        "portal_account": "it.admin",
        "portal_password": "Sandbox@2026",
    }

    sandbox = MockEnterpriseServer(preferred_port=18320)
    base_url = sandbox.start()
    try:
        results, elapsed = asyncio.run(
            mod.crawl_forms_concurrently(
                sandbox_url=base_url,
                form_numbers=target_forms,
                creds=creds,
                concurrency=5,
                headless=True,
            )
        )
    finally:
        sandbox.stop()

    assert len(results) == len(target_forms)
    assert elapsed > 0
    for form_no in target_forms:
        expected = INITIAL_AUDIT_FORMS[form_no]
        assert results[form_no]["request_type"] == expected["request_type"]
        assert results[form_no]["review_comment"] == expected["review_comment"]

    output_path = mod.make_output_path(sample_path, tmp_path / "downloads")
    updated = mod.write_results_to_excel(sample_path, output_path, results)
    assert updated == len(target_forms)
    assert output_path.is_file()

"""Unit tests for AppPaths, AppStorage (atomic settings & SQLite monthly KPIs), and CredentialStore."""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from it_rpa_suite.adapters.credentials_dpapi import (
    CredentialError,
    CredentialStore,
    decrypt_credentials,
    encrypt_credentials,
    is_sandbox_mode,
    resolve_login_credentials,
)
from it_rpa_suite.adapters.paths import get_app_paths
from it_rpa_suite.adapters.storage import AppStorage


def test_app_paths_ensure_directories_and_default_settings(tmp_path: Path) -> None:
    """Verify AppPaths creates data/ and tools/ and seeds default config and bundled tool files."""
    paths = get_app_paths(base_dir=tmp_path)

    assert paths.data_dir.is_dir()
    assert paths.logs_dir.is_dir()
    assert paths.tools_dir.is_dir()
    assert paths.settings_file.is_file()
    for filename in (
        "tool_sdk.py",
        "_tool_template.py",
        "ext_provision_demo.py",
        "async_form_audit_demo.py",
    ):
        assert (paths.tools_dir / filename).is_file()

    # Subsequent ensure_directories() calls must not overwrite existing user-modified tools
    custom_marker = "# user customized demo\n"
    (paths.tools_dir / "ext_provision_demo.py").write_text(custom_marker, encoding="utf-8")
    paths.ensure_directories()
    assert (paths.tools_dir / "ext_provision_demo.py").read_text(encoding="utf-8") == custom_marker

    settings_data = json.loads(paths.settings_file.read_text(encoding="utf-8"))
    assert settings_data["dark_mode"] is False
    assert settings_data["caller_id_enabled"] is True
    assert "coefficients" in settings_data
    assert settings_data["coefficients"]["onboarding_issue"] == 5.0


def test_app_paths_frozen_mode(tmp_path: Path, monkeypatch) -> None:
    """Verify AppPaths resolves sys.executable and sys._MEIPASS and seeds tools/ when frozen."""
    exe_dir = tmp_path / "dist" / "ITRPASuite"
    meipass_dir = exe_dir / "_internal"
    (meipass_dir / "assets").mkdir(parents=True)
    (meipass_dir / "tools").mkdir(parents=True)
    for filename in (
        "tool_sdk.py",
        "_tool_template.py",
        "ext_provision_demo.py",
        "async_form_audit_demo.py",
    ):
        (meipass_dir / "tools" / filename).write_text(f"# bundled {filename}\n", encoding="utf-8")
    fake_exe = exe_dir / "ITRPASuite.exe"
    fake_exe.write_text("", encoding="utf-8")

    monkeypatch.setattr("sys.frozen", True, raising=False)
    monkeypatch.setattr("sys.executable", str(fake_exe), raising=False)
    monkeypatch.setattr("sys._MEIPASS", str(meipass_dir), raising=False)

    paths = get_app_paths()
    assert paths.base_dir == exe_dir.resolve()
    assert paths.resource_dir == meipass_dir.resolve()
    assert paths.assets_dir == (meipass_dir / "assets").resolve()
    assert paths.bundled_tools_dir == (meipass_dir / "tools").resolve()
    for filename in (
        "tool_sdk.py",
        "_tool_template.py",
        "ext_provision_demo.py",
        "async_form_audit_demo.py",
    ):
        assert (exe_dir / "tools" / filename).read_text(
            encoding="utf-8"
        ) == f"# bundled {filename}\n"


def test_storage_atomic_settings_read_write(tmp_path: Path) -> None:
    """Verify settings.json atomic save and update operations."""
    storage = AppStorage(base_dir=tmp_path)

    assert storage.get_dark_mode() is False
    assert storage.get_caller_id_enabled() is True

    storage.set_dark_mode(True)
    storage.set_caller_id_enabled(False)

    reloaded = AppStorage(base_dir=tmp_path)
    assert reloaded.get_dark_mode() is True
    assert reloaded.get_caller_id_enabled() is False
    assert not storage.settings_path.with_suffix(".json.tmp").exists()


def test_storage_sqlite_cross_month_weighted_statistics(tmp_path: Path) -> None:
    """Verify SQLite feature_usage recording and cross-month weighted KPI calculation (including Jan -> Dec)."""
    storage = AppStorage(base_dir=tmp_path)

    # Custom coefficients to test weighted calculation
    settings = storage.load_settings()
    settings["coefficients"] = {
        "short_loan": 2.0,
        "onboarding_issue": 5.0,
        "offboarding_clearance": 10.0,
        "incident_ticket": 3.0,
        "routine_ticket": 4.0,
    }
    storage.save_settings(settings)

    # Record usage in December 2025 (last month relative to Jan 2026)
    dec_time = datetime(2025, 12, 15, 10, 30, 0)
    storage.record_usage("short_loan", count=3, timestamp=dec_time)  # 3 * 2 = 6 mins
    storage.record_usage(
        "incident_ticket", count=2, timestamp=dec_time
    )  # 2 * 3 = 6 mins (2 tickets)
    storage.record_usage("routine_ticket", count=1, timestamp=dec_time)  # 1 * 4 = 4 mins (1 ticket)

    # Record usage in January 2026 (this month)
    jan_time = datetime(2026, 1, 10, 14, 0, 0)
    storage.record_usage("onboarding_issue", count=2, timestamp=jan_time)  # 2 * 5 = 10 mins
    storage.record_usage("offboarding_clearance", count=1, timestamp=jan_time)  # 1 * 10 = 10 mins
    storage.record_usage(
        "incident_ticket", count=4, timestamp=jan_time
    )  # 4 * 3 = 12 mins (4 tickets)

    # Record usage in an older month (November 2025) that should not pollute Dec/Jan
    nov_time = datetime(2025, 11, 5, 9, 0, 0)
    storage.record_usage("offboarding_clearance", count=5, timestamp=nov_time)

    stats = storage.get_usage_stats(now=datetime(2026, 1, 20, 12, 0, 0))

    assert stats["last_month_saved_minutes"] == 16  # 6 + 6 + 4
    assert stats["this_month_saved_minutes"] == 32  # 10 + 10 + 12
    assert stats["last_month_tickets"] == 3  # 2 + 1
    assert stats["this_month_tickets"] == 4  # 4
    assert stats["上月總節省分鐘"] == 16
    assert stats["本月已節省分鐘"] == 32
    assert stats["上月總開單數"] == 3
    assert stats["本月已開單數"] == 4


def test_credential_store_dpapi_and_validation(tmp_path: Path) -> None:
    """Verify DPAPI encryption/decryption, file persistence, and input validation."""
    store = CredentialStore(base_dir=tmp_path)
    assert not store.exists()

    invalid_res = store.validate({"email": "bad-email", "portal_account": "u"})
    assert not invalid_res.valid

    sample_creds = {
        "email": "alex.chen@enterprise.local",
        "portal_account": "it.admin",
        "portal_password": "SecretPassword!123",
        "nac_account": "nac.admin",
        "nac_password": "NacPassword!456",
    }
    valid_res = store.validate(sample_creds)
    assert valid_res.valid

    cipher = encrypt_credentials(sample_creds)
    assert "SecretPassword!123" not in cipher
    assert decrypt_credentials(cipher) == sample_creds

    store.save(sample_creds)
    assert store.exists()
    assert store.load() == sample_creds


def test_credentials_fail_fast_outside_sandbox_mode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify non-sandbox mode rejects missing/corrupted credentials instead of falling back."""
    from it_rpa_suite.features.asset_loan.service import login_portal_if_needed
    from it_rpa_suite.features.nac_access.service import login_nac_if_needed

    monkeypatch.delenv("IT_SUITE_SANDBOX_MODE", raising=False)
    assert is_sandbox_mode() is True

    monkeypatch.setenv("IT_SUITE_SANDBOX_MODE", "false")
    assert is_sandbox_mode() is False

    # 1. Missing credentials must raise CredentialError instead of falling back
    store = CredentialStore(base_dir=tmp_path)
    with pytest.raises(CredentialError, match="禁止自動退回"):
        resolve_login_credentials(
            None,
            account_keys=("portal_account",),
            password_keys=("portal_password",),
            default_account="it.admin",
            default_password="Sandbox@2026",
            store=store,
            system_name="企業入口網",
        )

    # 2. Corrupted DPAPI ciphertext must raise CredentialError when raise_on_error=True
    store.file_path.parent.mkdir(parents=True, exist_ok=True)
    store.file_path.write_text("corrupted-not-valid-dpapi-blob!!!", encoding="utf-8")
    with pytest.raises(CredentialError):
        store.load(raise_on_error=True)

    # 3. Portal & NAC login helpers must propagate CredentialError (never swallow it)
    mock_page = MagicMock()
    mock_locator = MagicMock()
    mock_locator.is_visible.return_value = True
    mock_page.locator.return_value = mock_locator

    with pytest.raises(CredentialError):
        login_portal_if_needed(mock_page, credentials={})
    mock_locator.fill.assert_not_called()

    with pytest.raises(CredentialError):
        login_nac_if_needed(mock_page, credentials={})
    mock_locator.fill.assert_not_called()

    # 4. External tool_sdk.read_credentials() also fails fast outside sandbox mode
    tools_dir = Path(__file__).resolve().parents[1] / "tools"
    if str(tools_dir) not in sys.path:
        sys.path.insert(0, str(tools_dir))
    import tool_sdk

    empty_root = tmp_path / "empty_sdk_root"
    empty_root.mkdir()
    with pytest.raises(FileNotFoundError):
        tool_sdk.read_credentials(base_dir=empty_root)


def test_mock_server_port_fallback_when_occupied() -> None:
    """Verify MockEnterpriseServer skips ports occupied by SO_REUSEADDR / wildcard listeners on Windows."""
    import socket
    import urllib.request
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    from it_rpa_suite.mock_server.server import MockEnterpriseServer

    base_port = 18120
    # 1. Occupy base_port on 127.0.0.1 using standard ThreadingHTTPServer (which sets SO_REUSEADDR=1)
    dummy_http = ThreadingHTTPServer(("127.0.0.1", base_port), BaseHTTPRequestHandler)
    # 2. Occupy base_port + 1 on wildcard 0.0.0.0 with SO_REUSEADDR=1
    wildcard_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    wildcard_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    wildcard_sock.bind(("0.0.0.0", base_port + 1))
    wildcard_sock.listen(1)

    sandbox = MockEnterpriseServer(preferred_port=base_port)
    try:
        started_url = sandbox.start()
        assert sandbox.port not in (base_port, base_port + 1)
        assert sandbox.port == base_port + 2
        assert started_url == f"http://127.0.0.1:{base_port + 2}"

        with urllib.request.urlopen(f"{started_url}/api/directory", timeout=2.0) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
            assert payload.get("ok") is True
            assert isinstance(payload.get("results"), list)
    finally:
        sandbox.stop()
        wildcard_sock.close()
        dummy_http.server_close()


def test_slow_mo_env_resolution_for_worker_and_tool_sdk(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify `IT_SUITE_SLOW_MO` parsing, invalid fallback, and BrowserSession propagation."""
    from it_rpa_suite.adapters.browser_worker import (
        AutomationWorker,
        BrowserSession,
        get_slow_mo_ms,
    )

    tools_dir = Path(__file__).resolve().parents[1] / "tools"
    if str(tools_dir) not in sys.path:
        sys.path.insert(0, str(tools_dir))
    import tool_sdk

    monkeypatch.delenv("IT_SUITE_SLOW_MO", raising=False)
    assert get_slow_mo_ms() == 0.0
    assert tool_sdk.get_slow_mo_ms() == 0.0
    assert BrowserSession(headless=True).slow_mo == 0.0

    monkeypatch.setenv("IT_SUITE_SLOW_MO", "450")
    assert get_slow_mo_ms() == 450.0
    assert tool_sdk.get_slow_mo_ms() == 450.0
    assert BrowserSession(headless=True).slow_mo == 450.0
    assert BrowserSession(headless=True, slow_mo=0).slow_mo == 0.0
    assert AutomationWorker(headless=True, slow_mo=600).slow_mo == 600.0

    for bad_value in ("-100", "not-a-number"):
        monkeypatch.setenv("IT_SUITE_SLOW_MO", bad_value)
        assert get_slow_mo_ms() == 0.0
        assert tool_sdk.get_slow_mo_ms() == 0.0

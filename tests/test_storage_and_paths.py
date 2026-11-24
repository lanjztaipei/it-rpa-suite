"""Unit tests for AppPaths, AppStorage (atomic settings & SQLite monthly KPIs), and CredentialStore."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from it_rpa_suite.adapters.credentials_dpapi import (
    CredentialStore,
    decrypt_credentials,
    encrypt_credentials,
)
from it_rpa_suite.adapters.paths import AppPaths, get_app_paths
from it_rpa_suite.adapters.storage import AppStorage


def test_app_paths_ensure_directories_and_default_settings(tmp_path: Path) -> None:
    """Verify AppPaths creates data/ and data/logs/ and seeds default_settings.json."""
    paths = get_app_paths(base_dir=tmp_path)

    assert paths.data_dir.is_dir()
    assert paths.logs_dir.is_dir()
    assert paths.settings_file.is_file()

    settings_data = json.loads(paths.settings_file.read_text(encoding="utf-8"))
    assert settings_data["dark_mode"] is False
    assert settings_data["caller_id_enabled"] is True
    assert "coefficients" in settings_data
    assert settings_data["coefficients"]["onboarding_issue"] == 5.0


def test_app_paths_frozen_mode(tmp_path: Path, monkeypatch) -> None:
    """Verify AppPaths resolves sys.executable and sys._MEIPASS when frozen."""
    exe_dir = tmp_path / "dist" / "ITRPASuite"
    meipass_dir = exe_dir / "_internal"
    (meipass_dir / "assets").mkdir(parents=True)
    fake_exe = exe_dir / "ITRPASuite.exe"
    fake_exe.write_text("", encoding="utf-8")

    monkeypatch.setattr("sys.frozen", True, raising=False)
    monkeypatch.setattr("sys.executable", str(fake_exe), raising=False)
    monkeypatch.setattr("sys._MEIPASS", str(meipass_dir), raising=False)

    paths = AppPaths()
    assert paths.base_dir == exe_dir.resolve()
    assert paths.resource_dir == meipass_dir.resolve()
    assert paths.assets_dir == (meipass_dir / "assets").resolve()


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

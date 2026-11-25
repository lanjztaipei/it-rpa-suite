"""Unit tests for in-app non-closing update availability checking and MainWindow integration."""

from __future__ import annotations

import os
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from it_rpa_suite.adapters.paths import AppPaths
from it_rpa_suite.adapters.update_checker import (
    UpdateCheckResult,
    UpdateCheckStatus,
    check_for_updates,
    format_timestamp,
)
from it_rpa_suite.app import main_window as main_window_module
from it_rpa_suite.app.main_window import MainWindow


def _write_dummy_zip(path: Path, mtime: float) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("ITRPASuite.exe", "dummy")
    os.utime(path, (mtime, mtime))
    return path


def test_check_for_updates_all_states(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify check_for_updates accurately classifies all update states without side effects."""
    monkeypatch.delenv("IT_SUITE_UPDATE_ZIP", raising=False)
    app_root = tmp_path / "ITRPASuite"
    paths = AppPaths(base_dir=app_root)
    paths.data_dir.mkdir(parents=True, exist_ok=True)
    expected_zip = (tmp_path / "released" / "ITRPASuite.zip").resolve()

    # 1. Source ZIP missing
    res = check_for_updates(paths)
    assert res.status == UpdateCheckStatus.SOURCE_NOT_FOUND
    assert res.source_zip == expected_zip
    assert res.needs_update is False

    # 2. Source ZIP exists, version.txt missing
    _write_dummy_zip(expected_zip, mtime=2000.0)
    res = check_for_updates(paths)
    assert res.status == UpdateCheckStatus.VERSION_MISSING
    assert res.needs_update is True
    assert res.source_timestamp == pytest.approx(2000.0)

    # 3. Installed version >= source mtime -> UP_TO_DATE
    paths.version_file.write_text("2000.0", encoding="utf-8")
    res = check_for_updates(paths)
    assert res.status == UpdateCheckStatus.UP_TO_DATE
    assert res.needs_update is False
    assert res.installed_timestamp == pytest.approx(2000.0)

    # 4. Installed version < source mtime -> UPDATE_AVAILABLE
    paths.version_file.write_text("1500.0", encoding="utf-8")
    res = check_for_updates(paths)
    assert res.status == UpdateCheckStatus.UPDATE_AVAILABLE
    assert res.needs_update is True
    assert res.installed_timestamp == pytest.approx(1500.0)
    assert res.source_timestamp == pytest.approx(2000.0)

    # 5. Corrupted version.txt -> ERROR
    paths.version_file.write_text("not-a-float", encoding="utf-8")
    res = check_for_updates(paths)
    assert res.status == UpdateCheckStatus.ERROR
    assert res.needs_update is False
    assert res.error_message and "版本紀錄格式錯誤" in res.error_message

    # 6. Pending Stage 3 marker -> UPDATE_PENDING
    paths.updating_version_file.write_text("2000.0", encoding="utf-8")
    res = check_for_updates(paths)
    assert res.status == UpdateCheckStatus.UPDATE_PENDING
    assert res.needs_update is True


def test_check_for_updates_respects_env_and_settings_priority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify IT_SUITE_UPDATE_ZIP overrides configured_zip from settings.json."""
    app_root = tmp_path / "ITRPASuite"
    paths = AppPaths(base_dir=app_root)
    paths.data_dir.mkdir(parents=True, exist_ok=True)
    paths.version_file.write_text("1000.0", encoding="utf-8")

    cfg_zip = _write_dummy_zip(tmp_path / "custom" / "cfg.zip", mtime=1000.0)
    env_zip = _write_dummy_zip(tmp_path / "env_release" / "env.zip", mtime=2500.0)

    monkeypatch.delenv("IT_SUITE_UPDATE_ZIP", raising=False)
    res_cfg = check_for_updates(paths, configured_zip=str(cfg_zip))
    assert res_cfg.source_zip == cfg_zip.resolve()
    assert res_cfg.status == UpdateCheckStatus.UP_TO_DATE

    monkeypatch.setenv("IT_SUITE_UPDATE_ZIP", str(env_zip))
    res_env = check_for_updates(paths, configured_zip=str(cfg_zip))
    assert res_env.source_zip == env_zip.resolve()
    assert res_env.status == UpdateCheckStatus.UPDATE_AVAILABLE


def test_format_timestamp_handles_none_and_epoch() -> None:
    assert format_timestamp(None) == "未知"
    formatted = format_timestamp(1700000000.0)
    assert len(formatted) == 19
    assert formatted[4] == "-" and formatted[13] == ":"


def _make_stub_window(tmp_path: Path) -> SimpleNamespace:
    paths = AppPaths(base_dir=tmp_path)
    (tmp_path / "_internal").mkdir(parents=True, exist_ok=True)
    (tmp_path / "_internal" / "updater.exe").write_text("exe", encoding="utf-8")

    stub = SimpleNamespace(
        root=MagicMock(),
        paths=paths,
        closing=False,
        _checking_update=True,
        scale_factor=1.0,
        update_browser_status=MagicMock(),
        request_close=MagicMock(),
        _launch_updater=MagicMock(),
    )
    return stub


def test_handle_update_check_up_to_date_does_not_close_app(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When already up to date, MainWindow notifies user without launching updater or closing."""
    stub = _make_stub_window(tmp_path)
    info_mock = MagicMock()
    confirm_mock = MagicMock()
    monkeypatch.setattr(main_window_module.messagebox, "showinfo", info_mock)
    monkeypatch.setattr(main_window_module, "show_confirm_dialog", confirm_mock)

    result = UpdateCheckResult(
        status=UpdateCheckStatus.UP_TO_DATE,
        source_zip=tmp_path / "released" / "ITRPASuite.zip",
        installed_timestamp=2000.0,
        source_timestamp=2000.0,
    )
    MainWindow._handle_update_check_result(stub, result)  # type: ignore[arg-type]

    assert stub._checking_update is False
    stub.update_browser_status.assert_called_once()
    info_mock.assert_called_once()
    confirm_mock.assert_not_called()
    stub._launch_updater.assert_not_called()
    stub.request_close.assert_not_called()


def test_handle_update_check_available_cancel_keeps_app_open(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When update is available and user clicks cancel, app remains open and updater is not launched."""
    stub = _make_stub_window(tmp_path)
    confirm_mock = MagicMock(return_value=False)
    monkeypatch.setattr(main_window_module, "show_confirm_dialog", confirm_mock)

    result = UpdateCheckResult(
        status=UpdateCheckStatus.UPDATE_AVAILABLE,
        source_zip=tmp_path / "released" / "ITRPASuite.zip",
        installed_timestamp=1000.0,
        source_timestamp=2000.0,
    )
    MainWindow._handle_update_check_result(stub, result)  # type: ignore[arg-type]

    confirm_mock.assert_called_once()
    stub._launch_updater.assert_not_called()
    stub.request_close.assert_not_called()


def test_handle_update_check_available_confirm_launches_updater(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When update is available and user confirms, updater is launched with resolved ZIP."""
    stub = _make_stub_window(tmp_path)
    confirm_mock = MagicMock(return_value=True)
    monkeypatch.setattr(main_window_module, "show_confirm_dialog", confirm_mock)

    source_zip = tmp_path / "released" / "ITRPASuite.zip"
    result = UpdateCheckResult(
        status=UpdateCheckStatus.UPDATE_AVAILABLE,
        source_zip=source_zip,
        installed_timestamp=1000.0,
        source_timestamp=2000.0,
    )
    MainWindow._handle_update_check_result(stub, result)  # type: ignore[arg-type]

    confirm_mock.assert_called_once()
    stub._launch_updater.assert_called_once_with(
        source_zip,
        stub.paths.base_dir / "_internal" / "updater.exe",
        stub.paths.tools_dir / "updater" / "updater.py",
    )

"""Unit tests for the three-stage Updater state machine, Zip Slip security, and Toolbox scanner."""

from __future__ import annotations

import os
import sys
import zipfile
from pathlib import Path

import pytest

# Ensure `tools/` is importable for testing updater, tool_sdk, and ext_provision_demo
_REPO_ROOT = Path(__file__).resolve().parents[1]
_TOOLS_DIR = _REPO_ROOT / "tools"
_UPDATER_DIR = _TOOLS_DIR / "updater"
for _p in (_TOOLS_DIR, _UPDATER_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from ext_provision_demo import is_last_two_digits_repeated  # noqa: E402
from it_rpa_suite.features.toolbox.view import find_tool_files  # noqa: E402
from updater import (  # noqa: E402
    MAIN_EXECUTABLE_NAME,
    UpdateError,
    UpdateHandoff,
    UpdatePaths,
    Updater,
    UpdateStage,
    resolve_expected_sha256_arg,
    resolve_source_zip_arg,
)


def _make_paths(
    app_root: Path,
    source_zip: Path,
    running_from_internal: bool = True,
) -> UpdatePaths:
    internal_dir = app_root / "_internal"
    executable = internal_dir / "updater.exe" if running_from_internal else app_root / "updater.exe"
    return UpdatePaths.from_runtime(
        source_zip=source_zip,
        executable_path=executable,
    )


def _create_release_zip(zip_path: Path, entries: dict[str, str]) -> Path:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w") as zf:
        for arcname, content in entries.items():
            zf.writestr(arcname, content)
    return zip_path


# ------------------------------------------------------------------
# 1. Zip Slip Security Tests
# ------------------------------------------------------------------
@pytest.mark.parametrize(
    "malicious_entry",
    [
        "../../evil.exe",
        "../outside.txt",
        "subdir/../../../escape.dll",
        "..\\..\\windows_traversal.bat",
        "/etc/passwd",
    ],
)
def test_extract_zip_safely_blocks_zip_slip_traversal(
    tmp_path: Path,
    malicious_entry: str,
) -> None:
    """Verify `_extract_zip_safely` rejects ZIP archives containing path traversal entries."""
    zip_path = _create_release_zip(
        tmp_path / "malicious.zip",
        {
            "ITRPASuite.exe": "binary",
            malicious_entry: "malicious-payload",
        },
    )
    dest_dir = tmp_path / "app_root"
    dest_dir.mkdir(parents=True, exist_ok=True)

    with pytest.raises(UpdateError, match="不安全"):
        Updater._extract_zip_safely(zip_path, dest_dir)

    # Confirm nothing escaped into parent tmp_path
    assert not (tmp_path / "evil.exe").exists()
    assert not (tmp_path / "outside.txt").exists()
    assert not (tmp_path / "escape.dll").exists()
    assert not (tmp_path / "windows_traversal.bat").exists()


def test_extract_zip_safely_allows_valid_top_level_release(tmp_path: Path) -> None:
    """Verify valid release ZIP extracts cleanly into destination."""
    zip_path = _create_release_zip(
        tmp_path / "released" / "ITRPASuite.zip",
        {
            MAIN_EXECUTABLE_NAME: "exe-v2",
            "_internal/updater.exe": "updater-v2",
            "_internal/tools/tool_sdk.py": "# sdk-v2\n",
        },
    )
    dest_dir = tmp_path / "app"
    dest_dir.mkdir(parents=True, exist_ok=True)

    Updater._extract_zip_safely(zip_path, dest_dir)

    assert (dest_dir / MAIN_EXECUTABLE_NAME).read_text(encoding="utf-8") == "exe-v2"
    assert (dest_dir / "_internal" / "updater.exe").read_text(encoding="utf-8") == "updater-v2"
    assert (dest_dir / "_internal" / "tools" / "tool_sdk.py").read_text(
        encoding="utf-8"
    ) == "# sdk-v2\n"


# ------------------------------------------------------------------
# 2. Atomic Write & Path Configuration Tests
# ------------------------------------------------------------------
def test_write_text_atomic_creates_file_without_leftover_tmp(tmp_path: Path) -> None:
    """Verify `_write_text_atomic` writes content atomically and leaves no `.tmp` file."""
    target = tmp_path / "data" / "version.txt"
    Updater._write_text_atomic(target, "1700000000.5")

    assert target.is_file()
    assert target.read_text(encoding="utf-8") == "1700000000.5"
    assert not target.with_suffix(".txt.tmp").exists()


def test_update_paths_defaults_to_relative_released_and_data_dir(tmp_path: Path) -> None:
    """Verify UpdatePaths resolves default `./released/ITRPASuite.zip` and `data/` markers."""
    internal_exe = tmp_path / "_internal" / "updater.exe"
    paths = UpdatePaths.from_runtime(executable_path=internal_exe)

    assert paths.running_from_internal is True
    assert paths.app_root == tmp_path.resolve()
    assert paths.source_zip == (tmp_path / "released" / "ITRPASuite.zip").resolve()
    assert paths.data_dir == (tmp_path / "data").resolve()
    assert paths.version_file == (tmp_path / "data" / "version.txt").resolve()
    assert paths.updating_version_file == (tmp_path / "data" / "updating_version.txt").resolve()
    assert paths.application_executable == (tmp_path / MAIN_EXECUTABLE_NAME).resolve()
    assert paths.tool_sdk_source == (tmp_path / "_internal" / "tools" / "tool_sdk.py").resolve()
    assert paths.tool_sdk_target == (tmp_path / "tools" / "tool_sdk.py").resolve()


def test_update_paths_single_canonical_project_root_released_when_inside_app_folder(
    tmp_path: Path,
) -> None:
    """Verify running inside `ITRPASuite/` strictly resolves `<project_root>/released/ITRPASuite.zip`."""
    app_root = tmp_path / "ITRPASuite"
    internal_exe = app_root / "_internal" / "updater.exe"

    paths = UpdatePaths.from_runtime(executable_path=internal_exe)

    assert paths.running_from_internal is True
    assert paths.app_root == app_root.resolve()
    # Even before the file exists, the single canonical path points to project_root/released/ITRPASuite.zip
    assert paths.source_zip == (tmp_path / "released" / "ITRPASuite.zip").resolve()


def test_update_paths_supports_settings_json_override(tmp_path: Path) -> None:
    """Verify `data/settings.json` can override `update_source_zip` without recompiling."""
    app_root = tmp_path / "ITRPASuite"
    data_dir = app_root / "data"
    data_dir.mkdir(parents=True)
    (data_dir / "settings.json").write_text(
        '{"update_source_zip": "custom_releases/my_build.zip"}',
        encoding="utf-8",
    )

    paths = UpdatePaths.from_runtime(executable_path=app_root / "_internal" / "updater.exe")
    assert paths.source_zip == (tmp_path / "custom_releases" / "my_build.zip").resolve()


def test_update_paths_dev_tools_updater_recognized_as_internal(tmp_path: Path) -> None:
    """Verify running `tools/updater/updater.py` treats itself as internal for Stage 1 handoff."""
    dev_script = tmp_path / "tools" / "updater" / "updater.py"
    paths = UpdatePaths.from_runtime(executable_path=dev_script)

    assert paths.running_from_internal is True
    assert paths.app_root == tmp_path.resolve()
    assert paths.safe_updater == (tmp_path / "updater.py").resolve()


def test_resolve_source_zip_arg_supports_cli_and_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify `--source-zip` CLI flag and `IT_SUITE_UPDATE_ZIP` env var overrides."""
    cli_res = resolve_source_zip_arg(["--source-zip", "custom/release.zip"])
    assert cli_res == Path("custom/release.zip")

    monkeypatch.setenv("IT_SUITE_UPDATE_ZIP", "env/ITRPASuite.zip")
    env_res = resolve_source_zip_arg([])
    assert env_res == Path("env/ITRPASuite.zip")


# ------------------------------------------------------------------
# 3. State Machine Stage Detection & Full 3-Stage Flow Tests
# ------------------------------------------------------------------
def test_check_stage_transitions_and_validation(tmp_path: Path) -> None:
    """Verify `check_stage` accurately determines all 4 stages and catches invalid states."""
    app_root = tmp_path / "suite"
    source_zip = app_root / "released" / "ITRPASuite.zip"

    # 1) Missing source_zip -> UpdateError
    paths_internal = _make_paths(app_root, source_zip, running_from_internal=True)
    updater_internal = Updater(paths_internal, sleep_fn=lambda _: None)
    with pytest.raises(UpdateError, match="更新來源 ZIP 不存在"):
        updater_internal.check_stage()

    # Create source_zip with known mtime
    _create_release_zip(source_zip, {MAIN_EXECUTABLE_NAME: "v2"})
    os.utime(source_zip, (2000.0, 2000.0))

    # 2) Missing version.txt -> NEEDED when in _internal, STARTED when in safe zone
    assert updater_internal.check_stage() == UpdateStage.NEEDED
    paths_safe = _make_paths(app_root, source_zip, running_from_internal=False)
    updater_safe = Updater(paths_safe, sleep_fn=lambda _: None)
    assert updater_safe.check_stage() == UpdateStage.STARTED

    # 3) Installed version >= source mtime -> NOT_NEEDED
    Updater._write_text_atomic(paths_internal.version_file, "2000.0")
    assert updater_internal.check_stage() == UpdateStage.NOT_NEEDED

    # 4) Installed version < source mtime -> NEEDED (internal) / STARTED (safe zone)
    Updater._write_text_atomic(paths_internal.version_file, "1500.0")
    assert updater_internal.check_stage() == UpdateStage.NEEDED
    assert updater_safe.check_stage() == UpdateStage.STARTED

    # 5) Presence of updating_version.txt -> IN_PROGRESS (internal) / Error (safe zone)
    Updater._write_text_atomic(paths_internal.updating_version_file, "2000.0")
    assert updater_internal.check_stage() == UpdateStage.IN_PROGRESS
    with pytest.raises(UpdateError, match="不在 _internal 中"):
        updater_safe.check_stage()


def test_full_three_stage_self_update_lifecycle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Simulate a complete Stage 1 -> Stage 2 -> Stage 3 update lifecycle end-to-end."""
    app_root = tmp_path / "app"
    internal_dir = app_root / "_internal"
    internal_dir.mkdir(parents=True)

    # Seed old installation (v1)
    (app_root / MAIN_EXECUTABLE_NAME).write_text("old-exe-v1", encoding="utf-8")
    old_updater = internal_dir / "updater.exe"
    old_updater.write_text("updater-v1", encoding="utf-8")
    (internal_dir / "obsolete.dll").write_text("obsolete", encoding="utf-8")
    Updater._write_text_atomic(app_root / "data" / "version.txt", "1000.0")

    # Seed new release package (v2) in ./released/ITRPASuite.zip
    source_zip = _create_release_zip(
        app_root / "released" / "ITRPASuite.zip",
        {
            MAIN_EXECUTABLE_NAME: "new-exe-v2",
            "_internal/updater.exe": "updater-v2",
            "_internal/tools/tool_sdk.py": "# Updated Tool SDK v2\n",
        },
    )
    os.utime(source_zip, (3000.0, 3000.0))

    launched_processes: list[tuple[Path, Path]] = []
    monkeypatch.setattr(
        Updater,
        "_launch",
        lambda _self, exe, cwd: launched_processes.append((Path(exe), Path(cwd))),
    )

    # --- Stage 1: Running from `_internal/updater.exe` (NEEDED) ---
    stage1_paths = _make_paths(app_root, source_zip, running_from_internal=True)
    stage1_updater = Updater(stage1_paths, sleep_fn=lambda _: None)
    assert stage1_updater.check_stage() == UpdateStage.NEEDED

    with pytest.raises(UpdateHandoff):
        stage1_updater.run()

    assert stage1_paths.safe_updater.is_file()
    assert launched_processes[-1] == (stage1_paths.safe_updater, app_root)

    # --- Stage 2: Running from safe zone `app_root/updater.exe` (STARTED) ---
    stage2_paths = _make_paths(app_root, source_zip, running_from_internal=False)
    stage2_updater = Updater(stage2_paths, sleep_fn=lambda _: None)
    assert stage2_updater.check_stage() == UpdateStage.STARTED

    with pytest.raises(UpdateHandoff):
        stage2_updater.run()

    assert not (internal_dir / "obsolete.dll").exists()
    assert (app_root / MAIN_EXECUTABLE_NAME).read_text(encoding="utf-8") == "new-exe-v2"
    assert stage2_paths.updating_version_file.is_file()
    assert not stage2_paths.local_zip.exists()
    assert launched_processes[-1] == (stage2_paths.internal_updater, internal_dir)

    # --- Stage 3: Running from new `_internal/updater.exe` (IN_PROGRESS) ---
    stage3_paths = _make_paths(app_root, source_zip, running_from_internal=True)
    stage3_updater = Updater(stage3_paths, sleep_fn=lambda _: None)
    assert stage3_updater.check_stage() == UpdateStage.IN_PROGRESS

    completed_stage = stage3_updater.run()
    assert completed_stage == UpdateStage.IN_PROGRESS

    assert not stage3_paths.updating_version_file.exists()
    assert not stage3_paths.safe_updater.exists()
    assert stage3_paths.version_file.is_file()
    assert float(stage3_paths.version_file.read_text(encoding="utf-8")) == pytest.approx(3000.0)
    assert (app_root / "tools" / "tool_sdk.py").read_text(
        encoding="utf-8"
    ) == "# Updated Tool SDK v2\n"

    # Subsequent check should report NOT_NEEDED and backups must be cleaned up
    assert stage3_updater.check_stage() == UpdateStage.NOT_NEEDED
    assert not stage3_paths.backup_internal_dir.exists()
    assert not stage3_paths.backup_executable.exists()
    assert not stage3_paths.staging_dir.exists()


def test_install_update_corrupted_zip_preserves_existing_core(tmp_path: Path) -> None:
    """Verify corrupted ZIP fails in staging without removing or bricking the old installation."""
    app_root = tmp_path / "app"
    internal_dir = app_root / "_internal"
    internal_dir.mkdir(parents=True)
    (app_root / MAIN_EXECUTABLE_NAME).write_text("old-exe-v1", encoding="utf-8")
    (internal_dir / "updater.exe").write_text("updater-v1", encoding="utf-8")
    Updater._write_text_atomic(app_root / "data" / "version.txt", "1000.0")

    bad_zip = app_root / "released" / "ITRPASuite.zip"
    bad_zip.parent.mkdir(parents=True, exist_ok=True)
    bad_zip.write_bytes(b"not-a-valid-zip-archive")
    os.utime(bad_zip, (3000.0, 3000.0))

    paths = _make_paths(app_root, bad_zip, running_from_internal=False)
    updater = Updater(paths, sleep_fn=lambda _: None)

    with pytest.raises(UpdateError, match="損毀"):
        updater.install_update()

    assert (app_root / MAIN_EXECUTABLE_NAME).read_text(encoding="utf-8") == "old-exe-v1"
    assert (internal_dir / "updater.exe").read_text(encoding="utf-8") == "updater-v1"
    assert not paths.local_zip.exists()
    assert not paths.staging_dir.exists()


def test_install_update_zip_slip_preserves_existing_core(tmp_path: Path) -> None:
    """Verify Zip Slip archive is rejected before touching existing `_internal/` and EXE."""
    app_root = tmp_path / "app"
    internal_dir = app_root / "_internal"
    internal_dir.mkdir(parents=True)
    (app_root / MAIN_EXECUTABLE_NAME).write_text("old-exe-v1", encoding="utf-8")
    (internal_dir / "updater.exe").write_text("updater-v1", encoding="utf-8")
    Updater._write_text_atomic(app_root / "data" / "version.txt", "1000.0")

    evil_zip = _create_release_zip(
        app_root / "released" / "ITRPASuite.zip",
        {
            MAIN_EXECUTABLE_NAME: "evil-v2",
            "../../escaped.exe": "payload",
        },
    )
    os.utime(evil_zip, (3000.0, 3000.0))

    paths = _make_paths(app_root, evil_zip, running_from_internal=False)
    updater = Updater(paths, sleep_fn=lambda _: None)

    with pytest.raises(UpdateError, match="不安全"):
        updater.install_update()

    assert (app_root / MAIN_EXECUTABLE_NAME).read_text(encoding="utf-8") == "old-exe-v1"
    assert (internal_dir / "updater.exe").read_text(encoding="utf-8") == "updater-v1"
    assert not (tmp_path / "escaped.exe").exists()
    assert not paths.staging_dir.exists()


def test_install_update_sha256_verification_and_sidecar(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify SHA-256 sidecar & CLI/env checksum mismatch blocks update, and valid hash succeeds."""
    app_root = tmp_path / "app"
    internal_dir = app_root / "_internal"
    internal_dir.mkdir(parents=True)
    (app_root / MAIN_EXECUTABLE_NAME).write_text("old-exe-v1", encoding="utf-8")
    (internal_dir / "updater.exe").write_text("updater-v1", encoding="utf-8")

    source_zip = _create_release_zip(
        app_root / "released" / "ITRPASuite.zip",
        {
            MAIN_EXECUTABLE_NAME: "new-exe-v2",
            "_internal/updater.exe": "updater-v2",
        },
    )
    sidecar = Path(f"{source_zip}.sha256")
    sidecar.write_text(("0" * 64) + "  ITRPASuite.zip\n", encoding="utf-8")

    paths = _make_paths(app_root, source_zip, running_from_internal=False)
    updater = Updater(paths, sleep_fn=lambda _: None)

    # Mismatched sidecar hash must fail without touching old core
    with pytest.raises(UpdateError, match="SHA-256"):
        updater.install_update()
    assert (app_root / MAIN_EXECUTABLE_NAME).read_text(encoding="utf-8") == "old-exe-v1"
    assert (internal_dir / "updater.exe").read_text(encoding="utf-8") == "updater-v1"

    # Write matching sidecar hash -> promotion should succeed and hand off
    valid_hash = Updater._compute_sha256(source_zip)
    sidecar.write_text(f"{valid_hash}  ITRPASuite.zip\n", encoding="utf-8")
    launched: list[Path] = []
    monkeypatch.setattr(Updater, "_launch", lambda _self, exe, _cwd: launched.append(Path(exe)))

    with pytest.raises(UpdateHandoff):
        updater.install_update()

    assert (app_root / MAIN_EXECUTABLE_NAME).read_text(encoding="utf-8") == "new-exe-v2"
    assert launched[-1] == paths.internal_updater

    # Verify CLI & env SHA-256 argument resolution
    assert resolve_expected_sha256_arg(["--sha256", valid_hash]) == valid_hash
    monkeypatch.setenv("IT_SUITE_UPDATE_SHA256", valid_hash)
    assert resolve_expected_sha256_arg([]) == valid_hash


def test_install_update_rolls_back_old_core_on_promotion_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify failed promotion automatically restores backed-up old core."""
    app_root = tmp_path / "app"
    internal_dir = app_root / "_internal"
    internal_dir.mkdir(parents=True)
    (app_root / MAIN_EXECUTABLE_NAME).write_text("old-exe-v1", encoding="utf-8")
    (internal_dir / "updater.exe").write_text("updater-v1", encoding="utf-8")

    source_zip = _create_release_zip(
        app_root / "released" / "ITRPASuite.zip",
        {
            MAIN_EXECUTABLE_NAME: "new-exe-v2",
            "_internal/updater.exe": "updater-v2",
        },
    )

    paths = _make_paths(app_root, source_zip, running_from_internal=False)
    updater = Updater(paths, sleep_fn=lambda _: None)

    def _broken_promote(_staging: Path, target_root: Path) -> None:
        (target_root / MAIN_EXECUTABLE_NAME).write_text("partial-broken", encoding="utf-8")
        raise OSError("simulated disk full during promotion")

    monkeypatch.setattr(Updater, "_promote_staging", staticmethod(_broken_promote))

    with pytest.raises(OSError, match="simulated disk full"):
        updater.install_update()

    # Rollback must have restored the original files cleanly
    assert (app_root / MAIN_EXECUTABLE_NAME).read_text(encoding="utf-8") == "old-exe-v1"
    assert (internal_dir / "updater.exe").read_text(encoding="utf-8") == "updater-v1"
    assert not paths.backup_internal_dir.exists()
    assert not paths.backup_executable.exists()
    assert not paths.staging_dir.exists()


# ------------------------------------------------------------------
# 4. Toolbox Scanner & Extension Demo Helper Tests
# ------------------------------------------------------------------
def test_toolbox_find_tool_files_excludes_updater_and_sdk(tmp_path: Path) -> None:
    """Verify `find_tool_files` discovers user scripts/exes while excluding updater & SDK."""
    tools_dir = tmp_path / "tools"
    (tools_dir / "updater").mkdir(parents=True)
    (tools_dir / "subtool").mkdir(parents=True)

    (tools_dir / "tool_sdk.py").write_text("# sdk", encoding="utf-8")
    (tools_dir / "updater" / "updater.py").write_text("# updater", encoding="utf-8")
    (tools_dir / "updater" / "updater.exe").write_text("bin", encoding="utf-8")
    (tools_dir / "ext_provision_demo.py").write_text("# demo", encoding="utf-8")
    (tools_dir / "subtool" / "custom_helper.exe").write_text("bin", encoding="utf-8")

    discovered = find_tool_files(tools_dir)
    names = [item["name"] for item in discovered]

    assert "ext_provision_demo.py" in names
    assert "custom_helper.exe" in names
    assert "tool_sdk.py" not in names
    assert "updater.py" not in names
    assert "updater.exe" not in names


def test_is_last_two_digits_repeated() -> None:
    """Verify telecom extension non-repeating last-2-digits rule."""
    assert is_last_two_digits_repeated("50200") is True
    assert is_last_two_digits_repeated("50222") is True
    assert is_last_two_digits_repeated("86-502000") is True
    assert is_last_two_digits_repeated("50234") is False
    assert is_last_two_digits_repeated("50238") is False

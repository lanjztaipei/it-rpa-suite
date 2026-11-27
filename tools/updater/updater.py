"""Three-stage self-updating state machine with Zip Slip protection and atomic version tracking.

State Machine Stages (`UpdateStage`):
1. `NEEDED` (`prepare_update`):
   Running from `_internal/`, detects a newer update package in `./released/ITRPASuite.zip`
   (or missing `data/version.txt`). Copies itself to `app_root` (safe zone), launches the safe copy,
   and raises `UpdateHandoff`.
2. `STARTED` (`install_update`):
   Running from `app_root` (safe zone), copies the update ZIP locally, removes the old `_internal/`
   directory and `ITRPASuite.exe`, safely extracts the ZIP (blocking Zip Slip traversal),
   atomically writes `data/updating_version.txt`, launches the newly extracted `_internal/updater`,
   and raises `UpdateHandoff`.
3. `IN_PROGRESS` (`finalize_update`):
   Running from the new `_internal/`, validates `data/updating_version.txt`, atomically writes
   `data/version.txt`, removes `data/updating_version.txt` and the safe-zone updater copy,
   synchronizes `_internal/tools/tool_sdk.py` to `tools/tool_sdk.py`, then relaunches
   `ITRPASuite.exe` detached and exits without pausing so the console window closes automatically.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import logging
import os
import shutil
import subprocess
import sys
import time
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import TypeVar

LOGGER = logging.getLogger("updater")
T = TypeVar("T")

# =====================================================================
# 更新來源設定 (Update Source Configuration)
# ---------------------------------------------------------------------
# 若未來需要更改更新壓縮檔位置，可選擇以下任一方式（由高至低優先順序）：
# 1. 命令列參數：`updater.exe --source-zip "路徑"` 或環境變數 `IT_SUITE_UPDATE_ZIP`
# 2. 設定檔覆寫：於 `data/settings.json` 設定 `"update_source_zip": "路徑"`（免重新打包 EXE）
# 3. 預設常數：直接修改下方 `DEFAULT_RELEASE_RELATIVE_PATH`
#
# 預設標準：統一指向專案根目錄下的 `released/ITRPASuite.zip`
# =====================================================================
DEFAULT_RELEASE_RELATIVE_PATH = Path("released") / "ITRPASuite.zip"
APP_FOLDER_NAME = "ITRPASuite"
MAIN_EXECUTABLE_NAME = "ITRPASuite.exe"
# Stage 3 更新時一律強制同步覆蓋的工具底座／範本檔
ALWAYS_SYNC_TOOL_FILES: tuple[str, ...] = (
    "tool_sdk.py",
    "_tool_template.py",
)
# Stage 3 更新時僅於目標不存在時植入的內建示範工具（避免覆蓋使用者自行修改版本）
SEED_IF_MISSING_TOOL_FILES: tuple[str, ...] = (
    "ext_provision_demo.py",
    "async_form_audit_demo.py",
)


class UpdateStage(Enum):
    """Current phase of the three-stage self-update state machine."""

    NOT_NEEDED = auto()
    NEEDED = auto()
    STARTED = auto()
    IN_PROGRESS = auto()


class UpdateError(RuntimeError):
    """Expected or recoverable error during the update workflow."""


class UpdateHandoff(Exception):
    """Signal that update execution has been handed off to another updater process."""


@dataclass(frozen=True)
class UpdatePaths:
    """Centralized path layout for the three-stage self-update state machine."""

    source_zip: Path
    executable: Path
    app_root: Path
    internal_dir: Path
    data_dir: Path
    version_file: Path
    updating_version_file: Path
    safe_updater: Path
    internal_updater: Path
    local_zip: Path
    application_executable: Path
    tools_dir: Path
    tool_sdk_source: Path
    tool_sdk_target: Path
    running_from_internal: bool

    @property
    def staging_dir(self) -> Path:
        return self.app_root / ".update_staging"

    @property
    def backup_internal_dir(self) -> Path:
        return self.app_root / "_internal.bak"

    @property
    def backup_executable(self) -> Path:
        return self.app_root / f"{MAIN_EXECUTABLE_NAME}.bak"

    @property
    def source_sha256_file(self) -> Path:
        return Path(f"{self.source_zip}.sha256")

    @property
    def tool_template_source(self) -> Path:
        return self.internal_dir / "tools" / "_tool_template.py"

    @property
    def tool_template_target(self) -> Path:
        return self.tools_dir / "_tool_template.py"

    @classmethod
    def from_runtime(
        cls,
        source_zip: Path | str | None = None,
        executable_path: Path | str | None = None,
    ) -> UpdatePaths:
        """Resolve all update paths from the current runtime executable or script location."""
        if executable_path is not None:
            executable = Path(executable_path).resolve()
        elif getattr(sys, "frozen", False):
            executable = Path(sys.executable).resolve()
        else:
            executable = Path(__file__).resolve()

        current_dir = executable.parent
        running_from_internal = current_dir.name.casefold() == "_internal"
        running_from_dev_updater = (
            current_dir.name.casefold() == "updater"
            and current_dir.parent.name.casefold() == "tools"
        )

        if running_from_internal:
            app_root = current_dir.parent
        elif running_from_dev_updater:
            # Running directly from repo `tools/updater/updater.py` (or `updater.exe`) in development
            app_root = current_dir.parent.parent
            running_from_internal = True
        else:
            app_root = current_dir

        internal_dir = app_root / "_internal"
        data_dir = app_root / "data"
        tools_dir = app_root / "tools"
        updater_name = executable.name

        resolved_source_zip = cls._resolve_source_zip(
            app_root=app_root,
            data_dir=data_dir,
            source_zip=source_zip,
        )

        internal_updater = internal_dir / updater_name
        if (
            updater_name.casefold().endswith(".py")
            and not internal_updater.is_file()
            and (internal_dir / "updater.exe").is_file()
        ):
            internal_updater = internal_dir / "updater.exe"

        return cls(
            source_zip=resolved_source_zip,
            executable=executable,
            app_root=app_root,
            internal_dir=internal_dir,
            data_dir=data_dir,
            version_file=data_dir / "version.txt",
            updating_version_file=data_dir / "updating_version.txt",
            safe_updater=app_root / updater_name,
            internal_updater=internal_updater,
            local_zip=app_root / f"{updater_name}.zip",
            application_executable=app_root / MAIN_EXECUTABLE_NAME,
            tools_dir=tools_dir,
            tool_sdk_source=internal_dir / "tools" / "tool_sdk.py",
            tool_sdk_target=tools_dir / "tool_sdk.py",
            running_from_internal=running_from_internal,
        )

    @classmethod
    def _resolve_source_zip(
        cls,
        app_root: Path,
        data_dir: Path,
        source_zip: Path | str | None = None,
    ) -> Path:
        """Resolve single deterministic update ZIP path.

        Priority:
        1. Explicit `source_zip` argument (CLI `--source-zip` or `IT_SUITE_UPDATE_ZIP` env var)
        2. `update_source_zip` in `data/settings.json` (if non-empty)
        3. Project root `released/ITRPASuite.zip`
        """
        project_root = (
            app_root.parent if app_root.name.casefold() == APP_FOLDER_NAME.casefold() else app_root
        )

        raw_override: Path | str | None = source_zip
        if not raw_override:
            settings_file = data_dir / "settings.json"
            if settings_file.is_file():
                try:
                    data = json.loads(settings_file.read_text(encoding="utf-8"))
                    if isinstance(data, dict):
                        cfg_zip = str(data.get("update_source_zip", "")).strip()
                        if cfg_zip:
                            raw_override = cfg_zip
                except Exception:
                    pass

        if raw_override:
            candidate = Path(raw_override)
            if candidate.is_absolute():
                return candidate.resolve()
            return (project_root / candidate).resolve()

        return (project_root / DEFAULT_RELEASE_RELATIVE_PATH).resolve()


@dataclass(frozen=True)
class RetryPolicy:
    """Retry configuration for file removal and process handoff."""

    attempts: int
    delay_seconds: float


class Updater:
    """Executes the three-stage self-update state machine."""

    def __init__(
        self,
        paths: UpdatePaths,
        sleep_fn: Callable[[float], None] = time.sleep,
        expected_sha256: str | None = None,
        no_relaunch: bool = False,
    ) -> None:
        self.paths = paths
        self._sleep = sleep_fn
        self._expected_sha256 = (expected_sha256 or "").strip() or None
        self._no_relaunch = bool(no_relaunch)

    def run(self) -> UpdateStage:
        """Evaluate current stage and execute the corresponding state handler."""
        stage = self.check_stage()
        handlers: dict[UpdateStage, Callable[[], None]] = {
            UpdateStage.NOT_NEEDED: self._handle_no_update,
            UpdateStage.NEEDED: self.prepare_update,
            UpdateStage.STARTED: self.install_update,
            UpdateStage.IN_PROGRESS: self.finalize_update,
        }
        handlers[stage]()
        return stage

    def check_stage(self) -> UpdateStage:
        """Determine the current `UpdateStage` based on marker files, location, and timestamps."""
        p = self.paths

        if not p.source_zip.is_file():
            raise UpdateError(f"更新來源 ZIP 不存在：{p.source_zip}")

        if p.updating_version_file.is_file():
            if not p.running_from_internal:
                raise UpdateError("偵測到更新標記，但 updater 不在 _internal 中。")
            LOGGER.info("核心檔案已更新，準備執行收尾作業 (Stage 3: IN_PROGRESS)。")
            return UpdateStage.IN_PROGRESS

        if not p.version_file.is_file():
            if p.running_from_internal:
                LOGGER.warning("版本紀錄不存在，將直接執行修復更新：%s", p.version_file)
                return UpdateStage.NEEDED
            LOGGER.warning("版本紀錄不存在，將由安全區繼續更新。")
            return UpdateStage.STARTED

        installed_version = self._read_timestamp(p.version_file)
        source_version = p.source_zip.stat().st_mtime

        if source_version <= installed_version:
            return UpdateStage.NOT_NEEDED

        if p.running_from_internal:
            LOGGER.info("偵測到較新版本，準備更新 (Stage 1: NEEDED)。")
            return UpdateStage.NEEDED

        LOGGER.info("安全區 updater 已啟動，繼續更新 (Stage 2: STARTED)。")
        return UpdateStage.STARTED

    def prepare_update(self) -> None:
        """Stage 1: Copy updater from `_internal` to `app_root` safe zone and hand off."""
        LOGGER.info("正在準備更新程式 (Stage 1)。")
        self.paths.safe_updater.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(self.paths.executable, self.paths.safe_updater)
        LOGGER.info("已複製 updater 至安全區：%s", self.paths.safe_updater)

        self._retry(
            action=lambda: self._launch(self.paths.safe_updater, self.paths.app_root),
            policy=RetryPolicy(attempts=3, delay_seconds=3),
            description="啟動安全區 updater",
        )
        self._sleep(1)
        raise UpdateHandoff

    def install_update(self) -> None:
        """Stage 2: Validate ZIP & SHA-256 in staging, back up old core, promote with rollback, and hand off."""
        p = self.paths
        LOGGER.info("正在複製新版 ZIP (Stage 2)。")
        p.local_zip.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p.source_zip, p.local_zip)
        target_version = p.local_zip.stat().st_mtime

        try:
            expected_hash = self._resolve_expected_sha256()
            if expected_hash is not None:
                LOGGER.info("正在校驗新版 ZIP SHA-256 雜湊值。")
                self._verify_sha256(p.local_zip, expected_hash)

            LOGGER.info("正在暫存區安全驗證並解壓縮新版 ZIP。")
            self._prepare_staging_dir(p.staging_dir)
            self._extract_zip_safely(p.local_zip, p.staging_dir)
            self._validate_staged_release(p.staging_dir)

            LOGGER.info("驗證通過，正在備份舊核心程式。")
            self._retry(
                action=self._backup_old_core,
                policy=RetryPolicy(attempts=10, delay_seconds=3),
                description=f"備份舊程式，請確認 {MAIN_EXECUTABLE_NAME} 相關程序已關閉",
            )

            try:
                LOGGER.info("正在切換為新版核心程式。")
                self._promote_staging(p.staging_dir, p.app_root)
                target_internal_updater = self._resolve_promoted_internal_updater()
            except Exception as exc:
                LOGGER.error("切換新版核心失敗，正在自動回滾還原舊版程式：%s", exc)
                self._rollback_old_core()
                raise

            p.data_dir.mkdir(parents=True, exist_ok=True)
            self._write_text_atomic(p.updating_version_file, str(target_version))
            LOGGER.info("已鎖定本次更新版本：%s", target_version)
        finally:
            p.local_zip.unlink(missing_ok=True)
            if p.staging_dir.exists():
                shutil.rmtree(p.staging_dir, ignore_errors=True)

        self._sleep(2)
        self._launch(target_internal_updater, p.internal_dir)
        self._sleep(1)
        raise UpdateHandoff

    def finalize_update(self) -> None:
        """Stage 3: Commit `data/version.txt`, clean backups/safe-zone copy, and sync `tools/tool_sdk.py`."""
        p = self.paths
        LOGGER.info("正在完成更新收尾作業 (Stage 3)。")
        self._sleep(1)

        if not p.updating_version_file.is_file():
            raise UpdateError(f"找不到更新版本標記：{p.updating_version_file}")

        target_version = p.updating_version_file.read_text(encoding="utf-8").strip()
        self._validate_timestamp(target_version, p.updating_version_file)

        p.data_dir.mkdir(parents=True, exist_ok=True)
        self._write_text_atomic(p.version_file, target_version)
        p.updating_version_file.unlink(missing_ok=True)
        self._retry(
            action=self._cleanup_safe_updater,
            policy=RetryPolicy(attempts=10, delay_seconds=1),
            description="刪除安全區 updater",
        )
        self._cleanup_backups()

        self._initialize_tools_directory()
        LOGGER.info("更新成功，版本已更新為：%s", target_version)

    def _cleanup_safe_updater(self) -> None:
        p = self.paths
        p.safe_updater.unlink(missing_ok=True)
        for candidate in ("updater.exe", "updater.py"):
            (p.app_root / candidate).unlink(missing_ok=True)

    def _cleanup_backups(self) -> None:
        p = self.paths
        if p.backup_internal_dir.exists():
            shutil.rmtree(p.backup_internal_dir, ignore_errors=True)
        p.backup_executable.unlink(missing_ok=True)
        if p.staging_dir.exists():
            shutil.rmtree(p.staging_dir, ignore_errors=True)

    def _handle_no_update(self) -> None:
        LOGGER.info("目前已是最新版本，無需更新。")

    def _remove_old_core(self) -> None:
        p = self.paths
        if p.internal_dir.is_dir():
            shutil.rmtree(p.internal_dir)
        p.application_executable.unlink(missing_ok=True)

    def _backup_old_core(self) -> None:
        p = self.paths
        if p.backup_internal_dir.exists():
            shutil.rmtree(p.backup_internal_dir)
        p.backup_executable.unlink(missing_ok=True)

        if p.internal_dir.is_dir():
            p.internal_dir.rename(p.backup_internal_dir)
        if p.application_executable.is_file():
            try:
                p.application_executable.rename(p.backup_executable)
            except OSError:
                # Restore _internal backup if main executable is still locked
                if p.backup_internal_dir.is_dir() and not p.internal_dir.exists():
                    p.backup_internal_dir.rename(p.internal_dir)
                raise

    def _rollback_old_core(self) -> None:
        p = self.paths
        if p.internal_dir.exists():
            shutil.rmtree(p.internal_dir, ignore_errors=True)
        p.application_executable.unlink(missing_ok=True)

        if p.backup_internal_dir.is_dir():
            p.backup_internal_dir.rename(p.internal_dir)
        if p.backup_executable.is_file():
            p.backup_executable.rename(p.application_executable)

    @staticmethod
    def _prepare_staging_dir(staging_dir: Path) -> None:
        if staging_dir.exists():
            shutil.rmtree(staging_dir)
        staging_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _validate_staged_release(staging_dir: Path) -> None:
        has_exe = (staging_dir / MAIN_EXECUTABLE_NAME).is_file()
        has_internal = (staging_dir / "_internal").is_dir()
        if not has_exe and not has_internal:
            raise UpdateError(
                f"更新壓縮包內容異常，缺少 {MAIN_EXECUTABLE_NAME} 或 _internal 目錄。"
            )

    @staticmethod
    def _promote_staging(staging_dir: Path, app_root: Path) -> None:
        for item in staging_dir.iterdir():
            target = app_root / item.name
            if item.is_dir():
                if target.exists():
                    shutil.copytree(item, target, dirs_exist_ok=True)
                    shutil.rmtree(item)
                else:
                    shutil.move(str(item), str(target))
            else:
                if target.is_file():
                    target.unlink()
                shutil.move(str(item), str(target))

    def _resolve_promoted_internal_updater(self) -> Path:
        p = self.paths
        if p.internal_updater.is_file():
            return p.internal_updater
        fallback_updater_exe = p.internal_dir / "updater.exe"
        if fallback_updater_exe.is_file():
            return fallback_updater_exe
        raise UpdateError(f"新版 updater 不存在：{p.internal_updater}")

    def _resolve_expected_sha256(self) -> str | None:
        if self._expected_sha256:
            return self._expected_sha256
        sidecar = self.paths.source_sha256_file
        if sidecar.is_file():
            raw = sidecar.read_text(encoding="utf-8").strip()
            if not raw:
                raise UpdateError(f"SHA-256 校驗檔內容為空：{sidecar}")
            return raw.split()[0]
        return None

    @staticmethod
    def _compute_sha256(file_path: Path) -> str:
        digest = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                digest.update(chunk)
        return digest.hexdigest().lower()

    @classmethod
    def _verify_sha256(cls, zip_path: Path, expected_sha256: str) -> None:
        expected = expected_sha256.strip().lower()
        if len(expected) != 64 or any(ch not in "0123456789abcdef" for ch in expected):
            raise UpdateError(f"無效的 SHA-256 雜湊格式：{expected_sha256}")
        actual = cls._compute_sha256(zip_path)
        if not hmac.compare_digest(actual, expected):
            raise UpdateError(f"更新檔 SHA-256 校驗失敗：預期 {expected}，實際 {actual}")

    def _initialize_tools_directory(self) -> None:
        p = self.paths
        tools_dir_existed = p.tools_dir.exists()
        p.tools_dir.mkdir(parents=True, exist_ok=True)

        if tools_dir_existed:
            LOGGER.info("tools 資料夾已存在：%s", p.tools_dir)
        else:
            LOGGER.info("已建立 tools 資料夾：%s", p.tools_dir)

        if not p.tool_sdk_source.is_file():
            LOGGER.warning("找不到內建工具 SDK 範本：%s", p.tool_sdk_source)
        else:
            target_existed = p.tool_sdk_target.exists()
            shutil.copy2(p.tool_sdk_source, p.tool_sdk_target)

            if target_existed:
                LOGGER.info("已同步更新 tools/tool_sdk.py：%s", p.tool_sdk_target)
            else:
                LOGGER.info("已複製初始 tools/tool_sdk.py：%s", p.tool_sdk_target)

        bundled_tools_dir = p.internal_dir / "tools"
        for filename in ALWAYS_SYNC_TOOL_FILES:
            if filename == "tool_sdk.py":
                continue
            source_file = bundled_tools_dir / filename
            target_file = p.tools_dir / filename
            if source_file.is_file():
                existed = target_file.exists()
                shutil.copy2(source_file, target_file)
                action = "同步更新" if existed else "複製初始"
                LOGGER.info("已%s tools/%s：%s", action, filename, target_file)

        for filename in SEED_IF_MISSING_TOOL_FILES:
            source_file = bundled_tools_dir / filename
            target_file = p.tools_dir / filename
            if source_file.is_file() and not target_file.exists():
                shutil.copy2(source_file, target_file)
                LOGGER.info("已植入內建示範工具 tools/%s：%s", filename, target_file)

    @staticmethod
    def _build_clean_env(*, strip_updater_vars: bool = False) -> dict[str, str]:
        """Return a copy of `os.environ` stripped of PyInstaller bootloader variables."""
        env = {
            key: value
            for key, value in os.environ.items()
            if key != "_MEIPASS2" and not key.startswith("_PYI_")
        }
        if strip_updater_vars:
            for key in (
                "IT_SUITE_UPDATE_ZIP",
                "IT_SUITE_UPDATE_SHA256",
                "IT_SUITE_UPDATER_NO_RELAUNCH",
            ):
                env.pop(key, None)
        return env

    def relaunch_application(self) -> bool:
        """Start the updated main application detached from the updater console."""
        executable = self.paths.application_executable
        if not executable.is_file():
            LOGGER.warning("找不到主程式執行檔，略過自動重新啟動：%s", executable)
            return False

        creation_flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(
            subprocess, "CREATE_NEW_PROCESS_GROUP", 0
        )
        env = self._build_clean_env(strip_updater_vars=True)
        LOGGER.info("正在重新啟動主程式：%s", executable)
        subprocess.Popen(
            [str(executable)],
            cwd=str(self.paths.app_root),
            env=env,
            creationflags=creation_flags,
            close_fds=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True

    def _launch(self, executable: Path, cwd: Path) -> None:
        cmd = (
            [sys.executable, str(executable)]
            if executable.suffix.casefold() == ".py"
            else [str(executable)]
        )
        env = self._build_clean_env(strip_updater_vars=False)
        env["IT_SUITE_UPDATE_ZIP"] = str(self.paths.source_zip)
        if self._expected_sha256:
            env["IT_SUITE_UPDATE_SHA256"] = self._expected_sha256
        if self._no_relaunch:
            env["IT_SUITE_UPDATER_NO_RELAUNCH"] = "1"
        subprocess.Popen(cmd, cwd=str(cwd), env=env)

    @staticmethod
    def _read_timestamp(path: Path) -> float:
        value = path.read_text(encoding="utf-8").strip()
        return Updater._validate_timestamp(value, path)

    @staticmethod
    def _validate_timestamp(value: str, path: Path) -> float:
        try:
            timestamp = float(value)
        except ValueError as exc:
            raise UpdateError(f"版本紀錄格式錯誤：{path}") from exc
        if timestamp < 0:
            raise UpdateError(f"版本紀錄不可為負數：{path}")
        return timestamp

    @staticmethod
    def _write_text_atomic(path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_suffix(f"{path.suffix}.tmp")
        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                f.write(content)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp_path, path)
        except Exception:
            if temp_path.exists():
                temp_path.unlink(missing_ok=True)
            raise

    @staticmethod
    def _extract_zip_safely(zip_path: Path, destination: Path) -> None:
        """Validate all ZIP entries before extraction to prevent Zip Slip path traversal."""
        destination = destination.resolve()
        try:
            with zipfile.ZipFile(zip_path, "r") as archive:
                for member in archive.infolist():
                    raw_name = member.filename
                    normalized = raw_name.replace("\\", "/")
                    member_obj = Path(normalized)
                    if member_obj.is_absolute() or (
                        normalized.startswith("/") or ":" in member_obj.drive
                    ):
                        raise UpdateError(f"ZIP 內含不安全絕對路徑：{raw_name}")

                    member_path = (destination / normalized).resolve()
                    try:
                        member_path.relative_to(destination)
                    except ValueError as exc:
                        raise UpdateError(f"ZIP 內含不安全路徑：{raw_name}") from exc

                archive.extractall(destination)
        except zipfile.BadZipFile as exc:
            raise UpdateError(f"ZIP 檔案損毀或格式無效：{zip_path}") from exc

    def _retry(
        self,
        action: Callable[[], T],
        policy: RetryPolicy,
        description: str,
    ) -> T:
        last_error: Exception | None = None
        for attempt in range(1, policy.attempts + 1):
            try:
                return action()
            except (OSError, subprocess.SubprocessError) as exc:
                last_error = exc
                if attempt == policy.attempts:
                    break
                LOGGER.warning(
                    "%s失敗：%s；%.0f 秒後重試（%d/%d）。",
                    description,
                    exc,
                    policy.delay_seconds,
                    attempt,
                    policy.attempts,
                )
                self._sleep(policy.delay_seconds)

        raise UpdateError(f"{description}失敗，已達重試上限。") from last_error


def resolve_source_zip_arg(cli_args: list[str] | None = None) -> Path | None:
    """Resolve explicit source ZIP override from CLI (`--source-zip`) or environment variable."""
    parser = argparse.ArgumentParser(description="IT RPA Suite Three-Stage Updater")
    parser.add_argument(
        "--source-zip",
        dest="source_zip",
        default=None,
        help="Path to update package ZIP (default: ./released/ITRPASuite.zip)",
    )
    parsed, _ = parser.parse_known_args(cli_args)

    if parsed.source_zip:
        return Path(parsed.source_zip)

    env_zip = os.environ.get("IT_SUITE_UPDATE_ZIP", "").strip()
    if env_zip:
        return Path(env_zip)

    return None


def resolve_expected_sha256_arg(cli_args: list[str] | None = None) -> str | None:
    """Resolve optional expected SHA-256 hash from CLI (`--sha256`) or environment variable."""
    parser = argparse.ArgumentParser(description="IT RPA Suite Three-Stage Updater")
    parser.add_argument(
        "--sha256",
        dest="sha256",
        default=None,
        help="Optional expected SHA-256 checksum for the update package ZIP",
    )
    parsed, _ = parser.parse_known_args(cli_args)

    if parsed.sha256:
        return str(parsed.sha256).strip()

    env_sha = os.environ.get("IT_SUITE_UPDATE_SHA256", "").strip()
    if env_sha:
        return env_sha

    return None


def resolve_no_relaunch_arg(cli_args: list[str] | None = None) -> bool:
    """Resolve whether automatic main-app relaunch is disabled via CLI or env var."""
    parser = argparse.ArgumentParser(description="IT RPA Suite Three-Stage Updater")
    parser.add_argument(
        "--no-relaunch",
        dest="no_relaunch",
        action="store_true",
        default=False,
        help="Do not automatically relaunch ITRPASuite.exe after a successful update",
    )
    parsed, _ = parser.parse_known_args(cli_args)
    if parsed.no_relaunch:
        return True

    env_flag = os.environ.get("IT_SUITE_UPDATER_NO_RELAUNCH", "").strip().lower()
    return env_flag in {"1", "true", "yes", "on"}


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def pause(message: str) -> None:
    if sys.stdin and sys.stdin.isatty():
        input(message)


def main(cli_args: list[str] | None = None) -> int:
    configure_logging()

    source_zip_override = resolve_source_zip_arg(cli_args)
    expected_sha256 = resolve_expected_sha256_arg(cli_args)
    no_relaunch = resolve_no_relaunch_arg(cli_args)
    paths = UpdatePaths.from_runtime(source_zip=source_zip_override)
    updater = Updater(
        paths,
        expected_sha256=expected_sha256,
        no_relaunch=no_relaunch,
    )

    try:
        stage = updater.run()
    except UpdateHandoff:
        LOGGER.info("更新工作已交棒，目前 updater 程序立即結束。")
        return 0
    except (UpdateError, OSError, zipfile.BadZipFile) as exc:
        LOGGER.exception("更新失敗：%s", exc)
        pause("更新發生錯誤，按 Enter 結束...")
        return 1

    if stage == UpdateStage.IN_PROGRESS:
        if not no_relaunch:
            try:
                updater.relaunch_application()
            except OSError as exc:
                LOGGER.exception("更新已完成，但重新啟動主程式失敗：%s", exc)
                pause("更新已完成，但重新啟動主程式失敗，按 Enter 結束...")
                return 1
        LOGGER.info("更新流程全部完成，更新視窗即將自動關閉。")
        return 0

    pause("執行完成，按 Enter 結束...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

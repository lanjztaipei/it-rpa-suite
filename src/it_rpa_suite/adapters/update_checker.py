"""In-app update availability checker mirroring the three-stage updater contract."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path

from it_rpa_suite.adapters.paths import AppPaths


class UpdateCheckStatus(Enum):
    """Outcome of a non-destructive in-app update check."""

    UP_TO_DATE = "up_to_date"
    UPDATE_AVAILABLE = "update_available"
    VERSION_MISSING = "version_missing"
    UPDATE_PENDING = "update_pending"
    SOURCE_NOT_FOUND = "source_not_found"
    ERROR = "error"


@dataclass(frozen=True)
class UpdateCheckResult:
    """Structured result returned by :func:`check_for_updates`."""

    status: UpdateCheckStatus
    source_zip: Path
    installed_timestamp: float | None = None
    source_timestamp: float | None = None
    error_message: str | None = None

    @property
    def needs_update(self) -> bool:
        return self.status in {
            UpdateCheckStatus.UPDATE_AVAILABLE,
            UpdateCheckStatus.VERSION_MISSING,
            UpdateCheckStatus.UPDATE_PENDING,
        }


def format_timestamp(ts: float | None) -> str:
    """Format a POSIX timestamp into local ``YYYY-MM-DD HH:MM:SS`` text."""
    if ts is None:
        return "未知"
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")


def resolve_update_source_zip(
    paths: AppPaths,
    configured_zip: str | Path | None = None,
) -> Path:
    """Resolve the update ZIP path following updater priority (env > settings > default)."""
    env_zip = os.environ.get("IT_SUITE_UPDATE_ZIP", "").strip()
    effective = env_zip or (str(configured_zip).strip() if configured_zip is not None else "")
    return paths.get_update_zip_path(effective or None)


def _read_timestamp_file(path: Path) -> float:
    raw = path.read_text(encoding="utf-8").strip()
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"版本紀錄格式錯誤：{path}") from exc
    if value < 0:
        raise ValueError(f"版本紀錄不可為負數：{path}")
    return value


def check_for_updates(
    paths: AppPaths,
    configured_zip: str | Path | None = None,
) -> UpdateCheckResult:
    """Check whether a newer update ZIP exists without launching updater or closing the app."""
    source_zip = resolve_update_source_zip(paths, configured_zip=configured_zip)

    try:
        if not source_zip.is_file():
            return UpdateCheckResult(
                status=UpdateCheckStatus.SOURCE_NOT_FOUND,
                source_zip=source_zip,
                error_message=f"更新來源壓縮檔不存在：{source_zip}",
            )
        source_mtime = source_zip.stat().st_mtime
    except OSError as exc:
        return UpdateCheckResult(
            status=UpdateCheckStatus.ERROR,
            source_zip=source_zip,
            error_message=f"無法存取更新來源壓縮檔：{source_zip}\n{exc}",
        )

    if paths.updating_version_file.is_file():
        return UpdateCheckResult(
            status=UpdateCheckStatus.UPDATE_PENDING,
            source_zip=source_zip,
            source_timestamp=source_mtime,
        )

    if not paths.version_file.is_file():
        return UpdateCheckResult(
            status=UpdateCheckStatus.VERSION_MISSING,
            source_zip=source_zip,
            source_timestamp=source_mtime,
        )

    try:
        installed_ts = _read_timestamp_file(paths.version_file)
    except (OSError, ValueError) as exc:
        return UpdateCheckResult(
            status=UpdateCheckStatus.ERROR,
            source_zip=source_zip,
            source_timestamp=source_mtime,
            error_message=str(exc),
        )

    if source_mtime <= installed_ts:
        return UpdateCheckResult(
            status=UpdateCheckStatus.UP_TO_DATE,
            source_zip=source_zip,
            installed_timestamp=installed_ts,
            source_timestamp=source_mtime,
        )

    return UpdateCheckResult(
        status=UpdateCheckStatus.UPDATE_AVAILABLE,
        source_zip=source_zip,
        installed_timestamp=installed_ts,
        source_timestamp=source_mtime,
    )

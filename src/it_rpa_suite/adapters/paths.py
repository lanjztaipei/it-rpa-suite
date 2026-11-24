"""Unified application path resolution for source and PyInstaller frozen modes."""

from __future__ import annotations

import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

# 統一預設更新壓縮檔位置（相對於 project_root），亦可於 data/settings.json 的 "update_source_zip" 覆寫
DEFAULT_UPDATE_ZIP_REL_PATH = Path("released") / "ITRPASuite.zip"
APP_FOLDER_NAME = "ITRPASuite"


def _default_project_root() -> Path:
    """Return the repository root when running from source."""
    return Path(__file__).resolve().parents[3]


def _default_base_dir() -> Path:
    """Return the writable base directory (EXE directory when frozen, repo root otherwise)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return _default_project_root()


def _default_resource_dir(base_dir: Path | None = None) -> Path:
    """Return the read-only bundled assets directory root."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(getattr(sys, "_MEIPASS")).resolve()
    if base_dir is not None and (base_dir / "assets").exists():
        return base_dir
    return _default_project_root()


@dataclass(frozen=True)
class AppPaths:
    """Centralized path manager for writable runtime data and read-only bundled assets."""

    base_dir: Path
    resource_dir: Path

    def __init__(
        self,
        base_dir: str | Path | None = None,
        resource_dir: str | Path | None = None,
    ) -> None:
        resolved_base = Path(base_dir).resolve() if base_dir is not None else _default_base_dir()
        resolved_resource = (
            Path(resource_dir).resolve()
            if resource_dir is not None
            else _default_resource_dir(resolved_base)
        )
        object.__setattr__(self, "base_dir", resolved_base)
        object.__setattr__(self, "resource_dir", resolved_resource)

    @property
    def assets_dir(self) -> Path:
        return self.resource_dir / "assets"

    @property
    def icons_dir(self) -> Path:
        return self.assets_dir / "icons"

    @property
    def default_settings_file(self) -> Path:
        return self.assets_dir / "default_settings.json"

    @property
    def default_templates_file(self) -> Path:
        return self.assets_dir / "default_ticket_templates.json"

    @property
    def data_dir(self) -> Path:
        return self.base_dir / "data"

    @property
    def logs_dir(self) -> Path:
        return self.data_dir / "logs"

    @property
    def log_file(self) -> Path:
        return self.logs_dir / "app.log"

    @property
    def db_file(self) -> Path:
        return self.data_dir / "app.db"

    @property
    def settings_file(self) -> Path:
        return self.data_dir / "settings.json"

    @property
    def credentials_file(self) -> Path:
        return self.data_dir / "credentials.dat"

    @property
    def ticket_templates_file(self) -> Path:
        return self.data_dir / "ticket_templates.json"

    @property
    def tools_dir(self) -> Path:
        return self.base_dir / "tools"

    @property
    def project_root(self) -> Path:
        """Return the top-level project root (parent of `ITRPASuite/` when packaged inside it)."""
        if self.base_dir.name.casefold() == APP_FOLDER_NAME.casefold():
            return self.base_dir.parent
        return self.base_dir

    def get_update_zip_path(self, custom_path: str | Path | None = None) -> Path:
        """Resolve the single canonical update ZIP path (defaults to `<project_root>/released/ITRPASuite.zip`)."""
        raw = str(custom_path).strip() if custom_path is not None else ""
        target = Path(raw) if raw else DEFAULT_UPDATE_ZIP_REL_PATH
        if target.is_absolute():
            return target.resolve()
        return (self.project_root / target).resolve()

    def get_icon_path(self, filename: str) -> Path:
        return self.icons_dir / filename

    def ensure_directories(self) -> None:
        """Create writable data/ and data/logs/ directories and seed default config files."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)

        if self.default_settings_file.is_file() and not self.settings_file.exists():
            shutil.copy2(self.default_settings_file, self.settings_file)

        if self.default_templates_file.is_file() and not self.ticket_templates_file.exists():
            shutil.copy2(self.default_templates_file, self.ticket_templates_file)


def get_app_paths(
    base_dir: str | Path | None = None,
    resource_dir: str | Path | None = None,
) -> AppPaths:
    """Create an AppPaths instance and ensure runtime directories exist."""
    paths = AppPaths(base_dir=base_dir, resource_dir=resource_dir)
    paths.ensure_directories()
    return paths

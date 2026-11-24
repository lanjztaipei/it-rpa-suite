"""Unified SQLite usage statistics and atomic settings.json storage adapter."""

from __future__ import annotations

import copy
import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from it_rpa_suite.adapters.logger import get_logger
from it_rpa_suite.adapters.paths import AppPaths, get_app_paths

logger = get_logger(__name__)

DEFAULT_SETTINGS: dict[str, Any] = {
    "dark_mode": False,
    "caller_id_enabled": True,
    "update_source_zip": "released/ITRPASuite.zip",
    "coefficients": {
        "short_loan": 1.5,
        "project_loan": 2.0,
        "asset_return": 2.0,
        "holder_lookup": 1.5,
        "onboarding_issue": 5.0,
        "offboarding_clearance": 10.0,
        "nac_single_mac": 1.5,
        "nac_dual_mac": 2.0,
        "incident_ticket": 3.0,
        "routine_ticket": 3.0,
        "caller_lookup": 2.0,
    },
}

TICKET_FEATURE_KEYS = frozenset(
    {
        "incident_ticket",
        "routine_ticket",
        "default_request",
        "it_routine",
    }
)


def _format_number(value: float) -> int | float:
    """Return an int if value has no fractional part, else a 1-decimal rounded float."""
    rounded = round(float(value), 1)
    if rounded.is_integer():
        return int(rounded)
    return rounded


def _previous_year_month(dt: datetime) -> str:
    """Return YYYYMM string for the month preceding dt."""
    year = dt.year
    month = dt.month - 1
    if month <= 0:
        month = 12
        year -= 1
    return f"{year:04d}{month:02d}"


class AppStorage:
    """Manages data/settings.json (atomic JSON I/O) and data/app.db (SQLite usage tracking)."""

    def __init__(
        self,
        paths: AppPaths | None = None,
        base_dir: str | Path | None = None,
    ) -> None:
        if paths is not None:
            self.paths = paths
            self.paths.ensure_directories()
        else:
            self.paths = get_app_paths(base_dir=base_dir)
        self._init_db()

    @property
    def db_path(self) -> Path:
        return self.paths.db_file

    @property
    def settings_path(self) -> Path:
        return self.paths.settings_file

    def _init_db(self) -> None:
        """Ensure feature_usage table and index exist in data/app.db."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS feature_usage (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        feature_key TEXT NOT NULL,
                        year_month TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_feature_usage_year_month
                    ON feature_usage (year_month)
                    """
                )
                conn.commit()
        except Exception as exc:
            logger.warning("初始化 SQLite 資料庫失敗: %s", exc)

    # ------------------------------------------------------------------
    # Settings (data/settings.json)
    # ------------------------------------------------------------------
    def load_settings(self) -> dict[str, Any]:
        """Load settings from data/settings.json, merging with safe defaults."""
        merged = copy.deepcopy(DEFAULT_SETTINGS)

        # Load bundled default_settings.json if available
        if self.paths.default_settings_file.is_file():
            try:
                raw_default = json.loads(
                    self.paths.default_settings_file.read_text(encoding="utf-8")
                )
                if isinstance(raw_default, dict):
                    merged.update({k: v for k, v in raw_default.items() if k != "coefficients"})
                    if isinstance(raw_default.get("coefficients"), dict):
                        merged["coefficients"].update(raw_default["coefficients"])
            except Exception as exc:
                logger.warning("讀取預設設定檔失敗: %s", exc)

        if not self.settings_path.exists():
            return merged

        try:
            data = json.loads(self.settings_path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                logger.warning("設定檔格式非 JSON object: %s", self.settings_path)
                return merged

            for key, value in data.items():
                if key == "coefficients" and isinstance(value, dict):
                    merged["coefficients"].update(value)
                else:
                    merged[key] = value
            return merged
        except Exception as exc:
            logger.warning("讀取設定檔失敗 (%s)，將使用預設值: %s", self.settings_path, exc)
            return merged

    def save_settings(self, settings: dict[str, Any]) -> None:
        """Atomically write settings dictionary to data/settings.json via .tmp + os.replace."""
        self.settings_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.settings_path.with_suffix(".json.tmp")
        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)
            os.replace(temp_path, self.settings_path)
        except Exception:
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except OSError:
                    pass
            raise

    def update_setting(self, key: str, value: Any) -> dict[str, Any]:
        """Update a single top-level key in settings.json atomically."""
        current = self.load_settings()
        current[key] = value
        self.save_settings(current)
        return current

    def get_dark_mode(self) -> bool:
        return bool(self.load_settings().get("dark_mode", False))

    def set_dark_mode(self, enabled: bool) -> None:
        self.update_setting("dark_mode", bool(enabled))

    def get_caller_id_enabled(self) -> bool:
        return bool(self.load_settings().get("caller_id_enabled", True))

    def set_caller_id_enabled(self, enabled: bool) -> None:
        self.update_setting("caller_id_enabled", bool(enabled))

    def get_coefficients(self) -> dict[str, float]:
        coeffs = self.load_settings().get("coefficients", {})
        if not isinstance(coeffs, dict):
            return dict(DEFAULT_SETTINGS["coefficients"])
        return coeffs

    # ------------------------------------------------------------------
    # Feature Usage Tracking (data/app.db)
    # ------------------------------------------------------------------
    def record_usage(
        self,
        feature_key: str,
        count: int = 1,
        timestamp: datetime | None = None,
        year_month: str | None = None,
    ) -> None:
        """Record one or more executions of a feature in SQLite."""
        if count <= 0:
            return

        now = timestamp or datetime.now()
        ym = year_month or now.strftime("%Y%m")
        created_at = now.strftime("%Y-%m-%d %H:%M:%S")

        try:
            with sqlite3.connect(self.db_path) as conn:
                rows = [(feature_key, ym, created_at) for _ in range(count)]
                conn.executemany(
                    """
                    INSERT INTO feature_usage (feature_key, year_month, created_at)
                    VALUES (?, ?, ?)
                    """,
                    rows,
                )
                conn.commit()
        except Exception as exc:
            logger.warning("記錄功能使用統計失敗 (%s): %s", feature_key, exc)

    def get_month_counts(self, year_month: str) -> dict[str, int]:
        """Return {feature_key: count} for a specific YYYYMM string."""
        if not self.db_path.exists():
            return {}
        try:
            with sqlite3.connect(self.db_path) as conn:
                rows = conn.execute(
                    """
                    SELECT feature_key, COUNT(*) AS usage_count
                    FROM feature_usage
                    WHERE year_month = ?
                    GROUP BY feature_key
                    """,
                    (year_month,),
                ).fetchall()
            return {str(feature_key): int(usage_count) for feature_key, usage_count in rows}
        except Exception as exc:
            logger.warning("查詢月份統計失敗 (year_month=%s): %s", year_month, exc)
            return {}

    def get_usage_stats(self, now: datetime | None = None) -> dict[str, int | float]:
        """Calculate weighted saved minutes and ticket counts for current and previous months."""
        ref_time = now or datetime.now()
        this_month = ref_time.strftime("%Y%m")
        last_month = _previous_year_month(ref_time)

        coefficients = self.get_coefficients()
        this_counts = self.get_month_counts(this_month)
        last_counts = self.get_month_counts(last_month)

        def calc_saved_minutes(counts: dict[str, int]) -> int | float:
            total = 0.0
            for feature_key, count in counts.items():
                raw_coeff = coefficients.get(feature_key, 0.0)
                try:
                    coeff = float(raw_coeff)
                except (TypeError, ValueError):
                    coeff = 0.0
                total += count * coeff
            return _format_number(total)

        def calc_tickets(counts: dict[str, int]) -> int:
            return sum(count for key, count in counts.items() if key in TICKET_FEATURE_KEYS)

        last_saved = calc_saved_minutes(last_counts)
        this_saved = calc_saved_minutes(this_counts)
        last_tickets = calc_tickets(last_counts)
        this_tickets = calc_tickets(this_counts)

        return {
            "last_month_saved_minutes": last_saved,
            "this_month_saved_minutes": this_saved,
            "last_month_tickets": last_tickets,
            "this_month_tickets": this_tickets,
            "上月總節省分鐘": last_saved,
            "本月已節省分鐘": this_saved,
            "上月總開單數": last_tickets,
            "本月已開單數": this_tickets,
        }

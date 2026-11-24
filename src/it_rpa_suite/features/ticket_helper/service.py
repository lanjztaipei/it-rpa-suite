"""Template repository, '__' placeholder marker resolution, and batch Service Desk Playwright automation."""

from __future__ import annotations

import json
import os
import shutil
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from it_rpa_suite.adapters.credentials_dpapi import CredentialStore
from it_rpa_suite.adapters.logger import get_logger
from it_rpa_suite.adapters.paths import AppPaths, get_app_paths
from it_rpa_suite.adapters.result import ServiceResult
from it_rpa_suite.adapters.storage import AppStorage
from it_rpa_suite.features.asset_loan.service import (
    login_portal_if_needed,
    select_searchable_employee,
)

logger = get_logger(__name__)

CATEGORY_INCIDENT = "Incident Request"
CATEGORY_ROUTINE = "Routine Task"

CATEGORY_ALIASES: dict[str, str] = {
    "Incident Request": CATEGORY_INCIDENT,
    "Default Request": CATEGORY_INCIDENT,
    "incident": CATEGORY_INCIDENT,
    "Routine Task": CATEGORY_ROUTINE,
    "IT 例行工作": CATEGORY_ROUTINE,
    "routine": CATEGORY_ROUTINE,
}

VALID_CATEGORIES = (CATEGORY_INCIDENT, CATEGORY_ROUTINE)

TEMPLATE_GROUPS = ("例行事項", "電腦相關", "開給同仁", "IT交辦", "未分類")
DEFAULT_TEMPLATE_GROUP = "未分類"

VALID_CORPS = ("Enterprise-HQ", "Enterprise-Branch", "Enterprise-Cloud")
PLACEHOLDER_MARKER = "__"


@dataclass(frozen=True)
class PlaceholderFocusTarget:
    """Resolved focus target and cleaned text for the first '__' placeholder marker."""

    field: str
    cursor_index: int
    cleaned_text: str
    found_marker: bool

    def __iter__(self) -> Iterator[Any]:
        """Allow tuple unpacking as (field, cursor_index, cleaned_text)."""
        yield self.field
        yield self.cursor_index
        yield self.cleaned_text


def find_first_placeholder_marker(
    template: dict[str, Any],
    marker: str = PLACEHOLDER_MARKER,
    priority_fields: tuple[str, ...] = ("email", "title"),
) -> PlaceholderFocusTarget:
    """Locate the first `__` placeholder marker (prioritizing `email`, then `title`).

    If found, removes the first occurrence of `marker` and returns the exact character
    index where the input cursor should be positioned.
    If no marker is present in any priority field, defaults to focusing the end of `title`.
    """
    if not isinstance(template, dict):
        raise TypeError("模板資料必須是 dict")

    for field_name in priority_fields:
        raw_val = str(template.get(field_name, "") or "")
        marker_idx = raw_val.find(marker)
        if marker_idx >= 0:
            cleaned = raw_val[:marker_idx] + raw_val[marker_idx + len(marker) :]
            return PlaceholderFocusTarget(
                field=field_name,
                cursor_index=marker_idx,
                cleaned_text=cleaned,
                found_marker=True,
            )

    fallback_title = str(template.get("title", "") or "")
    return PlaceholderFocusTarget(
        field="title",
        cursor_index=len(fallback_title),
        cleaned_text=fallback_title,
        found_marker=False,
    )


class TemplateRepository:
    """Manages ticket templates in `data/ticket_templates.json` with validation, CRUD, and atomic I/O."""

    VALID_CATEGORIES = VALID_CATEGORIES

    def __init__(
        self,
        paths: AppPaths | None = None,
        template_file: str | Path | None = None,
        default_template_file: str | Path | None = None,
    ) -> None:
        if template_file is not None:
            self._template_path = Path(template_file).resolve()
            self._default_path = (
                Path(default_template_file).resolve() if default_template_file is not None else None
            )
        else:
            app_paths = paths or get_app_paths()
            self._template_path = app_paths.ticket_templates_file
            self._default_path = (
                Path(default_template_file).resolve()
                if default_template_file is not None
                else app_paths.default_templates_file
            )

    @property
    def template_path(self) -> Path:
        return self._template_path

    @classmethod
    def normalize_template(cls, template: dict[str, Any]) -> dict[str, str]:
        """Validate and normalize a ticket template dictionary."""
        if not isinstance(template, dict):
            raise TypeError("單筆工單模板必須是 dict")

        raw_category = str(template.get("category", "")).strip()
        category = CATEGORY_ALIASES.get(raw_category, raw_category)
        if category not in VALID_CATEGORIES:
            raise ValueError(f"不支援的工單模板類型：{raw_category}")

        raw_group = str(template.get("_ui_group", DEFAULT_TEMPLATE_GROUP)).strip()
        ui_group = raw_group or DEFAULT_TEMPLATE_GROUP

        normalized: dict[str, str] = {
            "category": category,
            "email": str(template.get("email", "")).strip(),
            "title": str(template.get("title", "")).strip(),
            "type": str(template.get("type", "")).strip(),
            "sub_type": str(template.get("sub_type", "")).strip(),
            "corp": str(template.get("corp", "")).strip(),
            "resolve": str(template.get("resolve", "")).strip(),
            "_ui_group": ui_group,
        }

        required_fields: dict[str, str] = {
            "email": "請求人 Email",
            "title": "工單主題",
            "type": "服務子分類" if category == CATEGORY_INCIDENT else "例行作業類別",
            "resolve": "解決方案",
        }

        if category == CATEGORY_INCIDENT:
            if not normalized["sub_type"]:
                normalized["sub_type"] = "General Support"
            if not normalized["corp"]:
                normalized["corp"] = "Enterprise-HQ"
        else:
            normalized["sub_type"] = ""
            normalized["corp"] = ""

        for key, label in required_fields.items():
            if not normalized[key]:
                raise ValueError(f"{label}不可空白")

        email = normalized["email"]
        local_part, sep, domain_part = email.partition("@")
        if not sep or not local_part.strip() or not domain_part.strip():
            raise ValueError("請求人 Email 格式不正確")

        return normalized

    def ensure_template_file(self) -> Path:
        """Ensure the template file directory exists and seed from defaults or empty list."""
        self._template_path.parent.mkdir(parents=True, exist_ok=True)
        if not self._template_path.exists():
            if self._default_path is not None and self._default_path.is_file():
                shutil.copy2(self._default_path, self._template_path)
            else:
                self._write_raw_templates([])
        return self._template_path

    def _write_raw_templates(self, data: list[dict[str, str]]) -> None:
        """Atomically write template list to disk via `.tmp` + `os.replace()`."""
        self._template_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = Path(f"{self._template_path}.tmp")
        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(temp_path, self._template_path)
        except Exception:
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except OSError:
                    pass
            raise

    def load_templates(self) -> list[dict[str, str]]:
        """Load and validate all ticket templates from JSON file."""
        self.ensure_template_file()
        try:
            raw_text = self._template_path.read_text(encoding="utf-8")
            data = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            logger.exception("工單模板 JSON 格式錯誤：%s", self._template_path)
            raise ValueError(f"工單模板檔案格式錯誤：{self._template_path}") from exc
        except OSError:
            logger.exception("無法讀取工單模板檔案：%s", self._template_path)
            raise

        if not isinstance(data, list):
            raise ValueError("工單模板 JSON 最外層必須是陣列 list")

        templates: list[dict[str, str]] = []
        for idx, item in enumerate(data):
            try:
                templates.append(self.normalize_template(item))
            except Exception as exc:
                raise ValueError(f"第 {idx + 1} 筆模板格式錯誤：{exc}") from exc
        return templates

    def save_templates(self, data: list[dict[str, Any]]) -> list[dict[str, str]]:
        """Validate and atomically save a list of templates."""
        if not isinstance(data, list):
            raise TypeError("工單模板資料必須是 list")
        normalized_list = [self.normalize_template(item) for item in data]
        self._write_raw_templates(normalized_list)
        return normalized_list

    def add_template(self, template_dict: dict[str, Any]) -> dict[str, str]:
        """Append a new validated template and persist to disk."""
        normalized = self.normalize_template(template_dict)
        data = self.load_templates()
        data.append(normalized)
        self.save_templates(data)
        return normalized

    def duplicate_template(
        self,
        index: int,
        overrides: dict[str, Any] | None = None,
    ) -> dict[str, str]:
        """Duplicate an existing template at `index` (with optional field overrides) and append it."""
        data = self.load_templates()
        if not 0 <= index < len(data):
            raise IndexError(f"模板索引 {index} 超出範圍")
        copied = dict(data[index])
        if overrides:
            copied.update(overrides)
        normalized = self.normalize_template(copied)
        data.append(normalized)
        self.save_templates(data)
        return normalized

    def update_template(self, index: int, template_dict: dict[str, Any]) -> dict[str, str]:
        """Update an existing template at `index` and persist to disk."""
        data = self.load_templates()
        if not 0 <= index < len(data):
            raise IndexError(f"模板索引 {index} 超出範圍")
        normalized = self.normalize_template(template_dict)
        data[index] = normalized
        self.save_templates(data)
        return normalized

    def delete_template(self, index: int) -> dict[str, str]:
        """Delete the template at `index` and return the removed template."""
        data = self.load_templates()
        if not 0 <= index < len(data):
            raise IndexError(f"模板索引 {index} 超出範圍")
        deleted = data.pop(index)
        self.save_templates(data)
        return deleted

    def move_template(self, index: int, direction: int) -> int:
        """Move template at `index` by `direction` (-1 for up, +1 for down) and return new index."""
        data = self.load_templates()
        if not 0 <= index < len(data):
            raise IndexError(f"模板索引 {index} 超出範圍")

        target_index = index + direction
        if not 0 <= target_index < len(data):
            return index

        data[index], data[target_index] = data[target_index], data[index]
        self.save_templates(data)
        return target_index


def _fill_incident_ticket(
    page: Any,
    template: dict[str, str],
    base_url: str,
    credentials: dict[str, str],
) -> None:
    """Fill and submit an Incident Request ticket on the Service Desk sandbox."""
    page.goto(
        f"{base_url.rstrip('/')}/servicedesk/new?template=incident",
        wait_until="domcontentloaded",
    )
    login_portal_if_needed(page, credentials)

    # 1. Select requester (triggers native JS confirm, auto-accepted by BrowserSession)
    select_searchable_employee(
        page,
        "#requester-select-trigger",
        "#requester-select-input",
        template["email"],
    )

    # 2. Fill ticket subject
    page.locator("#input-ticket-subject").fill(template["title"])

    # 3. Select classification dropdowns
    select_searchable_employee(
        page,
        "#type-select-trigger",
        "#type-select-input",
        template["type"],
    )
    select_searchable_employee(
        page,
        "#subtype-select-trigger",
        "#subtype-select-input",
        template.get("sub_type") or "General Support",
    )
    select_searchable_employee(
        page,
        "#corp-select-trigger",
        "#corp-select-input",
        template.get("corp") or "Enterprise-HQ",
    )

    engineer_email = credentials.get("email") or "alex.chen@enterprise.local"
    tech_keyword = engineer_email.split("@")[0].strip() or "alex.chen"
    select_searchable_employee(
        page,
        "#tech-select-trigger",
        "#tech-select-input",
        tech_keyword,
    )

    # 4. Inject resolution into iframe#resolution-editor-frame > body.editor-body
    editor = page.frame_locator("#resolution-editor-frame").locator("body.editor-body")
    editor.wait_for(state="visible", timeout=5000)
    editor.click()
    editor.fill(template["resolve"])

    # 5. Submit form
    page.locator("#btn-submit-ticket").click()
    page.locator("#ticket-submit-banner").wait_for(state="visible", timeout=5000)
    page.wait_for_timeout(180)


def _fill_routine_ticket(
    page: Any,
    template: dict[str, str],
    base_url: str,
    credentials: dict[str, str],
) -> None:
    """Fill and submit a Routine Task ticket on the Service Desk sandbox."""
    page.goto(
        f"{base_url.rstrip('/')}/servicedesk/new?template=routine",
        wait_until="domcontentloaded",
    )
    login_portal_if_needed(page, credentials)

    # 1. Select requester (triggers native JS confirm, auto-accepted by BrowserSession)
    select_searchable_employee(
        page,
        "#requester-select-trigger",
        "#requester-select-input",
        template["email"],
    )

    # 2. Fill ticket subject
    page.locator("#input-ticket-subject").fill(template["title"])

    # 3. Select routine task type, scheduled date, and support group
    select_searchable_employee(
        page,
        "#type-select-trigger",
        "#type-select-input",
        template["type"],
    )
    page.locator("#btn-fill-today-date").click()
    select_searchable_employee(
        page,
        "#group-select-trigger",
        "#group-select-input",
        "IT-Site-Service",
    )

    # 4. Inject resolution into iframe#resolution-editor-frame > body.editor-body
    editor = page.frame_locator("#resolution-editor-frame").locator("body.editor-body")
    editor.wait_for(state="visible", timeout=5000)
    editor.click()
    editor.fill(template["resolve"])

    # 5. Submit form
    page.locator("#btn-submit-ticket").click()
    page.locator("#ticket-submit-banner").wait_for(state="visible", timeout=5000)
    page.wait_for_timeout(180)


def run_batch_tickets(
    browser_session: Any,
    prepared_templates: list[dict[str, Any]],
    base_url: str = "http://127.0.0.1:8000",
    credentials: dict[str, str] | None = None,
    storage: AppStorage | None = None,
) -> ServiceResult:
    """Execute batch Service Desk ticket creation for user-confirmed templates."""
    logger.info("開始執行批次服務台自動開單: count=%d", len(prepared_templates or []))
    page = None
    completed_count = 0
    store = storage or AppStorage()
    creds = credentials or CredentialStore().load()

    try:
        if not prepared_templates:
            raise ValueError("沒有選取任何工單模板")

        validated_templates = [
            TemplateRepository.normalize_template(item) for item in prepared_templates
        ]

        page = browser_session.new_page()

        for template in validated_templates:
            category = template["category"]
            logger.info("正在建立服務台工單: category=%s, title=%s", category, template["title"])

            if category == CATEGORY_INCIDENT:
                _fill_incident_ticket(page, template, base_url, creds)
                store.record_usage("incident_ticket")
            elif category == CATEGORY_ROUTINE:
                _fill_routine_ticket(page, template, base_url, creds)
                store.record_usage("routine_ticket")
            else:
                raise ValueError(f"不支援的工單類別：{category}")

            completed_count += 1

        logger.info("批次服務台自動開單完成: completed=%d", completed_count)
        return ServiceResult.success(
            message=f"IT 服務台自動開單完成，共成功建立 {completed_count} 筆工單。",
            data={
                "operation": "batch_tickets",
                "completed_count": completed_count,
            },
        )
    except Exception as exc:
        logger.exception("批次服務台自動開單發生錯誤")
        return ServiceResult.failed(
            message=(
                f"IT 服務台自動開單發生錯誤（已完成 {completed_count} 筆），"
                "已保留目前瀏覽器分頁供手動確認。"
            ),
            error=str(exc),
            data={
                "operation": "batch_tickets",
                "completed_count": completed_count,
                "keep_browser_page": page is not None,
            },
        )

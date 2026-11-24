"""Unified service execution result types and pure input validation functions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ServiceResult:
    """Result object returned by automation and service workflows.

    Valid status values:
    - "success"
    - "manual_confirmation"
    - "failed"
    - "cancelled"
    """

    status: str
    message: str
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    @property
    def is_success(self) -> bool:
        return self.status in {"success", "manual_confirmation"}

    @classmethod
    def success(
        cls,
        message: str,
        data: dict[str, Any] | None = None,
    ) -> ServiceResult:
        return cls(
            status="success",
            message=message,
            data=data or {},
        )

    @classmethod
    def manual_confirmation(
        cls,
        message: str,
        data: dict[str, Any] | None = None,
    ) -> ServiceResult:
        return cls(
            status="manual_confirmation",
            message=message,
            data=data or {},
        )

    @classmethod
    def failed(
        cls,
        message: str,
        error: str | None = None,
        data: dict[str, Any] | None = None,
    ) -> ServiceResult:
        return cls(
            status="failed",
            message=message,
            error=error,
            data=data or {},
        )


@dataclass
class ValidationResult:
    """Result of validating user input."""

    valid: bool
    value: Any = None
    message: str = ""


def normalize_asset_tag(value: str) -> tuple[str, str]:
    """Normalize an asset tag into ('IT-xxxxxx', 'xxxxxx').

    Accepts inputs like '100001', 'it-100001', 'IT100001', or 'IT-100001'.
    """
    cleaned = (value or "").strip().upper()
    if cleaned.startswith("IT-"):
        digits = cleaned[3:]
    elif cleaned.startswith("IT"):
        digits = cleaned[2:]
    else:
        digits = cleaned

    full_tag = f"IT-{digits}"
    return full_tag, digits


def validate_asset_tag(value: str) -> ValidationResult:
    """Validate a single enterprise asset tag (IT- followed by 6 digits)."""
    if value is None or not str(value).strip():
        return ValidationResult(valid=False, message="資產編號不可為空白")

    full_tag, digits = normalize_asset_tag(str(value))
    if len(digits) != 6:
        return ValidationResult(
            valid=False,
            message="資產編號數字部分長度應為 6 位數（例如 IT-100001）",
        )
    if not digits.isdigit():
        return ValidationResult(
            valid=False,
            message="資產編號只能包含 IT- 前綴與 6 位數字",
        )

    return ValidationResult(valid=True, value=(full_tag, digits))


def validate_asset_tag_lines(
    text: str | list[str],
    minimum_count: int = 1,
    maximum_count: int | None = None,
) -> ValidationResult:
    """Validate multiple asset tags from a multiline string or list of strings."""
    lines = text.splitlines() if isinstance(text, str) else list(text)

    valid_results: list[tuple[str, str]] = []
    errors: list[str] = []
    seen_tags: set[str] = set()

    for line_number, line in enumerate(lines, start=1):
        cleaned_line = str(line).strip()
        if not cleaned_line:
            continue

        result = validate_asset_tag(cleaned_line)
        if not result.valid:
            errors.append(f"第 {line_number} 行：{result.message}")
            continue

        full_tag, digits = result.value
        if full_tag in seen_tags:
            errors.append(f"第 {line_number} 行：資產編號 {full_tag} 重複輸入")
            continue

        seen_tags.add(full_tag)
        valid_results.append((full_tag, digits))

    if errors:
        return ValidationResult(valid=False, message="\n".join(errors))

    if len(valid_results) < minimum_count:
        return ValidationResult(
            valid=False,
            message=f"至少需要輸入 {minimum_count} 筆資產編號",
        )

    if maximum_count is not None and len(valid_results) > maximum_count:
        return ValidationResult(
            valid=False,
            message=f"此操作最多只能輸入 {maximum_count} 筆資產編號",
        )

    return ValidationResult(valid=True, value=valid_results)


def normalize_employee_id(value: str) -> str:
    """Normalize an employee ID into 'EMP...' format (e.g. 'EMP101').

    Accepts inputs like '101', 'emp101', 'EMP-101', or 'EMP101'.
    """
    cleaned = (value or "").strip().upper()
    if not cleaned:
        return ""
    if cleaned.startswith("EMP-"):
        body = cleaned[4:].strip()
    elif cleaned.startswith("EMP"):
        body = cleaned[3:].strip()
    else:
        body = cleaned

    return f"EMP{body}"


def validate_employee_id(value: str) -> ValidationResult:
    """Validate an employee ID (auto-prefixing EMP if omitted, e.g. '101' -> 'EMP101')."""
    if value is None or not str(value).strip():
        return ValidationResult(valid=False, message="請輸入員工工號")

    full_emp_id = normalize_employee_id(str(value))
    body = full_emp_id[3:]
    if not body or not body.isalnum():
        return ValidationResult(
            valid=False,
            message="員工工號只能包含英文字母與數字（例如 EMP101 或 101）",
        )

    return ValidationResult(valid=True, value=full_emp_id)


def validate_request_no(value: str) -> ValidationResult:
    """Validate a project/service request number (6 digits like '260101' or 'REQ-260101')."""
    cleaned = (value or "").strip().upper()
    if not cleaned:
        return ValidationResult(valid=False, message="請輸入申請單號")

    digits = cleaned[4:] if cleaned.startswith("REQ-") else cleaned
    if not digits.isdigit() or len(digits) != 6:
        return ValidationResult(
            valid=False,
            message="申請單號必須為 6 位數字或 REQ- 加上 6 位數字（例如 260101）",
        )

    return ValidationResult(valid=True, value=digits)


def validate_required_text(value: str, field_name: str) -> ValidationResult:
    """Validate a non-empty text field."""
    cleaned = (value or "").strip()
    if not cleaned:
        return ValidationResult(valid=False, message=f"請輸入{field_name}")
    return ValidationResult(valid=True, value=cleaned)


def validate_yes_no(value: str, field_name: str) -> ValidationResult:
    """Validate a Y/N choice."""
    cleaned = (value or "").strip().upper()
    if cleaned not in {"Y", "N"}:
        return ValidationResult(valid=False, message=f"請選擇{field_name}")
    return ValidationResult(valid=True, value=cleaned)


def validate_device_type(value: str) -> ValidationResult:
    """Validate returned computer device type (PC or NB)."""
    cleaned = (value or "").strip().upper()
    if cleaned not in {"PC", "NB"}:
        return ValidationResult(valid=False, message="請選擇繳回 PC 或 NB")
    return ValidationResult(valid=True, value=cleaned)

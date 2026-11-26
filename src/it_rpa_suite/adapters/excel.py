"""Lightweight pure-openpyxl Excel adapter for report parsing and filtering."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from openpyxl import load_workbook

from it_rpa_suite.adapters.logger import get_logger

logger = get_logger(__name__)

DEFAULT_BORROW_SHEET = "BORROW_DETAIL"
REQUIRED_BORROW_COLUMNS: frozenset[str] = frozenset(
    {
        "ASSET_CATEGORY",
        "SITE",
        "PURPOSE",
        "DELAY_DAY",
        "OWNER_EMAIL",
    }
)


def _normalize_cell_text(value: Any) -> str:
    """Convert cell value to stripped string, treating None/NaN as empty."""
    if value is None:
        return ""
    if isinstance(value, float) and value != value:  # NaN check
        return ""
    text = str(value).replace("\u00a0", " ").strip()
    if text.lower() == "nan":
        return ""
    return text


def _parse_numeric(value: Any) -> float | None:
    """Safely parse numeric cell values into float, returning None when invalid."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        if isinstance(value, float) and value != value:
            return None
        return float(value)
    text = _normalize_cell_text(value)
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def read_sheet_records(
    filepath: str | Path,
    *,
    sheet_name: str | None = None,
    required_columns: set[str] | frozenset[str] | None = None,
) -> list[dict[str, Any]]:
    """Read an Excel worksheet into a list of header-keyed dictionaries using read-only openpyxl.

    Always closes the workbook handle in ``finally`` to prevent Windows file-lock issues.
    """
    path = Path(filepath)
    if not path.is_file():
        raise FileNotFoundError(f"找不到 Excel 報表檔案：{path}")

    wb = load_workbook(filename=path, read_only=True, data_only=True)
    try:
        if sheet_name is not None:
            if sheet_name not in wb.sheetnames:
                raise ValueError(f"報表缺少必要工作表：{sheet_name}")
            ws = wb[sheet_name]
        else:
            ws = wb.active
            if ws is None:
                raise ValueError("Excel 檔案中沒有可用的工作表")

        rows_iter = ws.iter_rows(values_only=True)
        try:
            raw_headers = next(rows_iter)
        except StopIteration:
            return []

        headers: list[str] = [_normalize_cell_text(col) for col in raw_headers]
        header_set = {name for name in headers if name}

        if required_columns:
            missing = sorted(set(required_columns) - header_set)
            if missing:
                raise ValueError("報表缺少必要欄位：" + ", ".join(missing))

        records: list[dict[str, Any]] = []
        for raw_row in rows_iter:
            if raw_row is None or all(
                cell is None or _normalize_cell_text(cell) == "" for cell in raw_row
            ):
                continue
            record: dict[str, Any] = {}
            for idx, header in enumerate(headers):
                if not header:
                    continue
                record[header] = raw_row[idx] if idx < len(raw_row) else None
            records.append(record)

        return records
    finally:
        wb.close()


def parse_overdue_borrow_recipients(
    filepath: str | Path,
    site: str,
    *,
    sheet_name: str = DEFAULT_BORROW_SHEET,
    min_delay_days: float = 3.0,
) -> list[str]:
    """Filter overdue short-term laptop borrowers for ``site`` and return deduplicated emails.

    Filter criteria:
    - ``ASSET_CATEGORY`` in ``{"NB", "LAPTOP"}``
    - ``SITE`` equals ``site`` (trimmed, case-insensitive)
    - ``PURPOSE`` equals ``"SHORT_TERM_BORROW"``
    - ``DELAY_DAY`` > ``min_delay_days``
    """
    target_site = _normalize_cell_text(site).casefold()
    if not target_site:
        raise ValueError("廠區不可空白")

    records = read_sheet_records(
        filepath,
        sheet_name=sheet_name,
        required_columns=REQUIRED_BORROW_COLUMNS,
    )

    recipients: list[str] = []
    seen: set[str] = set()

    for row in records:
        category = _normalize_cell_text(row.get("ASSET_CATEGORY")).upper()
        row_site = _normalize_cell_text(row.get("SITE")).casefold()
        purpose = _normalize_cell_text(row.get("PURPOSE")).upper()
        delay_days = _parse_numeric(row.get("DELAY_DAY"))

        if category not in {"NB", "LAPTOP"}:
            continue
        if row_site != target_site:
            continue
        if purpose != "SHORT_TERM_BORROW":
            continue
        if delay_days is None or delay_days <= min_delay_days:
            continue

        email = _normalize_cell_text(row.get("OWNER_EMAIL"))
        if not email:
            continue

        email_key = email.casefold()
        if email_key in seen:
            continue
        seen.add(email_key)
        recipients.append(email)

    logger.info(
        "已完成逾期借用報表解析：site=%s, matched_recipients=%d",
        site,
        len(recipients),
    )
    return recipients

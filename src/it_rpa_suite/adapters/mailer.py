"""Outlook COM email draft adapter with automatic HTML preview fallback."""

from __future__ import annotations

import html
import os
import tempfile
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from it_rpa_suite.adapters.logger import get_logger

logger = get_logger(__name__)


@dataclass
class DraftEmail:
    """Represents an email draft created via Outlook COM or prepared for GUI preview fallback."""

    to: str
    subject: str
    html_body: str
    cc: str = ""
    bcc: str = ""
    used_fallback: bool = False
    fallback_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "to": self.to,
            "subject": self.subject,
            "html_body": self.html_body,
            "cc": self.cc,
            "bcc": self.bcc,
            "used_fallback": self.used_fallback,
            "fallback_reason": self.fallback_reason,
        }


def compose_or_preview_email(
    to: str,
    subject: str,
    html_body: str,
    cc: str = "",
    bcc: str = "",
    *,
    force_fallback: bool = False,
) -> DraftEmail:
    """Create an Outlook HTML email draft via COM, or fall back to structured preview data.

    In a background worker thread, COM must be initialized via `pythoncom.CoInitialize()`.
    If Classic Outlook is not installed, not configured, or `force_fallback=True`,
    this function never raises; instead it returns a `DraftEmail` with `used_fallback=True`
    so the GUI can present `HTMLPreviewDialog`.
    """
    env_force = os.getenv("IT_SUITE_FORCE_EMAIL_FALLBACK", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    if force_fallback or env_force:
        reason = "已啟用沙盒郵件安全預覽模式 (force_fallback)"
        logger.info("跳過 Outlook COM，使用內建郵件預覽模式: %s", subject)
        return DraftEmail(
            to=to,
            subject=subject,
            html_body=html_body,
            cc=cc,
            bcc=bcc,
            used_fallback=True,
            fallback_reason=reason,
        )

    pythoncom_mod: Any = None
    try:
        import pythoncom
        import win32com.client as win32

        pythoncom_mod = pythoncom
        pythoncom_mod.CoInitialize()

        outlook = win32.Dispatch("Outlook.Application")
        mail = outlook.CreateItem(0)
        mail.To = to
        if cc:
            mail.CC = cc
        if bcc:
            mail.BCC = bcc
        mail.Subject = subject
        mail.HTMLBody = html_body
        mail.Display()

        logger.info("已透過 Outlook COM 建立郵件草稿: subject=%s, to=%s", subject, to)
        return DraftEmail(
            to=to,
            subject=subject,
            html_body=html_body,
            cc=cc,
            bcc=bcc,
            used_fallback=False,
        )
    except Exception as exc:
        logger.info(
            "無法透過 Outlook COM 開啟草稿 (%s)，將改用內建 HTMLPreviewDialog 預覽",
            exc,
        )
        return DraftEmail(
            to=to,
            subject=subject,
            html_body=html_body,
            cc=cc,
            bcc=bcc,
            used_fallback=True,
            fallback_reason=str(exc),
        )
    finally:
        if pythoncom_mod is not None:
            try:
                pythoncom_mod.CoUninitialize()
            except Exception:
                pass


def render_standalone_email_html(draft: DraftEmail | dict[str, Any]) -> str:
    """Render a complete standalone HTML page for browser preview of a DraftEmail."""
    data = draft.to_dict() if isinstance(draft, DraftEmail) else dict(draft)
    to_addr = html.escape(str(data.get("to", "")))
    cc_addr = html.escape(str(data.get("cc", ""))) or "（無）"
    subject = html.escape(str(data.get("subject", "（無主旨）")))
    body_html = str(data.get("html_body", ""))

    return f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
  <meta charset="utf-8" />
  <title>郵件草稿預覽 — {subject}</title>
  <style>
    body {{
      margin: 0; padding: 32px 20px;
      background: #f1f5f9; color: #0f172a;
      font-family: "Microsoft JhengHei UI", "Segoe UI", sans-serif;
    }}
    .mail-container {{
      max-width: 880px; margin: 0 auto;
      background: #ffffff; border: 1px solid #cbd5e1;
      border-radius: 12px; overflow: hidden;
      box-shadow: 0 4px 20px rgba(15, 23, 42, 0.08);
    }}
    .mail-banner {{
      background: linear-gradient(135deg, #1e3a8a 0%, #2563eb 100%);
      color: #ffffff; padding: 16px 24px;
      font-size: 14px; font-weight: 600;
    }}
    .mail-meta {{
      padding: 18px 24px; background: #f8fafc;
      border-bottom: 1px solid #e2e8f0; font-size: 14px;
    }}
    .mail-meta div {{ margin-bottom: 8px; }}
    .mail-meta div:last-child {{ margin-bottom: 0; }}
    .mail-meta strong {{
      display: inline-block; width: 90px; color: #475569;
    }}
    .mail-body {{
      padding: 24px; line-height: 1.6; font-size: 14.5px;
    }}
    table {{
      width: 100%; border-collapse: collapse; margin-top: 14px;
    }}
    th, td {{
      border: 1px solid #cbd5e1; padding: 10px 12px; text-align: left; font-size: 13.5px;
    }}
    th {{
      background: #f1f5f9; font-weight: 700; color: #334155;
    }}
  </style>
</head>
<body>
  <div class="mail-container">
    <div class="mail-banner">
      📧 IT RPA Suite — 郵件草稿安全預覽 (Outlook Fallback Preview)
    </div>
    <div class="mail-meta">
      <div><strong>收件人 (To):</strong> {to_addr}</div>
      <div><strong>副本 (CC):</strong> {cc_addr}</div>
      <div><strong>主旨 (Subject):</strong> <b>{subject}</b></div>
    </div>
    <div class="mail-body">
      {body_html}
    </div>
  </div>
</body>
</html>"""


def open_draft_in_browser(draft: DraftEmail | dict[str, Any]) -> Path:
    """Write standalone HTML preview to a temporary file and open it in the default web browser."""
    full_html = render_standalone_email_html(draft)
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".html",
        prefix="it_suite_email_preview_",
        delete=False,
        encoding="utf-8",
    ) as tmp:
        tmp.write(full_html)
        temp_path = Path(tmp.name)

    try:
        webbrowser.open(temp_path.as_uri())
    except Exception:
        logger.warning("無法自動以瀏覽器開啟預覽檔: %s", temp_path, exc_info=True)
    return temp_path


class MailerAdapter:
    """Object-oriented adapter wrapper around compose_or_preview_email."""

    def __init__(self, *, force_fallback: bool = False) -> None:
        self.force_fallback = force_fallback

    def compose_or_preview(
        self,
        to: str,
        subject: str,
        html_body: str,
        cc: str = "",
        bcc: str = "",
    ) -> DraftEmail:
        return compose_or_preview_email(
            to=to,
            subject=subject,
            html_body=html_body,
            cc=cc,
            bcc=bcc,
            force_fallback=self.force_fallback,
        )

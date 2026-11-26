"""Minimalist GUI view for batch notifications (site persistence + 1x3 action buttons)."""

from __future__ import annotations

import tkinter as tk
from concurrent.futures import Future
from tkinter import ttk
from typing import Any

from it_rpa_suite.adapters.logger import get_logger
from it_rpa_suite.adapters.result import ServiceResult
from it_rpa_suite.app.theme import FONT_FAMILY, configure_ui_styles, scale
from it_rpa_suite.app.widgets import ModernDropdown, show_html_preview_dialog
from it_rpa_suite.features.batch_notify.service import (
    NOTIFICATION_ACTIONS,
    SITE_OPTIONS,
    NotificationActionSpec,
    run_overdue_borrow_notify,
)

logger = get_logger(__name__)

SITE_PLACEHOLDER = "請選擇廠區"


class BatchNotifyView(ttk.Frame):
    """Streamlined batch notification view with persisted site dropdown and 1x3 action buttons."""

    def __init__(
        self,
        parent: tk.Misc,
        app: Any,
        automation_worker: Any = None,
    ) -> None:
        self.app = app
        self.automation_worker = automation_worker or getattr(app, "automation_worker", None)
        self.sf: float = float(getattr(app, "scale_factor", 1.5))
        super().__init__(parent, style="Content.TFrame", padding=scale(20, self.sf))

        self.colors: dict[str, str] = getattr(
            app, "colors", getattr(self.winfo_toplevel(), "theme_colors", {})
        )
        self.color_text = self.colors.get("text", "#172033")
        self.color_muted = self.colors.get("text_secondary", "#667085")
        self.color_disabled = self.colors.get("text_muted", "#98A2B3")
        self.color_success = self.colors.get("success", "#16A36A")
        self.color_error = self.colors.get("danger", "#D84A4A")
        self.color_info = self.colors.get("primary", "#2D6CDF")
        self.color_card_bg = self.colors.get("surface", "#FFFFFF")
        self.color_card_disabled = self.colors.get("surface_soft", "#F8FAFC")
        self.color_card_hover = self.colors.get("card_hover", "#F0F5FD")
        self.color_card_border = self.colors.get("border", "#E4E9F0")

        self._toplevel = self.winfo_toplevel()
        self.current_future: Future[Any] | None = None
        self.action_buttons: dict[str, dict[str, Any]] = {}

        saved_site = self._load_saved_site()
        self.site_var = tk.StringVar(value=saved_site or SITE_PLACEHOLDER)
        self.status_var = tk.StringVar(value="")

        self._build_widgets()

    def s(self, value: float) -> int:
        return scale(value, self.sf)

    def _load_saved_site(self) -> str:
        storage = getattr(self.app, "storage", None)
        if storage is None or not hasattr(storage, "get_report_site"):
            return ""
        saved = str(storage.get_report_site() or "").strip()
        return saved if saved in SITE_OPTIONS else ""

    def _build_widgets(self) -> None:
        configure_ui_styles(self, sf=self.sf)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        wrapper = ttk.Frame(self, style="Content.TFrame")
        wrapper.grid(row=0, column=0, sticky="nsew")
        wrapper.columnconfigure(0, weight=1)
        wrapper.rowconfigure(0, weight=1)

        container = ttk.Frame(wrapper, style="Content.TFrame", padding=self.s(12))
        container.grid(row=0, column=0, sticky="ew", padx=self.s(12))
        container.columnconfigure(0, weight=1)

        ttk.Label(
            container,
            text="批量信件通知",
            foreground=self.color_text,
            font=(FONT_FAMILY, self.s(22), "bold"),
            anchor="center",
            justify="center",
        ).grid(row=0, column=0, sticky="ew", pady=(0, self.s(20)))

        # Site selector row (auto-persisted on selection)
        site_row = ttk.Frame(container, style="Content.TFrame")
        site_row.grid(row=1, column=0, pady=(0, self.s(26)))

        ttk.Label(
            site_row,
            text="所在廠區",
            foreground=self.color_muted,
            font=(FONT_FAMILY, self.s(10.5), "bold"),
        ).grid(row=0, column=0, padx=(0, self.s(12)))

        self.site_dropdown = ModernDropdown(
            site_row,
            options=SITE_OPTIONS,
            textvariable=self.site_var,
            placeholder=SITE_PLACEHOLDER,
            width=self.s(210),
            on_select=self._on_site_selected,
            sf=self.sf,
        )
        self.site_dropdown.grid(row=0, column=1)

        # 1x3 Action buttons row
        buttons_row = ttk.Frame(container, style="Content.TFrame")
        buttons_row.grid(row=2, column=0, sticky="ew", padx=self.s(24))
        for col_idx in range(len(NOTIFICATION_ACTIONS)):
            buttons_row.columnconfigure(col_idx, weight=1, uniform="batch_notify_cards")

        for col_idx, spec in enumerate(NOTIFICATION_ACTIONS):
            self._create_action_card(buttons_row, col_idx, spec)

        # Subtle inline status message (no popups)
        self.status_label = ttk.Label(
            container,
            textvariable=self.status_var,
            foreground=self.color_muted,
            font=(FONT_FAMILY, self.s(9.5)),
            anchor="center",
            justify="center",
            wraplength=self.s(640),
        )
        self.status_label.grid(row=3, column=0, sticky="ew", pady=(self.s(22), 0))

    def _create_action_card(
        self,
        parent: ttk.Frame,
        column: int,
        spec: NotificationActionSpec,
    ) -> tk.Frame:
        is_enabled = spec.enabled
        bg = self.color_card_bg if is_enabled else self.color_card_disabled
        border = self.color_info if is_enabled else self.color_card_border
        fg = self.color_text if is_enabled else self.color_disabled

        card = tk.Frame(
            parent,
            background=bg,
            highlightbackground=border,
            highlightcolor=self.color_info,
            highlightthickness=1,
            bd=0,
            cursor="hand2" if is_enabled else "arrow",
            padx=self.s(16),
            pady=self.s(20),
        )
        card.grid(
            row=0,
            column=column,
            sticky="nsew",
            padx=(0 if column == 0 else self.s(8), 0 if column == 2 else self.s(8)),
        )
        card.columnconfigure(0, weight=1)

        title_label = tk.Label(
            card,
            text=spec.title,
            background=bg,
            foreground=fg,
            font=(FONT_FAMILY, self.s(11.5), "bold"),
            anchor="center",
            justify="center",
            cursor="hand2" if is_enabled else "arrow",
        )
        title_label.grid(row=0, column=0, sticky="ew")

        tag_label = tk.Label(
            card,
            text="點擊執行" if is_enabled else "規劃中",
            background=bg,
            foreground=self.color_info if is_enabled else self.color_disabled,
            font=(FONT_FAMILY, self.s(8.5)),
            anchor="center",
        )
        tag_label.grid(row=1, column=0, pady=(self.s(6), 0))

        self.action_buttons[spec.key] = {
            "spec": spec,
            "frame": card,
            "title": title_label,
            "tag": tag_label,
            "enabled": is_enabled,
        }

        if is_enabled:
            widgets = (card, title_label, tag_label)

            def _on_click(_e: tk.Event[Any], key: str = spec.key) -> str:
                self._trigger_action(key)
                return "break"

            def _on_enter(_e: tk.Event[Any], key: str = spec.key) -> None:
                self._set_card_hover(key, True)

            def _on_leave(_e: tk.Event[Any], key: str = spec.key) -> None:
                self._set_card_hover(key, False)

            for widget in widgets:
                widget.bind("<Button-1>", _on_click)
                widget.bind("<Enter>", _on_enter)
                widget.bind("<Leave>", _on_leave)

        return card

    def _set_card_hover(self, key: str, hovering: bool) -> None:
        item = self.action_buttons.get(key)
        if not item or not item["enabled"]:
            return
        bg = self.color_card_hover if hovering else self.color_card_bg
        for part in ("frame", "title", "tag"):
            item[part].configure(background=bg)

    def _set_running_state(self, running: bool) -> None:
        self.site_dropdown.set_enabled(not running)
        for item in self.action_buttons.values():
            spec: NotificationActionSpec = item["spec"]
            active = spec.enabled and not running
            item["enabled"] = active
            bg = self.color_card_bg if active else self.color_card_disabled
            border = self.color_info if active else self.color_card_border
            fg = self.color_text if active else self.color_disabled
            tag_fg = self.color_info if active else self.color_disabled
            cursor = "hand2" if active else "arrow"
            item["frame"].configure(background=bg, highlightbackground=border, cursor=cursor)
            item["title"].configure(background=bg, foreground=fg, cursor=cursor)
            item["tag"].configure(background=bg, foreground=tag_fg, cursor=cursor)

    def _set_status(self, text: str, color: str | None = None) -> None:
        self.status_var.set(text)
        self.status_label.configure(foreground=color or self.color_muted)

    def _on_site_selected(self, selected: str | None = None) -> None:
        site = (selected or self.get_selected_site()).strip()
        if site not in SITE_OPTIONS:
            return
        storage = getattr(self.app, "storage", None)
        if storage is not None and hasattr(storage, "set_report_site"):
            storage.set_report_site(site)
        self._set_status("")

    def get_selected_site(self) -> str:
        return self.site_dropdown.get()

    def on_show(self) -> None:
        if not self.get_selected_site():
            self.after(50, self.site_dropdown.focus_set)

    def _trigger_action(self, action_key: str) -> None:
        if self.current_future is not None and not self.current_future.done():
            return
        if action_key != "overdue_borrow":
            return

        self.site_dropdown.close_popup()
        site = self.get_selected_site()
        if not site:
            self._set_status("請先選擇所在廠區", self.color_error)
            self.site_dropdown.focus_set()
            return

        if self.automation_worker is None:
            self._set_status("自動化工作引擎尚未啟動", self.color_error)
            return

        storage = getattr(self.app, "storage", None)
        if storage is not None and hasattr(storage, "set_report_site"):
            storage.set_report_site(site)

        cred_store = getattr(self.app, "credential_store", None)
        creds = cred_store.load() if cred_store is not None else None
        base_url = getattr(self.app, "sandbox_base_url", "http://127.0.0.1:8000")
        paths = getattr(self.app, "paths", None)

        self._set_running_state(True)
        self._set_status(f"正在下載並解析 {site} 逾期借用報表...", self.color_info)
        if hasattr(self.app, "update_browser_status"):
            self.app.update_browser_status(
                f"瀏覽器自動化：正在執行 {site} 逾期借用批量信件通知...",
                state="running",
            )

        self.current_future = self.automation_worker.submit(
            run_overdue_borrow_notify,
            site,
            base_url,
            creds,
            storage,
            paths,
        )
        self._toplevel.after(150, self._poll_future)

    def _is_view_alive(self) -> bool:
        try:
            return bool(self.winfo_exists())
        except tk.TclError:
            return False

    def _poll_future(self) -> None:
        if self.current_future is None or getattr(self.app, "closing", False):
            return
        if not self.current_future.done():
            try:
                if self._toplevel.winfo_exists():
                    self._toplevel.after(150, self._poll_future)
            except tk.TclError:
                pass
            return

        view_alive = self._is_view_alive()
        if view_alive:
            self._set_running_state(False)
        try:
            result = self.current_future.result()
        except Exception as exc:
            logger.exception("批量信件通知任務發生未預期錯誤")
            if view_alive:
                self._set_status(f"執行失敗：{exc}", self.color_error)
            if hasattr(self.app, "update_browser_status"):
                self.app.update_browser_status("瀏覽器自動化：批量信件通知失敗", state="off")
        else:
            self._handle_service_result(result, view_alive=view_alive)
        finally:
            self.current_future = None

    def _handle_service_result(self, result: Any, *, view_alive: bool = True) -> None:
        if not isinstance(result, ServiceResult):
            if hasattr(self.app, "update_browser_status"):
                self.app.update_browser_status("瀏覽器自動化：結果格式異常", state="off")
            return

        if hasattr(self.app, "refresh_usage_stats"):
            self.app.refresh_usage_stats()

        if result.is_success:
            if view_alive:
                self._set_status(result.message, self.color_success)
            if hasattr(self.app, "update_browser_status"):
                self.app.update_browser_status(f"瀏覽器自動化：{result.message}", state="ready")
            draft_email = (result.data or {}).get("draft_email")
            if isinstance(draft_email, dict) and draft_email.get("used_fallback"):
                target_parent = self if view_alive else self._toplevel
                active_sf = float(getattr(self.app, "scale_factor", self.sf))
                show_html_preview_dialog(target_parent, draft_email, sf=active_sf)
        else:
            error_text = f"{result.message}：{result.error}" if result.error else result.message
            if view_alive:
                self._set_status(error_text, self.color_error)
            if hasattr(self.app, "update_browser_status"):
                self.app.update_browser_status("瀏覽器自動化：批量信件通知失敗", state="off")

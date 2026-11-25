"""System credentials view supporting first-run onboarding, DPAPI storage, and network admin credential sync."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import messagebox, ttk
from typing import Any

from it_rpa_suite.adapters.credentials_dpapi import (
    CredentialStore,
    validate_credentials,
)
from it_rpa_suite.adapters.logger import get_logger
from it_rpa_suite.app.theme import FONT_FAMILY, configure_ui_styles, scale
from it_rpa_suite.app.widgets import (
    create_modern_entry,
    create_primary_button,
    create_secondary_button,
)

logger = get_logger(__name__)


class CredentialsView(ttk.Frame):
    """GUI view for configuring and encrypting enterprise portal & network admin credentials via DPAPI."""

    def __init__(
        self,
        parent: tk.Misc,
        app: Any,
        first_run: bool = False,
        on_saved: Callable[[], Any] | None = None,
    ) -> None:
        self.app = app
        self.sf: float = float(getattr(app, "scale_factor", 1.5))
        super().__init__(parent, style="Content.TFrame", padding=scale(20, self.sf))

        self.first_run = bool(first_run)
        self.on_saved = on_saved
        self.credential_store: CredentialStore = getattr(
            app, "credential_store", None
        ) or CredentialStore(paths=getattr(app, "paths", None))

        self._load_theme_colors()

        self.email_var = tk.StringVar()
        self.portal_account_var = tk.StringVar()
        self.portal_password_var = tk.StringVar()
        self.nac_account_var = tk.StringVar()
        self.nac_password_var = tk.StringVar()

        self.show_portal_password_var = tk.BooleanVar(value=False)
        self.show_nac_password_var = tk.BooleanVar(value=False)
        self.sync_nac_with_portal_var = tk.BooleanVar(value=False)
        self.status_var = tk.StringVar(value="")

        self.entries: list[ttk.Entry] = []

        self._load_existing_values()
        self._build_widgets()
        self._bind_events()

    def s(self, value: float) -> int:
        return scale(value, self.sf)

    def _load_theme_colors(self) -> None:
        colors: dict[str, str] = getattr(self.winfo_toplevel(), "theme_colors", {})
        self.colors = colors
        self.color_text = colors.get("text", "#172033")
        self.color_muted = colors.get("text_secondary", "#667085")
        self.color_success = colors.get("success", "#16A36A")
        self.color_error = colors.get("danger", "#D84A4A")
        self.color_info = colors.get("primary", "#2D6CDF")

    def _build_widgets(self) -> None:
        configure_ui_styles(self, sf=self.sf)

        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        wrapper = ttk.Frame(self, style="Content.TFrame")
        wrapper.grid(row=0, column=0, sticky="nsew")
        wrapper.columnconfigure(0, weight=1)
        wrapper.rowconfigure(0, weight=1)

        self.content_frame = ttk.Frame(wrapper, style="Content.TFrame", padding=self.s(14))
        self.content_frame.grid(row=0, column=0, sticky="ew", padx=self.s(16))
        self.content_frame.columnconfigure(0, weight=1)

        self._build_title()
        self._build_form()
        self._build_status_area()

    def _build_title(self) -> None:
        title = "初次設定系統憑證" if self.first_run else "系統憑證設定"
        subtitle = (
            "請完成工程師與系統帳號設定（或點擊下方按鈕填入沙盒範例憑證），完成後即可開始使用"
            if self.first_run
            else "管理自動化流程登入企業入口網與網管系統所需之加密憑證"
        )

        ttk.Label(
            self.content_frame,
            text=title,
            foreground=self.color_text,
            font=(FONT_FAMILY, self.s(22), "bold"),
            anchor="center",
            justify="center",
        ).grid(row=0, column=0, sticky="ew", pady=(0, self.s(6)))

        ttk.Label(
            self.content_frame,
            text=subtitle,
            foreground=self.color_muted,
            font=(FONT_FAMILY, self.s(10)),
            anchor="center",
            justify="center",
        ).grid(row=1, column=0, sticky="ew", pady=(0, self.s(18)))

    def _build_form(self) -> None:
        form_frame = ttk.Frame(
            self.content_frame,
            style="Content.TFrame",
            padding=(self.s(12), 0, self.s(12), 0),
        )
        form_frame.grid(row=2, column=0, sticky="ew")
        form_frame.columnconfigure(0, weight=1)

        self.email_entry = self._add_entry(
            form_frame,
            row=0,
            variable=self.email_var,
            placeholder="公司 Email (例如 alex.chen@enterprise.local)",
        )
        self.portal_account_entry = self._add_entry(
            form_frame,
            row=1,
            variable=self.portal_account_var,
            placeholder="企業入口網帳號",
        )
        self.portal_password_entry = self._add_entry(
            form_frame,
            row=2,
            variable=self.portal_password_var,
            placeholder="企業入口網密碼",
            password=True,
        )

        portal_options = ttk.Frame(form_frame, style="Content.TFrame")
        portal_options.grid(row=3, column=0, pady=(0, self.s(10)))
        ttk.Checkbutton(
            portal_options,
            text="顯示密碼",
            variable=self.show_portal_password_var,
            command=self._toggle_portal_password,
        ).grid(row=0, column=0)

        ttk.Separator(form_frame, orient="horizontal").grid(
            row=4,
            column=0,
            sticky="ew",
            padx=self.s(36),
            pady=(self.s(4), self.s(14)),
        )

        self.nac_account_entry = self._add_entry(
            form_frame,
            row=5,
            variable=self.nac_account_var,
            placeholder="網管帳號",
        )
        self.nac_password_entry = self._add_entry(
            form_frame,
            row=6,
            variable=self.nac_password_var,
            placeholder="網管密碼",
            password=True,
        )

        nac_options = ttk.Frame(form_frame, style="Content.TFrame")
        nac_options.grid(row=7, column=0, pady=(0, self.s(10)))
        ttk.Checkbutton(
            nac_options,
            text="顯示密碼",
            variable=self.show_nac_password_var,
            command=self._toggle_nac_password,
        ).grid(row=0, column=0, padx=(0, self.s(16)))

        self.sync_nac_checkbutton = ttk.Checkbutton(
            nac_options,
            text="網管帳密同上",
            variable=self.sync_nac_with_portal_var,
            command=self._toggle_nac_sync,
        )
        self.sync_nac_checkbutton.grid(row=0, column=1)

        ttk.Label(
            form_frame,
            text="以上憑證採用 Windows DPAPI (CryptProtectData) 本機加密保護",
            foreground=self.color_muted,
            font=(FONT_FAMILY, self.s(9.5)),
            justify="center",
            anchor="center",
        ).grid(row=8, column=0, sticky="ew", pady=(self.s(4), self.s(16)))

        button_frame = ttk.Frame(form_frame, style="Content.TFrame")
        button_frame.grid(row=9, column=0, pady=(self.s(6), 0))

        self.demo_button = create_secondary_button(
            button_frame,
            text="🎲 填入範例資料",
            command=self.fill_sample_data,
        )
        self.demo_button.pack(side="left", padx=(0, self.s(12)))

        self.save_button = create_primary_button(
            button_frame,
            text="儲存憑證資料",
            command=self._save,
        )
        self.save_button.pack(side="left")

    def _add_entry(
        self,
        parent: ttk.Frame,
        row: int,
        variable: tk.StringVar,
        placeholder: str,
        password: bool = False,
    ) -> ttk.Entry:
        entry = create_modern_entry(
            parent,
            owner=self,
            textvariable=variable,
            placeholder=placeholder,
            width=36,
        )
        entry.grid(row=row, column=0, pady=self.s(6))
        if password:
            entry.configure(show="*")
        self.entries.append(entry)
        return entry

    def _build_status_area(self) -> None:
        status_frame = ttk.Frame(self.content_frame, style="Content.TFrame")
        status_frame.grid(row=3, column=0, sticky="ew", pady=(self.s(18), 0))
        status_frame.columnconfigure(0, weight=1)

        self.status_label = ttk.Label(
            status_frame,
            textvariable=self.status_var,
            foreground=self.color_muted,
            font=(FONT_FAMILY, self.s(10)),
            wraplength=self.s(760),
            justify="center",
            anchor="center",
        )
        self.status_label.grid(row=0, column=0, sticky="ew")

    def _bind_events(self) -> None:
        for entry in self.entries[:-1]:
            entry.bind("<Return>", self._focus_next_widget)
        self.nac_password_entry.bind("<Return>", self._save_on_enter)

        self.portal_account_var.trace_add("write", self._sync_nac_credentials)
        self.portal_password_var.trace_add("write", self._sync_nac_credentials)

    def _load_existing_values(self) -> None:
        data = self.credential_store.load()
        self.email_var.set(str(data.get("email", "")))
        self.portal_account_var.set(str(data.get("portal_account", "")))
        self.nac_account_var.set(str(data.get("nac_account", "")))

    def fill_sample_data(self) -> None:
        """Populate sandbox demo credentials for instant portfolio testing."""
        self.email_var.set("alex.chen@enterprise.local")
        self.portal_account_var.set("it.admin")
        self.portal_password_var.set("Sandbox@2026")
        self.sync_nac_with_portal_var.set(True)
        self._toggle_nac_sync()
        self._set_status("已帶入沙盒範例憑證，請點擊「儲存憑證資料」完成設定", self.color_info)

    def on_show(self) -> None:
        self.after(50, self.email_entry.focus_set)

    def _set_status(self, message: str, color: str | None = None) -> None:
        self.status_var.set(str(message).replace("。", ""))
        if color:
            self.status_label.configure(foreground=color)

    def _focus_next_widget(self, event: Any) -> str:
        event.widget.tk_focusNext().focus_set()
        return "break"

    def _save_on_enter(self, _event: Any = None) -> str:
        self._save()
        return "break"

    def _toggle_portal_password(self) -> None:
        self.portal_password_entry.configure(
            show="" if self.show_portal_password_var.get() else "*"
        )

    def _toggle_nac_password(self) -> None:
        self.nac_password_entry.configure(show="" if self.show_nac_password_var.get() else "*")

    def _toggle_nac_sync(self) -> None:
        syncing = bool(self.sync_nac_with_portal_var.get())
        if syncing:
            self._sync_nac_credentials()

        state = "disabled" if syncing else "normal"
        self.nac_account_entry.configure(state=state)
        self.nac_password_entry.configure(state=state)

    def _sync_nac_credentials(self, *_args: Any) -> None:
        if not self.sync_nac_with_portal_var.get():
            return
        self.nac_account_var.set(self.portal_account_var.get())
        self.nac_password_var.set(self.portal_password_var.get())

    def _collect_credentials(self) -> dict[str, str]:
        return {
            "email": self.email_var.get().strip(),
            "portal_account": self.portal_account_var.get().strip(),
            "portal_password": self.portal_password_var.get(),
            "nac_account": self.nac_account_var.get().strip(),
            "nac_password": self.nac_password_var.get(),
        }

    def _focus_invalid_entry(self, error_message: str) -> None:
        field_entries = (
            ("Email", self.email_entry),
            ("企業入口網帳號", self.portal_account_entry),
            ("企業入口網密碼", self.portal_password_entry),
            ("網管帳號", self.nac_account_entry),
            ("網管密碼", self.nac_password_entry),
        )
        for keyword, entry in field_entries:
            if keyword in error_message:
                entry.focus_set()
                try:
                    entry.selection_range(0, tk.END)
                except tk.TclError:
                    pass
                return

    def _save(self) -> None:
        raw_data = self._collect_credentials()
        validation = validate_credentials(raw_data)
        if not validation.valid:
            self._set_status(validation.message, self.color_error)
            messagebox.showwarning("憑證資料不完整", validation.message, parent=self)
            self._focus_invalid_entry(validation.message)
            return

        if self.credential_store.exists() and not self.first_run:
            should_replace = messagebox.askyesno(
                "確認更新憑證",
                "儲存後將替換目前的加密帳號密碼設定。\n\n確定要繼續嗎？",
                parent=self,
            )
            if not should_replace:
                return

        self._set_controls_enabled(False)
        self._set_status("正在加密並儲存系統憑證", self.color_info)

        try:
            self.credential_store.save(validation.value)
        except Exception as exc:
            logger.exception("寫入 DPAPI 加密憑證時發生錯誤")
            self._set_status(f"憑證儲存失敗：{exc}", self.color_error)
            messagebox.showerror(
                "儲存失敗",
                f"憑證儲存失敗，請查看 data/logs/app.log。\n\n錯誤內容：{exc}",
                parent=self,
            )
        else:
            self._set_status("系統憑證已加密並成功儲存", self.color_success)
            messagebox.showinfo(
                "儲存完成",
                "系統憑證已使用 Windows DPAPI 加密並成功儲存。",
                parent=self,
            )
            self.portal_password_var.set("")
            self.nac_password_var.set("")

            if callable(self.on_saved):
                self.on_saved()
            else:
                self.app.set_global_status("系統憑證已更新")
                self.app.show_dashboard()
        finally:
            try:
                if self.winfo_exists():
                    self._set_controls_enabled(True)
            except tk.TclError:
                pass

    def _set_controls_enabled(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        controls: tuple[ttk.Entry | ttk.Button | ttk.Checkbutton, ...] = (
            *self.entries,
            self.save_button,
            self.demo_button,
            self.sync_nac_checkbutton,
        )
        for widget in controls:
            widget.configure(state=state)

        if enabled and self.sync_nac_with_portal_var.get():
            self.nac_account_entry.configure(state="disabled")
            self.nac_password_entry.configure(state="disabled")

"""GUI view for employee onboarding equipment provisioning and offboarding multi-system clearance."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from concurrent.futures import Future
from tkinter import messagebox, ttk
from typing import Any

from it_rpa_suite.adapters.logger import get_logger
from it_rpa_suite.adapters.result import ServiceResult, normalize_asset_tag
from it_rpa_suite.app.theme import FONT_FAMILY, configure_ui_styles, scale
from it_rpa_suite.app.widgets import (
    create_info_tooltip,
    create_modern_entry,
    create_primary_button,
    create_secondary_button,
    show_html_preview_dialog,
)
from it_rpa_suite.features.onboarding.service import (
    ACTION_OFFBOARDING,
    ACTION_ONBOARDING,
    run_offboarding_clearance,
    run_onboarding_issue,
    validate_offboarding_inputs,
    validate_onboarding_inputs,
)

logger = get_logger(__name__)


class OnboardingView(ttk.Frame):
    """Dual-mode view for New Hire Equipment Assignment and Employee Offboarding Clearance."""

    ONBOARDING_PRESETS = (
        {
            "request_no": "260201",
            "employee_id": "EMP104",
            "computer_tag": "IT-100002",
            "monitor_tag": "IT-200002",
            "deskphone": "Y",
        },
        {
            "request_no": "260202",
            "employee_id": "EMP101",
            "computer_tag": "IT-300002",
            "monitor_tag": "",
            "deskphone": "N",
        },
    )

    OFFBOARDING_PRESETS = (
        {
            "employee_id": "EMP103",
            "device_type": "NB",
            "deskphone": "N",
        },
        {
            "employee_id": "EMP101",
            "device_type": "PC",
            "deskphone": "Y",
        },
    )

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
        self.color_success = self.colors.get("success", "#16A36A")
        self.color_error = self.colors.get("danger", "#D84A4A")
        self.color_info = self.colors.get("primary", "#2D6CDF")
        self.color_card_bg = self.colors.get("surface_soft", "#F8FAFC")
        self.color_card_hover = self.colors.get("card_hover", "#F0F5FD")
        self.color_card_selected = self.colors.get("button_active", "#EEF2F7")
        self.color_card_border = self.colors.get("border", "#E4E9F0")
        self.color_card_selected_border = self.colors.get("primary", "#2D6CDF")
        self.color_disabled = self.colors.get("text_muted", "#98A2B3")

        self._toplevel = self.winfo_toplevel()
        self.current_future: Future[Any] | None = None
        self._onboard_preset_idx = 0
        self._offboard_preset_idx = 0

        self.action_var = tk.StringVar(value=ACTION_ONBOARDING)
        self.action_title_var = tk.StringVar(value="新人入職設備配發")
        self.status_var = tk.StringVar(value="")

        # Onboarding fields
        self.req_no_var = tk.StringVar()
        self.new_emp_id_var = tk.StringVar()
        self.computer_tag_var = tk.StringVar()
        self.monitor_tag_var = tk.StringVar()
        self.new_deskphone_var = tk.StringVar(value="N")

        # Offboarding fields
        self.quit_emp_id_var = tk.StringVar()
        self.device_type_var = tk.StringVar(value="NB")
        self.quit_deskphone_var = tk.StringVar(value="N")

        self._build_widgets()
        self._bind_traces_and_shortcuts()
        self._update_action_mode()

    def s(self, value: float) -> int:
        return scale(value, self.sf)

    def _build_widgets(self) -> None:
        configure_ui_styles(self, sf=self.sf)

        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        wrapper = ttk.Frame(self, style="Content.TFrame")
        wrapper.grid(row=0, column=0, sticky="nsew")
        wrapper.columnconfigure(0, weight=1)
        wrapper.rowconfigure(0, weight=1)

        self.content_frame = ttk.Frame(wrapper, style="Content.TFrame", padding=self.s(12))
        self.content_frame.grid(row=0, column=0, sticky="ew", padx=self.s(12))
        self.content_frame.columnconfigure(0, weight=1)

        self._build_header()
        self._build_action_selector()
        self._build_form_container()
        self._build_status_area()

    def _build_header(self) -> None:
        self.title_label = ttk.Label(
            self.content_frame,
            textvariable=self.action_title_var,
            foreground=self.color_text,
            font=(FONT_FAMILY, self.s(22), "bold"),
            anchor="center",
            justify="center",
        )
        self.title_label.grid(row=0, column=0, sticky="ew", pady=(0, self.s(12)))

    def _build_action_selector(self) -> None:
        selector_frame = ttk.Frame(self.content_frame, style="Content.TFrame")
        selector_frame.grid(row=2, column=0, pady=(self.s(4), self.s(18)))

        self.action_cards: dict[str, dict[str, Any]] = {}
        self.onboard_card = self._create_action_card(
            selector_frame,
            column=0,
            action=ACTION_ONBOARDING,
            title="新人入職配發",
        )
        self.offboard_card = self._create_action_card(
            selector_frame,
            column=1,
            action=ACTION_OFFBOARDING,
            title="員工離職清點",
        )
        self._refresh_action_cards()

    def _create_action_card(
        self,
        parent: ttk.Frame,
        column: int,
        action: str,
        title: str,
    ) -> tk.Frame:
        card = tk.Frame(
            parent,
            background=self.color_card_bg,
            highlightbackground=self.color_card_border,
            highlightcolor=self.color_card_selected_border,
            highlightthickness=1,
            bd=0,
            cursor="hand2",
            takefocus=1,
            padx=self.s(22),
            pady=self.s(8),
        )
        card.grid(
            row=0,
            column=column,
            padx=(0, self.s(8)) if column == 0 else (self.s(8), 0),
        )

        title_label = tk.Label(
            card,
            text=title,
            background=self.color_card_bg,
            foreground=self.color_text,
            font=(FONT_FAMILY, self.s(10.5), "bold"),
            anchor="center",
        )
        title_label.grid(row=0, column=0)

        def _on_select(_e: tk.Event[Any], val: str = action) -> Any:
            return self._select_action(val)

        def _on_enter(_e: tk.Event[Any], val: str = action) -> Any:
            return self._set_card_hover(val, True)

        def _on_leave(_e: tk.Event[Any], val: str = action) -> Any:
            return self._set_card_hover(val, False)

        for widget in (card, title_label):
            widget.bind("<Button-1>", _on_select)
            widget.bind("<Enter>", _on_enter)
            widget.bind("<Leave>", _on_leave)

        card.bind("<Return>", _on_select)
        card.bind("<space>", _on_select)
        card.bind("<Left>", lambda _e: self._select_action(ACTION_ONBOARDING))
        card.bind("<Right>", lambda _e: self._select_action(ACTION_OFFBOARDING))

        self.action_cards[action] = {
            "frame": card,
            "title": title_label,
            "enabled": True,
        }
        return card

    def _select_action(self, action: str) -> str:
        card_data = self.action_cards.get(action)
        if not card_data or not card_data["enabled"]:
            return "break"
        self.action_var.set(action)
        self._update_action_mode()
        return "break"

    def _set_card_hover(self, action: str, hovering: bool) -> None:
        card_data = self.action_cards.get(action)
        if not card_data or not card_data["enabled"]:
            return
        if self.action_var.get() == action:
            return
        bg = self.color_card_hover if hovering else self.color_card_bg
        card_data["frame"].configure(background=bg)
        card_data["title"].configure(background=bg)

    def _refresh_action_cards(self) -> None:
        selected_action = self.action_var.get()
        for action, card_data in self.action_cards.items():
            selected = action == selected_action
            enabled = card_data["enabled"]
            bg = self.color_card_selected if selected else self.color_card_bg
            border = self.color_card_selected_border if selected else self.color_card_border
            fg = (
                self.color_info
                if (selected and enabled)
                else (self.color_text if enabled else self.color_disabled)
            )
            card_data["frame"].configure(
                background=bg,
                highlightbackground=border,
                cursor="hand2" if enabled else "arrow",
            )
            card_data["title"].configure(background=bg, foreground=fg)

    def _build_form_container(self) -> None:
        self.form_container = ttk.Frame(self.content_frame, style="Content.TFrame")
        self.form_container.grid(row=3, column=0, sticky="ew")
        self.form_container.columnconfigure(0, weight=1)

        self.onboarding_frame = self._build_onboarding_form(self.form_container)
        self.offboarding_frame = self._build_offboarding_form(self.form_container)

    def _build_onboarding_form(self, parent: ttk.Frame) -> ttk.Frame:
        frame = ttk.Frame(
            parent,
            style="Content.TFrame",
            padding=(self.s(12), 0, self.s(12), 0),
        )
        frame.grid(row=0, column=0, sticky="ew")
        frame.columnconfigure(0, weight=1)

        self.req_no_entry = create_modern_entry(
            frame,
            owner=self,
            textvariable=self.req_no_var,
            placeholder="入職申請單號 (如 260201)",
            width=32,
        )
        self.req_no_entry.grid(row=0, column=0, pady=self.s(6))

        self.new_emp_id_entry = create_modern_entry(
            frame,
            owner=self,
            textvariable=self.new_emp_id_var,
            placeholder="新人員工工號 (可省略 EMP)",
            width=32,
        )
        self.new_emp_id_entry.grid(row=1, column=0, pady=self.s(6))

        comp_row = ttk.Frame(frame, style="Content.TFrame")
        comp_row.grid(row=2, column=0, pady=self.s(6))
        self.computer_tag_entry = create_modern_entry(
            comp_row,
            owner=self,
            textvariable=self.computer_tag_var,
            placeholder="電腦資產編號 (可省略 IT-，如 100002)",
            width=32,
        )
        self.computer_tag_entry.grid(row=0, column=0)
        comp_info = create_info_tooltip(
            self,
            comp_row,
            "智慧設備判別規則：\n• 預設 / 1 開頭桌機 (如 IT-100002)：顯示螢幕編號欄位，桌機自動加配 USB 鍵盤\n• 3 開頭筆電 (如 IT-300002)：免填螢幕（自動縮減為三個欄位），加配滑鼠、耳機與網路線",
        )
        comp_info.grid(row=0, column=1, padx=(self.s(6), 0))

        self.monitor_row_frame = ttk.Frame(frame, style="Content.TFrame")
        self.monitor_row_frame.grid(row=3, column=0, pady=self.s(6))
        self.monitor_tag_entry = create_modern_entry(
            self.monitor_row_frame,
            owner=self,
            textvariable=self.monitor_tag_var,
            placeholder="螢幕資產編號 (可省略 IT-，如 200002)",
            width=32,
        )
        self.monitor_tag_entry.grid(row=0, column=0)

        phone_frame = ttk.Frame(frame, style="Content.TFrame")
        phone_frame.grid(row=4, column=0, pady=(self.s(12), self.s(4)))
        ttk.Label(
            phone_frame,
            text="是否配發實體話機  ← →",
            foreground=self.color_text,
        ).grid(row=0, column=0, padx=(0, self.s(16)))

        self.new_phone_yes_btn = ttk.Radiobutton(
            phone_frame,
            text="有 (Y)",
            value="Y",
            variable=self.new_deskphone_var,
        )
        self.new_phone_yes_btn.grid(row=0, column=1, padx=(0, self.s(14)))

        self.new_phone_no_btn = ttk.Radiobutton(
            phone_frame,
            text="沒有 (N)",
            value="N",
            variable=self.new_deskphone_var,
        )
        self.new_phone_no_btn.grid(row=0, column=2)

        btn_frame = ttk.Frame(frame, style="Content.TFrame")
        btn_frame.grid(row=5, column=0, pady=(self.s(18), 0))

        self.new_demo_btn = create_secondary_button(
            btn_frame,
            text="🎲 填入範例資料",
            command=self.fill_sample_data,
        )
        self.new_demo_btn.pack(side="left", padx=(0, self.s(12)))

        self.new_run_btn = create_primary_button(
            btn_frame,
            text="執行新人配發",
            command=self._start_operation,
        )
        self.new_run_btn.pack(side="left")

        return frame

    def _build_offboarding_form(self, parent: ttk.Frame) -> ttk.Frame:
        frame = ttk.Frame(
            parent,
            style="Content.TFrame",
            padding=(self.s(12), 0, self.s(12), 0),
        )
        frame.grid(row=0, column=0, sticky="ew")
        frame.columnconfigure(0, weight=1)

        emp_row = ttk.Frame(frame, style="Content.TFrame")
        emp_row.grid(row=0, column=0, pady=self.s(6))
        self.quit_emp_id_entry = create_modern_entry(
            emp_row,
            owner=self,
            textvariable=self.quit_emp_id_var,
            placeholder="離職員工工號 (可省略 EMP)",
            width=32,
        )
        self.quit_emp_id_entry.grid(row=0, column=0)
        quit_info = create_info_tooltip(
            self,
            emp_row,
            "跨系統離職清點 4 步驟：\n1. HR 離職系統查詢單號並擷取交接表格 outerHTML\n2. 資產歸還系統載入保管設備與標準配件\n3. 電信系統查詢員工分機\n4. 產生停權通知信草稿（無 Outlook 時自動彈出內建 HTML 預覽視窗）",
        )
        quit_info.grid(row=0, column=1, padx=(self.s(6), 0))

        device_frame = ttk.Frame(frame, style="Content.TFrame")
        device_frame.grid(row=1, column=0, pady=(self.s(12), self.s(6)))
        ttk.Label(
            device_frame,
            text="繳回電腦類型  ← →",
            foreground=self.color_text,
        ).grid(row=0, column=0, padx=(0, self.s(16)))

        self.pc_radio_btn = ttk.Radiobutton(
            device_frame,
            text="桌機 (PC)",
            value="PC",
            variable=self.device_type_var,
        )
        self.pc_radio_btn.grid(row=0, column=1, padx=(0, self.s(14)))

        self.nb_radio_btn = ttk.Radiobutton(
            device_frame,
            text="筆電 (NB)",
            value="NB",
            variable=self.device_type_var,
        )
        self.nb_radio_btn.grid(row=0, column=2)

        phone_frame = ttk.Frame(frame, style="Content.TFrame")
        phone_frame.grid(row=2, column=0, pady=self.s(6))
        ttk.Label(
            phone_frame,
            text="繳回實體話機  ← →",
            foreground=self.color_text,
        ).grid(row=0, column=0, padx=(0, self.s(16)))

        self.quit_phone_yes_btn = ttk.Radiobutton(
            phone_frame,
            text="有 (Y)",
            value="Y",
            variable=self.quit_deskphone_var,
        )
        self.quit_phone_yes_btn.grid(row=0, column=1, padx=(0, self.s(14)))

        self.quit_phone_no_btn = ttk.Radiobutton(
            phone_frame,
            text="沒有 (N)",
            value="N",
            variable=self.quit_deskphone_var,
        )
        self.quit_phone_no_btn.grid(row=0, column=2)

        btn_frame = ttk.Frame(frame, style="Content.TFrame")
        btn_frame.grid(row=3, column=0, pady=(self.s(18), 0))

        self.quit_demo_btn = create_secondary_button(
            btn_frame,
            text="🎲 填入範例資料",
            command=self.fill_sample_data,
        )
        self.quit_demo_btn.pack(side="left", padx=(0, self.s(12)))

        self.quit_run_btn = create_primary_button(
            btn_frame,
            text="執行離職清點",
            command=self._start_operation,
        )
        self.quit_run_btn.pack(side="left")

        return frame

    def _build_status_area(self) -> None:
        self.status_label = ttk.Label(
            self.content_frame,
            textvariable=self.status_var,
            foreground=self.color_muted,
            font=(FONT_FAMILY, self.s(9.5)),
            wraplength=self.s(820),
            justify="center",
            anchor="center",
        )
        self.status_label.grid(row=4, column=0, sticky="ew", pady=(self.s(16), 0))

    def _bind_traces_and_shortcuts(self) -> None:
        self.computer_tag_var.trace_add("write", self._on_computer_tag_changed)

        self.req_no_entry.bind("<Return>", lambda _e: self._focus_next(self.new_emp_id_entry))
        self.new_emp_id_entry.bind("<Return>", lambda _e: self._focus_next(self.computer_tag_entry))
        self.computer_tag_entry.bind("<Return>", self._focus_after_computer_tag)
        self.monitor_tag_entry.bind(
            "<Return>",
            lambda _e: self._focus_next(
                self.new_phone_yes_btn
                if self.new_deskphone_var.get() == "Y"
                else self.new_phone_no_btn
            ),
        )
        self.quit_emp_id_entry.bind(
            "<Return>",
            lambda _e: self._focus_next(
                self.pc_radio_btn if self.device_type_var.get() == "PC" else self.nb_radio_btn
            ),
        )

        self._bind_radio_group(
            (self.new_phone_yes_btn, self.new_phone_no_btn),
            self.new_deskphone_var,
            ("Y", "N"),
            self._start_operation,
            execute_on_enter=True,
        )
        self._bind_radio_group(
            (self.pc_radio_btn, self.nb_radio_btn),
            self.device_type_var,
            ("PC", "NB"),
            lambda: (
                self.quit_phone_yes_btn
                if self.quit_deskphone_var.get() == "Y"
                else self.quit_phone_no_btn
            ),
            execute_on_enter=False,
        )
        self._bind_radio_group(
            (self.quit_phone_yes_btn, self.quit_phone_no_btn),
            self.quit_deskphone_var,
            ("Y", "N"),
            self._start_operation,
            execute_on_enter=True,
        )

    def _focus_next(self, widget: tk.Widget) -> str:
        self.after(0, widget.focus_set)
        return "break"

    def _focus_after_computer_tag(self, _event: Any = None) -> str:
        raw = self.computer_tag_var.get().strip()
        _, digits = normalize_asset_tag(raw)
        is_laptop = bool(digits) and not digits.startswith("1")
        if not is_laptop:
            return self._focus_next(self.monitor_tag_entry)
        target = (
            self.new_phone_yes_btn if self.new_deskphone_var.get() == "Y" else self.new_phone_no_btn
        )
        return self._focus_next(target)

    def _bind_radio_group(
        self,
        buttons: tuple[ttk.Radiobutton, ...],
        variable: tk.StringVar,
        values: tuple[str, ...],
        next_target: Callable[[], Any],
        *,
        execute_on_enter: bool = False,
    ) -> None:
        def move(direction: int) -> str:
            try:
                idx = values.index(variable.get())
            except ValueError:
                idx = 0
            new_idx = (idx + direction) % len(values)
            variable.set(values[new_idx])
            buttons[new_idx].focus_set()
            return "break"

        def on_enter(_event: Any = None) -> str:
            if execute_on_enter:
                next_target()
                return "break"
            target = next_target()
            if isinstance(target, tk.Widget):
                return self._focus_next(target)
            return "break"

        for btn in buttons:
            btn.bind("<Left>", lambda _e: move(-1))
            btn.bind("<Right>", lambda _e: move(1))
            btn.bind("<Return>", on_enter)

    def on_show(self) -> None:
        self.after(50, self._focus_active_form)

    def _focus_active_form(self) -> None:
        if self.action_var.get() == ACTION_ONBOARDING:
            self.req_no_entry.focus_set()
        else:
            self.quit_emp_id_entry.focus_set()

    def _update_action_mode(self) -> None:
        mode = self.action_var.get()
        self._refresh_action_cards()
        self._set_status("", self.color_muted)

        if mode == ACTION_ONBOARDING:
            self.offboarding_frame.grid_remove()
            self.onboarding_frame.grid()
            self.action_title_var.set("新人入職設備配發")
        else:
            self.onboarding_frame.grid_remove()
            self.offboarding_frame.grid()
            self.action_title_var.set("員工離職跨系統清點")

        self.after(50, self._focus_active_form)

    def _on_computer_tag_changed(self, *_args: Any) -> None:
        raw = self.computer_tag_var.get().strip()
        if not raw:
            self.monitor_row_frame.grid()
            return
        _, digits = normalize_asset_tag(raw)
        is_laptop = bool(digits) and not digits.startswith("1")
        if is_laptop:
            self.monitor_row_frame.grid_remove()
            if self.monitor_tag_var.get():
                self.monitor_tag_var.set("")
        else:
            self.monitor_row_frame.grid()

    def fill_sample_data(self) -> None:
        """Fill sample onboarding or offboarding data for instant portfolio testing."""
        self._set_status("", self.color_muted)
        if self.action_var.get() == ACTION_ONBOARDING:
            preset = self.ONBOARDING_PRESETS[
                self._onboard_preset_idx % len(self.ONBOARDING_PRESETS)
            ]
            self._onboard_preset_idx += 1
            self.req_no_var.set(preset["request_no"])
            self.new_emp_id_var.set(preset["employee_id"])
            self.computer_tag_var.set(preset["computer_tag"])
            self.monitor_tag_var.set(preset["monitor_tag"])
            self.new_deskphone_var.set(preset["deskphone"])
        else:
            preset = self.OFFBOARDING_PRESETS[
                self._offboard_preset_idx % len(self.OFFBOARDING_PRESETS)
            ]
            self._offboard_preset_idx += 1
            self.quit_emp_id_var.set(preset["employee_id"])
            self.device_type_var.set(preset["device_type"])
            self.quit_deskphone_var.set(preset["deskphone"])

    def _set_status(self, message: str, color: str | None = None) -> None:
        self.status_var.set((message or "").strip())
        if color:
            self.status_label.configure(foreground=color)

    def _start_operation(self) -> None:
        if self.current_future is not None and not self.current_future.done():
            self.app.set_global_status("目前已有入離職自動化作業正在執行中")
            return

        if self.automation_worker is None:
            messagebox.showerror("錯誤", "AutomationWorker 尚未初始化", parent=self)
            return

        base_url = getattr(self.app, "sandbox_base_url", "http://127.0.0.1:8000")
        creds = self.app.credential_store.load() if hasattr(self.app, "credential_store") else None
        storage = getattr(self.app, "storage", None)

        if self.action_var.get() == ACTION_ONBOARDING:
            val = validate_onboarding_inputs(
                request_no=self.req_no_var.get(),
                employee_id=self.new_emp_id_var.get(),
                computer_tag=self.computer_tag_var.get(),
                monitor_tag=self.monitor_tag_var.get(),
                deskphone=self.new_deskphone_var.get(),
            )
            if not val.valid:
                self._set_status(val.message, self.color_error)
                messagebox.showwarning("輸入資料錯誤", val.message, parent=self)
                return

            payload = val.value
            self.current_future = self.automation_worker.submit(
                run_onboarding_issue,
                payload["request_no"],
                payload["employee_id"],
                payload["computer_tag"],
                payload["computer_digits"],
                payload["monitor_tag"],
                payload["deskphone"],
                base_url,
                creds,
                storage,
            )
            self._set_status("正在執行新人設備配發與配件加配...", self.color_info)
            self.app.update_browser_status(
                "瀏覽器自動化：正在執行新人入職設備配發...", state="running"
            )
        else:
            val = validate_offboarding_inputs(
                employee_id=self.quit_emp_id_var.get(),
                device_type=self.device_type_var.get(),
                deskphone=self.quit_deskphone_var.get(),
            )
            if not val.valid:
                self._set_status(val.message, self.color_error)
                messagebox.showwarning("輸入資料錯誤", val.message, parent=self)
                return

            payload = val.value
            self.current_future = self.automation_worker.submit(
                run_offboarding_clearance,
                payload["employee_id"],
                payload["device_type"],
                payload["deskphone"],
                base_url,
                creds,
                storage,
            )
            self._set_status("正在跨系統查詢 HR 離職單、資產歸還與分機...", self.color_info)
            self.app.update_browser_status(
                "瀏覽器自動化：正在執行員工離職跨系統清點...", state="running"
            )

        self._set_running_state(True)
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
            logger.exception("入離職自動化任務發生未預期錯誤")
            if view_alive:
                self._set_status(f"執行失敗：{exc}", self.color_error)
            self.app.update_browser_status("瀏覽器自動化：任務執行失敗", state="off")
            messagebox.showerror(
                "執行失敗",
                f"執行入離職自動化作業時發生錯誤：\n\n{exc}",
                parent=self if view_alive else self._toplevel,
            )
        else:
            self._handle_service_result(result, view_alive=view_alive)
        finally:
            self.current_future = None

    def _handle_service_result(self, result: Any, *, view_alive: bool = True) -> None:
        if not isinstance(result, ServiceResult):
            self.app.update_browser_status("瀏覽器自動化：結果格式異常", state="off")
            return

        if hasattr(self.app, "refresh_usage_stats"):
            self.app.refresh_usage_stats()

        if result.is_success:
            if view_alive:
                self._set_status(result.message, self.color_success)
            self.app.update_browser_status(f"瀏覽器自動化：{result.message}", state="ready")
            draft_email = (result.data or {}).get("draft_email")
            if isinstance(draft_email, dict) and draft_email.get("used_fallback"):
                target_parent = self if view_alive else self._toplevel
                active_sf = float(getattr(self.app, "scale_factor", self.sf))
                show_html_preview_dialog(target_parent, draft_email, sf=active_sf)
        else:
            if view_alive:
                self._set_status(result.message, self.color_error)
            self.app.update_browser_status("瀏覽器自動化：執行失敗", state="off")
            detail = result.message
            if result.error:
                detail += f"\n\n錯誤原因：\n{result.error}"
            messagebox.showerror("執行失敗", detail, parent=self if view_alive else self._toplevel)

    def _set_running_state(self, running: bool) -> None:
        state = "disabled" if running else "normal"
        for card_data in self.action_cards.values():
            card_data["enabled"] = not running
        self._refresh_action_cards()

        for widget in (
            self.req_no_entry,
            self.new_emp_id_entry,
            self.computer_tag_entry,
            self.monitor_tag_entry,
            self.new_phone_yes_btn,
            self.new_phone_no_btn,
            self.new_demo_btn,
            self.new_run_btn,
            self.quit_emp_id_entry,
            self.pc_radio_btn,
            self.nb_radio_btn,
            self.quit_phone_yes_btn,
            self.quit_phone_no_btn,
            self.quit_demo_btn,
            self.quit_run_btn,
        ):
            try:
                widget.configure(state=state)
            except tk.TclError:
                pass

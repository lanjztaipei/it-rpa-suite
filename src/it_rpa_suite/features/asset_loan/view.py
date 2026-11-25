"""GUI view for equipment short loan, project loan, and return & custodian lookup."""

from __future__ import annotations

import re
import tkinter as tk
from concurrent.futures import Future
from tkinter import messagebox, ttk
from typing import Any

from it_rpa_suite.adapters.logger import get_logger
from it_rpa_suite.adapters.result import (
    ServiceResult,
    validate_asset_tag_lines,
)
from it_rpa_suite.app.theme import FONT_FAMILY, configure_ui_styles, scale
from it_rpa_suite.app.widgets import (
    BubbleList,
    create_info_tooltip,
    create_modern_entry,
    create_primary_button,
    create_secondary_button,
)
from it_rpa_suite.features.asset_loan.service import (
    OPERATION_PROJECT_LOAN,
    OPERATION_SHORT_LOAN,
    detect_loan_operation,
    run_project_loan,
    run_return_and_lookup,
    run_short_loan,
)

logger = get_logger(__name__)


class AssetLoanView(ttk.Frame):
    """Streamlined single-hand Enter view for asset short loan, project loan, and return lookup."""

    SAMPLE_PRESETS = (
        {
            "label": "短期借用範例",
            "tags": [("IT-300002", "300002")],
            "target": "EMP101",
        },
        {
            "label": "專案長借範例",
            "tags": [
                ("IT-100002", "100002"),
                ("IT-100003", "100003"),
                ("IT-100004", "100004"),
                ("IT-200002", "200002"),
                ("IT-200003", "200003"),
                ("IT-200004", "200004"),
                ("IT-300003", "300003"),
                ("IT-300005", "300005"),
                ("IT-300006", "300006"),
                ("IT-300007", "300007"),
            ],
            "target": "260101",
        },
        {
            "label": "歸還與查分機範例",
            "tags": [("IT-300001", "300001")],
            "target": "",
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

        self._toplevel = self.winfo_toplevel()
        self.current_future: Future[Any] | None = None
        self._error_hide_job: str | None = None
        self._sample_index = 0

        self.asset_tag_var = tk.StringVar()
        self.asset_error_var = tk.StringVar()
        self.borrower_or_req_var = tk.StringVar()
        self.operation_preview_var = tk.StringVar(value="設備借用 / 歸還與保管人聯查")

        self.validated_assets: list[tuple[str, str]] = []
        self.validated_asset_keys: set[str] = set()

        self._build_widgets()

        self.borrower_or_req_var.trace_add("write", self._on_target_input_changed)
        self.asset_tag_var.trace_add("write", self._update_auto_preview)
        self.asset_error_var.trace_add("write", self._update_error_visibility)

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

        container = ttk.Frame(wrapper, style="Content.TFrame", padding=self.s(12))
        container.grid(row=0, column=0, sticky="ew", padx=self.s(12))
        container.columnconfigure(0, weight=1)

        self.operation_result_label = ttk.Label(
            container,
            textvariable=self.operation_preview_var,
            foreground=self.color_text,
            font=(FONT_FAMILY, self.s(22), "bold"),
            wraplength=self.s(920),
            justify="center",
            anchor="center",
        )
        self.operation_result_label.grid(row=0, column=0, sticky="ew", pady=(0, self.s(6)))

        self.asset_bubble_list = BubbleList(
            container,
            owner=self,
            items=self.validated_assets,
            display_text=self._format_asset_item,
            on_remove=self._remove_asset_at_index,
            min_bubble_width=self.s(105),
        )
        self.asset_bubble_list.grid(row=2, column=0, sticky="ew", pady=(0, self.s(8)))

        asset_entry_row = ttk.Frame(container, style="Content.TFrame")
        asset_entry_row.grid(row=3, column=0)

        self.asset_entry = create_modern_entry(
            asset_entry_row,
            owner=self,
            textvariable=self.asset_tag_var,
            placeholder="資產編號 (可省略 IT-，如 300002)",
            width=32,
        )
        self.asset_entry.grid(row=0, column=0)

        self.asset_info_icon = create_info_tooltip(
            self,
            asset_entry_row,
            "支援多筆資產編號（按 Enter 逐筆加入氣泡標籤）：\n• 1 開頭：桌機 (IT-100001)\n• 3 開頭：筆電 (IT-300001)\n• 2 開頭：螢幕/周邊 (IT-200001)",
        )
        self.asset_info_icon.grid(row=0, column=1, padx=(self.s(6), 0))

        self.asset_entry.bind("<Return>", self._validate_asset_on_enter)
        self.asset_entry.bind("<Tab>", self._validate_asset_on_tab)

        self.asset_error_label = ttk.Label(
            container,
            textvariable=self.asset_error_var,
            foreground=self.color_error,
            font=(FONT_FAMILY, self.s(9.5)),
            wraplength=self.s(760),
            justify="center",
            anchor="center",
        )
        self.asset_error_label.grid(row=4, column=0, sticky="ew", pady=(self.s(4), self.s(2)))
        self.asset_error_label.grid_remove()

        target_entry_row = ttk.Frame(container, style="Content.TFrame")
        target_entry_row.grid(row=5, column=0, pady=(self.s(10), 0))

        self.target_entry = create_modern_entry(
            target_entry_row,
            owner=self,
            textvariable=self.borrower_or_req_var,
            placeholder="工號 (可省略 EMP) / 單號 (如 260101)",
            width=32,
        )
        self.target_entry.grid(row=0, column=0)

        self.target_info_icon = create_info_tooltip(
            self,
            target_entry_row,
            "智慧模式自動判別：\n• 資產編號 ＋ 工號 ＝ 短期借用\n• 資產編號 ＋ 單號 ＝ 專案長借\n• 僅輸入 1 筆資產編號 ＝ 歸還 & 查保管人分機",
        )
        self.target_info_icon.grid(row=0, column=1, padx=(self.s(6), 0))
        self.target_entry.bind("<Return>", self._start_operation_on_enter)

        button_frame = ttk.Frame(container, style="Content.TFrame")
        button_frame.grid(row=6, column=0, pady=(self.s(18), 0))

        self.demo_button = create_secondary_button(
            button_frame,
            text="🎲 填入範例資料",
            command=self.fill_sample_data,
        )
        self.demo_button.pack(side="left", padx=(0, self.s(12)))

        self.run_button = create_primary_button(
            button_frame,
            text="執行自動化作業",
            command=self._start_operation,
        )
        self.run_button.pack(side="left")

    def on_show(self) -> None:
        self.after(50, self.asset_entry.focus_set)

    def fill_sample_data(self) -> None:
        """Cycle through the 3 demo scenarios (Short Loan -> Project Loan -> Return Lookup)."""
        preset = self.SAMPLE_PRESETS[self._sample_index % len(self.SAMPLE_PRESETS)]
        self._sample_index += 1

        self.validated_assets.clear()
        self.validated_asset_keys.clear()
        for full_tag, digits in preset["tags"]:
            self.validated_assets.append((full_tag, digits))
            self.validated_asset_keys.add(full_tag)

        self.asset_tag_var.set("")
        self.asset_error_var.set("")
        self.borrower_or_req_var.set(str(preset["target"]))
        self.asset_bubble_list.render()
        self._update_auto_preview()

    @staticmethod
    def _format_asset_item(item: Any) -> str:
        if isinstance(item, tuple) and item:
            return str(item[0]).upper()
        match = re.search(r"IT-[0-9]{6}", str(item), flags=re.IGNORECASE)
        return match.group(0).upper() if match else str(item).strip().upper()

    def _update_error_visibility(self, *_args: Any) -> None:
        msg = (self.asset_error_var.get() or "").replace("。", "")
        if self._error_hide_job is not None:
            try:
                self.after_cancel(self._error_hide_job)
            except tk.TclError:
                pass
            self._error_hide_job = None

        if msg:
            self.asset_error_label.grid()
            self._error_hide_job = self.after(3200, lambda: self.asset_error_var.set(""))
        else:
            self.asset_error_label.grid_remove()

    def _validate_asset_on_enter(self, _event: Any = None) -> str:
        raw_tag = self.asset_tag_var.get().strip()
        if not raw_tag:
            self.asset_error_var.set("請輸入資產編號")
            self.asset_entry.focus_set()
            return "break"

        validation = validate_asset_tag_lines(raw_tag, minimum_count=1, maximum_count=1)
        if not validation.valid:
            self.asset_error_var.set(validation.message or "資產編號格式錯誤")
            self.asset_entry.selection_range(0, tk.END)
            self.asset_entry.focus_set()
            return "break"

        is_first_item = len(self.validated_assets) == 0
        added = 0
        duplicates = 0

        for full_tag, digits in validation.value:
            key = full_tag.upper()
            if key in self.validated_asset_keys:
                duplicates += 1
                continue
            self.validated_assets.append((full_tag, digits))
            self.validated_asset_keys.add(key)
            added += 1

        if added > 0:
            self.asset_bubble_list.render()
            self.asset_tag_var.set("")
            self.asset_error_var.set("")
            self._update_auto_preview()

        if duplicates > 0:
            self.asset_tag_var.set("")
            self.asset_error_var.set("此資產編號已加入清單，不會重複新增")

        if is_first_item and added > 0:
            self.after(0, self.target_entry.focus_set)
        else:
            self.after(0, self.asset_entry.focus_set)
        return "break"

    def _validate_asset_on_tab(self, _event: Any = None) -> str:
        pending = self.asset_tag_var.get().strip()
        if pending:
            self._validate_asset_on_enter()
            if self.asset_tag_var.get().strip():
                return "break"
        elif not self.validated_assets:
            self.asset_error_var.set("請先輸入資產編號")
            self.asset_entry.focus_set()
            return "break"
        else:
            self.asset_error_var.set("")

        self.after(0, self.target_entry.focus_set)
        return "break"

    def _remove_asset_at_index(self, index: int) -> None:
        if self.asset_bubble_list.disabled:
            return
        if 0 <= index < len(self.validated_assets):
            full_tag, _ = self.validated_assets[index]
            del self.validated_assets[index]
            self.validated_asset_keys.discard(full_tag.upper())
            self.asset_bubble_list.render()
            self._update_auto_preview()
            self.asset_entry.focus_set()

    def _on_target_input_changed(self, *_args: Any) -> None:
        self._update_auto_preview()

    def _update_auto_preview(self, *_args: Any) -> None:
        count = len(self.validated_assets)
        pending_tag = self.asset_tag_var.get().strip()
        target_val = self.borrower_or_req_var.get().strip()

        effective_count = count + (1 if pending_tag else 0)
        if effective_count == 0:
            self.operation_preview_var.set("設備借用 / 歸還與保管人聯查")
            self.operation_result_label.configure(foreground=self.color_text)
            return

        if target_val:
            upper_target = target_val.upper()
            if (upper_target.isdigit() and len(upper_target) == 6) or upper_target.startswith(
                "REQ-"
            ):
                self.operation_preview_var.set(
                    f"專案長借 (Project Loan) — 共 {effective_count} 筆設備"
                )
            else:
                self.operation_preview_var.set(
                    f"短期借用 (Short Loan) — 共 {effective_count} 筆設備"
                )
            self.operation_result_label.configure(foreground=self.color_success)
        elif effective_count == 1:
            self.operation_preview_var.set("歸還 & 查保管人分機 (Return & Lookup)")
            self.operation_result_label.configure(foreground=self.color_info)
        else:
            self.operation_preview_var.set("歸還限單筆資產編號（若要借用請填寫工號或單號）")
            self.operation_result_label.configure(foreground=self.color_error)

    def _start_operation_on_enter(self, _event: Any = None) -> str:
        self._start_operation()
        return "break"

    def _start_operation(self) -> None:
        if self.current_future is not None and not self.current_future.done():
            self.app.set_global_status("目前已有設備借還自動化任務正在執行中")
            return

        pending = self.asset_tag_var.get().strip()
        if pending:
            self._validate_asset_on_enter()
            if self.asset_tag_var.get().strip():
                return

        detection = detect_loan_operation(
            self.validated_assets,
            self.borrower_or_req_var.get(),
        )
        if not detection.valid:
            self.asset_error_var.set(detection.message)
            return

        payload = detection.value
        operation = payload["operation"]
        asset_tags = payload["asset_tags"]
        base_url = getattr(self.app, "sandbox_base_url", "http://127.0.0.1:8000")
        creds = self.app.credential_store.load() if hasattr(self.app, "credential_store") else None
        storage = getattr(self.app, "storage", None)

        if self.automation_worker is None:
            messagebox.showerror("錯誤", "AutomationWorker 尚未初始化", parent=self)
            return

        if operation == OPERATION_SHORT_LOAN:
            self.current_future = self.automation_worker.submit(
                run_short_loan,
                asset_tags,
                payload["employee_id"],
                base_url,
                creds,
                storage,
            )
        elif operation == OPERATION_PROJECT_LOAN:
            self.current_future = self.automation_worker.submit(
                run_project_loan,
                asset_tags,
                payload["request_no"],
                base_url,
                creds,
                storage,
            )
        else:
            self.current_future = self.automation_worker.submit(
                run_return_and_lookup,
                asset_tags,
                base_url,
                creds,
                storage,
            )

        self._set_running_state(True)
        self.app.update_browser_status("瀏覽器自動化：正在執行設備借還作業...", state="running")
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
            logger.exception("設備借還背景任務發生未預期錯誤")
            self.app.update_browser_status("瀏覽器自動化：任務執行失敗", state="off")
            messagebox.showerror(
                "執行失敗",
                f"執行設備借還自動化時發生錯誤：\n\n{exc}",
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
            self.app.update_browser_status(f"瀏覽器自動化：{result.message}", state="ready")
            if view_alive:
                self._reset_inputs()
        else:
            self.app.update_browser_status("瀏覽器自動化：執行失敗", state="off")
            detail = result.message
            if result.error:
                detail += f"\n\n錯誤原因：\n{result.error}"
            messagebox.showerror("執行失敗", detail, parent=self if view_alive else self._toplevel)

    def _set_running_state(self, running: bool) -> None:
        state = "disabled" if running else "normal"
        self.run_button.configure(state=state)
        self.demo_button.configure(state=state)
        self.asset_entry.configure(state=state)
        self.target_entry.configure(state=state)
        self.asset_bubble_list.set_disabled(running)

    def _reset_inputs(self) -> None:
        self.asset_tag_var.set("")
        self.borrower_or_req_var.set("")

        self.validated_assets.clear()
        self.validated_asset_keys.clear()
        self.asset_bubble_list.render()
        self.asset_error_var.set("")
        self._update_auto_preview()
        self.after(50, self.asset_entry.focus_set)

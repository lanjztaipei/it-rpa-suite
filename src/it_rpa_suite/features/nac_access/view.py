"""GUI view for network access unlock (single/dual MAC real-time preview)."""

from __future__ import annotations

import tkinter as tk
from concurrent.futures import Future
from tkinter import messagebox, ttk
from typing import Any

from it_rpa_suite.adapters.logger import get_logger
from it_rpa_suite.adapters.result import ServiceResult
from it_rpa_suite.app.theme import FONT_FAMILY, configure_ui_styles, scale
from it_rpa_suite.app.widgets import (
    create_info_tooltip,
    create_modern_entry,
    create_primary_button,
    create_secondary_button,
)
from it_rpa_suite.features.nac_access.service import (
    preview_nac_unlock_mode,
    run_nac_unlock,
    validate_nac_asset_input,
)

logger = get_logger(__name__)


class NacAccessView(ttk.Frame):
    """GUI view for network access unlock with real-time NIC mode preview."""

    SAMPLE_TAGS = (
        "IT-300001",  # Laptop: Wired + Wi-Fi MAC
        "IT-100001",  # Desktop: Wired MAC only
        "IT-300004",  # Laptop: Wired + Wi-Fi MAC
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
        self._sample_idx = 0

        self.asset_tag_var = tk.StringVar()
        self.preview_mode_var = tk.StringVar(value="等待輸入設備資產編號")
        self.status_var = tk.StringVar(value="")

        self._build_widgets()
        self._bind_events()

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

        ttk.Label(
            container,
            text="網路存取授權開通",
            foreground=self.color_text,
            font=(FONT_FAMILY, self.s(22), "bold"),
            anchor="center",
            justify="center",
        ).grid(row=0, column=0, sticky="ew", pady=(0, self.s(6)))

        entry_row = ttk.Frame(container, style="Content.TFrame")
        entry_row.grid(row=2, column=0, pady=self.s(6))

        self.asset_entry = create_modern_entry(
            entry_row,
            owner=self,
            textvariable=self.asset_tag_var,
            placeholder="設備資產編號 (可省略 IT-，如 300001)",
            width=32,
        )
        self.asset_entry.grid(row=0, column=0)

        info_icon = create_info_tooltip(
            self,
            entry_row,
            "自動判定開通模式：\n• 1 開頭桌機 (如 IT-100001)：開通單網卡 (Wired MAC)\n• 3 開頭筆電 (如 IT-300001)：自動連續開通雙網卡 (Wired + Wi-Fi MAC)\n\n技術特點：跨分頁擷取 MAC 後自動關閉明細頁，並穿透 navFrame / mainFrame 攔截 window.open 彈窗。",
        )
        info_icon.grid(row=0, column=1, padx=(self.s(6), 0))

        preview_row = ttk.Frame(container, style="Content.TFrame")
        preview_row.grid(row=3, column=0, pady=(self.s(12), self.s(6)))

        ttk.Label(
            preview_row,
            text="預計開通模式：",
            foreground=self.color_text,
        ).grid(row=0, column=0, padx=(0, self.s(8)))

        self.preview_label = ttk.Label(
            preview_row,
            textvariable=self.preview_mode_var,
            foreground=self.color_muted,
            font=(FONT_FAMILY, self.s(10.5), "bold"),
        )
        self.preview_label.grid(row=0, column=1)

        btn_frame = ttk.Frame(container, style="Content.TFrame")
        btn_frame.grid(row=4, column=0, pady=(self.s(16), 0))

        self.demo_button = create_secondary_button(
            btn_frame,
            text="🎲 填入範例資料",
            command=self.fill_sample_data,
        )
        self.demo_button.pack(side="left", padx=(0, self.s(12)))

        self.run_button = create_primary_button(
            btn_frame,
            text="執行網路權限開通",
            command=self._start_operation,
        )
        self.run_button.pack(side="left")

        self.status_label = ttk.Label(
            container,
            textvariable=self.status_var,
            foreground=self.color_muted,
            font=(FONT_FAMILY, self.s(9.5)),
            wraplength=self.s(820),
            justify="center",
            anchor="center",
        )
        self.status_label.grid(row=5, column=0, sticky="ew", pady=(self.s(18), 0))

    def _bind_events(self) -> None:
        self.asset_tag_var.trace_add("write", self._on_asset_tag_changed)
        self.asset_entry.bind("<Return>", self._start_operation_on_enter)

    def on_show(self) -> None:
        self.after(50, self.asset_entry.focus_set)

    def fill_sample_data(self) -> None:
        """Cycle through sample Laptop (dual MAC) and Desktop (single MAC) asset tags."""
        tag = self.SAMPLE_TAGS[self._sample_idx % len(self.SAMPLE_TAGS)]
        self._sample_idx += 1
        self.asset_tag_var.set(tag)
        self._set_status("", self.color_muted)

    def _on_asset_tag_changed(self, *_args: Any) -> None:
        preview_text, role = preview_nac_unlock_mode(self.asset_tag_var.get())
        self.preview_mode_var.set(preview_text)
        color_map = {
            "success": self.color_success,
            "info": self.color_info,
            "error": self.color_error,
            "muted": self.color_muted,
        }
        self.preview_label.configure(foreground=color_map.get(role, self.color_info))

    def _set_status(self, message: str, color: str | None = None) -> None:
        self.status_var.set((message or "").strip())
        if color:
            self.status_label.configure(foreground=color)

    def _start_operation_on_enter(self, _event: Any = None) -> str:
        self._start_operation()
        return "break"

    def _start_operation(self) -> None:
        if self.current_future is not None and not self.current_future.done():
            self.app.set_global_status("目前已有網路權限開通工作正在執行中")
            return

        val = validate_nac_asset_input(self.asset_tag_var.get())
        if not val.valid:
            self._set_status(val.message, self.color_error)
            messagebox.showwarning("資產編號格式錯誤", val.message, parent=self)
            self.asset_entry.focus_set()
            try:
                self.asset_entry.selection_range(0, tk.END)
            except tk.TclError:
                pass
            return

        if self.automation_worker is None:
            messagebox.showerror("錯誤", "AutomationWorker 尚未初始化", parent=self)
            return

        full_tag, digits = val.value
        base_url = getattr(self.app, "sandbox_base_url", "http://127.0.0.1:8000")
        creds = self.app.credential_store.load() if hasattr(self.app, "credential_store") else None
        storage = getattr(self.app, "storage", None)

        self.current_future = self.automation_worker.submit(
            run_nac_unlock,
            full_tag,
            digits,
            base_url,
            creds,
            storage,
        )

        self._set_running_state(True)
        target_desc = (
            "雙網卡 (Wired + Wi-Fi MAC)" if digits.startswith("3") else "單網卡 (Wired MAC)"
        )
        self._set_status(
            f"正在查詢資產 {full_tag} 明細並開通 {target_desc}...",
            self.color_info,
        )
        self.app.update_browser_status(
            f"瀏覽器自動化：正在執行網路權限開通 ({full_tag})...",
            state="running",
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
            logger.exception("網路權限開通任務發生未預期錯誤")
            if view_alive:
                self._set_status(f"執行失敗：{exc}", self.color_error)
            self.app.update_browser_status("瀏覽器自動化：任務執行失敗", state="off")
            messagebox.showerror(
                "執行失敗",
                f"執行網路權限開通時發生未預期錯誤：\n\n{exc}",
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
            if view_alive:
                self.asset_tag_var.set("")
                self.after(50, self.asset_entry.focus_set)
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
        self.asset_entry.configure(state=state)
        self.demo_button.configure(state=state)
        self.run_button.configure(state=state)

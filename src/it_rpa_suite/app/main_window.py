"""Main application window, sidebar navigation, status bar, and debounced scaling."""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import tkinter as tk
from collections.abc import Callable
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Any

from it_rpa_suite import __version__
from it_rpa_suite.adapters.browser_worker import get_slow_mo_ms
from it_rpa_suite.adapters.credentials_dpapi import CredentialStore
from it_rpa_suite.adapters.logger import get_logger
from it_rpa_suite.adapters.paths import AppPaths, get_app_paths
from it_rpa_suite.adapters.storage import AppStorage
from it_rpa_suite.adapters.update_checker import (
    UpdateCheckResult,
    UpdateCheckStatus,
    check_for_updates,
    format_timestamp,
)
from it_rpa_suite.app.theme import FONT_FAMILY, ThemeManager, scale
from it_rpa_suite.app.widgets import (
    ModernScrollbar,
    ToggleSwitch,
    show_confirm_dialog,
)
from it_rpa_suite.features.credentials.view import CredentialsView
from it_rpa_suite.features.dashboard.view import DashboardView

logger = get_logger(__name__)


class MainWindow:
    """Primary GUI container managing sidebar routing, theme switching, and responsive scaling."""

    def __init__(
        self,
        root: tk.Tk,
        paths: AppPaths | None = None,
        storage: AppStorage | None = None,
        credential_store: CredentialStore | None = None,
        automation_worker: Any = None,
        mock_server: Any = None,
        caller_monitor: Any = None,
        on_close_callback: Callable[[], Any] | None = None,
    ) -> None:
        self.root = root
        self.paths = paths or get_app_paths()
        self.storage = storage or AppStorage(paths=self.paths)
        self.credential_store = credential_store or CredentialStore(paths=self.paths)
        self.automation_worker = automation_worker
        self.mock_server = mock_server
        self.caller_monitor = caller_monitor
        self.on_close_callback = on_close_callback

        self.current_view: tk.Widget | None = None
        self.closing = False
        self._checking_update = False

        is_dark = self.storage.get_dark_mode()
        self.theme = ThemeManager(is_dark_mode=is_dark, initial_scale=1.5)
        self.is_dark_mode = self.theme.is_dark_mode
        self.colors = self.theme.colors
        self.scale_factor = self.theme.scale_factor

        self.caller_id_enabled = self.storage.get_caller_id_enabled()
        self.background_switch_var = tk.BooleanVar(value=self.caller_id_enabled)
        self.browser_status_var = tk.StringVar(value="瀏覽器自動化：待機中")
        self.feature_usage_stats: dict[str, int | float] = {}
        self.refresh_usage_stats()

        self._configure_root()
        self._configure_style()
        self._build_application_container()
        self.root.protocol("WM_DELETE_WINDOW", self.request_close)

    def s(self, value: float) -> int:
        return scale(value, self.scale_factor)

    def refresh_usage_stats(self) -> dict[str, int | float]:
        """Reload usage statistics from SQLite and settings coefficients."""
        self.feature_usage_stats = self.storage.get_usage_stats()
        return self.feature_usage_stats

    def record_feature_usage(self, feature_key: str, count: int = 1) -> None:
        """Record feature usage in SQLite and refresh in-memory KPI stats."""
        self.storage.record_usage(feature_key, count=count)
        self.refresh_usage_stats()

    @property
    def sandbox_base_url(self) -> str:
        if self.mock_server is not None and hasattr(self.mock_server, "base_url"):
            return str(self.mock_server.base_url)
        return os.environ.get("IT_SUITE_SANDBOX_URL", "http://127.0.0.1:8000")

    # ------------------------------------------------------------------
    # Root Window & Debounced Scaling (180ms)
    # ------------------------------------------------------------------
    def _configure_root(self) -> None:
        root = self.root
        slow_mo_ms = get_slow_mo_ms()
        title = (
            f"IT RPA Suite [教學／展示慢速模式 {slow_mo_ms:.0f}ms]"
            if slow_mo_ms > 0
            else "IT RPA Suite"
        )
        root.title(title)
        root.configure(background=self.colors["background"])
        root.update_idletasks()

        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        logger.info("偵測到螢幕解析度：%sx%s", screen_width, screen_height)

        self.base_width = ThemeManager.BASE_WIDTH
        self.base_height = ThemeManager.BASE_HEIGHT
        self.min_scale_factor = ThemeManager.MIN_SCALE
        self.max_scale_factor = ThemeManager.MAX_SCALE
        self.scale_step = ThemeManager.SCALE_STEP

        self._resize_after_id: str | None = None
        self._is_rebuilding_for_resize = False
        self._last_applied_scale = self.scale_factor
        self._last_window_size: tuple[int, int] | None = None

        try:
            root.tk.call("tk", "scaling", 1.6)
        except Exception:
            logger.warning("設定 Tkinter scaling 失敗", exc_info=True)

        width = self.s(self.base_width)
        height = self.s(self.base_height)
        x = max((screen_width - width) // 2, 0)
        y = max((screen_height - height) // 2, 0)

        min_width = round(self.base_width * self.min_scale_factor)
        min_height = round(self.base_height * self.min_scale_factor)
        root.minsize(min_width, min_height)
        root.geometry(f"{width}x{height}+{x}+{y}")

        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)
        root.bind("<Configure>", self._on_root_configure, add="+")

    def _on_root_configure(self, event: Any) -> None:
        if event.widget is not self.root:
            return
        if self.closing or self._is_rebuilding_for_resize:
            return

        current_size = (event.width, event.height)
        if current_size == self._last_window_size:
            return
        self._last_window_size = current_size

        if self._resize_after_id is not None:
            try:
                self.root.after_cancel(self._resize_after_id)
            except tk.TclError:
                pass

        self._resize_after_id = self.root.after(180, self._apply_window_scale)

    def _apply_window_scale(self) -> None:
        self._resize_after_id = None
        if self.closing or self._is_rebuilding_for_resize:
            return

        current_width = self.root.winfo_width()
        current_height = self.root.winfo_height()
        if current_width <= 1 or current_height <= 1:
            return

        new_scale = self.theme.compute_window_scale(current_width, current_height)
        if abs(new_scale - self._last_applied_scale) < 0.01:
            return

        old_scale = self.scale_factor
        self.scale_factor = new_scale
        self.theme.scale_factor = new_scale
        self._last_applied_scale = new_scale
        logger.info(
            "視窗尺寸變更為 %sx%s，scale_factor：%.2f -> %.2f",
            current_width,
            current_height,
            old_scale,
            new_scale,
        )
        self._rebuild_for_scale()

    def _rebuild_for_scale(self) -> None:
        if self._is_rebuilding_for_resize or self.closing:
            return

        self._is_rebuilding_for_resize = True
        try:
            active_key = (
                getattr(getattr(self, "sidebar", None), "active_item_key", None) or "dashboard"
            )
            self._configure_style()
            self.current_view = None

            for attr in ("application_frame", "status_bar"):
                widget = getattr(self, attr, None)
                if widget is not None:
                    try:
                        widget.destroy()
                    except tk.TclError:
                        pass

            self._build_application_container()
            self._navigate_by_key(active_key)
        except Exception:
            logger.exception("依照視窗大小重新縮放介面失敗")
        finally:
            self._is_rebuilding_for_resize = False

    def _configure_style(self) -> None:
        self.theme.apply_styles(self.root)

    def _build_application_container(self) -> None:
        self.application_frame = ttk.Frame(self.root, style="App.TFrame")
        self.application_frame.grid(row=0, column=0, sticky="nsew")
        self.application_frame.columnconfigure(0, weight=0, minsize=self.s(290))
        self.application_frame.columnconfigure(1, weight=1)
        self.application_frame.rowconfigure(0, weight=1)

        self.sidebar = MainSidebar(self.application_frame, self)
        self.sidebar.grid(row=0, column=0, sticky="nsew")

        self.content_frame = ttk.Frame(self.application_frame, style="Content.TFrame")
        self.content_frame.grid(row=0, column=1, sticky="nsew")
        self.content_frame.columnconfigure(0, weight=1)
        self.content_frame.rowconfigure(0, weight=1)

        self._build_status_bar()

    def _build_status_bar(self) -> None:
        dot_size = self.s(10)
        bar = ttk.Frame(
            self.root,
            style="StatusBar.TFrame",
            padding=(self.s(18), self.s(8)),
        )
        self.status_bar = bar
        bar.grid(row=1, column=0, sticky="ew")

        self.status_dot = tk.Canvas(
            bar,
            width=dot_size,
            height=dot_size,
            highlightthickness=0,
            background=self.colors["surface"],
        )
        self.status_dot.pack(side="left", padx=(0, self.s(8)))
        self.status_dot_indicator = self.status_dot.create_oval(
            1,
            1,
            dot_size - 1,
            dot_size - 1,
            fill=self.colors["success"],
            outline="",
        )
        ttk.Label(
            bar,
            textvariable=self.browser_status_var,
            style="StatusBar.TLabel",
        ).pack(side="left")

        right_label = f"IT RPA Suite v{__version__}"
        if self.mock_server is not None and hasattr(self.mock_server, "base_url"):
            right_label = f"Sandbox: {self.mock_server.base_url}  |  v{__version__}"
        ttk.Label(bar, text=right_label, style="StatusBar.TLabel").pack(side="right")
        self.update_browser_status()

    # ------------------------------------------------------------------
    # Theme Switching
    # ------------------------------------------------------------------
    def toggle_theme(self) -> None:
        """Toggle between light and dark themes, persist to settings.json, and rebuild UI."""
        active_key = getattr(getattr(self, "sidebar", None), "active_item_key", None) or "dashboard"
        self.is_dark_mode = not self.is_dark_mode
        self.storage.set_dark_mode(self.is_dark_mode)
        self.theme.set_dark_mode(self.is_dark_mode)
        self.root.configure(background=self.colors["background"])
        self._configure_style()

        self.current_view = None
        for attr in ("application_frame", "status_bar"):
            widget = getattr(self, attr, None)
            if widget is not None:
                try:
                    widget.destroy()
                except tk.TclError:
                    pass

        self._build_application_container()
        self._navigate_by_key(active_key)

    def get_theme_icon_path(self) -> str:
        filename = "moon.png" if self.is_dark_mode else "sun.png"
        return str(self.paths.get_icon_path(filename))

    # ------------------------------------------------------------------
    # View Routing
    # ------------------------------------------------------------------
    def _clear_current_view(self) -> None:
        if self.current_view is None:
            return
        try:
            self.current_view.destroy()
        except tk.TclError:
            logger.warning("銷毀目前功能畫面時發生 TclError", exc_info=True)
        self.current_view = None

    def _show_view(
        self,
        view_class: Callable[..., tk.Widget],
        sidebar_item: str | None = None,
        call_on_show: bool = True,
        **kwargs: Any,
    ) -> bool:
        if self.closing:
            return False
        self._clear_current_view()
        if sidebar_item == "dashboard":
            self._configure_style()
        try:
            view = view_class(parent=self.content_frame, app=self, **kwargs)
            view.grid(row=0, column=0, sticky="nsew")
            view.tkraise()
            if call_on_show and hasattr(view, "on_show"):
                view.on_show()
            self.current_view = view
            if sidebar_item is not None and hasattr(self, "sidebar"):
                self.sidebar.set_active_item(sidebar_item)
            self.update_browser_status()
            return True
        except Exception:
            logger.exception(
                "載入功能畫面失敗：%s", getattr(view_class, "__name__", str(view_class))
            )
            self.current_view = None
            messagebox.showerror(
                "功能載入失敗",
                "無法開啟指定功能畫面，請查看 data/logs/app.log。",
                parent=self.root,
            )
            return False

    def _navigate_by_key(self, key: str) -> None:
        routes: dict[str, Callable[[], Any]] = {
            "dashboard": self.show_dashboard,
            "asset_loan": self.show_asset_loan,
            "onboarding": self.show_onboarding,
            "nac_access": self.show_nac_access,
            "batch_notify": self.show_batch_notify,
            "ticket_helper": self.show_ticket_helper,
            "toolbox": self.show_toolbox,
            "credentials": self.show_credentials,
        }
        handler = routes.get(key, self.show_dashboard)
        handler()

    def show_dashboard(self) -> bool:
        return self._show_view(DashboardView, sidebar_item="dashboard", call_on_show=False)

    def show_credentials(
        self,
        first_run: bool = False,
        on_saved: Callable[[], Any] | None = None,
    ) -> bool:
        return self._show_view(
            CredentialsView,
            sidebar_item="credentials",
            first_run=first_run,
            on_saved=on_saved,
        )

    def show_asset_loan(self) -> bool:
        from it_rpa_suite.features.asset_loan.view import AssetLoanView

        return self._show_view(
            AssetLoanView,
            sidebar_item="asset_loan",
            automation_worker=self.automation_worker,
        )

    def show_onboarding(self) -> bool:
        from it_rpa_suite.features.onboarding.view import OnboardingView

        return self._show_view(
            OnboardingView,
            sidebar_item="onboarding",
            automation_worker=self.automation_worker,
        )

    def show_nac_access(self) -> bool:
        from it_rpa_suite.features.nac_access.view import NacAccessView

        return self._show_view(
            NacAccessView,
            sidebar_item="nac_access",
            automation_worker=self.automation_worker,
        )

    def show_batch_notify(self) -> bool:
        from it_rpa_suite.features.batch_notify.view import BatchNotifyView

        return self._show_view(
            BatchNotifyView,
            sidebar_item="batch_notify",
            automation_worker=self.automation_worker,
        )

    def show_ticket_helper(self) -> bool:
        from it_rpa_suite.features.ticket_helper.view import TicketHelperView

        return self._show_view(
            TicketHelperView,
            sidebar_item="ticket_helper",
            automation_worker=self.automation_worker,
        )

    def show_toolbox(self) -> bool:
        from it_rpa_suite.features.toolbox.view import ToolboxView

        return self._show_view(ToolboxView, sidebar_item="toolbox")

    def trigger_mock_call(self) -> None:
        from it_rpa_suite.features.caller_id.monitor import (
            spawn_mock_incoming_call,
        )

        spawn_mock_incoming_call(self.root)

    # ------------------------------------------------------------------
    # Status Bar & Background Switch
    # ------------------------------------------------------------------
    def update_browser_status(
        self, custom_text: str | None = None, state: str | None = None
    ) -> None:
        if custom_text is not None:
            self.browser_status_var.set(custom_text)
            color_key = {
                "running": "warning",
                "ready": "success",
                "idle": "primary",
                "off": "text_muted",
            }.get(state or "ready", "success")
            color = self.colors.get(color_key, self.colors["success"])
        elif self.automation_worker is not None:
            is_running = bool(getattr(self.automation_worker, "is_running", False))
            browser_ready = bool(getattr(self.automation_worker, "is_browser_initialized", False))
            if is_running and browser_ready:
                self.browser_status_var.set("瀏覽器自動化：運作中 (Edge 已連線)")
                color = self.colors["success"]
            elif is_running:
                self.browser_status_var.set("瀏覽器自動化：待機中 (Lazy 待命)")
                color = self.colors["primary"]
            else:
                self.browser_status_var.set("瀏覽器自動化：未啟用")
                color = self.colors["text_muted"]
        else:
            self.browser_status_var.set("瀏覽器自動化：待機中")
            color = self.colors["primary"]

        if hasattr(self, "status_dot") and hasattr(self, "status_dot_indicator"):
            try:
                self.status_dot.itemconfigure(self.status_dot_indicator, fill=color)
            except tk.TclError:
                pass

    def set_global_status(self, message: str) -> None:
        logger.info("全域狀態：%s", message)
        self.browser_status_var.set(f"狀態：{message}")

    def set_background_config_enabled(self, enabled: bool) -> bool:
        enabled = bool(enabled)
        try:
            self.storage.set_caller_id_enabled(enabled)
            if self.caller_monitor is not None and hasattr(self.caller_monitor, "set_enabled"):
                self.caller_monitor.set_enabled(enabled)
        except Exception as exc:
            logger.exception("切換背景來電識別設定失敗")
            self.background_switch_var.set(self.caller_id_enabled)
            messagebox.showerror(
                "設定失敗",
                f"無法變更背景來電識別服務設定。\n\n錯誤內容：{exc}",
                parent=self.root,
            )
            return False

        self.caller_id_enabled = enabled
        self.background_switch_var.set(enabled)
        return True

    def run_updater(self) -> None:
        if self._checking_update or self.closing:
            return

        self._checking_update = True
        self.set_global_status("正在檢查更新...")

        configured_zip = ""
        if hasattr(self, "storage") and self.storage is not None:
            configured_zip = str(self.storage.load_settings().get("update_source_zip", "")).strip()

        def _worker() -> None:
            result = check_for_updates(self.paths, configured_zip=configured_zip or None)
            if self.closing:
                return
            try:
                self.root.after(0, lambda: self._handle_update_check_result(result))
            except tk.TclError:
                self._checking_update = False

        threading.Thread(
            target=_worker,
            name="UpdateCheckThread",
            daemon=True,
        ).start()

    def _handle_update_check_result(self, result: UpdateCheckResult) -> None:
        self._checking_update = False
        if self.closing:
            return
        self.update_browser_status()

        if result.status == UpdateCheckStatus.UP_TO_DATE:
            messagebox.showinfo(
                "檢查更新",
                (
                    f"目前已是最新版本（v{__version__}），無需更新。\n\n"
                    f"套件時間：{format_timestamp(result.source_timestamp)}"
                ),
                parent=self.root,
            )
            return

        if result.status == UpdateCheckStatus.SOURCE_NOT_FOUND:
            messagebox.showwarning(
                "檢查更新",
                (
                    f"找不到更新來源壓縮檔，目前無法檢查更新：\n{result.source_zip}\n\n"
                    "請確認網路磁碟或 data/settings.json 中的 update_source_zip 路徑設定。"
                ),
                parent=self.root,
            )
            return

        if result.status == UpdateCheckStatus.ERROR:
            messagebox.showerror(
                "檢查更新失敗",
                f"檢查更新時發生錯誤：\n{result.error_message or '未知錯誤'}",
                parent=self.root,
            )
            return

        updater_exe = self.paths.base_dir / "_internal" / "updater.exe"
        updater_py = self.paths.tools_dir / "updater" / "updater.py"
        if not updater_exe.exists() and not updater_py.exists():
            messagebox.showwarning(
                "發現新版本",
                (
                    "偵測到可用的更新，但找不到更新程式"
                    "（_internal/updater.exe 或 tools/updater/updater.py）。"
                ),
                parent=self.root,
            )
            return

        if result.status == UpdateCheckStatus.UPDATE_PENDING:
            title = "完成待處理更新"
            message = "偵測到前次更新尚未完成收尾作業。\n\n立即更新將關閉本程式與相關自動化分頁，是否立即繼續？"
        elif result.status == UpdateCheckStatus.VERSION_MISSING:
            title = "偵測到更新套件"
            message = (
                f"目前找不到本機版本紀錄（data/version.txt），偵測到更新套件"
                f"（時間：{format_timestamp(result.source_timestamp)}）。\n\n"
                "立即更新將關閉本程式，是否立即更新？"
            )
        else:
            title = "發現新版本"
            message = (
                "偵測到較新的更新版本！\n\n"
                f"目前版本時間：{format_timestamp(result.installed_timestamp)}\n"
                f"最新套件時間：{format_timestamp(result.source_timestamp)}\n\n"
                "立即更新將關閉本程式，是否立即更新？"
            )

        if not show_confirm_dialog(
            parent=self.root,
            title=title,
            message=message,
            confirm_text="立即更新",
            cancel_text="稍後再說",
            sf=self.scale_factor,
        ):
            return

        self._launch_updater(result.source_zip, updater_exe, updater_py)

    def _launch_updater(
        self,
        source_zip: Path,
        updater_exe: Path,
        updater_py: Path,
    ) -> None:
        try:
            creation_flags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
            env = os.environ.copy()
            env["IT_SUITE_UPDATE_ZIP"] = str(source_zip)

            if updater_exe.exists():
                subprocess.Popen(
                    [str(updater_exe)],
                    cwd=str(self.paths.base_dir),
                    creationflags=creation_flags,
                    env=env,
                )
            else:
                subprocess.Popen(
                    [sys.executable, str(updater_py)],
                    cwd=str(self.paths.base_dir),
                    creationflags=creation_flags,
                    env=env,
                )
        except Exception as exc:
            logger.exception("啟動更新程式失敗")
            messagebox.showerror("啟動更新失敗", f"無法啟動更新程式：\n{exc}", parent=self.root)
            return

        self.request_close(skip_confirmation=True)

    def request_close(self, skip_confirmation: bool = False) -> None:
        if self.closing:
            return
        if not skip_confirmation and not show_confirm_dialog(
            parent=self.root,
            title="關閉 IT RPA Suite",
            message="關閉程式後，所有由本程式開啟的 Edge 自動化分頁與本機沙盒將一併關閉。\n\n確定要關閉嗎？",
            confirm_text="確定關閉",
            cancel_text="取消",
            sf=self.scale_factor,
        ):
            return

        self.closing = True
        self.browser_status_var.set("正在關閉程式，請稍候...")
        if callable(self.on_close_callback):
            self.on_close_callback()
        else:
            self.root.destroy()


class MainSidebar(tk.Frame):
    """Left navigation sidebar with brand theme toggle, scrollable menu, and caller ID switch."""

    MENU_GROUPS = (
        (
            "主選單",
            (
                ("dashboard", "首頁總覽", "show_dashboard"),
                ("asset_loan", "設備借還與聯查", "show_asset_loan"),
                ("onboarding", "人員入職與離職", "show_onboarding"),
                ("nac_access", "網路開通", "show_nac_access"),
                ("batch_notify", "批量通知", "show_batch_notify"),
            ),
        ),
        (
            "進階工具",
            (
                ("ticket_helper", "IT 服務台開單", "show_ticket_helper"),
                ("toolbox", "個人自訂工具箱", "show_toolbox"),
                ("mock_call", "📞 觸發模擬來電", "trigger_mock_call"),
            ),
        ),
        (
            "系統",
            (
                ("credentials", "系統憑證設定", "show_credentials"),
                ("updater", "檢查更新", "run_updater"),
            ),
        ),
    )

    def __init__(self, parent: tk.Misc, app: MainWindow) -> None:
        self.app = app
        self.colors = app.colors
        self.sf = app.scale_factor
        super().__init__(parent, background=app.colors["sidebar"], width=self.s(290))
        self.sidebar_buttons: dict[str, tk.Button] = {}
        self.active_item_key: str | None = None

        self.grid_propagate(False)
        self.columnconfigure(0, weight=1)
        for row, weight in enumerate((0, 1, 0)):
            self.rowconfigure(row, weight=weight)

        self._build_brand()
        self._build_menu()
        self._build_bottom_service_switch()

    def s(self, value: float) -> int:
        return scale(value, self.sf)

    def _build_brand(self) -> None:
        frame = tk.Frame(self, background=self.colors["sidebar"])
        frame.grid(
            row=0,
            column=0,
            sticky="ew",
            padx=self.s(20),
            pady=(self.s(26), self.s(22)),
        )
        icon_path = self.app.get_theme_icon_path()
        try:
            self.brand_icon: tk.PhotoImage | None = tk.PhotoImage(file=icon_path)
            logo = tk.Label(
                frame,
                image=self.brand_icon,
                background=self.colors["sidebar"],
                borderwidth=0,
                highlightthickness=0,
                cursor="hand2",
            )
        except tk.TclError:
            logger.warning("載入主題切換圖示失敗：%s", icon_path)
            self.brand_icon = None
            logo = tk.Label(
                frame,
                text="IT",
                font=(FONT_FAMILY, self.s(13), "bold"),
                foreground=self.colors["white"],
                background=self.colors["primary"],
                width=3,
                height=1,
                padx=self.s(4),
                pady=self.s(7),
                cursor="hand2",
            )
        logo.bind("<Button-1>", lambda _e: self.app.toggle_theme())
        logo.pack(anchor="center")

    def _build_menu(self) -> None:
        container = tk.Frame(self, background=self.colors["sidebar"])
        container.grid(row=1, column=0, sticky="nsew")
        container.columnconfigure(0, weight=1)
        container.rowconfigure(0, weight=1)

        self.menu_canvas = tk.Canvas(
            container,
            background=self.colors["sidebar"],
            highlightthickness=0,
            borderwidth=0,
            relief="flat",
            bd=0,
        )
        self.menu_canvas.grid(row=0, column=0, sticky="nsew")

        self.menu_scrollbar = ModernScrollbar(
            container,
            command=self.menu_canvas.yview,
            width=self.s(10),
            track_color=self.colors["sidebar"],
            thumb_color="#46556D",
            thumb_hover_color="#70819B",
            min_thumb_height=self.s(40),
        )
        self.menu_scrollbar.grid(row=0, column=1, sticky="ns")
        self.menu_canvas.configure(yscrollcommand=self.menu_scrollbar.set)

        self.menu_frame = tk.Frame(
            self.menu_canvas,
            background=self.colors["sidebar"],
            padx=self.s(14),
        )
        self.menu_window_id = self.menu_canvas.create_window(
            0, 0, window=self.menu_frame, anchor="nw"
        )
        self.menu_frame.bind("<Configure>", self._update_menu_scroll_region)
        self.menu_canvas.bind("<Configure>", self._resize_menu_frame)

        for group_label, items in self.MENU_GROUPS:
            self._create_sidebar_label(self.menu_frame, group_label)
            for key, text, method_name in items:
                self._create_sidebar_button(
                    self.menu_frame, key, text, getattr(self.app, method_name)
                )

        self._bind_mousewheel_recursive(self.menu_frame)
        self.after_idle(self._update_menu_scroll_region)

    def _update_menu_scroll_region(self, _event: Any = None) -> None:
        try:
            self.menu_canvas.configure(scrollregion=self.menu_canvas.bbox("all"))
            self._update_scrollbar_visibility()
        except tk.TclError:
            pass

    def _resize_menu_frame(self, event: Any) -> None:
        try:
            self.menu_canvas.itemconfigure(self.menu_window_id, width=event.width)
            self._update_scrollbar_visibility()
        except tk.TclError:
            pass

    def _update_scrollbar_visibility(self) -> None:
        try:
            self.menu_canvas.update_idletasks()
            overflow = self.menu_frame.winfo_reqheight() - self.menu_canvas.winfo_height()
            if overflow > 4:
                if not self.menu_scrollbar.winfo_ismapped():
                    self.menu_scrollbar.grid(
                        row=0,
                        column=1,
                        sticky="ns",
                        padx=(self.s(2), self.s(4)),
                        pady=self.s(6),
                    )
            else:
                if self.menu_scrollbar.winfo_ismapped():
                    self.menu_scrollbar.grid_remove()
                self.menu_canvas.yview_moveto(0)
        except tk.TclError:
            pass

    def _on_menu_mousewheel(self, event: Any) -> str:
        try:
            if self.menu_frame.winfo_reqheight() <= self.menu_canvas.winfo_height():
                return "break"
            delta = getattr(event, "delta", 0)
            if not delta:
                return "break"
            direction = -int(delta / 120) or (-1 if delta > 0 else 1)
            self.menu_canvas.yview_scroll(direction, "units")
        except tk.TclError:
            pass
        return "break"

    def _bind_mousewheel_recursive(self, widget: tk.Misc) -> None:
        widget.bind("<MouseWheel>", self._on_menu_mousewheel, add="+")
        for child in widget.winfo_children():
            self._bind_mousewheel_recursive(child)

    def _build_bottom_service_switch(self) -> None:
        bottom = tk.Frame(self, background=self.colors["sidebar"])
        bottom.grid(row=2, column=0, sticky="sew", padx=self.s(20), pady=self.s(18))

        tk.Frame(bottom, background="#2A354A", height=1).pack(fill="x", pady=(0, self.s(14)))
        row = tk.Frame(bottom, background=self.colors["sidebar"])
        row.pack(fill="x")

        text_col = tk.Frame(row, background=self.colors["sidebar"])
        text_col.pack(side="left", fill="x", expand=True)
        tk.Label(
            text_col,
            text="背景來電識別服務",
            font=(FONT_FAMILY, self.s(9), "bold"),
            foreground=self.colors["white"],
            background=self.colors["sidebar"],
        ).pack(anchor="w")
        self.background_status_label = tk.Label(
            text_col,
            font=(FONT_FAMILY, self.s(8)),
            background=self.colors["sidebar"],
        )
        self.background_status_label.pack(anchor="w", pady=(self.s(3), 0))

        self.background_switch = ToggleSwitch(
            row,
            variable=self.app.background_switch_var,
            command=self._on_background_switch_changed,
            on_color=self.colors["success"],
            off_color="#59677D",
        )
        self.background_switch.pack(side="right", padx=(self.s(10), 0))
        self._update_background_switch_display()

    def _update_background_switch_display(self) -> None:
        enabled = bool(self.app.background_switch_var.get())
        if enabled:
            self.background_status_label.configure(
                text="已啟用即時來電監聽",
                foreground="#8FE3B9",
            )
        else:
            self.background_status_label.configure(
                text="目前停用",
                foreground="#9EABC0",
            )

    def _on_background_switch_changed(self, enabled: bool) -> None:
        self.app.set_background_config_enabled(enabled)
        self._update_background_switch_display()

    def _create_sidebar_label(self, parent: tk.Misc, text: str) -> None:
        tk.Label(
            parent,
            text=text,
            font=(FONT_FAMILY, self.s(8), "bold"),
            foreground="#76849A",
            background=self.colors["sidebar"],
        ).pack(
            fill="x",
            anchor="w",
            padx=self.s(12),
            pady=(self.s(16), self.s(6)),
        )

    def _create_sidebar_button(
        self,
        parent: tk.Misc,
        item_key: str,
        text: str,
        command: Callable[[], Any],
    ) -> tk.Button:
        button = tk.Button(
            parent,
            text=text,
            command=command,
            font=(FONT_FAMILY, self.s(10), "bold"),
            foreground=self.colors["white"],
            background=self.colors["sidebar"],
            activeforeground=self.colors["white"],
            activebackground=self.colors["sidebar_hover"],
            relief="flat",
            borderwidth=0,
            anchor="w",
            cursor="hand2",
            padx=self.s(14),
            pady=self.s(9),
        )
        button.pack(fill="x", pady=self.s(2))
        self.sidebar_buttons[item_key] = button

        def _on_enter(_e: tk.Event[Any], key: str = item_key) -> Any:
            return self._set_hover(key, True)

        def _on_leave(_e: tk.Event[Any], key: str = item_key) -> Any:
            return self._set_hover(key, False)

        button.bind("<Enter>", _on_enter)
        button.bind("<Leave>", _on_leave)
        return button

    def _set_hover(self, item_key: str, entering: bool) -> None:
        if (
            item_key != self.active_item_key
            and (btn := self.sidebar_buttons.get(item_key)) is not None
        ):
            btn.configure(background=self.colors["sidebar_hover" if entering else "sidebar"])

    def set_active_item(self, item_key: str) -> None:
        self.active_item_key = item_key
        for key, btn in self.sidebar_buttons.items():
            btn.configure(
                background=self.colors["sidebar_active" if key == item_key else "sidebar"]
            )

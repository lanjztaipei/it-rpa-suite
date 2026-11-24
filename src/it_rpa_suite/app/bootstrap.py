"""Application bootstrap coordinator for DPI, environment setup, background services, and GUI mainloop."""

from __future__ import annotations

import os
import threading
import tkinter as tk
from tkinter import messagebox
from typing import Any

from it_rpa_suite.adapters.credentials_dpapi import CredentialStore
from it_rpa_suite.adapters.logger import get_logger
from it_rpa_suite.adapters.paths import AppPaths, get_app_paths
from it_rpa_suite.adapters.storage import AppStorage
from it_rpa_suite.app.main_window import MainWindow
from it_rpa_suite.app.theme import enable_windows_dpi_awareness

logger = get_logger(__name__)


def set_window_icon(root: tk.Tk, paths: AppPaths) -> None:
    """Attach corner_icon.png as the window icon if present."""
    try:
        icon_path = paths.get_icon_path("corner_icon.png")
        if not icon_path.is_file():
            logger.warning("找不到視窗圖示：%s", icon_path)
            return
        window_icon = tk.PhotoImage(file=str(icon_path))
        root.iconphoto(True, window_icon)
        setattr(root, "_window_icon", window_icon)
    except Exception:
        logger.exception("設定視窗圖示失敗")


def shutdown_application(
    root: tk.Tk | None,
    automation_worker: Any = None,
    caller_monitor: Any = None,
    mock_server: Any = None,
) -> None:
    """Gracefully stop background services on a daemon thread and destroy root."""
    logger.info("開始關閉應用程式與背景服務")

    def perform_shutdown() -> None:
        try:
            if caller_monitor is not None and hasattr(caller_monitor, "stop"):
                caller_monitor.stop(timeout=3.0)
            if automation_worker is not None and hasattr(automation_worker, "shutdown"):
                automation_worker.shutdown(wait=True, timeout=10.0)
            if mock_server is not None and hasattr(mock_server, "stop"):
                mock_server.stop()
        except Exception:
            logger.exception("關閉背景服務時發生錯誤")
        finally:
            if root is not None:
                try:
                    root.after(0, root.destroy)
                except Exception:
                    pass

    threading.Thread(
        target=perform_shutdown,
        name="ApplicationShutdownThread",
        daemon=True,
    ).start()


def main(auto_close_ms: int | None = None) -> None:
    """Bootstrap and launch IT RPA Suite."""
    enable_windows_dpi_awareness()
    paths = get_app_paths()
    storage = AppStorage(paths=paths)
    credential_store = CredentialStore(paths=paths)
    first_run = not credential_store.exists()

    logger.info("啟動 IT RPA Suite，base_dir=%s", paths.base_dir)

    root: tk.Tk | None = None
    automation_worker: Any = None
    mock_server: Any = None
    caller_monitor: Any = None

    try:
        root = tk.Tk()
        set_window_icon(root, paths)
        root.withdraw()

        # Start MockEnterpriseServer
        from it_rpa_suite.mock_server.server import MockEnterpriseServer

        mock_server = MockEnterpriseServer()
        mock_server.start()

        # Start AutomationWorker (Lazy Browser Initialization)
        from it_rpa_suite.adapters.browser_worker import AutomationWorker

        automation_worker = AutomationWorker(headless=False)
        automation_worker.start()

        def on_close() -> None:
            shutdown_application(
                root=root,
                automation_worker=automation_worker,
                caller_monitor=caller_monitor,
                mock_server=mock_server,
            )

        app = MainWindow(
            root=root,
            paths=paths,
            storage=storage,
            credential_store=credential_store,
            automation_worker=automation_worker,
            mock_server=mock_server,
            caller_monitor=caller_monitor,
            on_close_callback=on_close,
        )

        # Start CallerIdMonitor
        from it_rpa_suite.features.caller_id.monitor import CallerIdMonitor

        caller_monitor = CallerIdMonitor(
            root=root,
            sandbox_base_url=app.sandbox_base_url,
            enabled=storage.get_caller_id_enabled(),
            on_caller_matched=lambda _info: app.record_feature_usage("caller_lookup"),
        )
        caller_monitor.start()
        app.caller_monitor = caller_monitor

        if first_run:
            app.show_credentials(first_run=True, on_saved=app.show_dashboard)
        else:
            app.show_dashboard()

        root.deiconify()

        env_auto_close = os.getenv("IT_SUITE_AUTO_CLOSE_MS")
        effective_close_ms = auto_close_ms or (
            int(env_auto_close) if env_auto_close and env_auto_close.isdigit() else None
        )
        if effective_close_ms is not None and effective_close_ms > 0:
            root.after(effective_close_ms, lambda: app.request_close(skip_confirmation=True))

        root.mainloop()

    except KeyboardInterrupt:
        logger.info("接收到使用者中斷訊號")
    except Exception:
        logger.exception("主程式執行時發生未預期錯誤")
        if root is not None:
            try:
                messagebox.showerror(
                    "IT RPA Suite 錯誤",
                    "主程式執行時發生未預期錯誤，請查看 data/logs/app.log。",
                    parent=root,
                )
            except Exception:
                pass
    finally:
        if caller_monitor is not None and hasattr(caller_monitor, "stop"):
            try:
                caller_monitor.stop(timeout=2.0)
            except Exception:
                pass
        if automation_worker is not None and hasattr(automation_worker, "shutdown"):
            try:
                automation_worker.shutdown(wait=True, timeout=5.0)
            except Exception:
                pass
        if mock_server is not None and hasattr(mock_server, "stop"):
            try:
                mock_server.stop()
            except Exception:
                pass

"""Playwright FIFO queue worker thread and lazy-initialized Edge BrowserSession."""

from __future__ import annotations

import os
import queue
import threading
from collections.abc import Callable
from concurrent.futures import Future
from typing import Any

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

from it_rpa_suite.adapters.logger import get_logger

logger = get_logger(__name__)

SLOW_MO_ENV_VAR = "IT_SUITE_SLOW_MO"

EDGE_LAUNCH_ARGS = [
    "--start-maximized",
    "--disable-translate",
    ("--disable-features=DownloadBubble,DownloadBubbleV2,Translate,TranslateUI,msEdgeTranslate"),
]


def get_slow_mo_ms(default: float = 0.0) -> float:
    """Resolve Playwright `slow_mo` delay in milliseconds from `IT_SUITE_SLOW_MO`."""
    raw = os.environ.get(SLOW_MO_ENV_VAR, "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        logger.warning("%s 設定無效 (%r)，將回退為 %.0f ms", SLOW_MO_ENV_VAR, raw, default)
        return default
    if value < 0:
        logger.warning("%s 不可為負數 (%r)，將回退為 %.0f ms", SLOW_MO_ENV_VAR, raw, default)
        return default
    return value


def _attach_dialog_handler(page: Any, handler: Callable[[Any], None]) -> None:
    """Ensure only one dialog listener is attached to a Playwright Page."""
    old_handler = getattr(page, "_suite_dialog_handler", None)
    if old_handler is not None:
        try:
            page.remove_listener("dialog", old_handler)
        except Exception:
            pass
    page.on("dialog", handler)
    setattr(page, "_suite_dialog_handler", handler)


class BrowserSession:
    """Manages the shared Playwright BrowserContext on the AutomationWorker thread."""

    def __init__(
        self,
        headless: bool = False,
        downloads_path: str | None = None,
        slow_mo: float | None = None,
    ) -> None:
        self.headless = headless
        self.downloads_path = downloads_path
        self.slow_mo = get_slow_mo_ms() if slow_mo is None else max(0.0, float(slow_mo))
        self.playwright: Any = None
        self.browser: Any = None
        self.context: Any = None
        self._owner_thread_id: int | None = None
        self._closed = False

    def start(self) -> BrowserSession:
        """Start Playwright and launch Microsoft Edge (with fallback to Chromium)."""
        if self.is_available():
            return self

        self._owner_thread_id = threading.get_ident()
        self._closed = False
        logger.info(
            "開始建立共用 BrowserSession (headless=%s, slow_mo=%.0fms)",
            self.headless,
            self.slow_mo,
        )

        self.playwright = sync_playwright().start()
        launch_args = [] if self.headless else EDGE_LAUNCH_ARGS

        try:
            self.browser = self.playwright.chromium.launch(
                channel="msedge",
                headless=self.headless,
                args=launch_args,
                downloads_path=self.downloads_path,
                slow_mo=self.slow_mo,
            )
        except Exception:
            logger.warning("以 msedge channel 啟動失敗，改用預設 Chromium 啟動")
            self.browser = self.playwright.chromium.launch(
                headless=self.headless,
                args=launch_args,
                downloads_path=self.downloads_path,
                slow_mo=self.slow_mo,
            )

        context_kwargs: dict[str, Any] = {
            "accept_downloads": True,
            "locale": "zh-TW",
        }
        if not self.headless:
            context_kwargs["no_viewport"] = True

        self.context = self.browser.new_context(**context_kwargs)
        logger.info("共用 BrowserContext 建立完成")
        return self

    def _check_thread(self) -> None:
        """Enforce single-thread affinity required by Playwright Sync API."""
        current_id = threading.get_ident()
        if self._owner_thread_id is not None and current_id != self._owner_thread_id:
            raise RuntimeError(
                "BrowserSession 不可跨執行緒操作，請透過 AutomationWorker.submit() 執行任務。"
            )

    def is_available(self) -> bool:
        if self._closed:
            return False
        if self.playwright is None or self.browser is None or self.context is None:
            return False
        try:
            return bool(self.browser.is_connected())
        except Exception:
            return False

    def ensure_started(self) -> None:
        self._check_thread()
        if not self.is_available():
            logger.info("偵測到 BrowserSession 尚未啟動或已關閉，正在初始化瀏覽器...")
            self.close()
            self.start()

    def _handle_dialog(self, dialog: Any) -> None:
        """Automatically accept native JavaScript dialogs (alert/confirm/prompt)."""
        try:
            logger.info(
                "自動同意網頁原生 Dialog: type=%s, message=%s",
                dialog.type,
                dialog.message,
            )
            dialog.accept()
        except Exception:
            logger.warning("自動同意網頁 Dialog 失敗", exc_info=True)

    def new_page(self, timeout: int = 30000) -> Any:
        """Open a new browser tab in the shared context with dialog auto-handling."""
        self.ensure_started()
        page = self.context.new_page()
        page.set_default_timeout(timeout)
        _attach_dialog_handler(page, self._handle_dialog)
        return page

    def get_context(self) -> Any:
        self.ensure_started()
        return self.context

    def close_page(self, page: Any) -> None:
        self._check_thread()
        if page is None:
            return
        try:
            if not page.is_closed():
                page.close()
        except PlaywrightError:
            logger.warning("關閉分頁時發生 Playwright 錯誤")
        except Exception:
            logger.warning("關閉分頁時發生未預期錯誤", exc_info=True)

    def close(self) -> None:
        """Release BrowserContext, Browser, and Playwright resources on the worker thread."""
        if self._owner_thread_id is not None and threading.get_ident() != self._owner_thread_id:
            raise RuntimeError("BrowserSession.close() 必須由建立它的 Worker 執行緒呼叫")

        self._closed = True

        if self.context is not None:
            try:
                self.context.close()
            except Exception:
                logger.debug("關閉 BrowserContext 失敗", exc_info=True)
            finally:
                self.context = None

        if self.browser is not None:
            try:
                self.browser.close()
            except Exception:
                logger.debug("關閉 Browser 失敗", exc_info=True)
            finally:
                self.browser = None

        if self.playwright is not None:
            try:
                self.playwright.stop()
            except Exception:
                logger.debug("停止 Playwright 失敗", exc_info=True)
            finally:
                self.playwright = None


class AutomationWorker:
    """Dedicated FIFO daemon worker thread for Playwright automation with lazy browser startup."""

    _STOP_SIGNAL = object()

    def __init__(
        self,
        headless: bool = False,
        downloads_path: str | None = None,
        slow_mo: float | None = None,
    ) -> None:
        self.headless = headless
        self.downloads_path = downloads_path
        self.slow_mo = slow_mo

        self._task_queue: queue.Queue[Any] = queue.Queue()
        self._thread: threading.Thread | None = None
        self._ready_event = threading.Event()
        self._stopped_event = threading.Event()

        self._startup_error: BaseException | None = None
        self._accepting_tasks = False
        self._browser_session: BrowserSession | None = None

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive() and self._accepting_tasks

    @property
    def is_browser_initialized(self) -> bool:
        return self._browser_session is not None and self._browser_session.is_available()

    @property
    def startup_error(self) -> BaseException | None:
        return self._startup_error

    def start(self, wait_timeout: float = 10.0) -> None:
        """Start the background queue thread immediately without blocking on Edge launch."""
        if self._thread is not None and self._thread.is_alive():
            return

        self._ready_event.clear()
        self._stopped_event.clear()
        self._startup_error = None
        self._accepting_tasks = False

        self._thread = threading.Thread(
            target=self._run_loop,
            name="AutomationWorker",
            daemon=True,
        )
        self._thread.start()

        if not self._ready_event.wait(timeout=wait_timeout):
            raise RuntimeError("AutomationWorker 背景執行緒啟動逾時")

        if self._startup_error is not None:
            raise RuntimeError(f"AutomationWorker 啟動失敗：{self._startup_error}")

    def submit(
        self,
        task_function: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> Future[Any]:
        """Submit a task to be executed sequentially on the worker thread.

        `task_function` will be called as `task_function(browser_session, *args, **kwargs)`.
        """
        future: Future[Any] = Future()
        if not self.is_running:
            future.set_exception(RuntimeError("AutomationWorker 尚未啟動或已停止"))
            return future

        self._task_queue.put((future, task_function, args, kwargs))
        return future

    def shutdown(self, wait: bool = True, timeout: float = 15.0) -> None:
        """Stop accepting tasks, close BrowserSession if initialized, and join thread."""
        if self._thread is None:
            return

        self._accepting_tasks = False
        self._task_queue.put(self._STOP_SIGNAL)

        if wait and self._thread.is_alive():
            self._thread.join(timeout=timeout)

        if self._thread.is_alive():
            logger.warning("AutomationWorker 未在 %s 秒內完全停止", timeout)

    def _ensure_browser_session(self) -> BrowserSession:
        """Lazily initialize BrowserSession on the worker thread when the first task runs."""
        if self._browser_session is None:
            self._browser_session = BrowserSession(
                headless=self.headless,
                downloads_path=self.downloads_path,
                slow_mo=self.slow_mo,
            )
        self._browser_session.ensure_started()
        return self._browser_session

    def _run_loop(self) -> None:
        logger.info("AutomationWorker 佇列執行緒已就緒 (Lazy Browser 模式)")
        try:
            self._accepting_tasks = True
            self._ready_event.set()

            while True:
                task = self._task_queue.get()
                if task is self._STOP_SIGNAL:
                    self._task_queue.task_done()
                    break

                future, task_function, args, kwargs = task
                try:
                    if future.set_running_or_notify_cancel():
                        session = self._ensure_browser_session()
                        result = task_function(session, *args, **kwargs)
                        future.set_result(result)
                except Exception as exc:
                    logger.exception("AutomationWorker 執行任務失敗")
                    if not future.done():
                        future.set_exception(exc)
                finally:
                    self._task_queue.task_done()

        except Exception as exc:
            self._startup_error = exc
            logger.exception("AutomationWorker 執行緒發生嚴重錯誤")
            self._ready_event.set()
        finally:
            self._accepting_tasks = False
            if self._browser_session is not None:
                try:
                    self._browser_session.close()
                except Exception:
                    logger.exception("關閉 BrowserSession 時發生錯誤")
                finally:
                    self._browser_session = None

            self._cancel_remaining_tasks()
            self._stopped_event.set()
            logger.info("AutomationWorker 已停止")

    def _cancel_remaining_tasks(self) -> None:
        while True:
            try:
                task = self._task_queue.get_nowait()
            except queue.Empty:
                break
            try:
                if task is not self._STOP_SIGNAL:
                    future, _, _, _ = task
                    if not future.done():
                        future.cancel()
            finally:
                self._task_queue.task_done()

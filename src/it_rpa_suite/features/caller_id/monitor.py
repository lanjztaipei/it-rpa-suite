"""Background UIA incoming call monitor (`pywinauto`) and mock incoming call window generator."""

from __future__ import annotations

import json
import re
import threading
import tkinter as tk
import urllib.parse
import urllib.request
from collections.abc import Callable
from typing import Any

from it_rpa_suite.adapters.logger import get_logger
from it_rpa_suite.app.theme import FONT_FAMILY, scale
from it_rpa_suite.app.widgets import CallerToast, show_caller_toast

logger = get_logger(__name__)

CALL_WINDOW_KEYWORDS = (
    "Incoming Call",
    "來電通知",
    "來電自",
    "來電 自",
)

SAMPLE_CALLER_EXTENSIONS = (
    ("50211", "陳建宏 (Alex Chen) — 雲端基礎架構部"),
    ("50212", "林雅婷 (Irene Lin) — 數位產品研發部"),
    ("50213", "王柏翰 (Brian Wang) — 資訊安全管理部"),
    ("50214", "張心怡 (Claire Chang) — 企業應用服務部"),
)

_mock_call_cycle_index = 0
_active_mock_call_window: tk.Toplevel | None = None


def is_incoming_call_window_title(title: str | None) -> bool:
    """Return True if a desktop window title matches incoming call notification patterns."""
    if not title:
        return False
    cleaned = title.strip()
    if "Caller ID Match" in cleaned or "IT RPA Suite" in cleaned:
        return False
    return any(keyword in cleaned for keyword in CALL_WINDOW_KEYWORDS)


def parse_caller_text(candidates: list[str] | str) -> str:
    """Extract a clean extension, phone number, or employee ID from candidate UI strings."""
    texts = [candidates] if isinstance(candidates, str) else list(candidates)
    prefixes = (
        "Incoming Call from ",
        "Incoming Call - 來電通知",
        "Incoming Call -",
        "Incoming Call:",
        "來電通知 -",
        "來電通知：",
        "來電 自 ",
        "來電自 ",
    )

    for raw in texts:
        text = (raw or "").strip()
        if not text:
            continue

        # 1. Explicit parenthesized or bracketed extension/ID, e.g. "Incoming Call - 來電通知 (50211)"
        paren_match = re.search(r"[\(\[（](EMP\d+|\d{4,6})[\)\]）]", text, re.IGNORECASE)
        if paren_match:
            return paren_match.group(1).upper()

        # 2. Known prefix stripping
        for prefix in prefixes:
            if prefix in text:
                remainder = text.split(prefix, 1)[1].strip(" :：-()（）[]")
                if remainder:
                    token_match = re.search(r"(EMP\d+|\d{4,10})", remainder, re.IGNORECASE)
                    if token_match:
                        return token_match.group(1).upper()
                    return remainder

        # 3. Standalone 5-digit extension or EMP ID in text
        ext_match = re.search(r"\b(EMP\d+|\d{5})\b", text, re.IGNORECASE)
        if ext_match:
            return ext_match.group(1).upper()

    for raw in texts:
        cleaned = (raw or "").strip()
        for prefix in prefixes:
            cleaned = cleaned.replace(prefix, "").strip(" :：-()（）[]")
        if cleaned:
            return cleaned
    return ""


def extract_caller_info(window: Any) -> str:
    """Extract caller identifier from a pywinauto UIA window wrapper and its descendants."""
    candidate_texts: list[str] = []
    try:
        title = str(window.window_text() or "").strip()
        if title:
            candidate_texts.append(title)
    except Exception:
        pass

    try:
        for element in window.descendants():
            try:
                text = str(element.window_text() or "").strip()
                if text:
                    candidate_texts.append(text)
            except Exception:
                continue
    except Exception:
        logger.debug("讀取來電視窗 descendants 失敗", exc_info=True)

    return parse_caller_text(candidate_texts)


def lookup_caller_directory(
    sandbox_base_url: str,
    caller_query: str,
    timeout: float = 2.5,
) -> dict[str, Any]:
    """Query the local sandbox REST API (`GET /api/directory?q=...`) for caller details."""
    clean_query = (caller_query or "").strip()
    fallback: dict[str, Any] = {
        "emp_id": "",
        "name": f"外部或未登錄來電 ({clean_query})",
        "dept": "未知部門",
        "title": "外部來電",
        "ext": clean_query,
        "email": "-",
        "manager": "-",
        "location": "-",
    }
    if not clean_query:
        return fallback

    url = f"{sandbox_base_url.rstrip('/')}/api/directory?q={urllib.parse.quote(clean_query)}"
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        results = payload.get("results", []) if isinstance(payload, dict) else []
        if results and isinstance(results[0], dict):
            return dict(results[0])
    except Exception as exc:
        logger.warning("查詢本機通訊錄 API 失敗 (%s): %s", url, exc)

    return fallback


class CallerIdMonitor:
    """Background daemon service monitoring desktop windows via `pywinauto` UIA for incoming calls."""

    POLL_INTERVAL_SECONDS = 0.75

    def __init__(
        self,
        root: tk.Misc,
        sandbox_base_url: str = "http://127.0.0.1:8000",
        enabled: bool = True,
        on_caller_matched: Callable[[dict[str, Any]], Any] | None = None,
        toast_duration_ms: int = 8000,
    ) -> None:
        self.root = root
        self.sandbox_base_url = sandbox_base_url
        self.enabled = bool(enabled)
        self.on_caller_matched = on_caller_matched
        self.toast_duration_ms = toast_duration_ms

        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_notified_signature: tuple[int, str] | None = None

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = bool(enabled)
        if not self.enabled:
            self._last_notified_signature = None
        logger.info("CallerIdMonitor 背景來電監聽狀態變更: enabled=%s", self.enabled)

    def start(self) -> None:
        """Start the background UIA polling daemon thread."""
        if self.is_running:
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run_loop,
            name="CallerIdMonitorThread",
            daemon=True,
        )
        self._thread.start()
        logger.info("CallerIdMonitor 背景服務已啟動 (enabled=%s)", self.enabled)

    def stop(self, timeout: float = 3.0) -> None:
        """Signal the background monitor thread to stop and wait up to `timeout` seconds."""
        self._stop_event.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=timeout)
        self._thread = None
        logger.info("CallerIdMonitor 背景服務已停止")

    def _scan_incoming_call_window(self) -> tuple[int, str] | None:
        """Scan desktop top-level windows using `pywinauto.Desktop(backend='uia')`."""
        try:
            from pywinauto import Desktop

            windows = Desktop(backend="uia").windows()
            for win in windows:
                try:
                    title = str(win.window_text() or "").strip()
                except Exception:
                    continue
                if not is_incoming_call_window_title(title):
                    continue

                caller_id = extract_caller_info(win)
                if not caller_id:
                    continue

                try:
                    handle = int(getattr(win, "handle", 0) or 0)
                except Exception:
                    handle = 0
                return handle, caller_id
        except Exception:
            logger.debug("pywinauto UIA 掃描視窗時發生例外", exc_info=True)
        return None

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            if not self.enabled:
                if self._stop_event.wait(self.POLL_INTERVAL_SECONDS):
                    break
                continue

            detected = self._scan_incoming_call_window()
            if detected is None:
                self._last_notified_signature = None
            else:
                signature = detected
                if signature != self._last_notified_signature:
                    self._last_notified_signature = signature
                    _, caller_query = signature
                    logger.info("偵測到桌面來電通知視窗: caller=%s", caller_query)
                    caller_info = lookup_caller_directory(self.sandbox_base_url, caller_query)
                    self._dispatch_toast(caller_info, caller_query)

            if self._stop_event.wait(self.POLL_INTERVAL_SECONDS):
                break

    def _dispatch_toast(self, caller_info: dict[str, Any], raw_query: str) -> None:
        """Marshal toast creation and KPI callback onto the Tkinter main GUI thread."""

        def _show_on_gui() -> None:
            try:
                if not self.root.winfo_exists():
                    return
                if callable(self.on_caller_matched):
                    self.on_caller_matched(caller_info)
                show_caller_toast(
                    parent=self.root,
                    caller_info=caller_info,
                    raw_query=raw_query,
                    duration_ms=self.toast_duration_ms,
                )
            except Exception:
                logger.exception("顯示來電識別 CallerToast 時發生錯誤")

        try:
            self.root.after(0, _show_on_gui)
        except Exception:
            logger.debug("無法派送 CallerToast 至主視窗執行緒", exc_info=True)


def spawn_mock_incoming_call(
    root: tk.Misc,
    caller_ext: str | None = None,
    auto_close_ms: int = 9000,
) -> tk.Toplevel:
    """Spawn a standalone top-level simulated softphone incoming call window for `pywinauto` testing."""
    global _mock_call_cycle_index, _active_mock_call_window

    if _active_mock_call_window is not None:
        try:
            if _active_mock_call_window.winfo_exists():
                _active_mock_call_window.destroy()
        except tk.TclError:
            pass
        _active_mock_call_window = None

    if caller_ext is None:
        ext, hint_label = SAMPLE_CALLER_EXTENSIONS[
            _mock_call_cycle_index % len(SAMPLE_CALLER_EXTENSIONS)
        ]
        _mock_call_cycle_index += 1
    else:
        ext = caller_ext.strip()
        hint_label = f"測試分機 {ext}"

    top_root = root.winfo_toplevel()
    sf = float(getattr(top_root, "scale_factor", 1.5))

    # Create a real non-transient OS top-level window so pywinauto Desktop(backend="uia").windows()
    # enumerates it as a standard top-level window on the Windows desktop.
    win = tk.Toplevel()
    _active_mock_call_window = win
    win.title(f"Incoming Call - 來電通知 ({ext})")
    win.configure(background="#0F172A")
    win.resizable(False, False)
    try:
        win.attributes("-topmost", True)
    except tk.TclError:
        pass

    def s(v: float) -> int:
        return scale(v, sf)

    container = tk.Frame(
        win,
        background="#0F172A",
        padx=s(22),
        pady=s(18),
    )
    container.pack(fill="both", expand=True)

    tk.Label(
        container,
        text="📞 Enterprise Softphone — 模擬來電視窗",
        font=(FONT_FAMILY, s(9.5), "bold"),
        foreground="#38BDF8",
        background="#0F172A",
        anchor="w",
    ).pack(fill="x")

    tk.Label(
        container,
        text=f"Incoming Call from {ext}",
        font=(FONT_FAMILY, s(15), "bold"),
        foreground="#FFFFFF",
        background="#0F172A",
        anchor="w",
    ).pack(fill="x", pady=(s(8), s(2)))

    tk.Label(
        container,
        text=f"來電自 {ext}  （沙盒對應：{hint_label}）",
        font=(FONT_FAMILY, s(9)),
        foreground="#94A3B8",
        background="#0F172A",
        anchor="w",
    ).pack(fill="x", pady=(0, s(14)))

    btn_row = tk.Frame(container, background="#0F172A")
    btn_row.pack(fill="x")

    tk.Button(
        btn_row,
        text="接聽 (Answer)",
        font=(FONT_FAMILY, s(9.5), "bold"),
        foreground="#FFFFFF",
        background="#16A36A",
        activeforeground="#FFFFFF",
        activebackground="#15803D",
        relief="flat",
        cursor="hand2",
        padx=s(16),
        pady=s(6),
        command=win.destroy,
    ).pack(side="left", padx=(0, s(10)))

    tk.Button(
        btn_row,
        text="掛斷 (Decline)",
        font=(FONT_FAMILY, s(9.5), "bold"),
        foreground="#FFFFFF",
        background="#DC2626",
        activeforeground="#FFFFFF",
        activebackground="#B91C1C",
        relief="flat",
        cursor="hand2",
        padx=s(16),
        pady=s(6),
        command=win.destroy,
    ).pack(side="left")

    win.update_idletasks()
    w = max(s(360), win.winfo_reqwidth())
    h = win.winfo_reqheight()
    screen_w = win.winfo_screenwidth()
    screen_h = win.winfo_screenheight()
    # Position at bottom-right so it never overlaps the top-right CallerToast card
    x = max(20, screen_w - w - s(26))
    y = max(40, screen_h - h - s(90))
    win.geometry(f"{w}x{h}+{x}+{y}")

    if auto_close_ms > 0:
        win.after(
            auto_close_ms,
            lambda: win.destroy() if win.winfo_exists() else None,
        )

    return win


__all__ = [
    "CALL_WINDOW_KEYWORDS",
    "CallerIdMonitor",
    "CallerToast",
    "extract_caller_info",
    "is_incoming_call_window_title",
    "lookup_caller_directory",
    "parse_caller_text",
    "show_caller_toast",
    "spawn_mock_incoming_call",
]

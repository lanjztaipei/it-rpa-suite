"""Threaded local HTTP server hosting the offline enterprise IT sandbox."""

from __future__ import annotations

import errno
import json
import os
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from it_rpa_suite.adapters.logger import get_logger
from it_rpa_suite.adapters.paths import AppPaths
from it_rpa_suite.mock_server.pages import (
    SandboxState,
    render_asset_detail_page,
    render_asset_issue_page,
    render_asset_return_page,
    render_asset_search_page,
    render_borrow_report_page,
    render_directory_page,
    render_form_detail_frame,
    render_form_view_page,
    render_forms_login_page,
    render_home_page,
    render_hr_offboarding_page,
    render_nac_console_page,
    render_nac_edit_popup,
    render_nac_main_frame,
    render_nac_nav_frame,
    render_servicedesk_page,
    render_telecom_extensions_page,
)

logger = get_logger(__name__)

DEFAULT_FORM_FRAME_DELAY_MS = 40


def _resolve_form_delay_ms(query_override: str = "") -> int:
    """Resolve simulated server latency in milliseconds for `/portal/forms/frame`."""
    raw = (query_override or os.environ.get("IT_SUITE_MOCK_FORM_DELAY_MS", "")).strip()
    if not raw:
        return DEFAULT_FORM_FRAME_DELAY_MS
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_FORM_FRAME_DELAY_MS
    return max(0, min(value, 5000))


class _ExclusiveThreadingHTTPServer(ThreadingHTTPServer):
    """ThreadingHTTPServer that disables SO_REUSEADDR and enforces exclusive port binding on Windows."""

    allow_reuse_address = False

    def server_bind(self) -> None:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def _is_port_available(host: str, port: int) -> bool:
    """Return True only if ``port`` is not bound on wildcard or loopback interfaces.

    On Windows, standard ``HTTPServer`` sets ``allow_reuse_address = 1`` (``SO_REUSEADDR``),
    which allows binding over an already-listening port without raising ``OSError``.
    Testing exclusive binds on ``0.0.0.0``, ``host``, and IPv6 loopback/wildcard guarantees
    occupied ports are detected and skipped.
    """
    if port == 0:
        return True

    for bind_host in dict.fromkeys(("0.0.0.0", host)):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            try:
                sock.bind((bind_host, port))
            except OSError:
                return False

    if socket.has_ipv6:
        for bind_host6 in ("::", "::1"):
            try:
                with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as sock6:
                    if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                        sock6.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
                    sock6.bind((bind_host6, port))
            except OSError as exc:
                winerr = getattr(exc, "winerror", None)
                if exc.errno in (errno.EADDRINUSE, errno.EACCES) or winerr in (10048, 10013):
                    return False

    return True


def _make_handler_class(state: SandboxState) -> type[BaseHTTPRequestHandler]:
    class SandboxRequestHandler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:
            # Silence standard stderr logging to keep console/logs clean
            pass

        def _is_portal_authenticated(self) -> bool:
            cookie_header = self.headers.get("Cookie", "")
            return "portal_auth=1" in cookie_header

        def _send_html(self, content: str, status: int = 200) -> None:
            encoded = content.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def _send_json(self, payload: Any, status: int = 200) -> None:
            encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def _send_xlsx_bytes(self, content: bytes, filename: str) -> None:
            self.send_response(200)
            self.send_header(
                "Content-Type",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            route = parsed.path.rstrip("/") or "/"
            query = parse_qs(parsed.query)
            authed = self._is_portal_authenticated()

            if route == "/":
                self._send_html(render_home_page(state))
                return

            if route == "/api/directory":
                keyword = query.get("q", [""])[0]
                matches = state.query_directory(keyword)
                self._send_json({"ok": True, "count": len(matches), "results": matches})
                return

            if route == "/portal/directory":
                keyword = query.get("q", [""])[0]
                self._send_html(render_directory_page(state, initial_query=keyword))
                return

            if route == "/portal/assets/issue":
                self._send_html(render_asset_issue_page(state, is_authenticated=authed))
                return

            if route == "/portal/assets/search":
                self._send_html(render_asset_search_page(state, is_authenticated=authed))
                return

            if route == "/portal/assets/detail":
                tag = query.get("tag", ["IT-300001"])[0]
                self._send_html(render_asset_detail_page(state, tag=tag))
                return

            if route == "/portal/assets/return":
                self._send_html(render_asset_return_page(state, is_authenticated=authed))
                return

            if route == "/portal/hr/offboarding":
                self._send_html(render_hr_offboarding_page(state, is_authenticated=authed))
                return

            if route == "/portal/telecom/extensions":
                self._send_html(render_telecom_extensions_page(state))
                return

            if route in ("/network/console", "/nac/console"):
                self._send_html(render_nac_console_page())
                return

            if route in ("/network/nav_frame", "/nac/nav_frame"):
                self._send_html(render_nac_nav_frame())
                return

            if route in ("/network/main_frame", "/nac/main_frame"):
                mac = query.get("mac", [""])[0]
                updated = query.get("updated", [""])[0]
                self._send_html(render_nac_main_frame(state, mac_query=mac, updated_policy=updated))
                return

            if route in ("/network/edit_popup", "/nac/edit_popup"):
                mac = query.get("mac", [""])[0]
                self._send_html(render_nac_edit_popup(mac=mac))
                return

            if route == "/servicedesk/new":
                template_mode = query.get("template", ["incident"])[0]
                self._send_html(
                    render_servicedesk_page(
                        state,
                        template_mode=template_mode,
                        is_authenticated=authed,
                    )
                )
                return

            if route == "/portal/reports/borrow-overdue":
                self._send_html(render_borrow_report_page(is_authenticated=authed))
                return

            if route == "/portal/reports/borrow-overdue/download":
                report_path = AppPaths().sample_borrow_report_file
                if not report_path.is_file():
                    self._send_html("Sample report file not found", status=404)
                    return
                self._send_xlsx_bytes(report_path.read_bytes(), report_path.name)
                return

            if route == "/portal/forms/login":
                self._send_html(render_forms_login_page(state, is_authenticated=authed))
                return

            if route == "/portal/forms/view":
                form_no = query.get("id", [""])[0]
                self._send_html(
                    render_form_view_page(state, form_no=form_no, is_authenticated=authed)
                )
                return

            if route == "/portal/forms/frame":
                delay_ms = _resolve_form_delay_ms(query.get("delay_ms", [""])[0])
                if delay_ms > 0:
                    time.sleep(delay_ms / 1000.0)
                form_no = query.get("id", [""])[0]
                status_code = 200 if authed else 401
                self._send_html(
                    render_form_detail_frame(state, form_no=form_no, is_authenticated=authed),
                    status=status_code,
                )
                return

            self._send_html(render_home_page(state), status=404)

    return SandboxRequestHandler


class MockEnterpriseServer:
    """Background ThreadingHTTPServer with automatic port fallback (8000..8020)."""

    def __init__(self, host: str = "127.0.0.1", preferred_port: int = 8000) -> None:
        self.host = host
        self.preferred_port = preferred_port
        self.port = preferred_port
        self.state = SandboxState()
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    @property
    def is_running(self) -> bool:
        return self._server is not None and self._thread is not None and self._thread.is_alive()

    def reset_state(self) -> None:
        self.state.reset()

    def start(self) -> str:
        """Bind to the first available port starting at preferred_port and start serving."""
        if self.is_running:
            return self.base_url

        handler_cls = _make_handler_class(self.state)
        candidate_ports = [*range(self.preferred_port, self.preferred_port + 21), 0]
        last_exc: Exception | None = None

        for port in candidate_ports:
            if port != 0 and not _is_port_available(self.host, port):
                last_exc = OSError(errno.EADDRINUSE, f"Port {port} is already in use")
                logger.info(
                    "連接埠 %d 已被占用，自動改試下一個候選連接埠...",
                    port,
                )
                continue
            try:
                server = _ExclusiveThreadingHTTPServer((self.host, port), handler_cls)
                self.port = int(server.server_address[1])
                self._server = server
                break
            except OSError as exc:
                last_exc = exc
                logger.info(
                    "無法綁定連接埠 %d (%s)，自動改試下一個候選連接埠...",
                    port,
                    exc,
                )
                continue

        if self._server is None:
            raise RuntimeError(f"無法啟動內建沙盒伺服器：{last_exc}")

        self._thread = threading.Thread(
            target=self._server.serve_forever,
            name="MockEnterpriseServerThread",
            daemon=True,
        )
        self._thread.start()
        os.environ["IT_SUITE_SANDBOX_URL"] = self.base_url
        if self.port != self.preferred_port:
            logger.info(
                "預設連接埠 %d 已被占用，內建企業 IT 沙盒伺服器已自動改用：%s",
                self.preferred_port,
                self.base_url,
            )
        else:
            logger.info("內建企業 IT 沙盒伺服器已啟動：%s", self.base_url)
        return self.base_url

    def stop(self, timeout: float = 5.0) -> None:
        """Shut down the sandbox HTTP server and join its daemon thread."""
        if self._server is None:
            return
        try:
            self._server.shutdown()
            self._server.server_close()
            if self._thread is not None and self._thread.is_alive():
                self._thread.join(timeout=timeout)
            logger.info("內建企業 IT 沙盒伺服器已停止")
        except Exception:
            logger.exception("關閉內建沙盒伺服器時發生錯誤")
        finally:
            self._server = None
            self._thread = None

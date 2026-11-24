"""Standard SDK for standalone external tools in the `tools/` directory.

Provides:
- Project root (`BASE_DIR`) and `data/` directory resolution across source and frozen modes
- Windows DPAPI credential decryption (`data/credentials.dat`)
- Active Sandbox HTTP server discovery and auto-start fallback (`get_sandbox_base_url`, `ensure_sandbox_server`)
- Playwright Microsoft Edge browser launcher (`setup_browser`)
"""

from __future__ import annotations

import base64
import json
import os
import sys
import urllib.request
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import win32crypt
from playwright.sync_api import sync_playwright

EDGE_LAUNCH_ARGS = [
    "--start-maximized",
    "--disable-translate",
    ("--disable-features=DownloadBubble,DownloadBubbleV2,Translate,TranslateUI,msEdgeTranslate"),
]

DEFAULT_SANDBOX_CREDENTIALS: dict[str, str] = {
    "email": "alex.chen@enterprise.local",
    "portal_account": "it.admin",
    "portal_password": "Sandbox@2026",
    "nac_account": "nac.admin",
    "nac_password": "Sandbox@2026",
}


def get_base_dir() -> Path:
    """Resolve the application root directory (`it-rpa-suite/`).

    Supports:
    1. Explicit `IT_SUITE_BASE_DIR` environment variable (set when launched from Toolbox GUI)
    2. Frozen `.exe` inside `tools/` or `tools/<subdir>/`
    3. `.py` script inside `tools/` or `tools/<subdir>/`
    """
    env_base = os.environ.get("IT_SUITE_BASE_DIR", "").strip()
    if env_base:
        candidate = Path(env_base).resolve()
        if candidate.is_dir():
            return candidate

    start_path = (
        Path(sys.executable).resolve().parent
        if getattr(sys, "frozen", False)
        else Path(__file__).resolve().parent
    )

    for ancestor in (start_path, *start_path.parents):
        if (ancestor / "data").is_dir() or (ancestor / "pyproject.toml").is_file():
            return ancestor
        if ancestor.name.casefold() == "tools" and ancestor.parent != ancestor:
            return ancestor.parent

    return start_path.parent


BASE_DIR: Path = get_base_dir()


def decrypt_credentials(encrypted_text: str) -> dict[str, str]:
    """Decrypt Base64 DPAPI blob into a credential dictionary."""
    try:
        encrypted_blob = base64.b64decode(encrypted_text.strip().encode("utf-8"))
        _, raw_bytes = win32crypt.CryptUnprotectData(
            encrypted_blob,
            None,
            None,
            None,
            0,
        )
        parsed = json.loads(raw_bytes.decode("utf-8"))
        if not isinstance(parsed, dict):
            return {}
        return {str(k): str(v) for k, v in parsed.items()}
    except Exception as exc:
        raise RuntimeError(f"DPAPI 憑證解密失敗：{exc}") from exc


def read_credentials(
    base_dir: Path | None = None,
    allow_default_fallback: bool = True,
) -> dict[str, str]:
    """Read and decrypt `data/credentials.dat`.

    If the file does not exist and `allow_default_fallback=True`, returns
    `DEFAULT_SANDBOX_CREDENTIALS` so standalone sandbox demos can run immediately.
    """
    root_dir = (base_dir or BASE_DIR).resolve()
    cred_path = root_dir / "data" / "credentials.dat"

    if not cred_path.is_file():
        if allow_default_fallback:
            return dict(DEFAULT_SANDBOX_CREDENTIALS)
        raise FileNotFoundError(f"找不到系統憑證檔：{cred_path}（請先於主程式設定系統憑證）")

    encrypted_data = cred_path.read_text(encoding="utf-8").strip()
    if not encrypted_data:
        if allow_default_fallback:
            return dict(DEFAULT_SANDBOX_CREDENTIALS)
        raise RuntimeError(f"系統憑證檔內容為空：{cred_path}")

    data = decrypt_credentials(encrypted_data)
    return {
        "email": data.get("email", DEFAULT_SANDBOX_CREDENTIALS["email"]),
        "portal_account": data.get("portal_account", DEFAULT_SANDBOX_CREDENTIALS["portal_account"]),
        "portal_password": data.get(
            "portal_password", DEFAULT_SANDBOX_CREDENTIALS["portal_password"]
        ),
        "nac_account": data.get("nac_account", DEFAULT_SANDBOX_CREDENTIALS["nac_account"]),
        "nac_password": data.get("nac_password", DEFAULT_SANDBOX_CREDENTIALS["nac_password"]),
    }


def _is_sandbox_alive(base_url: str, timeout: float = 0.6) -> bool:
    """Return True if the sandbox `/api/directory` endpoint responds with valid sandbox JSON."""
    url = f"{base_url.rstrip('/')}/api/directory"
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if int(getattr(resp, "status", 0)) != 200:
                return False
            payload = json.loads(resp.read().decode("utf-8"))
            return (
                isinstance(payload, dict)
                and payload.get("ok") is True
                and isinstance(payload.get("results"), list)
            )
    except Exception:
        return False


def get_sandbox_base_url(preferred_port: int = 8000) -> str:
    """Locate the running local enterprise sandbox URL (probing ports 8000..8020)."""
    env_url = os.environ.get("IT_SUITE_SANDBOX_URL", "").strip()
    if env_url and _is_sandbox_alive(env_url):
        return env_url.rstrip("/")

    for port in range(preferred_port, preferred_port + 21):
        candidate = f"http://127.0.0.1:{port}"
        if _is_sandbox_alive(candidate):
            return candidate

    return env_url.rstrip("/") if env_url else f"http://127.0.0.1:{preferred_port}"


@contextmanager
def ensure_sandbox_server(preferred_port: int = 8000) -> Iterator[str]:
    """Yield an active sandbox URL; start an embedded server if none is running."""
    active_url = get_sandbox_base_url(preferred_port=preferred_port)
    if _is_sandbox_alive(active_url):
        yield active_url
        return

    src_dir = BASE_DIR / "src"
    if src_dir.is_dir() and str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))

    server: Any = None
    try:
        from it_rpa_suite.mock_server.server import MockEnterpriseServer

        server = MockEnterpriseServer(preferred_port=preferred_port)
        started_url = server.start()
        yield started_url
    except ImportError:
        yield active_url
    finally:
        if server is not None:
            try:
                server.stop()
            except Exception:
                pass


def setup_browser(
    headless: bool = False,
    downloads_path: str | None = None,
    dialog_action: str | Callable[[Any], None] | None = "accept",
    default_timeout_ms: int = 30000,
) -> tuple[Any, Any, Any, Any]:
    """Launch Microsoft Edge (with fallback to Chromium) and return `(playwright, browser, context, page)`."""
    playwright = sync_playwright().start()
    launch_args = [] if headless else EDGE_LAUNCH_ARGS

    try:
        browser = playwright.chromium.launch(
            channel="msedge",
            headless=headless,
            args=launch_args,
            downloads_path=downloads_path,
        )
    except Exception:
        browser = playwright.chromium.launch(
            headless=headless,
            args=launch_args,
            downloads_path=downloads_path,
        )

    context_kwargs: dict[str, Any] = {
        "accept_downloads": True,
        "ignore_https_errors": True,
        "locale": "zh-TW",
    }
    if not headless:
        context_kwargs["no_viewport"] = True

    context = browser.new_context(**context_kwargs)
    page = context.new_page()
    page.set_default_timeout(default_timeout_ms)

    if dialog_action == "accept":
        page.on("dialog", lambda dialog: dialog.accept())
    elif dialog_action == "dismiss":
        page.on("dialog", lambda dialog: dialog.dismiss())
    elif callable(dialog_action):
        page.on("dialog", dialog_action)

    return playwright, browser, context, page

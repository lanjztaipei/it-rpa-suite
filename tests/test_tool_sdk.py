"""Unit tests for `tools/tool_sdk.py` and `tools/_tool_template.py`."""

from __future__ import annotations

import asyncio
import subprocess
import sys
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_TOOLS_DIR = _REPO_ROOT / "tools"
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

import tool_sdk  # noqa: E402


@pytest.mark.unit
def test_tool_sdk_path_constants_and_helpers(tmp_path: Path) -> None:
    """Verify standard SDK path constants and source/_internal assets resolution."""
    assert tool_sdk.TOOLS_DIR == tool_sdk.BASE_DIR / "tools"
    assert tool_sdk.DATA_DIR == tool_sdk.BASE_DIR / "data"
    assert tool_sdk.DOWNLOADS_DIR == tool_sdk.DATA_DIR / "downloads"

    downloads = tool_sdk.get_downloads_dir(tmp_path, create=True)
    assert downloads == (tmp_path / "data" / "downloads").resolve()
    assert downloads.is_dir()

    # Packaged `_internal/assets` layout
    packaged_root = tmp_path / "packaged"
    (packaged_root / "_internal" / "assets").mkdir(parents=True)
    assert (
        tool_sdk.get_assets_dir(packaged_root) == (packaged_root / "_internal" / "assets").resolve()
    )

    # Source `assets` layout takes precedence
    source_root = tmp_path / "source"
    (source_root / "assets").mkdir(parents=True)
    assert tool_sdk.get_assets_dir(source_root) == (source_root / "assets").resolve()


@pytest.mark.unit
def test_tool_sdk_lazy_imports_playwright() -> None:
    """Verify importing `tool_sdk` does not eagerly import Playwright modules."""
    code = (
        "import sys; "
        f"sys.path.insert(0, {str(_TOOLS_DIR)!r}); "
        "import tool_sdk; "
        "assert 'playwright.sync_api' not in sys.modules; "
        "assert 'playwright.async_api' not in sys.modules"
    )
    completed = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr


@pytest.mark.unit
def test_subdir_tool_script_can_import_tool_sdk(tmp_path: Path) -> None:
    """Verify a script copied from `_tool_template.py` into `tools/<subdir>/` imports `tool_sdk`."""
    fake_root = tmp_path / "suite"
    (fake_root / "data").mkdir(parents=True)
    tools_dir = fake_root / "tools"
    tools_dir.mkdir(parents=True)
    (tools_dir / "tool_sdk.py").write_text(
        (_TOOLS_DIR / "tool_sdk.py").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    nested_dir = tools_dir / "custom_group" / "nested_tool"
    nested_dir.mkdir(parents=True)
    nested_script = nested_dir / "my_tool.py"
    nested_script.write_text(
        "\n".join(
            [
                "import sys",
                "from pathlib import Path",
                "_TOOLS_DIR = next(",
                "    (",
                "        parent",
                "        for parent in (Path(__file__).resolve().parent, *Path(__file__).resolve().parents)",
                "        if (parent / 'tool_sdk.py').is_file()",
                "    ),",
                "    Path(__file__).resolve().parent,",
                ")",
                "if str(_TOOLS_DIR) not in sys.path:",
                "    sys.path.insert(0, str(_TOOLS_DIR))",
                "import tool_sdk",
                "print(tool_sdk.BASE_DIR)",
                "print(tool_sdk.DOWNLOADS_DIR)",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    completed = subprocess.run(
        [sys.executable, str(nested_script)],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
    assert lines == [
        str(fake_root.resolve()),
        str((fake_root / "data" / "downloads").resolve()),
    ]


@pytest.mark.unit
def test_open_browser_context_manager_cleans_up_on_success_and_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify `open_browser` yields `page` and closes context/browser/playwright even on error."""
    events: list[str] = []

    def _fake_setup(**_kwargs: Any) -> tuple[Any, Any, Any, Any]:
        pw = MagicMock()
        pw.stop.side_effect = lambda: events.append("pw.stop")
        browser = MagicMock()
        browser.close.side_effect = lambda: events.append("browser.close")
        context = MagicMock()
        context.close.side_effect = lambda: events.append("context.close")
        page = MagicMock(name="page")
        return pw, browser, context, page

    monkeypatch.setattr(tool_sdk, "setup_browser", _fake_setup)

    with tool_sdk.open_browser(headless=True) as page:
        assert page is not None
    assert events == ["context.close", "browser.close", "pw.stop"]

    events.clear()
    with pytest.raises(RuntimeError, match="boom"):
        with tool_sdk.open_browser(headless=True):
            raise RuntimeError("boom")
    assert events == ["context.close", "browser.close", "pw.stop"]


@pytest.mark.unit
def test_open_async_browser_context_manager_cleans_up_on_success_and_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify `open_async_browser` yields `context` and awaits cleanup even on exception."""
    events: list[str] = []

    async def _fake_async_setup(**_kwargs: Any) -> tuple[Any, Any, Any]:
        pw = MagicMock()
        pw.stop = AsyncMock(side_effect=lambda: events.append("pw.stop"))
        browser = MagicMock()
        browser.close = AsyncMock(side_effect=lambda: events.append("browser.close"))
        context = MagicMock(name="context")
        context.close = AsyncMock(side_effect=lambda: events.append("context.close"))
        return pw, browser, context

    monkeypatch.setattr(tool_sdk, "setup_async_browser", _fake_async_setup)

    async def _run() -> None:
        async with tool_sdk.open_async_browser(headless=True) as ctx:
            assert ctx is not None
        assert events == ["context.close", "browser.close", "pw.stop"]

        events.clear()
        with pytest.raises(RuntimeError, match="async boom"):
            async with tool_sdk.open_async_browser(headless=True):
                raise RuntimeError("async boom")
        assert events == ["context.close", "browser.close", "pw.stop"]

    asyncio.run(_run())

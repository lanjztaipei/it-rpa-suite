"""GUI view and scanner for launching standalone external scripts in `tools/`."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Any

from it_rpa_suite.adapters.logger import get_logger
from it_rpa_suite.adapters.paths import get_app_paths
from it_rpa_suite.app.theme import FONT_FAMILY, configure_ui_styles, scale
from it_rpa_suite.app.widgets import ModernScrollbar

logger = get_logger(__name__)

EXCLUDED_TOOL_FILENAMES = frozenset(
    {
        "updater.exe",
        "updater.py",
        "tool_sdk.py",
        "_tool_template.py",
        "__init__.py",
    }
)

EXCLUDED_DIR_NAMES = frozenset(
    {
        "updater",
        "__pycache__",
        ".pytest_cache",
        ".ruff_cache",
        "build",
        "dist",
    }
)


def find_tool_files(search_dir: str | Path) -> list[dict[str, str]]:
    """Recursively scan `search_dir` for `.py` and `.exe` tools, excluding updater and SDK files."""
    root_path = Path(search_dir)
    if not root_path.is_dir():
        return []

    tool_files: list[dict[str, str]] = []

    for current_root, dirs, files in os.walk(root_path):
        # Prune excluded subdirectories in-place
        dirs[:] = [d for d in dirs if d.casefold() not in EXCLUDED_DIR_NAMES]

        for file_name in files:
            lower_name = file_name.casefold()
            if not lower_name.endswith((".exe", ".py")):
                continue
            if lower_name in EXCLUDED_TOOL_FILENAMES:
                continue

            full_path = Path(current_root) / file_name
            rel_path = full_path.relative_to(root_path)

            tool_files.append(
                {
                    "name": file_name,
                    "path": str(full_path),
                    "relative_path": str(rel_path),
                    "directory": str(full_path.parent),
                }
            )

    return sorted(tool_files, key=lambda item: item["relative_path"].casefold())


def run_tool(
    tool_path: str | Path,
    extra_env: dict[str, str] | None = None,
) -> tuple[bool, str]:
    """Launch a `.py` or `.exe` tool in a new console window."""
    target = Path(tool_path)
    if not target.is_file():
        return False, f"找不到檔案：{target}"

    try:
        tool_dir = target.parent
        creation_flags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
        if target.suffix.casefold() == ".py":
            if getattr(sys, "frozen", False):
                python_exe = shutil.which("python") or shutil.which("py")
                if not python_exe:
                    return (
                        False,
                        "目前為封裝執行檔模式，且系統 PATH 找不到 Python 直譯器，無法執行 .py 腳本。",
                    )
                command = [python_exe, str(target)]
            else:
                command = [sys.executable, str(target)]
        else:
            command = [str(target)]

        env = os.environ.copy()
        if extra_env:
            env.update(extra_env)

        subprocess.Popen(
            command,
            cwd=str(tool_dir),
            creationflags=creation_flags,
            env=env,
        )
        logger.info("已啟動自訂工具：%s", target)
        return True, ""
    except Exception as exc:
        logger.exception("啟動自訂工具失敗：%s", target)
        return False, str(exc)


def open_tools_directory(search_dir: str | Path) -> tuple[bool, str]:
    """Open the `tools/` directory in Windows File Explorer."""
    target_dir = Path(search_dir)
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
        startfile = getattr(os, "startfile", None)
        if startfile is not None:
            startfile(str(target_dir))
        logger.info("已開啟 tools 資料夾：%s", target_dir)
        return True, ""
    except Exception as exc:
        logger.exception("開啟 tools 資料夾失敗")
        return False, str(exc)


class ToolboxView(ttk.Frame):
    """GUI view scanning `tools/` and presenting external scripts as launchable cards."""

    def __init__(self, parent: tk.Misc, app: Any) -> None:
        self.app = app
        self.sf: float = float(getattr(app, "scale_factor", 1.5))
        self.colors: dict[str, str] = getattr(
            app, "colors", getattr(parent.winfo_toplevel(), "theme_colors", {})
        )
        self._configure_styles(parent)
        super().__init__(parent, style="Toolbox.Page.TFrame", padding=self.s(24))

        paths = getattr(app, "paths", None) or get_app_paths()
        self.search_dir: Path = Path(paths.tools_dir)
        self.tool_files: list[dict[str, str]] = []
        self._card_widgets: list[tk.Frame] = []
        self._resize_after_id: str | None = None

        self.card_min_width = self.s(360)
        self.card_height = self.s(64)
        self.card_gap = self.s(10)
        self.tool_list_width = int((self.card_min_width + self.s(44)) * 1.15)
        self.tool_list_height = int((self.card_height + self.card_gap) * 4.5)

        self._build_widgets()
        self._refresh_tools()

    def s(self, value: float) -> int:
        return scale(value, self.sf)

    def _configure_styles(self, widget: tk.Misc) -> ttk.Style:
        style = configure_ui_styles(widget, sf=self.sf)
        page_bg = self.colors.get("background", "#F3F6FA")
        card_bg = self.colors.get("surface", "#FFFFFF")
        surface_soft = self.colors.get("surface_soft", "#F8FAFC")
        text_color = self.colors.get("text", "#172033")
        muted_color = self.colors.get("text_secondary", "#667085")
        pressed_color = self.colors.get("button_pressed", "#E9EEF5")

        style.configure("Toolbox.Page.TFrame", background=page_bg)
        style.configure("Toolbox.Card.TFrame", background=card_bg)
        style.configure(
            "Toolbox.Title.TLabel",
            background=page_bg,
            foreground=text_color,
            font=(FONT_FAMILY, self.s(22), "bold"),
        )
        style.configure(
            "Toolbox.Subtitle.TLabel",
            background=page_bg,
            foreground=muted_color,
            font=(FONT_FAMILY, self.s(10)),
        )
        style.configure(
            "Toolbox.Secondary.TButton",
            font=(FONT_FAMILY, self.s(9.5), "bold"),
            padding=(self.s(10), self.s(5)),
            background=surface_soft,
            foreground=text_color,
            relief="flat",
            borderwidth=0,
        )
        style.map(
            "Toolbox.Secondary.TButton",
            background=[
                ("active", card_bg),
                ("pressed", pressed_color),
                ("disabled", surface_soft),
            ],
            foreground=[("disabled", muted_color)],
            relief=[("pressed", "flat")],
        )
        return style

    def _build_widgets(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self.content_frame = ttk.Frame(self, style="Toolbox.Page.TFrame")
        self.content_frame.grid(row=0, column=0)
        self.content_frame.columnconfigure(0, weight=1)

        self._build_header()
        self._build_tool_cards()

    def _build_header(self) -> None:
        header = ttk.Frame(self.content_frame, style="Toolbox.Page.TFrame")
        header.grid(row=0, column=0, sticky="ew", pady=(0, self.s(18)))
        header.columnconfigure(0, weight=1)

        ttk.Label(
            header,
            text="個人自訂工具箱",
            style="Toolbox.Title.TLabel",
            anchor="center",
        ).grid(row=0, column=0, sticky="ew")

        ttk.Label(
            header,
            text=f"動態掃描 {self.search_dir}",
            style="Toolbox.Subtitle.TLabel",
            anchor="center",
            justify="center",
            wraplength=self.s(680),
        ).grid(row=1, column=0, sticky="ew", pady=(self.s(6), 0))

    def _build_tool_cards(self) -> None:
        surface_soft = self.colors.get("surface_soft", "#F8FAFC")
        border_color = self.colors.get("border", "#E4E9F0")

        container = tk.Frame(
            self.content_frame,
            background=surface_soft,
            highlightbackground=border_color,
            highlightcolor=border_color,
            highlightthickness=1,
            takefocus=0,
            padx=self.s(12),
            pady=self.s(12),
        )
        container.grid(row=1, column=0)
        container.columnconfigure(0, weight=1)
        container.rowconfigure(0, weight=0)

        canvas_frame = ttk.Frame(
            container,
            style="Toolbox.Card.TFrame",
            width=self.tool_list_width,
            height=self.tool_list_height,
        )
        canvas_frame.grid(row=0, column=0, sticky="n")
        canvas_frame.grid_propagate(False)
        canvas_frame.columnconfigure(0, weight=1)
        canvas_frame.rowconfigure(0, weight=1)

        self.card_canvas = tk.Canvas(
            canvas_frame,
            background=surface_soft,
            highlightthickness=0,
            borderwidth=0,
        )
        self.card_canvas.grid(row=0, column=0, sticky="nsew")

        self.card_scrollbar = ModernScrollbar(
            canvas_frame,
            command=self.card_canvas.yview,
            width=self.s(8),
            track_color=surface_soft,
            thumb_color="#CBD5E1",
            thumb_hover_color="#94A3B8",
            min_thumb_height=self.s(32),
        )
        self.card_scrollbar.grid(row=0, column=1, sticky="ns", padx=(2, 0))
        self.card_canvas.configure(yscrollcommand=self.card_scrollbar.set)

        self.cards_frame = tk.Frame(self.card_canvas, background=surface_soft)
        self.cards_window = self.card_canvas.create_window(
            (0, 0),
            window=self.cards_frame,
            anchor="nw",
        )

        self.cards_frame.bind("<Configure>", self._update_scroll_region)
        self.card_canvas.bind("<Configure>", self._on_canvas_resize)
        self.card_canvas.bind("<Enter>", self._bind_mousewheel)
        self.card_canvas.bind("<Leave>", self._unbind_mousewheel)
        self.bind("<Destroy>", self._on_destroy, add="+")

        footer = tk.Frame(container, background=surface_soft)
        footer.grid(row=1, column=0, pady=(self.s(12), 0))

        ttk.Button(
            footer,
            text="▱ 開啟工具箱資料夾",
            style="Toolbox.Secondary.TButton",
            cursor="hand2",
            command=self._open_tools_directory,
        ).pack(side="left")

        ttk.Button(
            footer,
            text="↻ 重新整理",
            style="Toolbox.Secondary.TButton",
            cursor="hand2",
            command=self._refresh_tools,
        ).pack(side="left", padx=(self.s(10), 0))

    def on_show(self) -> None:
        pass

    def _refresh_tools(self) -> None:
        logger.info("開始掃描自訂工具箱目錄：%s", self.search_dir)
        try:
            self.search_dir.mkdir(parents=True, exist_ok=True)
            self.tool_files = find_tool_files(self.search_dir)
        except Exception as exc:
            logger.exception("掃描自訂工具箱目錄失敗")
            self.tool_files = []
            messagebox.showerror(
                "掃描失敗",
                f"無法掃描 tools 資料夾。\n\n錯誤內容：{exc}",
                parent=self,
            )
            return

        self._populate_cards()

    def _populate_cards(self) -> None:
        for widget in self.cards_frame.winfo_children():
            widget.destroy()
        self._card_widgets.clear()

        surface_soft = self.colors.get("surface_soft", "#F8FAFC")
        card_bg = self.colors.get("surface", "#FFFFFF")
        border_color = self.colors.get("border", "#E4E9F0")
        primary_color = self.colors.get("primary", "#2D6CDF")
        text_color = self.colors.get("text", "#172033")
        muted_color = self.colors.get("text_muted", "#98A2B3")

        if not self.tool_files:
            empty_label = tk.Label(
                self.cards_frame,
                text="沒有可執行的工具腳本（請將 .py 或 .exe 放入 tools 資料夾）",
                background=surface_soft,
                foreground=muted_color,
                font=(FONT_FAMILY, self.s(10)),
                pady=self.s(32),
            )
            empty_label.grid(row=0, column=0, sticky="ew")
            self.cards_frame.columnconfigure(0, weight=1)
            return

        for tool_info in self.tool_files:
            card = tk.Frame(
                self.cards_frame,
                background=card_bg,
                highlightbackground=border_color,
                highlightcolor=primary_color,
                highlightthickness=1,
                cursor="hand2",
                height=self.card_height,
            )
            card.grid_propagate(False)
            card.columnconfigure(0, weight=1)
            card.rowconfigure(0, weight=1)

            display_name = tool_info["name"]
            label = tk.Label(
                card,
                text=display_name,
                background=card_bg,
                foreground=text_color,
                font=(FONT_FAMILY, self.s(10.5), "bold"),
                anchor="w",
                justify="left",
                wraplength=self.tool_list_width - self.s(60),
                cursor="hand2",
            )
            label.grid(
                row=0,
                column=0,
                sticky="ew",
                padx=(self.s(16), self.s(8)),
                pady=self.s(12),
            )

            arrow = tk.Label(
                card,
                text="›",
                background=card_bg,
                foreground=muted_color,
                font=(FONT_FAMILY, self.s(18)),
                cursor="hand2",
            )
            arrow.grid(row=0, column=1, padx=(self.s(6), self.s(16)))

            def _on_click(_e: tk.Event[Any], info: dict[str, Any] = tool_info) -> Any:
                return self._launch_tool(info)

            def _on_enter(
                _e: tk.Event[Any],
                c: tk.Frame = card,
                lbl: tk.Label = label,
                arr: tk.Label = arrow,
            ) -> Any:
                return self._set_card_hover(c, lbl, arr, True)

            def _on_leave(
                _e: tk.Event[Any],
                c: tk.Frame = card,
                lbl: tk.Label = label,
                arr: tk.Label = arrow,
            ) -> Any:
                return self._set_card_hover(c, lbl, arr, False)

            for widget in (card, label, arrow):
                widget.bind("<Button-1>", _on_click)
                widget.bind("<Enter>", _on_enter)
                widget.bind("<Leave>", _on_leave)

            self._card_widgets.append(card)

        self._layout_cards()

    def _layout_cards(self) -> None:
        if not self._card_widgets:
            return

        self.cards_frame.columnconfigure(0, weight=1, uniform="tool_card")
        for index, card in enumerate(self._card_widgets):
            card.grid(
                row=index,
                column=0,
                sticky="nsew",
                padx=self.card_gap // 2,
                pady=self.card_gap // 2,
            )

    def _on_canvas_resize(self, event: Any) -> None:
        self.card_canvas.itemconfigure(self.cards_window, width=event.width)
        if self._resize_after_id is not None:
            self.after_cancel(self._resize_after_id)
        self._resize_after_id = self.after(80, self._layout_cards)

    def _update_scroll_region(self, _event: Any = None) -> None:
        self.card_canvas.configure(scrollregion=self.card_canvas.bbox("all"))

    def _bind_mousewheel(self, _event: Any = None) -> None:
        self.card_canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    def _unbind_mousewheel(self, _event: Any = None) -> None:
        try:
            self.card_canvas.unbind_all("<MouseWheel>")
        except tk.TclError:
            pass

    def _on_destroy(self, event: Any = None) -> None:
        if event is not None and event.widget is not self:
            return
        self._unbind_mousewheel()
        if self._resize_after_id is not None:
            try:
                self.after_cancel(self._resize_after_id)
            except tk.TclError:
                pass
            self._resize_after_id = None

    def _on_mousewheel(self, event: Any) -> None:
        try:
            if not self.winfo_exists() or not self.card_canvas.winfo_exists():
                return
            self.card_canvas.yview_scroll(int(-event.delta / 120), "units")
        except tk.TclError:
            pass

    def _set_card_hover(
        self,
        card: tk.Frame,
        label: tk.Label,
        arrow: tk.Label,
        hovered: bool,
    ) -> None:
        bg = (
            self.colors.get("card_hover", "#F0F5FD")
            if hovered
            else self.colors.get("surface", "#FFFFFF")
        )
        primary = self.colors.get("primary", "#2D6CDF")
        text_color = self.colors.get("text", "#172033")
        muted_color = self.colors.get("text_muted", "#98A2B3")

        card.configure(background=bg)
        label.configure(
            background=bg,
            foreground=primary if hovered else text_color,
        )
        arrow.configure(
            background=bg,
            foreground=primary if hovered else muted_color,
        )

    def _launch_tool(self, tool_info: dict[str, str]) -> None:
        tool_path = tool_info["path"]
        if not os.path.isfile(tool_path):
            messagebox.showerror(
                "找不到程式",
                f"選取的程式已不存在：\n\n{tool_path}\n\n請點擊「重新整理」更新清單。",
                parent=self,
            )
            return

        extra_env: dict[str, str] = {}
        if hasattr(self.app, "sandbox_base_url"):
            extra_env["IT_SUITE_SANDBOX_URL"] = str(self.app.sandbox_base_url)
        if hasattr(self.app, "paths") and hasattr(self.app.paths, "base_dir"):
            extra_env["IT_SUITE_BASE_DIR"] = str(self.app.paths.base_dir)

        success, error_message = run_tool(tool_path, extra_env=extra_env)
        if not success:
            messagebox.showerror(
                "啟動失敗",
                f"無法啟動程式：\n{tool_info['name']}\n\n錯誤內容：{error_message}",
                parent=self,
            )
            return

        if hasattr(self.app, "record_feature_usage"):
            try:
                self.app.record_feature_usage("custom_tool")
            except Exception:
                pass

    def _open_tools_directory(self) -> None:
        success, error_message = open_tools_directory(self.search_dir)
        if not success:
            messagebox.showerror("開啟資料夾失敗", error_message, parent=self)

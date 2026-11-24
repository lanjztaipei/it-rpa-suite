"""Centralized theme palette, DPI awareness, scale_factor calculation, and ttk.Style configuration."""

from __future__ import annotations

import sys
import tkinter as tk
from tkinter import ttk

from it_rpa_suite.adapters.logger import get_logger

logger = get_logger(__name__)

FONT_FAMILY = "Microsoft JhengHei UI"

LIGHT_COLORS: dict[str, str] = {
    "background": "#F3F6FA",
    "surface": "#FFFFFF",
    "surface_soft": "#F8FAFC",
    "sidebar": "#172033",
    "sidebar_hover": "#24324A",
    "sidebar_active": "#2D6CDF",
    "primary": "#2D6CDF",
    "primary_hover": "#245ABD",
    "success": "#16A36A",
    "warning": "#E79A24",
    "danger": "#D84A4A",
    "text": "#172033",
    "text_secondary": "#667085",
    "text_muted": "#98A2B3",
    "border": "#E4E9F0",
    "white": "#FFFFFF",
    "button_active": "#EEF2F7",
    "button_pressed": "#E9EEF5",
    "card_hover": "#F0F5FD",
}

DARK_COLORS: dict[str, str] = {
    "background": "#0F172A",
    "surface": "#172033",
    "surface_soft": "#111827",
    "sidebar": "#090F1D",
    "sidebar_hover": "#1E293B",
    "sidebar_active": "#2D6CDF",
    "primary": "#60A5FA",
    "primary_hover": "#3B82F6",
    "success": "#34D399",
    "warning": "#FBBF24",
    "danger": "#F87171",
    "text": "#F1F5F9",
    "text_secondary": "#CBD5E1",
    "text_muted": "#94A3B8",
    "border": "#334155",
    "white": "#FFFFFF",
    "button_active": "#263449",
    "button_pressed": "#334155",
    "card_hover": "#22314A",
}


def scale(value: float, scale_factor: float = 1.5) -> int:
    """Scale a base pixel/point value by the unified scale_factor."""
    return round(value * scale_factor)


def enable_windows_dpi_awareness() -> None:
    """Enable Windows Per-Monitor DPI Awareness V2 before creating tk.Tk()."""
    if sys.platform != "win32":
        return

    try:
        import ctypes

        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        logger.info("已啟用 Per-Monitor DPI Awareness V2")
        return
    except Exception:
        logger.debug("無法啟用 Per-Monitor DPI Awareness V2", exc_info=True)

    try:
        import ctypes

        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        logger.info("已啟用 Per-Monitor DPI Awareness")
        return
    except Exception:
        logger.debug("無法啟用 Per-Monitor DPI Awareness", exc_info=True)

    try:
        import ctypes

        ctypes.windll.user32.SetProcessDPIAware()
        logger.info("已啟用 System DPI Awareness")
    except Exception:
        logger.warning("無法啟用 Windows DPI Awareness", exc_info=True)


class ThemeManager:
    """Centralized manager for light/dark color palettes and unified scale_factor."""

    BASE_WIDTH = 1180
    BASE_HEIGHT = 760
    MIN_SCALE = 0.75
    MAX_SCALE = 2.00
    SCALE_STEP = 0.05

    def __init__(self, is_dark_mode: bool = False, initial_scale: float = 1.5) -> None:
        self.is_dark_mode = bool(is_dark_mode)
        self.scale_factor = float(initial_scale)
        self.colors: dict[str, str] = (DARK_COLORS if self.is_dark_mode else LIGHT_COLORS).copy()

    def s(self, value: float) -> int:
        """Scale a design metric using the current scale_factor."""
        return scale(value, self.scale_factor)

    def set_dark_mode(self, is_dark: bool) -> dict[str, str]:
        """Update dark mode state and refresh the color palette dictionary in-place."""
        self.is_dark_mode = bool(is_dark)
        self.colors.clear()
        self.colors.update(DARK_COLORS if self.is_dark_mode else LIGHT_COLORS)
        return self.colors

    def compute_window_scale(self, width: int, height: int) -> float:
        """Compute quantized scale_factor from window dimensions."""
        width_scale = width / self.BASE_WIDTH
        height_scale = height / self.BASE_HEIGHT
        raw_scale = min(width_scale, height_scale)
        clamped = max(self.MIN_SCALE, min(self.MAX_SCALE, raw_scale))
        quantized = round(clamped / self.SCALE_STEP) * self.SCALE_STEP
        return round(quantized, 2)

    def apply_styles(self, root: tk.Misc) -> ttk.Style:
        """Apply unified ttk styles to root using current colors and scale_factor."""
        setattr(root, "theme_colors", self.colors)
        setattr(root, "scale_factor", self.scale_factor)
        return configure_ui_styles(root, sf=self.scale_factor)


def configure_ui_styles(widget: tk.Misc, sf: float | None = None) -> ttk.Style:
    """Configure shared ttk styles on widget's toplevel window."""
    style = ttk.Style(widget)
    if "clam" in style.theme_names():
        style.theme_use("clam")

    root = widget.winfo_toplevel()
    colors: dict[str, str] = getattr(root, "theme_colors", LIGHT_COLORS)
    if sf is None:
        sf = float(getattr(widget, "sf", getattr(root, "scale_factor", 1.5)))

    app_bg = colors.get("background", "#F3F6FA")
    surface = colors.get("surface", "#FFFFFF")
    surface_soft = colors.get("surface_soft", "#F8FAFC")
    text_color = colors.get("text", "#172033")
    text_secondary = colors.get("text_secondary", "#667085")
    text_muted = colors.get("text_muted", "#98A2B3")
    border_color = colors.get("border", "#E4E9F0")
    primary = colors.get("primary", "#2D6CDF")
    primary_hover = colors.get("primary_hover", "#245ABD")
    btn_active = colors.get("button_active", "#EEF2F7")
    btn_pressed = colors.get("button_pressed", "#E9EEF5")

    style.configure(
        ".",
        font=(FONT_FAMILY, scale(10, sf)),
        background=app_bg,
        foreground=text_color,
    )
    style.configure("TFrame", background=app_bg)
    style.configure("App.TFrame", background=app_bg)
    style.configure("Content.TFrame", background=app_bg)
    style.configure("Card.TFrame", background=surface)

    style.configure(
        "TLabel",
        font=(FONT_FAMILY, scale(10, sf)),
        background=app_bg,
        foreground=text_color,
    )
    style.configure(
        "Title.TLabel",
        font=(FONT_FAMILY, scale(22, sf), "bold"),
        background=app_bg,
        foreground=text_color,
    )
    style.configure(
        "Subtitle.TLabel",
        font=(FONT_FAMILY, scale(10, sf)),
        background=app_bg,
        foreground=text_secondary,
    )
    style.configure(
        "SectionTitle.TLabel",
        font=(FONT_FAMILY, scale(13, sf), "bold"),
        background=app_bg,
        foreground=text_color,
    )
    style.configure(
        "StatusBar.TFrame",
        background=surface,
        relief="flat",
    )
    style.configure(
        "StatusBar.TLabel",
        background=surface,
        foreground=text_secondary,
        font=(FONT_FAMILY, scale(9, sf)),
    )

    style.configure(
        "TRadiobutton",
        font=(FONT_FAMILY, scale(10, sf)),
        background=app_bg,
        foreground=text_color,
    )
    style.map(
        "TRadiobutton",
        background=[("active", app_bg)],
        foreground=[("disabled", text_muted)],
    )

    style.configure(
        "TCheckbutton",
        font=(FONT_FAMILY, scale(10, sf)),
        background=app_bg,
        foreground=text_color,
    )
    style.map(
        "TCheckbutton",
        background=[("active", app_bg)],
        foreground=[("disabled", text_muted)],
    )

    style.configure("TSeparator", background=border_color)

    style.configure(
        "Modern.TEntry",
        padding=(scale(11, sf), scale(8, sf)),
        fieldbackground=surface,
        foreground=text_color,
        insertcolor=text_color,
        bordercolor=border_color,
        lightcolor=border_color,
        darkcolor=border_color,
        relief="flat",
        borderwidth=1,
    )
    style.map(
        "Modern.TEntry",
        foreground=[("disabled", text_muted)],
        bordercolor=[("focus", primary), ("disabled", border_color)],
        lightcolor=[("focus", primary)],
        darkcolor=[("focus", primary)],
        fieldbackground=[
            ("disabled", surface_soft),
            ("readonly", surface),
            ("!disabled", surface),
        ],
    )

    style.configure(
        "Primary.TButton",
        font=(FONT_FAMILY, scale(10.5, sf), "bold"),
        foreground="#FFFFFF",
        background=primary,
        padding=(scale(14, sf), scale(8, sf)),
        relief="flat",
        borderwidth=0,
    )
    style.map(
        "Primary.TButton",
        foreground=[("disabled", "#E5E7EB"), ("active", "#FFFFFF")],
        background=[
            ("disabled", text_muted),
            ("pressed", primary_hover),
            ("active", primary_hover),
        ],
        relief=[("pressed", "flat"), ("active", "flat")],
    )

    style.configure(
        "Secondary.TButton",
        font=(FONT_FAMILY, scale(10, sf), "bold"),
        foreground=text_color,
        background=surface,
        padding=(scale(12, sf), scale(7, sf)),
        borderwidth=1,
        relief="flat",
    )
    style.map(
        "Secondary.TButton",
        background=[("pressed", btn_pressed), ("active", btn_active)],
    )

    return style

"""Shared custom Tkinter and ttk widgets for IT RPA Suite."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk
from typing import Any, Literal

from it_rpa_suite.app.theme import FONT_FAMILY, LIGHT_COLORS, scale


def add_entry_placeholder(
    owner: tk.Misc,
    entry: ttk.Entry,
    textvariable: tk.StringVar,
    text: str,
) -> tk.Label:
    """Attach a non-intrusive centered placeholder label to a ttk.Entry without mutating its StringVar."""
    root = owner.winfo_toplevel()
    colors: dict[str, str] = getattr(root, "theme_colors", LIGHT_COLORS)
    sf = float(getattr(owner, "sf", getattr(root, "scale_factor", 1.5)))

    placeholder = tk.Label(
        entry.master,
        text=text,
        font=(FONT_FAMILY, scale(10.5, sf)),
        foreground=colors.get("text_muted", "#98A2B3"),
        background=colors.get("surface", "#FFFFFF"),
        cursor="xterm",
    )

    def update_placeholder(*_args: Any) -> None:
        try:
            if not entry.winfo_exists() or not placeholder.winfo_exists():
                return
            state = str(entry.cget("state"))
            bg = (
                colors.get("surface_soft", "#F8FAFC")
                if state == "disabled"
                else colors.get("surface", "#FFFFFF")
            )
            placeholder.configure(background=bg)
            if textvariable.get():
                placeholder.place_forget()
            else:
                placeholder.place(in_=entry, relx=0.5, rely=0.5, anchor="center")
                placeholder.lift()
        except tk.TclError:
            pass

    def focus_entry(_event: Any = None) -> None:
        try:
            if str(entry.cget("state")) != "disabled":
                entry.focus_set()
        except tk.TclError:
            pass

    placeholder.bind("<Button-1>", focus_entry)
    entry.bind("<FocusIn>", lambda _e: update_placeholder(), add="+")
    entry.bind("<FocusOut>", lambda _e: owner.after_idle(update_placeholder), add="+")

    trace_id = textvariable.trace_add("write", update_placeholder)

    def remove_trace(event: Any = None) -> None:
        if event is not None and event.widget is not entry:
            return
        try:
            textvariable.trace_remove("write", trace_id)
        except (tk.TclError, ValueError):
            pass
        try:
            if placeholder.winfo_exists():
                placeholder.destroy()
        except tk.TclError:
            pass

    entry.bind("<Destroy>", remove_trace, add="+")
    owner.after_idle(update_placeholder)
    return placeholder


def create_modern_entry(
    parent: tk.Misc,
    *,
    owner: tk.Misc,
    textvariable: tk.StringVar,
    placeholder: str | None = None,
    width: int = 30,
    justify: Literal["left", "center", "right"] = "center",
) -> ttk.Entry:
    """Create a styled Modern.TEntry with optional placeholder overlay."""
    root = owner.winfo_toplevel()
    sf = float(getattr(owner, "sf", getattr(root, "scale_factor", 1.5)))
    entry = ttk.Entry(
        parent,
        textvariable=textvariable,
        font=(FONT_FAMILY, scale(10.5, sf)),
        style="Modern.TEntry",
        width=width,
        justify=justify,
    )
    if placeholder:
        add_entry_placeholder(
            owner=owner,
            entry=entry,
            textvariable=textvariable,
            text=placeholder,
        )
    return entry


def create_primary_button(
    parent: tk.Misc,
    *,
    text: str,
    command: Callable[[], Any],
) -> ttk.Button:
    """Create a primary action button using Primary.TButton style."""
    return ttk.Button(
        parent,
        text=text,
        command=command,
        style="Primary.TButton",
        cursor="hand2",
    )


def create_secondary_button(
    parent: tk.Misc,
    *,
    text: str,
    command: Callable[[], Any],
) -> ttk.Button:
    """Create a secondary action button using Secondary.TButton style."""
    return ttk.Button(
        parent,
        text=text,
        command=command,
        style="Secondary.TButton",
        cursor="hand2",
    )


class ToggleSwitch(tk.Canvas):
    """Custom pill-shaped boolean toggle switch widget."""

    def __init__(
        self,
        parent: tk.Misc,
        variable: tk.BooleanVar,
        command: Callable[[bool], Any] | None = None,
        on_color: str = "#16A36A",
        off_color: str = "#667085",
        knob_color: str = "#FFFFFF",
        width: int = 46,
        height: int = 24,
    ) -> None:
        parent_bg = self._get_parent_background(parent)
        super().__init__(
            parent,
            width=width,
            height=height,
            highlightthickness=0,
            borderwidth=0,
            relief="flat",
            background=parent_bg,
            cursor="hand2",
        )
        self.variable = variable
        self.command = command
        self.on_color = on_color
        self.off_color = off_color
        self.knob_color = knob_color
        self.switch_width = width
        self.switch_height = height
        self.trace_id: str | None = None

        self.bind("<Button-1>", self._on_click)
        self.bind("<Destroy>", self._on_destroy)
        self.trace_id = self.variable.trace_add("write", self._on_variable_changed)
        self._draw()

    @staticmethod
    def _get_parent_background(parent: tk.Misc) -> str:
        try:
            return str(parent.cget("background"))
        except (tk.TclError, KeyError):
            return "#F0F0F0"

    def _on_click(self, _event: Any = None) -> None:
        new_value = not bool(self.variable.get())
        self.variable.set(new_value)
        if callable(self.command):
            self.command(new_value)

    def _on_variable_changed(self, *_args: Any) -> None:
        try:
            if self.winfo_exists():
                self._draw()
        except tk.TclError:
            pass

    def _on_destroy(self, event: Any = None) -> None:
        if event is not None and event.widget is not self:
            return
        if not self.trace_id:
            return
        try:
            self.variable.trace_remove("write", self.trace_id)
        except (tk.TclError, ValueError):
            pass
        self.trace_id = None

    def _draw(self) -> None:
        try:
            self.delete("all")
        except tk.TclError:
            return

        enabled = bool(self.variable.get())
        track_color = self.on_color if enabled else self.off_color
        height = self.switch_height
        width = self.switch_width
        radius = height // 2

        self.create_oval(1, 1, height - 1, height - 1, fill=track_color, outline=track_color)
        self.create_oval(
            width - height + 1,
            1,
            width - 1,
            height - 1,
            fill=track_color,
            outline=track_color,
        )
        self.create_rectangle(
            radius,
            1,
            width - radius,
            height - 1,
            fill=track_color,
            outline=track_color,
        )

        knob_padding = 3
        knob_size = height - knob_padding * 2
        knob_x = (width - knob_size - knob_padding) if enabled else knob_padding
        self.create_oval(
            knob_x,
            knob_padding,
            knob_x + knob_size,
            knob_padding + knob_size,
            fill=self.knob_color,
            outline="",
        )


class ModernScrollbar(tk.Canvas):
    """Slim rounded vertical scrollbar canvas supporting drag and page-click."""

    def __init__(
        self,
        parent: tk.Misc,
        command: Callable[..., Any] | None = None,
        width: int = 8,
        track_color: str = "#172033",
        thumb_color: str = "#46556D",
        thumb_hover_color: str = "#70819B",
        min_thumb_height: int = 36,
    ) -> None:
        super().__init__(
            parent,
            width=width,
            highlightthickness=0,
            borderwidth=0,
            relief="flat",
            background=track_color,
            cursor="hand2",
        )
        self.command = command
        self.thumb_color = thumb_color
        self.thumb_hover_color = thumb_hover_color
        self.min_thumb_height = min_thumb_height

        self.first = 0.0
        self.last = 1.0
        self.dragging = False
        self.drag_start_y = 0
        self.drag_start_first = 0.0
        self.thumb_hovered = False

        self.bind("<Configure>", self._on_configure)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<ButtonPress-1>", self._on_button_press)
        self.bind("<B1-Motion>", self._on_drag)
        self.bind("<ButtonRelease-1>", self._on_button_release)

    def set(self, first: float | str, last: float | str) -> None:
        try:
            self.first = float(first)
            self.last = float(last)
        except (TypeError, ValueError):
            self.first = 0.0
            self.last = 1.0

        self.first = min(max(self.first, 0.0), 1.0)
        self.last = min(max(self.last, self.first), 1.0)
        self._draw()

    def _on_configure(self, _event: Any = None) -> None:
        self._draw()

    def _on_enter(self, _event: Any = None) -> None:
        self.thumb_hovered = True
        self._draw()

    def _on_leave(self, _event: Any = None) -> None:
        if not self.dragging:
            self.thumb_hovered = False
            self._draw()

    def _get_thumb_geometry(self) -> tuple[float, float]:
        canvas_height = self.winfo_height()
        if canvas_height <= 1:
            return 0.0, 0.0

        visible_ratio = max(self.last - self.first, 0.0)
        thumb_height = min(max(canvas_height * visible_ratio, self.min_thumb_height), canvas_height)
        available_height = max(canvas_height - thumb_height, 0)
        max_first = max(1.0 - visible_ratio, 0.0)
        position_ratio = (self.first / max_first) if max_first > 0 else 0.0
        position_ratio = min(max(position_ratio, 0.0), 1.0)

        thumb_top = available_height * position_ratio
        thumb_bottom = thumb_top + thumb_height
        return thumb_top, thumb_bottom

    def _draw(self) -> None:
        try:
            self.delete("all")
            canvas_width = self.winfo_width()
            canvas_height = self.winfo_height()
        except tk.TclError:
            return

        if canvas_width <= 1 or canvas_height <= 1:
            return
        if self.first <= 0.0 and self.last >= 1.0:
            return

        thumb_top, thumb_bottom = self._get_thumb_geometry()
        padding = 2
        left = padding
        right = max(canvas_width - padding, left + 1)
        color = (
            self.thumb_hover_color if (self.thumb_hovered or self.dragging) else self.thumb_color
        )
        radius = min((right - left) / 2, (thumb_bottom - thumb_top) / 2)
        if radius <= 0:
            return

        self.create_rectangle(
            left,
            thumb_top + radius,
            right,
            thumb_bottom - radius,
            fill=color,
            outline="",
        )
        self.create_oval(
            left,
            thumb_top,
            right,
            thumb_top + radius * 2,
            fill=color,
            outline="",
        )
        self.create_oval(
            left,
            thumb_bottom - radius * 2,
            right,
            thumb_bottom,
            fill=color,
            outline="",
        )

    def _on_button_press(self, event: Any) -> None:
        thumb_top, thumb_bottom = self._get_thumb_geometry()
        if thumb_top <= event.y <= thumb_bottom:
            self.dragging = True
            self.drag_start_y = event.y
            self.drag_start_first = self.first
            self.thumb_hovered = True
            try:
                self.grab_set()
            except tk.TclError:
                pass
            self._draw()
            return

        if not callable(self.command):
            return
        if event.y < thumb_top:
            self.command("scroll", -1, "pages")
        else:
            self.command("scroll", 1, "pages")

    def _on_drag(self, event: Any) -> None:
        if not self.dragging or not callable(self.command):
            return

        canvas_height = self.winfo_height()
        thumb_top, thumb_bottom = self._get_thumb_geometry()
        thumb_height = thumb_bottom - thumb_top
        available_height = max(canvas_height - thumb_height, 1)
        visible_ratio = max(self.last - self.first, 0.0)
        max_first = max(1.0 - visible_ratio, 0.0)

        delta_y = event.y - self.drag_start_y
        new_first = self.drag_start_first + (delta_y / available_height * max_first)
        new_first = min(max(new_first, 0.0), max_first)
        self.command("moveto", new_first)

    def _on_button_release(self, _event: Any = None) -> None:
        self.dragging = False
        try:
            if self.grab_current() is self:
                self.grab_release()
        except tk.TclError:
            pass

        try:
            px, py = self.winfo_pointerx(), self.winfo_pointery()
            wl, wt = self.winfo_rootx(), self.winfo_rooty()
            wr, wb = wl + self.winfo_width(), wt + self.winfo_height()
            pointer_inside = (wl <= px <= wr) and (wt <= py <= wb)
        except tk.TclError:
            pointer_inside = False

        self.thumb_hovered = pointer_inside
        self._draw()


def show_confirm_dialog(
    parent: tk.Misc,
    title: str,
    message: str,
    confirm_text: str = "是",
    cancel_text: str = "否",
    sf: float | None = None,
) -> bool:
    """Display a modal confirmation dialog scaled with the unified scale_factor."""
    root = parent.winfo_toplevel()
    colors: dict[str, str] = getattr(root, "theme_colors", LIGHT_COLORS)
    if sf is None:
        sf = float(getattr(root, "scale_factor", 1.5))

    bg_color = colors.get("surface", "#FFFFFF")
    text_color = colors.get("text", "#172033")
    border_color = colors.get("border", "#E4E9F0")
    primary_color = colors.get("primary", "#2D6CDF")
    btn_pressed = colors.get("button_pressed", "#EEF2F6")

    dialog = tk.Toplevel(root)
    dialog.title(title)
    dialog.configure(background=bg_color)
    dialog.transient(root)
    dialog.resizable(False, False)
    dialog.withdraw()

    result = [False]

    def on_confirm() -> None:
        result[0] = True
        dialog.destroy()

    def on_cancel() -> None:
        result[0] = False
        dialog.destroy()

    dialog.protocol("WM_DELETE_WINDOW", on_cancel)
    dialog.bind("<Escape>", lambda _e: on_cancel())
    dialog.bind("<Return>", lambda _e: on_confirm())

    container = tk.Frame(
        dialog,
        background=bg_color,
        padx=scale(28, sf),
        pady=scale(22, sf),
    )
    container.pack(fill="both", expand=True)

    tk.Label(
        container,
        text=title,
        font=(FONT_FAMILY, scale(14, sf), "bold"),
        foreground=text_color,
        background=bg_color,
        anchor="center",
    ).pack(fill="x", pady=(0, scale(14, sf)))

    tk.Label(
        container,
        text=message,
        font=(FONT_FAMILY, scale(11, sf)),
        foreground=text_color,
        background=bg_color,
        justify="center",
        wraplength=scale(420, sf),
    ).pack(fill="x", pady=(0, scale(22, sf)))

    btn_frame = tk.Frame(container, background=bg_color)
    btn_frame.pack()

    confirm_btn = tk.Button(
        btn_frame,
        text=confirm_text,
        font=(FONT_FAMILY, scale(10, sf), "bold"),
        foreground="#FFFFFF",
        background=primary_color,
        activeforeground="#FFFFFF",
        activebackground=colors.get("primary_hover", "#245ABD"),
        relief="flat",
        cursor="hand2",
        padx=scale(22, sf),
        pady=scale(7, sf),
        command=on_confirm,
    )
    cancel_btn = tk.Button(
        btn_frame,
        text=cancel_text,
        font=(FONT_FAMILY, scale(10, sf)),
        foreground=text_color,
        background=colors.get("surface_soft", "#F8FAFC"),
        activeforeground=text_color,
        activebackground=btn_pressed,
        highlightbackground=border_color,
        highlightthickness=1,
        relief="flat",
        cursor="hand2",
        padx=scale(22, sf),
        pady=scale(7, sf),
        command=on_cancel,
    )

    confirm_btn.pack(side="left", padx=scale(8, sf))
    cancel_btn.pack(side="left", padx=scale(8, sf))

    dialog.update_idletasks()
    pw, ph = root.winfo_width(), root.winfo_height()
    px, py = root.winfo_rootx(), root.winfo_rooty()
    dw, dh = dialog.winfo_reqwidth(), dialog.winfo_reqheight()
    x = px + max(0, (pw - dw) // 2)
    y = py + max(0, (ph - dh) // 2)
    dialog.geometry(f"+{x}+{y}")

    dialog.deiconify()
    dialog.grab_set()
    confirm_btn.focus_set()
    dialog.wait_window()
    return result[0]


def create_info_tooltip(
    owner: tk.Misc,
    parent: tk.Misc,
    text: str,
    *,
    wraplength: int | None = None,
) -> tk.Canvas:
    """Create a themed circular info icon that displays a floating tooltip on hover."""
    root = owner.winfo_toplevel()
    sf = float(getattr(owner, "sf", getattr(root, "scale_factor", 1.5)))
    colors: dict[str, str] = getattr(root, "theme_colors", LIGHT_COLORS)

    icon_bg = colors.get("background", "#F3F6FA")
    icon_color = colors.get("text_muted", "#98A2B3")
    tooltip_bg = colors.get("surface_soft", "#F8FAFC")
    tooltip_fg = colors.get("text", "#172033")
    tooltip_border = colors.get("border", "#E4E9F0")

    if wraplength is None:
        wraplength = scale(380, sf)

    icon_size = scale(20, sf)
    info_icon = tk.Canvas(
        parent,
        width=icon_size,
        height=icon_size,
        highlightthickness=0,
        borderwidth=0,
        relief="flat",
        background=icon_bg,
        cursor="hand2",
    )
    info_icon.create_oval(
        scale(2, sf),
        scale(2, sf),
        scale(18, sf),
        scale(18, sf),
        outline=icon_color,
        width=max(1, round(1.4 * sf)),
        fill=icon_bg,
    )
    info_icon.create_text(
        icon_size // 2,
        icon_size // 2,
        text="!",
        fill=icon_color,
        font=("Arial", scale(9.5, sf), "bold"),
    )

    tooltip = tk.Toplevel(owner)
    tooltip.withdraw()
    tooltip.overrideredirect(True)
    try:
        tooltip.attributes("-topmost", True)
    except tk.TclError:
        pass

    tooltip_label = tk.Label(
        tooltip,
        text=text,
        font=(FONT_FAMILY, scale(9, sf)),
        foreground=tooltip_fg,
        background=tooltip_bg,
        highlightbackground=tooltip_border,
        highlightcolor=tooltip_border,
        highlightthickness=1,
        relief="flat",
        borderwidth=0,
        padx=scale(10, sf),
        pady=scale(6, sf),
        justify="left",
        wraplength=wraplength,
    )
    tooltip_label.pack()

    def show_tooltip(_event: Any = None) -> None:
        try:
            tooltip.update_idletasks()
            x = info_icon.winfo_rootx() + info_icon.winfo_width() + 8
            y = (
                info_icon.winfo_rooty()
                + (info_icon.winfo_height() - tooltip.winfo_reqheight()) // 2
            )
            tooltip.geometry(f"+{max(0, x)}+{max(0, y)}")
            tooltip.deiconify()
            tooltip.lift()
        except tk.TclError:
            pass

    def hide_tooltip(_event: Any = None) -> None:
        try:
            tooltip.withdraw()
        except tk.TclError:
            pass

    def destroy_tooltip(event: Any = None) -> None:
        if event is not None and event.widget is not info_icon:
            return
        try:
            tooltip.destroy()
        except tk.TclError:
            pass

    info_icon.bind("<Enter>", show_tooltip)
    info_icon.bind("<Leave>", hide_tooltip)
    info_icon.bind("<Destroy>", destroy_tooltip, add="+")
    tooltip_label.bind("<Leave>", hide_tooltip)
    return info_icon


class BubbleList(ttk.Frame):
    """Auto-wrapping, centered tag bubble list supporting item removal via '×' click."""

    def __init__(
        self,
        parent: tk.Misc,
        *,
        owner: tk.Misc,
        items: list[Any],
        display_text: Callable[[Any], str] = str,
        on_remove: Callable[[int], Any] | None = None,
        on_render: Callable[[], Any] | None = None,
        min_bubble_width: int | None = None,
        bubble_height: int | None = None,
        horizontal_gap: int | None = None,
        vertical_gap: int | None = None,
        reserved_rows: int = 1,
        font: tuple[Any, ...] | None = None,
        text_color: str | None = None,
        remove_color: str | None = None,
    ) -> None:
        root = owner.winfo_toplevel()
        sf = float(getattr(owner, "sf", getattr(root, "scale_factor", 1.5)))
        self.sf = sf

        if min_bubble_width is None:
            min_bubble_width = scale(96, sf)
        if bubble_height is None:
            bubble_height = scale(32, sf)
        if horizontal_gap is None:
            horizontal_gap = scale(6, sf)
        if vertical_gap is None:
            vertical_gap = scale(6, sf)
        if font is None:
            font = (FONT_FAMILY, scale(9.5, sf))

        initial_height = (
            reserved_rows * bubble_height + max(0, reserved_rows - 1) * vertical_gap + scale(6, sf)
        )
        super().__init__(parent, height=initial_height, style="Content.TFrame")

        self.owner = owner
        self.items = items
        self.display_text = display_text
        self.on_remove = on_remove
        self.on_render = on_render
        self.min_bubble_width = min_bubble_width
        self.bubble_height = bubble_height
        self.horizontal_gap = horizontal_gap
        self.vertical_gap = vertical_gap
        self.reserved_rows = reserved_rows
        self.bubble_font = font

        self.colors: dict[str, str] = getattr(root, "theme_colors", LIGHT_COLORS)
        self.background_color = self.colors.get("background", "#F3F6FA")
        self.bubble_background = self.colors.get("surface", "#FFFFFF")
        self.bubble_border = self.colors.get("border", "#E4E9F0")
        self.text_color = text_color or self.colors.get("text", "#172033")
        self.remove_color = remove_color or self.colors.get("danger", "#D84A4A")

        self.disabled = False
        self.bubble_widgets: list[tk.Canvas] = []
        self._reflow_job: str | None = None
        self._last_width = 0

        self.bind("<Configure>", self._on_configure)
        self.bind("<Destroy>", self._on_destroy, add="+")

    def set_items(self, items: list[Any] | None = None) -> None:
        if items is not None:
            self.items = items
        self.render()

    def set_disabled(self, disabled: bool) -> None:
        self.disabled = bool(disabled)
        self.render()

    def _on_configure(self, event: Any) -> None:
        if event.width == self._last_width:
            return
        self._last_width = event.width

        if self._reflow_job is not None:
            try:
                self.owner.after_cancel(self._reflow_job)
            except tk.TclError:
                pass
        self._reflow_job = self.owner.after(60, self.render)

    def _on_destroy(self, event: Any = None) -> None:
        if event is not None and event.widget is not self:
            return
        if self._reflow_job is not None:
            try:
                self.owner.after_cancel(self._reflow_job)
            except tk.TclError:
                pass
            self._reflow_job = None

    def _measure_bubble_width(self, text: str) -> int:
        measure = tk.Label(
            self,
            text=text,
            font=self.bubble_font,
            background=self.background_color,
            foreground=self.text_color,
        )
        measure.update_idletasks()
        width = max(
            self.min_bubble_width,
            measure.winfo_reqwidth() + scale(42, self.sf),
        )
        measure.destroy()
        return width

    def _create_bubble(self, item: Any, index: int) -> tuple[tk.Canvas, int]:
        text = str(self.display_text(item))
        width = self._measure_bubble_width(text)
        bubble = tk.Canvas(
            self,
            width=width,
            height=self.bubble_height,
            highlightthickness=1,
            highlightbackground=self.bubble_border,
            borderwidth=0,
            background=self.bubble_background,
            cursor="arrow",
        )
        remove_tag = f"remove_{index}"
        bubble.create_text(
            scale(13, self.sf),
            self.bubble_height // 2 - 1,
            text="×",
            font=("Arial", scale(11, self.sf), "bold"),
            fill=self.remove_color,
            tags=(remove_tag, "remove_button"),
        )
        bubble.create_text(
            scale(26, self.sf),
            self.bubble_height // 2,
            text=text,
            anchor="w",
            font=self.bubble_font,
            fill=self.text_color,
        )

        def _on_remove(_e: tk.Event[Any], i: int = index) -> Any:
            return self._remove(i)

        def _on_enter(_e: tk.Event[Any], w: tk.Canvas = bubble) -> Any:
            return w.configure(cursor="hand2")

        def _on_leave(_e: tk.Event[Any], w: tk.Canvas = bubble) -> Any:
            return w.configure(cursor="arrow")

        bubble.tag_bind(remove_tag, "<Button-1>", _on_remove)
        bubble.tag_bind(remove_tag, "<Enter>", _on_enter)
        bubble.tag_bind(remove_tag, "<Leave>", _on_leave)
        if self.disabled:
            bubble.itemconfigure("remove_button", state="hidden")
        return bubble, width

    def _remove(self, index: int) -> None:
        if self.disabled or index < 0 or index >= len(self.items):
            return
        if callable(self.on_remove):
            self.on_remove(index)
        else:
            del self.items[index]
            self.render()

    def render(self) -> None:
        self._reflow_job = None
        for widget in self.bubble_widgets:
            try:
                widget.destroy()
            except tk.TclError:
                pass
        self.bubble_widgets.clear()

        try:
            available_width = max(180, self.winfo_width())
        except tk.TclError:
            return

        rows: list[tuple[list[tuple[tk.Canvas, int]], int]] = []
        current_row: list[tuple[tk.Canvas, int]] = []
        current_width = 0

        for index, item in enumerate(self.items):
            bubble, width = self._create_bubble(item, index)
            required_width = width + (self.horizontal_gap if current_row else 0)
            if current_row and current_width + required_width > available_width:
                rows.append((current_row, current_width))
                current_row = []
                current_width = 0
            if current_row:
                current_width += self.horizontal_gap
            current_row.append((bubble, width))
            current_width += width
            self.bubble_widgets.append(bubble)

        if current_row:
            rows.append((current_row, current_width))

        for row_index, (row_items, row_width) in enumerate(rows):
            x = max(0, (available_width - row_width) // 2)
            y = row_index * (self.bubble_height + self.vertical_gap)
            for bubble, width in row_items:
                bubble.place(x=x, y=y)
                x += width + self.horizontal_gap

        row_count = max(self.reserved_rows, len(rows))
        required_height = row_count * self.bubble_height + (row_count - 1) * self.vertical_gap + 8
        try:
            self.configure(height=required_height)
        except tk.TclError:
            pass
        if callable(self.on_render):
            self.on_render()


def _extract_readable_preview_from_html(raw_html: str) -> str:
    """Convert HTML email body (including tables) into a clean readable text preview."""
    from html.parser import HTMLParser

    class _EmailHTMLParser(HTMLParser):
        def __init__(self) -> None:
            super().__init__()
            self.lines: list[str] = []
            self.current_chunk: list[str] = []
            self.in_table_row = False
            self.row_cells: list[str] = []
            self.current_cell: list[str] = []
            self.in_cell = False
            self._ignore_depth = 0

        def handle_starttag(self, tag: str, _attrs: list[tuple[str, str | None]]) -> None:
            t = tag.lower()
            if t in {"style", "script"}:
                self._ignore_depth += 1
                return
            if self._ignore_depth > 0:
                return
            if t in {"br", "p", "div", "h1", "h2", "h3", "h4"}:
                self._flush_chunk()
            elif t == "tr":
                self._flush_chunk()
                self.in_table_row = True
                self.row_cells = []
            elif t in {"th", "td"}:
                self.in_cell = True
                self.current_cell = []
            elif t == "li":
                self._flush_chunk()
                self.current_chunk.append("• ")

        def handle_endtag(self, tag: str) -> None:
            t = tag.lower()
            if t in {"style", "script"}:
                self._ignore_depth = max(0, self._ignore_depth - 1)
                return
            if self._ignore_depth > 0:
                return
            if t in {"th", "td"} and self.in_cell:
                cell_text = " ".join("".join(self.current_cell).split())
                self.row_cells.append(cell_text)
                self.current_cell = []
                self.in_cell = False
            elif t == "tr" and self.in_table_row:
                if any(self.row_cells):
                    self.lines.append("  |  ".join(self.row_cells))
                self.row_cells = []
                self.in_table_row = False
            elif t in {"p", "div", "h1", "h2", "h3", "h4", "li", "table"}:
                self._flush_chunk()

        def handle_data(self, data: str) -> None:
            if self._ignore_depth > 0:
                return
            if self.in_cell:
                self.current_cell.append(data)
            else:
                self.current_chunk.append(data)

        def _flush_chunk(self) -> None:
            text = " ".join("".join(self.current_chunk).split())
            if text:
                self.lines.append(text)
            self.current_chunk = []

        def get_text(self) -> str:
            self._flush_chunk()
            return "\n".join(self.lines)

    parser = _EmailHTMLParser()
    try:
        parser.feed(raw_html or "")
        parsed = parser.get_text().strip()
        if parsed:
            return parsed
    except Exception:
        pass
    return (raw_html or "").strip()


class HTMLPreviewDialog(tk.Toplevel):
    """Built-in GUI dialog for previewing HTML email drafts when Classic Outlook COM is unavailable."""

    def __init__(
        self,
        parent: tk.Misc,
        draft: Any,
        *,
        sf: float | None = None,
    ) -> None:
        root = parent.winfo_toplevel()
        super().__init__(root)
        self.colors: dict[str, str] = getattr(root, "theme_colors", LIGHT_COLORS)
        if sf is None:
            sf = float(getattr(parent, "sf", getattr(root, "scale_factor", 1.5)))
        self.sf = sf

        if hasattr(draft, "to_dict"):
            self.draft_data: dict[str, Any] = draft.to_dict()
        elif isinstance(draft, dict):
            self.draft_data = dict(draft)
        else:
            self.draft_data = {
                "to": getattr(draft, "to", ""),
                "cc": getattr(draft, "cc", ""),
                "subject": getattr(draft, "subject", ""),
                "html_body": getattr(draft, "html_body", ""),
                "used_fallback": getattr(draft, "used_fallback", True),
                "fallback_reason": getattr(draft, "fallback_reason", ""),
            }

        bg = self.colors.get("surface", "#FFFFFF")
        self.title("郵件草稿預覽 — 安全模擬模式 (HTML Preview)")
        self.configure(background=bg)
        self.transient(root)
        self.withdraw()

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.bind("<Escape>", lambda _e: self.destroy())

        self.update_idletasks()
        width = scale(680, self.sf)
        height = scale(520, self.sf)
        px, py = root.winfo_rootx(), root.winfo_rooty()
        pw, ph = root.winfo_width(), root.winfo_height()
        x = px + max(0, (pw - width) // 2)
        y = py + max(0, (ph - height) // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")
        self.minsize(scale(520, self.sf), scale(380, self.sf))
        self.deiconify()
        try:
            self.lift()
            self.focus_force()
        except tk.TclError:
            pass

    def s(self, value: float) -> int:
        return scale(value, self.sf)

    def _build_ui(self) -> None:
        surface = self.colors.get("surface", "#FFFFFF")
        surface_soft = self.colors.get("surface_soft", "#F8FAFC")
        text_color = self.colors.get("text", "#172033")
        text_secondary = self.colors.get("text_secondary", "#667085")
        border_color = self.colors.get("border", "#E4E9F0")
        primary_color = self.colors.get("primary", "#2D6CDF")

        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        # 1. Top Banner
        banner = tk.Frame(
            self,
            background=primary_color,
            padx=self.s(20),
            pady=self.s(12),
        )
        banner.grid(row=0, column=0, sticky="ew")
        tk.Label(
            banner,
            text="📧 郵件草稿安全模擬模式 (Outlook Graceful Fallback)",
            font=(FONT_FAMILY, self.s(11), "bold"),
            foreground="#FFFFFF",
            background=primary_color,
            anchor="w",
        ).pack(fill="x")
        tk.Label(
            banner,
            text="環境未安裝或未啟動 Classic Outlook，系統已自動攔截並呈現完整通知信草稿與交接表格。",
            font=(FONT_FAMILY, self.s(8.5)),
            foreground="#DBEAFE",
            background=primary_color,
            anchor="w",
        ).pack(fill="x", pady=(self.s(2), 0))

        # 2. Metadata Header (To / CC / Subject)
        meta_frame = tk.Frame(
            self,
            background=surface_soft,
            highlightbackground=border_color,
            highlightthickness=1,
            padx=self.s(20),
            pady=self.s(12),
        )
        meta_frame.grid(
            row=1, column=0, sticky="ew", padx=self.s(18), pady=(self.s(14), self.s(10))
        )
        meta_frame.columnconfigure(1, weight=1)

        fields: list[tuple[str, str, bool]] = [
            ("收件人 (To):", str(self.draft_data.get("to") or "（未指定）"), False),
            ("副本 (CC):", str(self.draft_data.get("cc") or "（無）"), False),
        ]
        bcc_value = str(self.draft_data.get("bcc") or "").strip()
        if bcc_value:
            fields.append(("密件副本 (BCC):", bcc_value, False))
        fields.append(
            ("主旨 (Subject):", str(self.draft_data.get("subject") or "（無主旨）"), True)
        )

        for row_idx, (label_text, val_text, is_bold) in enumerate(fields):
            tk.Label(
                meta_frame,
                text=label_text,
                font=(FONT_FAMILY, self.s(9.5), "bold"),
                foreground=text_secondary,
                background=surface_soft,
                anchor="w",
            ).grid(row=row_idx, column=0, sticky="w", pady=self.s(2), padx=(0, self.s(12)))
            tk.Label(
                meta_frame,
                text=val_text,
                font=(FONT_FAMILY, self.s(9.5), "bold" if is_bold else "normal"),
                foreground=text_color,
                background=surface_soft,
                anchor="w",
                justify="left",
                wraplength=self.s(540),
            ).grid(row=row_idx, column=1, sticky="ew", pady=self.s(2))

        # 3. Formatted Body & Table Preview
        body_container = tk.Frame(
            self,
            background=surface,
            highlightbackground=border_color,
            highlightthickness=1,
        )
        body_container.grid(row=2, column=0, sticky="nsew", padx=self.s(18), pady=(0, self.s(12)))
        body_container.columnconfigure(0, weight=1)
        body_container.rowconfigure(0, weight=1)

        preview_text = _extract_readable_preview_from_html(
            str(self.draft_data.get("html_body", ""))
        )
        self.text_widget = tk.Text(
            body_container,
            wrap="word",
            font=(FONT_FAMILY, self.s(9.5)),
            foreground=text_color,
            background=surface,
            relief="flat",
            borderwidth=0,
            padx=self.s(14),
            pady=self.s(12),
        )
        self.text_widget.grid(row=0, column=0, sticky="nsew")

        scrollbar = ModernScrollbar(
            body_container,
            command=self.text_widget.yview,
            width=self.s(8),
            track_color=surface,
            thumb_color=border_color,
            thumb_hover_color=text_secondary,
        )
        scrollbar.grid(row=0, column=1, sticky="ns", padx=(0, self.s(2)), pady=self.s(4))
        self.text_widget.configure(yscrollcommand=scrollbar.set)

        self.text_widget.insert("1.0", preview_text)
        self.text_widget.configure(state="disabled")

        # 4. Action Buttons
        btn_bar = tk.Frame(self, background=surface, padx=self.s(18), pady=self.s(12))
        btn_bar.grid(row=3, column=0, sticky="ew")

        open_browser_btn = tk.Button(
            btn_bar,
            text="🌐 在瀏覽器開啟完整 HTML",
            font=(FONT_FAMILY, self.s(9.5), "bold"),
            foreground="#FFFFFF",
            background=primary_color,
            activeforeground="#FFFFFF",
            activebackground=self.colors.get("primary_hover", "#245ABD"),
            relief="flat",
            cursor="hand2",
            padx=self.s(16),
            pady=self.s(7),
            command=self._open_in_browser,
        )
        open_browser_btn.pack(side="left")

        close_btn = tk.Button(
            btn_bar,
            text="關閉預覽",
            font=(FONT_FAMILY, self.s(9.5)),
            foreground=text_color,
            background=surface_soft,
            activeforeground=text_color,
            activebackground=self.colors.get("button_pressed", "#E9EEF5"),
            highlightbackground=border_color,
            highlightthickness=1,
            relief="flat",
            cursor="hand2",
            padx=self.s(18),
            pady=self.s(7),
            command=self.destroy,
        )
        close_btn.pack(side="right")

    def _open_in_browser(self) -> None:
        from it_rpa_suite.adapters.mailer import open_draft_in_browser

        open_draft_in_browser(self.draft_data)


def show_html_preview_dialog(
    parent: tk.Misc,
    draft: Any,
    *,
    sf: float | None = None,
) -> HTMLPreviewDialog:
    """Instantiate and display HTMLPreviewDialog for a fallback email draft."""
    return HTMLPreviewDialog(parent=parent, draft=draft, sf=sf)


class CallerToast(tk.Toplevel):
    """Top-right desktop notification toast card displaying matched caller directory details."""

    _active_instance: CallerToast | None = None

    def __init__(
        self,
        parent: tk.Misc,
        caller_info: dict[str, Any],
        *,
        raw_query: str = "",
        duration_ms: int = 8000,
        sf: float | None = None,
    ) -> None:
        root = parent.winfo_toplevel()
        super().__init__(root)

        if CallerToast._active_instance is not None:
            try:
                if CallerToast._active_instance.winfo_exists():
                    CallerToast._active_instance.destroy()
            except tk.TclError:
                pass
        CallerToast._active_instance = self

        self.colors: dict[str, str] = getattr(root, "theme_colors", LIGHT_COLORS)
        if sf is None:
            sf = float(getattr(parent, "sf", getattr(root, "scale_factor", 1.5)))
        self.sf = sf
        self.caller_info = dict(caller_info or {})
        self.raw_query = raw_query
        self.duration_ms = max(1000, int(duration_ms))
        self._alpha = 0.96
        self._fade_job: str | None = None
        self._dismiss_job: str | None = None

        self.withdraw()
        self.overrideredirect(True)
        try:
            self.attributes("-topmost", True)
            self.attributes("-alpha", self._alpha)
        except tk.TclError:
            pass

        self._build_ui()
        self.update_idletasks()

        width = max(self.s(370), self.winfo_reqwidth())
        height = self.winfo_reqheight()
        screen_w = self.winfo_screenwidth()
        x = max(16, screen_w - width - self.s(22))
        y = self.s(24)
        self.geometry(f"{width}x{height}+{x}+{y}")
        self.deiconify()
        try:
            self.lift()
        except tk.TclError:
            pass

        self._dismiss_job = self.after(self.duration_ms, self._start_fade_out)
        self.bind("<Destroy>", self._on_destroy, add="+")

    def s(self, value: float) -> int:
        return scale(value, self.sf)

    def _build_ui(self) -> None:
        bg_dark = "#0F172A"
        card_bg = "#1E293B"
        border_color = "#3B82F6"
        accent_color = "#10B981"
        text_primary = "#F8FAFC"
        text_secondary = "#CBD5E1"
        text_muted = "#94A3B8"

        self.configure(
            background=border_color,
            padx=1,
            pady=1,
        )

        outer = tk.Frame(self, background=card_bg)
        outer.pack(fill="both", expand=True)

        tk.Frame(outer, background=accent_color, width=self.s(5)).pack(side="left", fill="y")

        body = tk.Frame(
            outer,
            background=card_bg,
            padx=self.s(16),
            pady=self.s(13),
        )
        body.pack(side="left", fill="both", expand=True)
        body.columnconfigure(0, weight=1)

        # Header Row
        header_row = tk.Frame(body, background=card_bg)
        header_row.grid(row=0, column=0, sticky="ew")
        header_row.columnconfigure(0, weight=1)

        tk.Label(
            header_row,
            text="📲 即時來電識別 (Caller ID Match)",
            font=(FONT_FAMILY, self.s(9), "bold"),
            foreground="#34D399",
            background=card_bg,
            anchor="w",
        ).grid(row=0, column=0, sticky="w")

        close_btn = tk.Label(
            header_row,
            text="×",
            font=("Arial", self.s(12), "bold"),
            foreground=text_muted,
            background=card_bg,
            cursor="hand2",
            padx=self.s(4),
        )
        close_btn.grid(row=0, column=1, sticky="e")
        close_btn.bind("<Button-1>", lambda _e: self.destroy())

        name = str(self.caller_info.get("name") or "未知來電者")
        emp_id = str(self.caller_info.get("emp_id") or "")
        dept = str(self.caller_info.get("dept") or "未登錄部門")
        title = str(self.caller_info.get("title") or "同仁")
        ext = str(self.caller_info.get("ext") or self.raw_query or "-")
        location = str(self.caller_info.get("location") or "-")
        manager = str(self.caller_info.get("manager") or "-")

        display_name = f"{name}  [{emp_id}]" if emp_id else name
        tk.Label(
            body,
            text=display_name,
            font=(FONT_FAMILY, self.s(12.5), "bold"),
            foreground=text_primary,
            background=card_bg,
            anchor="w",
        ).grid(row=1, column=0, sticky="ew", pady=(self.s(5), self.s(2)))

        tk.Label(
            body,
            text=f"{dept}  ｜  {title}",
            font=(FONT_FAMILY, self.s(9.5)),
            foreground="#60A5FA",
            background=card_bg,
            anchor="w",
        ).grid(row=2, column=0, sticky="ew", pady=(0, self.s(8)))

        meta_box = tk.Frame(
            body,
            background=bg_dark,
            padx=self.s(11),
            pady=self.s(8),
        )
        meta_box.grid(row=3, column=0, sticky="ew")
        meta_box.columnconfigure(1, weight=1)

        rows = (
            ("分機 / 座位置：", f"Ext. {ext}  （{location}）"),
            ("直屬主管：", manager),
        )
        for idx, (lbl, val) in enumerate(rows):
            tk.Label(
                meta_box,
                text=lbl,
                font=(FONT_FAMILY, self.s(8.5)),
                foreground=text_muted,
                background=bg_dark,
                anchor="w",
            ).grid(row=idx, column=0, sticky="w", pady=1)
            tk.Label(
                meta_box,
                text=val,
                font=(FONT_FAMILY, self.s(8.5), "bold"),
                foreground=text_secondary,
                background=bg_dark,
                anchor="w",
            ).grid(row=idx, column=1, sticky="w", pady=1)

    def _start_fade_out(self) -> None:
        self._dismiss_job = None
        self._step_fade()

    def _step_fade(self) -> None:
        try:
            if not self.winfo_exists():
                return
            self._alpha -= 0.12
            if self._alpha <= 0.08:
                self.destroy()
                return
            self.attributes("-alpha", self._alpha)
            self._fade_job = self.after(45, self._step_fade)
        except tk.TclError:
            pass

    def _on_destroy(self, event: Any = None) -> None:
        if event is not None and event.widget is not self:
            return
        for job in (self._dismiss_job, self._fade_job):
            if job is not None:
                try:
                    self.after_cancel(job)
                except tk.TclError:
                    pass
        if CallerToast._active_instance is self:
            CallerToast._active_instance = None


def show_caller_toast(
    parent: tk.Misc,
    caller_info: dict[str, Any],
    *,
    raw_query: str = "",
    duration_ms: int = 8000,
    sf: float | None = None,
) -> CallerToast:
    """Display the top-right CallerToast notification card."""
    return CallerToast(
        parent=parent,
        caller_info=caller_info,
        raw_query=raw_query,
        duration_ms=duration_ms,
        sf=sf,
    )


class ModernDropdown(tk.Frame):
    """Themed, DPI-scaled modern dropdown selector with a floating borderless option panel."""

    def __init__(
        self,
        parent: tk.Misc,
        *,
        options: tuple[str, ...] | list[str],
        textvariable: tk.StringVar | None = None,
        placeholder: str = "請選擇項目",
        width: int | None = None,
        height: int | None = None,
        font_size: float = 10.0,
        on_select: Callable[[str], Any] | None = None,
        sf: float | None = None,
    ) -> None:
        self._toplevel = parent.winfo_toplevel()
        self.colors: dict[str, str] = getattr(self._toplevel, "theme_colors", LIGHT_COLORS)
        self.sf: float = (
            float(sf)
            if sf is not None
            else float(getattr(parent, "sf", getattr(self._toplevel, "scale_factor", 1.5)))
        )
        self._items: tuple[str, ...] = tuple(options)
        self._placeholder = placeholder
        self._font_size = float(font_size)
        self._on_select = on_select
        self.variable = textvariable or tk.StringVar(value=placeholder)
        self._enabled = True
        self._hovered = False
        self._popup: tk.Toplevel | None = None
        self._previous_grab: tk.Misc | None = None
        self._outside_click_bind_id: str | None = None
        self._root_configure_bind_id: str | None = None
        self._escape_bind_id: str | None = None
        self._dropdown_width = width if width is not None else scale(210, self.sf)
        dropdown_height = height if height is not None else scale(38, self.sf)

        super().__init__(
            parent,
            background=self.colors.get("surface", "#FFFFFF"),
            highlightbackground=self.colors.get("border", "#E4E9F0"),
            highlightcolor=self.colors.get("primary", "#2D6CDF"),
            highlightthickness=1,
            bd=0,
            width=self._dropdown_width,
            height=dropdown_height,
            cursor="hand2",
            takefocus=1,
        )
        self.grid_propagate(False)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self._value_label = tk.Label(
            self,
            text="",
            font=(FONT_FAMILY, scale(self._font_size, self.sf)),
            background=self.colors.get("surface", "#FFFFFF"),
            foreground=self.colors.get("text", "#172033"),
            anchor="w",
            cursor="hand2",
        )
        self._value_label.grid(
            row=0,
            column=0,
            sticky="ew",
            padx=(scale(12, self.sf), scale(6, self.sf)),
        )

        self._chevron_label = tk.Label(
            self,
            text="▾",
            font=(FONT_FAMILY, scale(10, self.sf)),
            background=self.colors.get("surface", "#FFFFFF"),
            foreground=self.colors.get("text_secondary", "#667085"),
            anchor="e",
            cursor="hand2",
        )
        self._chevron_label.grid(
            row=0,
            column=1,
            sticky="e",
            padx=(0, scale(11, self.sf)),
        )

        for widget in (self, self._value_label, self._chevron_label):
            widget.bind("<Button-1>", self._on_trigger_click)
            widget.bind("<Enter>", self._on_hover_enter)
            widget.bind("<Leave>", self._on_hover_leave)

        self.bind("<Return>", self._on_trigger_click)
        self.bind("<space>", self._on_trigger_click)
        self.bind("<Down>", self._on_trigger_click)
        self.bind("<Escape>", lambda _e: self.close_popup())
        self.bind("<Destroy>", self._on_destroy, add="+")

        self._var_trace_id = self.variable.trace_add("write", lambda *_a: self._refresh_display())
        self._refresh_display()

    @property
    def options(self) -> tuple[str, ...]:
        return self._items

    @property
    def is_open(self) -> bool:
        return self._popup is not None and bool(self._popup.winfo_exists())

    def get(self) -> str:
        val = self.variable.get().strip()
        return val if val in self._items else ""

    def set(self, value: str) -> None:
        cleaned = (value or "").strip()
        self.variable.set(cleaned if cleaned in self._items else self._placeholder)

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = bool(enabled)
        if not self._enabled:
            self.close_popup()
        self._refresh_display()

    def _refresh_display(self) -> None:
        if not self.winfo_exists():
            return
        raw = self.variable.get().strip()
        is_placeholder = not raw or raw == self._placeholder or raw not in self._items
        display_text = self._placeholder if is_placeholder else raw

        surface = self.colors.get("surface", "#FFFFFF")
        surface_soft = self.colors.get("surface_soft", "#F8FAFC")
        card_hover = self.colors.get("card_hover", "#F0F5FD")
        border = self.colors.get("border", "#E4E9F0")
        primary = self.colors.get("primary", "#2D6CDF")
        text_color = self.colors.get("text", "#172033")
        text_secondary = self.colors.get("text_secondary", "#667085")
        text_muted = self.colors.get("text_muted", "#98A2B3")

        if not self._enabled:
            bg = surface_soft
            bd = border
            fg = text_muted
            chevron_fg = text_muted
            cursor = "arrow"
        elif self.is_open:
            bg = surface
            bd = primary
            fg = text_muted if is_placeholder else text_color
            chevron_fg = primary
            cursor = "hand2"
        elif self._hovered:
            bg = card_hover
            bd = primary
            fg = text_muted if is_placeholder else text_color
            chevron_fg = primary
            cursor = "hand2"
        else:
            bg = surface
            bd = border
            fg = text_muted if is_placeholder else text_color
            chevron_fg = text_secondary
            cursor = "hand2"

        self.configure(background=bg, highlightbackground=bd, cursor=cursor)
        self._value_label.configure(
            text=display_text,
            background=bg,
            foreground=fg,
            cursor=cursor,
        )
        self._chevron_label.configure(
            text="▴" if self.is_open else "▾",
            background=bg,
            foreground=chevron_fg,
            cursor=cursor,
        )

    def _on_hover_enter(self, _event: Any = None) -> None:
        if not self._enabled:
            return
        self._hovered = True
        self._refresh_display()

    def _on_hover_leave(self, _event: Any = None) -> None:
        self._hovered = False
        self._refresh_display()

    def _on_trigger_click(self, _event: Any = None) -> str:
        if not self._enabled:
            return "break"
        if self.is_open:
            self.close_popup()
        else:
            self.open_popup()
        return "break"

    def open_popup(self) -> None:
        if not self._enabled or self.is_open:
            return

        self.update_idletasks()
        x = self.winfo_rootx()
        y = self.winfo_rooty() + self.winfo_height() + scale(4, self.sf)
        actual_width = self.winfo_width()
        width = actual_width if actual_width > 1 else self._dropdown_width

        surface = self.colors.get("surface", "#FFFFFF")
        border = self.colors.get("border", "#E4E9F0")
        primary = self.colors.get("primary", "#2D6CDF")
        text_color = self.colors.get("text", "#172033")
        card_hover = self.colors.get("card_hover", "#F0F5FD")
        selected_bg = self.colors.get("button_active", "#EEF2F7")

        popup = tk.Toplevel(self._toplevel)
        popup.withdraw()
        popup.overrideredirect(True)
        try:
            popup.attributes("-topmost", True)
        except tk.TclError:
            pass
        popup.configure(background=border)

        panel = tk.Frame(
            popup,
            background=surface,
            padx=scale(4, self.sf),
            pady=scale(4, self.sf),
        )
        panel.pack(fill="both", expand=True, padx=1, pady=1)
        panel.columnconfigure(0, weight=1)

        current_val = self.get()
        for row_idx, option in enumerate(self._items):
            is_selected = option == current_val
            row_bg = selected_bg if is_selected else surface
            row_fg = primary if is_selected else text_color

            row_frame = tk.Frame(
                panel,
                background=row_bg,
                cursor="hand2",
                padx=scale(10, self.sf),
                pady=scale(7, self.sf),
            )
            row_frame.grid(row=row_idx, column=0, sticky="ew", pady=1)
            row_frame.columnconfigure(0, weight=1)

            opt_label = tk.Label(
                row_frame,
                text=option,
                font=(
                    FONT_FAMILY,
                    scale(self._font_size, self.sf),
                    "bold" if is_selected else "normal",
                ),
                background=row_bg,
                foreground=row_fg,
                anchor="w",
                cursor="hand2",
            )
            opt_label.grid(row=0, column=0, sticky="ew")

            check_label = tk.Label(
                row_frame,
                text="✓" if is_selected else "",
                font=(FONT_FAMILY, scale(9.5, self.sf), "bold"),
                background=row_bg,
                foreground=primary,
                anchor="e",
                cursor="hand2",
            )
            check_label.grid(row=0, column=1, sticky="e", padx=(scale(8, self.sf), 0))

            def _choose(_e: Any = None, val: str = option) -> str:
                self._select_option(val)
                return "break"

            def _enter(
                _e: Any = None,
                rf: tk.Frame = row_frame,
                ol: tk.Label = opt_label,
                cl: tk.Label = check_label,
            ) -> None:
                rf.configure(background=card_hover)
                ol.configure(background=card_hover, foreground=primary)
                cl.configure(background=card_hover)

            def _leave(
                _e: Any = None,
                rf: tk.Frame = row_frame,
                ol: tk.Label = opt_label,
                cl: tk.Label = check_label,
                bg_c: str = row_bg,
                fg_c: str = row_fg,
            ) -> None:
                rf.configure(background=bg_c)
                ol.configure(background=bg_c, foreground=fg_c)
                cl.configure(background=bg_c)

            for widget in (row_frame, opt_label, check_label):
                widget.bind("<Button-1>", _choose)
                widget.bind("<Enter>", _enter)
                widget.bind("<Leave>", _leave)

        popup.update_idletasks()
        popup_height = popup.winfo_reqheight()
        screen_h = self._toplevel.winfo_screenheight()
        if y + popup_height > screen_h - scale(24, self.sf):
            y = max(scale(8, self.sf), self.winfo_rooty() - popup_height - scale(4, self.sf))

        popup.geometry(f"{width}x{popup_height}+{x}+{y}")
        popup.deiconify()
        popup.lift()
        popup.bind("<Escape>", lambda _e: self.close_popup())

        self._popup = popup
        current_grab = self._toplevel.grab_current()
        if current_grab is not None and current_grab is not popup:
            self._previous_grab = current_grab
            try:
                popup.grab_set()
                popup.bind("<Button-1>", self._handle_popup_click, add="+")
            except tk.TclError:
                self._previous_grab = None
        else:
            self._previous_grab = None

        self._outside_click_bind_id = self._toplevel.bind(
            "<Button-1>", self._handle_outside_click, add="+"
        )
        self._root_configure_bind_id = self._toplevel.bind(
            "<Configure>", lambda _e: self.close_popup(), add="+"
        )
        self._escape_bind_id = self._toplevel.bind(
            "<Escape>", lambda _e: self.close_popup(), add="+"
        )
        self._refresh_display()

    def _handle_popup_click(self, event: Any) -> None:
        if not self.is_open or self._popup is None:
            return
        try:
            px, py = self._popup.winfo_rootx(), self._popup.winfo_rooty()
            pw, ph = self._popup.winfo_width(), self._popup.winfo_height()
            if px <= event.x_root < px + pw and py <= event.y_root < py + ph:
                return
        except tk.TclError:
            pass
        self.close_popup()

    def _handle_outside_click(self, event: Any) -> None:
        if not self.is_open:
            return
        widget = getattr(event, "widget", None)
        if widget is None:
            self.close_popup()
            return
        widget_path = str(widget)
        if widget_path.startswith(str(self)) or (
            self._popup is not None and widget_path.startswith(str(self._popup))
        ):
            return
        self.close_popup()

    def _select_option(self, value: str) -> None:
        self.variable.set(value)
        self.close_popup()
        if callable(self._on_select):
            self._on_select(value)

    def close_popup(self) -> None:
        if self._outside_click_bind_id is not None:
            try:
                self._toplevel.unbind("<Button-1>", self._outside_click_bind_id)
            except tk.TclError:
                pass
            self._outside_click_bind_id = None

        if self._root_configure_bind_id is not None:
            try:
                self._toplevel.unbind("<Configure>", self._root_configure_bind_id)
            except tk.TclError:
                pass
            self._root_configure_bind_id = None

        if self._escape_bind_id is not None:
            try:
                self._toplevel.unbind("<Escape>", self._escape_bind_id)
            except tk.TclError:
                pass
            self._escape_bind_id = None

        if self._popup is not None:
            try:
                if self._popup.winfo_exists():
                    if self._popup.grab_current() is self._popup:
                        self._popup.grab_release()
                    self._popup.destroy()
            except tk.TclError:
                pass
            self._popup = None

        if self._previous_grab is not None:
            previous_grab = self._previous_grab
            self._previous_grab = None
            try:
                if previous_grab.winfo_exists():
                    previous_grab.grab_set()
            except tk.TclError:
                pass

        self._refresh_display()

    def _on_destroy(self, event: Any = None) -> None:
        if event is not None and event.widget is not self:
            return
        self.close_popup()
        try:
            self.variable.trace_remove("write", self._var_trace_id)
        except (tk.TclError, ValueError):
            pass

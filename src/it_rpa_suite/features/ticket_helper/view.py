"""GUI view and dialogs for IT Service Desk template management and batch ticket automation."""

from __future__ import annotations

import tkinter as tk
from concurrent.futures import Future
from tkinter import messagebox, ttk
from typing import Any, TypedDict

from it_rpa_suite.adapters.logger import get_logger
from it_rpa_suite.adapters.result import ServiceResult
from it_rpa_suite.app.theme import (
    FONT_FAMILY,
    LIGHT_COLORS,
    configure_ui_styles,
    scale,
)
from it_rpa_suite.app.widgets import (
    BubbleList,
    ModernScrollbar,
    create_modern_entry,
    create_primary_button,
    show_confirm_dialog,
)
from it_rpa_suite.features.ticket_helper.service import (
    CATEGORY_INCIDENT,
    DEFAULT_TEMPLATE_GROUP,
    TEMPLATE_GROUPS,
    VALID_CATEGORIES,
    VALID_CORPS,
    PlaceholderFocusTarget,
    TemplateRepository,
    find_first_placeholder_marker,
    run_batch_tickets,
)

logger = get_logger(__name__)


class _GroupButtonWidgets(TypedDict):
    frame: tk.Frame
    inner: tk.Frame
    name: tk.Label
    count: tk.Label


def _center_window(window: tk.Toplevel, parent: tk.Misc) -> None:
    """Center a Toplevel dialog over its parent top-level window within screen bounds."""
    owner = parent.winfo_toplevel()
    owner.update_idletasks()
    window.update_idletasks()

    width = max(window.winfo_width(), window.winfo_reqwidth())
    height = max(window.winfo_height(), window.winfo_reqheight())
    owner_width = owner.winfo_width()
    owner_height = owner.winfo_height()

    x = owner.winfo_rootx() + (owner_width - width) // 2
    y = owner.winfo_rooty() + (owner_height - height) // 2

    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()
    x = max(0, min(x, screen_width - width))
    y = max(0, min(y, screen_height - height))

    window.geometry(f"{width}x{height}+{x}+{y}")
    window.deiconify()
    try:
        window.lift(owner)
        window.focus_force()
    except tk.TclError:
        pass


def _configure_ticket_styles(
    widget: tk.Misc,
    colors: dict[str, str],
    sf: float = 1.5,
) -> ttk.Style:
    """Configure scoped ttk styles for the Service Desk Ticket Helper view and dialogs."""
    style = configure_ui_styles(widget, sf=sf)

    page_bg = colors.get("background", "#F3F6FA")
    surface_soft = colors.get("surface_soft", "#F8FAFC")
    card_bg = colors.get("surface", "#FFFFFF")
    text_color = colors.get("text", "#172033")
    muted_color = colors.get("text_muted", "#98A2B3")
    border_color = colors.get("border", "#E4E9F0")
    danger_color = colors.get("danger", "#D84A4A")
    pressed_color = colors.get("button_pressed", "#E9EEF5")

    style.configure("Ticket.Page.TFrame", background=page_bg)
    style.configure("Ticket.Card.TFrame", background=card_bg)
    style.configure(
        "Ticket.Title.TLabel",
        background=page_bg,
        foreground=text_color,
        font=(FONT_FAMILY, scale(20, sf), "bold"),
    )
    style.configure(
        "Ticket.Subtitle.TLabel",
        background=page_bg,
        foreground=colors.get("text_secondary", "#667085"),
        font=(FONT_FAMILY, scale(10, sf)),
    )
    style.configure(
        "Ticket.CardTitle.TLabel",
        background=card_bg,
        foreground=text_color,
        font=(FONT_FAMILY, scale(10, sf), "bold"),
    )
    style.configure(
        "Ticket.CardText.TLabel",
        background=card_bg,
        foreground=muted_color,
        font=(FONT_FAMILY, scale(9, sf)),
    )
    style.configure(
        "Ticket.FooterText.TLabel",
        background=surface_soft,
        foreground=colors.get("text_secondary", "#667085"),
        font=(FONT_FAMILY, scale(9.5, sf)),
    )
    style.configure(
        "Ticket.Secondary.TButton",
        font=(FONT_FAMILY, scale(9.5, sf)),
        padding=(scale(10, sf), scale(5, sf)),
        background=surface_soft,
        foreground=text_color,
        relief="flat",
        borderwidth=1,
    )
    style.map(
        "Ticket.Secondary.TButton",
        background=[
            ("active", card_bg),
            ("pressed", pressed_color),
            ("disabled", surface_soft),
        ],
        foreground=[("disabled", muted_color)],
        relief=[("pressed", "flat")],
    )
    style.configure(
        "Ticket.Icon.TButton",
        font=(FONT_FAMILY, scale(9, sf)),
        padding=(scale(5, sf), scale(2, sf)),
        background=surface_soft,
        foreground=text_color,
        relief="flat",
        borderwidth=0,
    )
    style.map(
        "Ticket.Icon.TButton",
        background=[("active", card_bg), ("pressed", pressed_color)],
        relief=[("pressed", "flat")],
    )
    style.configure(
        "Ticket.Danger.TButton",
        font=(FONT_FAMILY, scale(9.5, sf), "bold"),
        padding=(scale(12, sf), scale(6, sf)),
        background=surface_soft,
        foreground=danger_color,
        relief="flat",
    )
    style.map(
        "Ticket.Danger.TButton",
        background=[("active", card_bg), ("pressed", pressed_color)],
    )
    style.configure(
        "Ticket.Readonly.TCombobox",
        font=(FONT_FAMILY, scale(10, sf)),
        padding=(scale(10, sf), scale(8, sf)),
        foreground=text_color,
        fieldbackground=card_bg,
        background=card_bg,
        bordercolor=border_color,
        lightcolor=border_color,
        darkcolor=border_color,
        arrowsize=scale(13, sf),
    )
    style.map(
        "Ticket.Readonly.TCombobox",
        fieldbackground=[("readonly", card_bg)],
        foreground=[("readonly", text_color)],
        selectbackground=[("readonly", card_bg)],
        selectforeground=[("readonly", text_color)],
    )
    return style


class TicketTemplateDialog(tk.Toplevel):
    """Modal dialog for creating, copying, editing, or deleting a Service Desk template."""

    def __init__(
        self,
        parent: tk.Misc,
        template: dict[str, Any] | None = None,
        *,
        default_group: str = DEFAULT_TEMPLATE_GROUP,
        runtime_edit: bool = False,
        template_number: int | None = None,
        total_count: int | None = None,
        copy_mode: bool = False,
        repository: TemplateRepository | None = None,
    ) -> None:
        owner = parent.winfo_toplevel()
        super().__init__(owner)

        self.theme_colors: dict[str, str] = dict(getattr(owner, "theme_colors", LIGHT_COLORS))
        self.sf: float = float(getattr(parent, "sf", getattr(owner, "scale_factor", 1.5)))
        self.repository = repository or TemplateRepository()

        page_bg = self.theme_colors.get("background", "#F3F6FA")
        self.configure(background=page_bg)
        self.withdraw()

        self.result: dict[str, str] | None = None
        self.result_group: str = DEFAULT_TEMPLATE_GROUP
        self.action: str | None = None
        self.original_template: dict[str, Any] = dict(template or {})
        self.runtime_edit = runtime_edit
        self.copy_mode = copy_mode
        self.is_edit_mode = (
            not runtime_edit
            and not copy_mode
            and any(key != "_ui_group" for key in self.original_template)
        )
        self.template_number = template_number
        self.total_count = total_count

        if runtime_edit:
            suffix = (
                f"{template_number}/{total_count}"
                if total_count is not None
                else str(template_number or 1)
            )
            self.title(f"確認開單內容 第 {suffix} 筆")
        else:
            self.title(
                "複製工單模板"
                if copy_mode
                else ("編輯工單模板" if self.is_edit_mode else "新增工單模板")
            )

        self.geometry(f"{self.s(640)}x{self.s(500)}")
        self.minsize(self.s(560), self.s(450))
        self.transient(owner)
        self.grab_set()

        self.category_var = tk.StringVar(
            value=self.original_template.get("category", CATEGORY_INCIDENT)
        )
        self.email_var = tk.StringVar(value=self.original_template.get("email", ""))
        self.title_var = tk.StringVar(value=self.original_template.get("title", ""))
        self.type_var = tk.StringVar(value=self.original_template.get("type", ""))
        self.sub_type_var = tk.StringVar(value=self.original_template.get("sub_type", ""))
        self.corp_var = tk.StringVar(
            value=self.original_template.get("corp", VALID_CORPS[0]) or VALID_CORPS[0]
        )
        self.resolve_var = tk.StringVar(value=self.original_template.get("resolve", ""))
        initial_group = self.original_template.get("_ui_group", default_group)
        if initial_group not in TEMPLATE_GROUPS:
            initial_group = DEFAULT_TEMPLATE_GROUP
        self.template_group_var = tk.StringVar(value=initial_group)

        _configure_ticket_styles(self, self.theme_colors, sf=self.sf)
        self._build_widgets()
        self._update_category_fields()

        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.bind("<Escape>", lambda _e: self._cancel())

        if self.runtime_edit:
            self.after(50, self._focus_runtime_placeholder)
        else:
            self.after(50, self.email_entry.focus_set)
        self.after_idle(lambda: _center_window(self, owner))

    def s(self, value: float) -> int:
        return scale(value, self.sf)

    def _focus_runtime_placeholder(self) -> PlaceholderFocusTarget:
        """Detect the first `__` marker in `email` or `title`, remove it, and place the caret there."""
        current_state = {
            "email": self.email_var.get(),
            "title": self.title_var.get(),
        }
        target = find_first_placeholder_marker(current_state)

        if target.field == "email" and target.found_marker:
            self.email_var.set(target.cleaned_text)
            self.email_entry.focus_set()
            self.email_entry.icursor(target.cursor_index)
            self.email_entry.xview(target.cursor_index)
            return target

        if target.field == "title" and target.found_marker:
            self.title_var.set(target.cleaned_text)
            self.title_entry.focus_set()
            self.title_entry.icursor(target.cursor_index)
            self.title_entry.xview(target.cursor_index)
            return target

        self.title_entry.focus_set()
        self.title_entry.icursor(tk.END)
        self.title_entry.xview(tk.END)
        return target

    def _field(
        self,
        parent: ttk.Frame,
        row: int,
        label: str,
        widget: tk.Widget,
    ) -> None:
        ttk.Label(parent, text=label, style="Ticket.CardTitle.TLabel").grid(
            row=row,
            column=0,
            sticky="w",
            padx=(0, self.s(14)),
            pady=(self.s(6), self.s(2)),
        )
        widget.grid(
            row=row,
            column=1,
            sticky="ew",
            pady=(self.s(6), self.s(2)),
        )

    def _build_widgets(self) -> None:
        page = ttk.Frame(self, style="Ticket.Page.TFrame", padding=self.s(18))
        page.pack(fill="both", expand=True)
        page.columnconfigure(0, weight=1)
        page.rowconfigure(1, weight=1)

        header_text = (
            "確認開單內容（可即時微調，不影響原儲存模板）"
            if self.runtime_edit
            else (
                "複製工單模板"
                if self.copy_mode
                else ("編輯工單模板" if self.is_edit_mode else "建立新工單模板")
            )
        )
        ttk.Label(
            page,
            text=header_text,
            style="Ticket.Title.TLabel",
            anchor="center",
        ).grid(row=0, column=0, sticky="ew", pady=(0, self.s(12)))

        card = ttk.Frame(page, style="Ticket.Card.TFrame", padding=self.s(16))
        card.grid(row=1, column=0, sticky="nsew")
        card.columnconfigure(1, weight=1)

        category_combo = ttk.Combobox(
            card,
            textvariable=self.category_var,
            values=VALID_CATEGORIES,
            state="readonly",
            style="Ticket.Readonly.TCombobox",
        )
        self._field(card, 0, "工單類型", category_combo)
        category_combo.bind("<<ComboboxSelected>>", lambda _e: self._update_category_fields())

        group_combo = None
        if not self.runtime_edit:
            group_combo = ttk.Combobox(
                card,
                textvariable=self.template_group_var,
                values=TEMPLATE_GROUPS,
                state="readonly",
                style="Ticket.Readonly.TCombobox",
            )
            self._field(card, 7, "顯示分類", group_combo)

        self.email_entry = create_modern_entry(
            card,
            owner=self,
            textvariable=self.email_var,
            placeholder="例如：alex.chen@enterprise.local",
            justify="left",
        )
        self._field(card, 1, "請求人 Email", self.email_entry)

        form_input_font = self.email_entry.cget("font")
        category_combo.configure(font=form_input_font)
        if group_combo is not None:
            group_combo.configure(font=form_input_font)

        card_bg = self.theme_colors.get("surface", "#FFFFFF")
        text_color = self.theme_colors.get("text", "#172033")
        primary_color = self.theme_colors.get("primary", "#2D6CDF")
        self.option_add("*TCombobox*Listbox.font", form_input_font)
        self.option_add("*TCombobox*Listbox.background", card_bg)
        self.option_add("*TCombobox*Listbox.foreground", text_color)
        self.option_add("*TCombobox*Listbox.selectBackground", primary_color)
        self.option_add("*TCombobox*Listbox.selectForeground", "#FFFFFF")

        self.title_entry = create_modern_entry(
            card,
            owner=self,
            textvariable=self.title_var,
            placeholder="請輸入工單主題",
            justify="left",
        )
        self._field(card, 2, "工單主題", self.title_entry)

        self.type_label = ttk.Label(card, text="服務子分類", style="Ticket.CardTitle.TLabel")
        self.type_label.grid(row=3, column=0, sticky="w", padx=(0, self.s(14)), pady=self.s(6))
        self.type_entry = create_modern_entry(
            card,
            owner=self,
            textvariable=self.type_var,
            placeholder="例如：Hardware / Network",
            justify="left",
        )
        self.type_entry.grid(row=3, column=1, sticky="ew", pady=self.s(6))

        self.sub_type_label = ttk.Label(card, text="服務細項", style="Ticket.CardTitle.TLabel")
        self.sub_type_label.grid(row=4, column=0, sticky="w", padx=(0, self.s(14)), pady=self.s(6))
        self.sub_type_entry = create_modern_entry(
            card,
            owner=self,
            textvariable=self.sub_type_var,
            placeholder="例如：RAM / Storage Upgrade",
            justify="left",
        )
        self.sub_type_entry.grid(row=4, column=1, sticky="ew", pady=self.s(6))

        self.corp_label = ttk.Label(card, text="所屬廠區", style="Ticket.CardTitle.TLabel")
        self.corp_label.grid(row=5, column=0, sticky="w", padx=(0, self.s(14)), pady=self.s(6))
        self.corp_combo = ttk.Combobox(
            card,
            textvariable=self.corp_var,
            values=VALID_CORPS,
            state="readonly",
            style="Ticket.Readonly.TCombobox",
            font=form_input_font,
        )
        self.corp_combo.grid(row=5, column=1, sticky="ew", pady=self.s(6))

        self.resolve_entry = create_modern_entry(
            card,
            owner=self,
            textvariable=self.resolve_var,
            placeholder="請輸入處理紀錄與解決方案）",
            justify="left",
        )
        self._field(card, 6, "解決方案", self.resolve_entry)

        actions = ttk.Frame(page, style="Ticket.Page.TFrame")
        actions.grid(row=2, column=0, sticky="ew", pady=(self.s(14), 0))

        if self.is_edit_mode:
            ttk.Button(
                actions,
                text="刪除模板",
                command=self._delete,
                style="Ticket.Danger.TButton",
                cursor="hand2",
            ).pack(side="left")

        ttk.Button(
            actions,
            text="取消",
            command=self._cancel,
            style="Ticket.Secondary.TButton",
            cursor="hand2",
        ).pack(side="right", padx=(self.s(8), 0))

        create_primary_button(
            actions,
            text="套用本次內容" if self.runtime_edit else "儲存模板",
            command=self._save,
        ).pack(side="right")

    def _update_category_fields(self) -> None:
        if self.category_var.get() == CATEGORY_INCIDENT:
            self.type_label.configure(text="服務子分類")
            for widget in (
                self.sub_type_label,
                self.sub_type_entry,
                self.corp_label,
                self.corp_combo,
            ):
                widget.grid()
        else:
            self.type_label.configure(text="例行作業類別")
            for widget in (
                self.sub_type_label,
                self.sub_type_entry,
                self.corp_label,
                self.corp_combo,
            ):
                widget.grid_remove()

    def _save(self) -> None:
        category = self.category_var.get()
        group = (
            self.template_group_var.get()
            if self.template_group_var.get() in TEMPLATE_GROUPS
            else DEFAULT_TEMPLATE_GROUP
        )
        raw_template = {
            "category": category,
            "email": self.email_var.get().strip(),
            "title": self.title_var.get().strip(),
            "type": self.type_var.get().strip(),
            "sub_type": (self.sub_type_var.get().strip() if category == CATEGORY_INCIDENT else ""),
            "corp": (self.corp_var.get().strip() if category == CATEGORY_INCIDENT else ""),
            "resolve": self.resolve_var.get().strip(),
            "_ui_group": group,
        }
        try:
            self.result = self.repository.normalize_template(raw_template)
            self.result_group = group
            self.action = "save"
        except Exception as exc:
            messagebox.showwarning("模板資料錯誤", str(exc), parent=self)
            return
        self.destroy()

    def _delete(self) -> None:
        title = self.original_template.get("title", "")
        if show_confirm_dialog(
            parent=self,
            title="刪除工單模板",
            message=f"確定要刪除以下模板嗎？\n\n「{title}」\n\n此動作無法復原。",
            confirm_text="確定刪除",
            cancel_text="取消",
            sf=self.sf,
        ):
            self.action = "delete"
            self.destroy()

    def _cancel(self) -> None:
        self.result = None
        self.action = None
        self.destroy()


class RuntimeTicketConfirmDialog(TicketTemplateDialog):
    """Pre-execution confirmation dialog allowing per-run adjustments and '__' marker focus."""

    def __init__(
        self,
        parent: tk.Misc,
        template: dict[str, Any],
        template_number: int,
        total_count: int | None = None,
        repository: TemplateRepository | None = None,
    ) -> None:
        super().__init__(
            parent,
            template=template,
            runtime_edit=True,
            template_number=template_number,
            total_count=total_count,
            repository=repository,
        )


class TicketHelperView(ttk.Frame):
    """GUI view for managing Service Desk templates, queuing items, and running batch tickets."""

    BUBBLE_MAX_LINES = 1

    def __init__(
        self,
        parent: tk.Misc,
        app: Any,
        automation_worker: Any = None,
        repository: TemplateRepository | None = None,
    ) -> None:
        self.app = app
        self.automation_worker = automation_worker or getattr(app, "automation_worker", None)
        self.sf: float = float(getattr(app, "scale_factor", 1.5))
        self.colors: dict[str, str] = getattr(
            app, "colors", getattr(parent.winfo_toplevel(), "theme_colors", LIGHT_COLORS)
        )
        _configure_ticket_styles(parent, self.colors, sf=self.sf)
        super().__init__(
            parent,
            style="Ticket.Page.TFrame",
            padding=(
                scale(30, self.sf),
                scale(24, self.sf),
                scale(30, self.sf),
                scale(24, self.sf),
            ),
        )

        self.repository = repository or TemplateRepository(paths=getattr(app, "paths", None))
        self.templates: list[dict[str, str]] = []
        self.active_group: str = TEMPLATE_GROUPS[0]
        self.group_buttons: dict[str, _GroupButtonWidgets] = {}
        self._toplevel = self.winfo_toplevel()
        self.current_future: Future[Any] | None = None
        self._is_preparing = False
        self._ctrl_n_binding_id: str | None = None

        self.selected_index: int | None = None
        self.selected_template_indices: list[int] = []
        self._card_widgets: list[tk.Frame] = []
        self._visible_template_indices: list[int] = []
        self._resize_after_id: str | None = None

        # Drag-and-drop state
        self.drag_start_index: int | None = None
        self.drag_start_x: int | None = None
        self.drag_start_y: int | None = None
        self.drag_active = False
        self.drag_threshold = 6
        self.drag_window: tk.Toplevel | None = None

        self.card_height = self.s(38)
        self.card_gap = self.s(8)
        self.bubble_line_height = self.s(38)

        self.selection_var = tk.StringVar(
            value="尚未選取模板（點擊卡片即可加入待開單佇列，支援重複加入）"
        )
        self.selected_template_bubbles: list[str] = []

        self._build_widgets()
        self._load_templates()

    def s(self, value: float) -> int:
        return scale(value, self.sf)

    def _build_widgets(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self.content_frame = ttk.Frame(self, style="Ticket.Page.TFrame")
        self.content_frame.grid(row=0, column=0, sticky="nsew")
        self.content_frame.columnconfigure(0, weight=1)
        self.content_frame.rowconfigure(1, weight=1)

        self._build_header()
        self._build_template_workspace()
        self._bind_shortcuts()

    def _build_header(self) -> None:
        header = ttk.Frame(self.content_frame, style="Ticket.Page.TFrame")
        header.grid(row=0, column=0, sticky="ew", pady=(0, self.s(14)))
        header.columnconfigure(0, weight=1)

        ttk.Label(
            header,
            text="IT 服務台工單自動化",
            style="Ticket.Title.TLabel",
            anchor="center",
        ).grid(row=0, column=0, sticky="ew")

    def _build_template_workspace(self) -> None:
        surface_soft = self.colors.get("surface_soft", "#F8FAFC")
        card_bg = self.colors.get("surface", "#FFFFFF")
        border_color = self.colors.get("border", "#E4E9F0")
        text_color = self.colors.get("text", "#172033")
        muted_color = self.colors.get("text_muted", "#98A2B3")
        primary_color = self.colors.get("primary", "#2D6CDF")
        selected_bg = self.colors.get("button_active", "#EEF2F7")

        container = tk.Frame(
            self.content_frame,
            background=surface_soft,
            highlightbackground=border_color,
            highlightcolor=border_color,
            highlightthickness=1,
            takefocus=0,
            padx=self.s(14),
            pady=self.s(14),
        )
        container.grid(row=1, column=0, sticky="nsew")
        container.columnconfigure(0, weight=1)
        container.rowconfigure(2, weight=1)

        toolbar = tk.Frame(container, background=surface_soft)
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, self.s(12)))
        toolbar.columnconfigure(0, weight=1)

        left_actions = tk.Frame(toolbar, background=surface_soft)
        left_actions.grid(row=0, column=0, sticky="w")

        self.add_button = ttk.Button(
            left_actions,
            text="＋ 新增模板",
            command=self._add_template,
            style="Ticket.Secondary.TButton",
            cursor="hand2",
        )
        self.add_button.pack(side="left")

        self.copy_button = ttk.Button(
            left_actions,
            text="⧉ 複製模板",
            command=self._copy_template,
            style="Ticket.Secondary.TButton",
            cursor="hand2",
        )
        self.copy_button.pack(side="left", padx=(self.s(6), 0))

        self.demo_button = ttk.Button(
            left_actions,
            text="🎲 填入範例佇列",
            command=self.fill_sample_data,
            style="Ticket.Secondary.TButton",
            cursor="hand2",
        )
        self.demo_button.pack(side="left", padx=(self.s(6), 0))

        ttk.Button(
            toolbar,
            text="↻ 重新整理",
            command=self._load_templates,
            style="Ticket.Secondary.TButton",
            cursor="hand2",
        ).grid(row=0, column=1, sticky="e")

        # Horizontal Category Tab Bar
        self.group_title_var = tk.StringVar(value=self.active_group)
        category_bar = tk.Frame(container, background=surface_soft)
        category_bar.grid(row=1, column=0, sticky="ew", pady=(0, self.s(12)))
        total_groups = len(TEMPLATE_GROUPS)
        for col in range(total_groups):
            category_bar.columnconfigure(col, weight=1, uniform="ticket_group_tab")

        for col, group in enumerate(TEMPLATE_GROUPS):
            active = group == self.active_group
            bg = selected_bg if active else card_bg
            border = primary_color if active else border_color
            item = tk.Frame(
                category_bar,
                background=bg,
                highlightbackground=border,
                highlightcolor=primary_color,
                highlightthickness=1,
                bd=0,
                cursor="hand2",
                padx=self.s(10),
                pady=self.s(8),
            )
            item.grid(
                row=0,
                column=col,
                sticky="ew",
                padx=(
                    0 if col == 0 else self.s(4),
                    0 if col == total_groups - 1 else self.s(4),
                ),
            )
            item.columnconfigure(0, weight=1)

            inner = tk.Frame(item, background=bg, cursor="hand2")
            inner.grid(row=0, column=0)

            name_label = tk.Label(
                inner,
                text=group,
                anchor="center",
                background=bg,
                foreground=primary_color if active else text_color,
                font=(FONT_FAMILY, self.s(9.5), "bold" if active else "normal"),
                cursor="hand2",
            )
            name_label.pack(side="left")

            count_label = tk.Label(
                inner,
                text="0",
                anchor="center",
                background=bg,
                foreground=primary_color if active else muted_color,
                font=(FONT_FAMILY, self.s(9)),
                cursor="hand2",
            )
            count_label.pack(side="left", padx=(self.s(6), 0))

            def _on_select_group(_e: tk.Event[Any], g: str = group) -> Any:
                return self._select_group(g)

            def _on_enter_group(_e: tk.Event[Any], g: str = group) -> None:
                self._set_group_tab_hover(g, True)

            def _on_leave_group(_e: tk.Event[Any], g: str = group) -> None:
                self._set_group_tab_hover(g, False)

            for w in (item, inner, name_label, count_label):
                w.bind("<Button-1>", _on_select_group)
                w.bind("<Enter>", _on_enter_group)
                w.bind("<Leave>", _on_leave_group)
            self.group_buttons[group] = {
                "frame": item,
                "inner": inner,
                "name": name_label,
                "count": count_label,
            }

        # Template Card List Panel
        canvas_frame = ttk.Frame(container, style="Ticket.Card.TFrame")
        canvas_frame.grid(row=2, column=0, sticky="nsew")
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
            width=self.s(7),
            track_color=surface_soft,
            thumb_color=border_color,
            thumb_hover_color=muted_color,
            min_thumb_height=self.s(32),
        )
        self.card_scrollbar.grid(row=0, column=1, sticky="ns", padx=(2, 0))
        self.card_canvas.configure(yscrollcommand=self.card_scrollbar.set)

        self.cards_frame = tk.Frame(self.card_canvas, background=surface_soft)
        self.cards_window = self.card_canvas.create_window(
            (0, 0), window=self.cards_frame, anchor="nw"
        )
        self.cards_frame.bind("<Configure>", self._update_scroll_region)
        self.card_canvas.bind("<Configure>", self._on_canvas_resize)
        self.card_canvas.bind("<Enter>", self._bind_mousewheel)
        self.card_canvas.bind("<Leave>", self._unbind_mousewheel)

        # Queued BubbleList Viewport
        self.selection_viewport = tk.Frame(
            container,
            background=surface_soft,
            height=self.bubble_line_height,
        )
        self.selection_viewport.grid(row=3, column=0, sticky="ew", pady=(self.s(12), 0))
        self.selection_viewport.grid_propagate(False)
        self.selection_viewport.columnconfigure(0, weight=1)
        self.selection_viewport.rowconfigure(0, weight=1)

        self.selection_canvas = tk.Canvas(
            self.selection_viewport,
            background=surface_soft,
            highlightthickness=0,
            borderwidth=0,
            height=self.bubble_line_height,
        )
        self.selection_canvas.grid(row=0, column=0, sticky="nsew")

        self.selection_scrollbar = ModernScrollbar(
            self.selection_viewport,
            command=self.selection_canvas.yview,
            width=self.s(6),
            track_color=surface_soft,
            thumb_color=border_color,
            thumb_hover_color=muted_color,
            min_thumb_height=self.s(20),
        )
        self.selection_canvas.configure(yscrollcommand=self.selection_scrollbar.set)

        self.selection_bubble_list = BubbleList(
            self.selection_canvas,
            owner=self,
            items=self.selected_template_bubbles,
            display_text=str,
            on_remove=self._remove_selected_template_at_index,
            min_bubble_width=self.s(120),
            reserved_rows=1,
        )
        self.selection_bubble_list.background_color = surface_soft
        self.selection_bubble_list.bubble_background = card_bg
        self.selection_bubble_list.text_color = text_color
        self.selection_bubble_list.remove_color = self.colors.get("danger", "#D84A4A")
        ttk.Style(self).configure(
            "Ticket.Selection.TFrame",
            background=surface_soft,
        )
        self.selection_bubble_list.configure(style="Ticket.Selection.TFrame")

        self.selection_bubbles_window = self.selection_canvas.create_window(
            (0, 0), window=self.selection_bubble_list, anchor="nw"
        )
        self.selection_canvas.bind("<Configure>", self._on_selection_canvas_resize)
        self.selection_bubble_list.bind("<Configure>", self._update_selection_viewport, add="+")

        # Footer Bar
        footer = tk.Frame(container, background=surface_soft)
        footer.grid(row=4, column=0, sticky="ew", pady=(self.s(10), 0))
        footer.columnconfigure(0, weight=1)

        ttk.Label(
            footer,
            textvariable=self.selection_var,
            style="Ticket.FooterText.TLabel",
        ).grid(row=0, column=0, sticky="w")

        self.run_button = create_primary_button(
            footer,
            text="執行批次開單",
            command=self._start_submit,
        )
        self.run_button.grid(row=0, column=1, sticky="e")
        self.run_button.configure(state="disabled")

    def _on_selection_canvas_resize(self, event: Any) -> None:
        self.selection_canvas.itemconfigure(self.selection_bubbles_window, width=event.width)
        self.after_idle(self._update_selection_viewport)

    def _update_selection_viewport(self, _event: Any = None) -> None:
        if not hasattr(self, "selection_bubble_list"):
            return
        try:
            self.selection_bubble_list.update_idletasks()
            content_height = max(
                self.bubble_line_height,
                self.selection_bubble_list.winfo_reqheight(),
            )
            max_height = int(self.bubble_line_height * self.BUBBLE_MAX_LINES)
            viewport_height = min(content_height, max_height)

            self.selection_viewport.configure(height=viewport_height)
            self.selection_canvas.configure(height=viewport_height)
            self.selection_canvas.update_idletasks()
            content_bbox = self.selection_canvas.bbox(self.selection_bubbles_window)
            if content_bbox is None:
                content_bbox = (
                    0,
                    0,
                    self.selection_canvas.winfo_width(),
                    content_height,
                )
            self.selection_canvas.configure(
                scrollregion=(
                    0,
                    0,
                    max(content_bbox[2], self.selection_canvas.winfo_width()),
                    content_height,
                )
            )
            if content_height > max_height:
                self.selection_scrollbar.grid(row=0, column=1, sticky="ns", padx=(2, 0))
            else:
                self.selection_scrollbar.grid_remove()
                self.selection_canvas.yview_moveto(0)
        except tk.TclError:
            pass

    def _bind_shortcuts(self) -> None:
        self._ctrl_n_binding_id = self._toplevel.bind(
            "<Control-n>", self._on_ctrl_n_shortcut, add="+"
        )
        self.bind("<Destroy>", self._on_destroy, add="+")

    def _on_ctrl_n_shortcut(self, _event: Any = None) -> None:
        if self._is_view_alive():
            self._add_template()

    def _on_destroy(self, event: Any = None) -> None:
        if event is not None and event.widget is not self:
            return
        self._unbind_mousewheel()
        self._destroy_drag_ghost()
        if self._ctrl_n_binding_id is not None:
            try:
                self._toplevel.unbind("<Control-n>", self._ctrl_n_binding_id)
            except tk.TclError:
                pass
            self._ctrl_n_binding_id = None
        if self._resize_after_id is not None:
            try:
                self.after_cancel(self._resize_after_id)
            except tk.TclError:
                pass
            self._resize_after_id = None

    def fill_sample_data(self) -> None:
        """Populate the execution queue with the first 2 templates for instant portfolio demo."""
        if self._is_running() or not self.templates:
            return
        self.selected_template_indices.clear()
        for idx in range(min(2, len(self.templates))):
            self.selected_template_indices.append(idx)
        self.selected_index = (
            self.selected_template_indices[-1] if self.selected_template_indices else None
        )
        self._sync_selection_bubbles()
        self._populate_cards()
        self._on_selection_changed()

    def _populate_cards(self) -> None:
        for widget in self.cards_frame.winfo_children():
            widget.destroy()
        self._card_widgets.clear()
        self._visible_template_indices.clear()

        surface_soft = self.colors.get("surface_soft", "#F8FAFC")
        card_bg = self.colors.get("surface", "#FFFFFF")
        border_color = self.colors.get("border", "#E4E9F0")
        text_color = self.colors.get("text", "#172033")
        muted_color = self.colors.get("text_muted", "#98A2B3")
        primary_color = self.colors.get("primary", "#2D6CDF")

        if not self.templates:
            tk.Label(
                self.cards_frame,
                text="目前沒有工單模板，請點擊左上方「＋ 新增模板」建立。",
                background=surface_soft,
                foreground=muted_color,
                font=(FONT_FAMILY, self.s(11)),
                pady=self.s(36),
            ).grid(row=0, column=0, sticky="ew")
            self.cards_frame.columnconfigure(0, weight=1)
            return

        visible_templates = [
            (index, template)
            for index, template in enumerate(self.templates)
            if self._group_for_template(template) == self.active_group
        ]
        if not visible_templates:
            tk.Label(
                self.cards_frame,
                text="此分類目前沒有模板",
                background=surface_soft,
                foreground=muted_color,
                font=(FONT_FAMILY, self.s(11)),
                pady=self.s(36),
            ).grid(row=0, column=0, sticky="ew")
            self.cards_frame.columnconfigure(0, weight=1)
            return

        for index, template in visible_templates:
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

            badge_text = "故障需求" if template.get("category") == CATEGORY_INCIDENT else "例行維運"
            title_label = tk.Label(
                card,
                text=f"[{badge_text}]  {template.get('title', '')}",
                background=card_bg,
                foreground=text_color,
                font=(FONT_FAMILY, self.s(9.5)),
                anchor="w",
                justify="left",
                cursor="hand2",
            )
            title_label.grid(row=0, column=0, sticky="nsew", padx=(self.s(14), self.s(8)), pady=0)

            def _move_up(i: int = index) -> Any:
                return self._move_template_step(i, -1)

            def _move_down(i: int = index) -> Any:
                return self._move_template_step(i, 1)

            def _edit_tpl(i: int = index) -> Any:
                return self._edit_template_at(i)

            up_btn = ttk.Button(
                card,
                text="↑",
                width=2,
                command=_move_up,
                style="Ticket.Icon.TButton",
                cursor="hand2",
            )
            up_btn.grid(row=0, column=1, sticky="e", padx=(0, self.s(2)), pady=self.s(4))

            down_btn = ttk.Button(
                card,
                text="↓",
                width=2,
                command=_move_down,
                style="Ticket.Icon.TButton",
                cursor="hand2",
            )
            down_btn.grid(row=0, column=2, sticky="e", padx=(0, self.s(4)), pady=self.s(4))

            edit_button = ttk.Button(
                card,
                text="✏",
                width=3,
                command=_edit_tpl,
                style="Ticket.Icon.TButton",
                cursor="hand2",
            )
            edit_button.grid(row=0, column=3, sticky="e", padx=(0, self.s(8)), pady=self.s(4))

            def _on_press(event: tk.Event[Any], i: int = index) -> Any:
                return self._on_card_press(event, i)

            def _on_double_click(_event: tk.Event[Any], i: int = index) -> Any:
                return self._edit_template_at(i)

            def _on_card_enter(
                _event: tk.Event[Any],
                c: tk.Frame = card,
                labels: tuple[tk.Label, ...] = (title_label,),
            ) -> Any:
                return self._set_card_hover(c, labels, True)

            def _on_card_leave(
                _event: tk.Event[Any],
                c: tk.Frame = card,
                labels: tuple[tk.Label, ...] = (title_label,),
            ) -> Any:
                return self._set_card_hover(c, labels, False)

            widgets = (card, title_label)
            for w in widgets:
                w.bind("<Button-1>", _on_press)
                w.bind("<B1-Motion>", self._on_drag_motion)
                w.bind("<ButtonRelease-1>", self._on_drag_drop)
                w.bind("<Double-1>", _on_double_click)
                w.bind("<Enter>", _on_card_enter)
                w.bind("<Leave>", _on_card_leave)

            self._card_widgets.append(card)
            self._visible_template_indices.append(index)

        self._layout_cards()

    def _layout_cards(self) -> None:
        self.cards_frame.columnconfigure(0, weight=1, uniform="template_card")
        for display_index, card in enumerate(self._card_widgets):
            card.grid(
                row=display_index,
                column=0,
                sticky="ew",
                padx=self.card_gap // 2,
                pady=self.card_gap // 2,
            )

    def _on_canvas_resize(self, event: Any) -> None:
        self.card_canvas.itemconfigure(self.cards_window, width=event.width)
        if self._resize_after_id is not None:
            try:
                self.after_cancel(self._resize_after_id)
            except tk.TclError:
                pass
        self._resize_after_id = self.after(80, self._layout_cards)

    def _update_scroll_region(self, _event: Any = None) -> None:
        try:
            self.card_canvas.configure(scrollregion=self.card_canvas.bbox("all"))
        except tk.TclError:
            pass

    def _bind_mousewheel(self, _event: Any = None) -> None:
        self.card_canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    def _unbind_mousewheel(self, _event: Any = None) -> None:
        try:
            self.card_canvas.unbind_all("<MouseWheel>")
        except tk.TclError:
            pass

    def _on_mousewheel(self, event: Any) -> None:
        try:
            if not self._is_view_alive() or not self.card_canvas.winfo_exists():
                return
            self.card_canvas.yview_scroll(int(-event.delta / 120), "units")
        except tk.TclError:
            pass

    def _set_card_hover(
        self,
        card: tk.Frame,
        labels: tuple[tk.Label, ...],
        hovered: bool,
    ) -> None:
        bg = (
            self.colors.get("card_hover", "#F0F5FD")
            if hovered
            else self.colors.get("surface", "#FFFFFF")
        )
        card.configure(background=bg)
        for label in labels:
            label.configure(background=bg)

    def _select_card(self, index: int) -> None:
        """Append the clicked template to the execution queue (duplicates allowed)."""
        self.selected_index = index
        self.selected_template_indices.append(index)
        self._sync_selection_bubbles()
        self._update_group_tabs()
        self._populate_cards()
        self._on_selection_changed()

    def _sync_selection_bubbles(self) -> None:
        self.selected_template_bubbles.clear()
        valid_indices: list[int] = []
        for index in self.selected_template_indices:
            if 0 <= index < len(self.templates):
                valid_indices.append(index)
                title = self.templates[index].get("title", "").strip()
                self.selected_template_bubbles.append(title or f"模板 {index + 1}")
        self.selected_template_indices[:] = valid_indices
        if hasattr(self, "selection_bubble_list"):
            self.selection_bubble_list.render()
            self.after_idle(self._update_selection_viewport)

    def _remove_selected_template_at_index(self, queue_index: int) -> None:
        if (
            self._is_running()
            or queue_index < 0
            or queue_index >= len(self.selected_template_indices)
        ):
            return
        self.selected_template_indices.pop(queue_index)
        self.selected_index = (
            self.selected_template_indices[-1] if self.selected_template_indices else None
        )
        self._sync_selection_bubbles()
        self._populate_cards()
        self._on_selection_changed()

    def _move_template_step(self, index: int, direction: int) -> None:
        """Move template up/down by one step within the repository."""
        if self._is_running():
            return
        try:
            target_index = self.repository.move_template(index, direction)
            if target_index == index:
                return
            self.templates = self.repository.load_templates()
            remapped: list[int] = []
            for sel in self.selected_template_indices:
                if sel == index:
                    remapped.append(target_index)
                elif sel == target_index:
                    remapped.append(index)
                else:
                    remapped.append(sel)
            self.selected_template_indices[:] = remapped
            self._refresh_tree(selected_index=target_index)
        except Exception as exc:
            logger.exception("移動工單模板順序失敗")
            messagebox.showerror("排序失敗", str(exc), parent=self)

    def _on_card_press(self, event: Any, index: int) -> None:
        self.drag_start_index = index
        self.drag_start_x = event.x_root
        self.drag_start_y = event.y_root
        self.drag_active = False

    def _create_drag_ghost(self, template: dict[str, str]) -> None:
        self._destroy_drag_ghost()
        drag_win = tk.Toplevel(self)
        drag_win.overrideredirect(True)
        drag_win.attributes("-topmost", True)
        try:
            drag_win.attributes("-alpha", 0.88)
        except tk.TclError:
            pass

        primary = self.colors.get("primary", "#2D6CDF")
        primary_soft = self.colors.get("card_hover", "#F0F5FD")
        text_color = self.colors.get("text", "#172033")

        outer = tk.Frame(drag_win, background=primary, padx=1, pady=1)
        outer.pack(fill="both", expand=True)
        inner = tk.Frame(outer, background=primary_soft, padx=self.s(14), pady=self.s(8))
        inner.pack(fill="both", expand=True)
        tk.Label(
            inner,
            text=template.get("title", ""),
            font=(FONT_FAMILY, self.s(9), "bold"),
            foreground=text_color,
            background=primary_soft,
            anchor="w",
        ).pack(anchor="w")
        self.drag_window = drag_win

    def _destroy_drag_ghost(self) -> None:
        if self.drag_window is not None:
            try:
                self.drag_window.destroy()
            except Exception:
                pass
            self.drag_window = None

    def _on_drag_motion(self, event: Any) -> None:
        if self.drag_start_index is None or self.drag_start_x is None or self.drag_start_y is None:
            return

        if not self.drag_active:
            dx = abs(event.x_root - self.drag_start_x)
            dy = abs(event.y_root - self.drag_start_y)
            if max(dx, dy) < self.drag_threshold:
                return
            self.drag_active = True
            self._create_drag_ghost(self.templates[self.drag_start_index])

        if self.drag_window is not None:
            self.drag_window.geometry(f"+{event.x_root + 15}+{event.y_root + 15}")

    def _card_index_at_pointer(self, x_root: int, y_root: int) -> int | None:
        for index, card in enumerate(self._card_widgets):
            x1, y1 = card.winfo_rootx(), card.winfo_rooty()
            x2, y2 = x1 + card.winfo_width(), y1 + card.winfo_height()
            if x1 <= x_root <= x2 and y1 <= y_root <= y2:
                return self._visible_template_indices[index]
        return None

    def _on_drag_drop(self, event: Any) -> None:
        self._destroy_drag_ghost()
        if self.drag_start_index is None:
            return

        start_index = self.drag_start_index
        was_dragging = self.drag_active
        self.drag_start_index = None
        self.drag_start_x = None
        self.drag_start_y = None
        self.drag_active = False

        if not was_dragging:
            self._select_card(start_index)
            return

        target_index = self._card_index_at_pointer(event.x_root, event.y_root)
        if target_index is None or target_index == start_index:
            return
        try:
            step = 1 if target_index > start_index else -1
            current = start_index
            for _ in range(abs(target_index - start_index)):
                current = self.repository.move_template(current, step)
            self.templates = self.repository.load_templates()

            remapped_indices: list[int] = []
            for sel_idx in self.selected_template_indices:
                if sel_idx == start_index:
                    remapped_indices.append(target_index)
                elif start_index < target_index and start_index < sel_idx <= target_index:
                    remapped_indices.append(sel_idx - 1)
                elif target_index < start_index and target_index <= sel_idx < start_index:
                    remapped_indices.append(sel_idx + 1)
                else:
                    remapped_indices.append(sel_idx)
            self.selected_template_indices[:] = remapped_indices
            self._refresh_tree(selected_index=target_index)
        except Exception as exc:
            logger.exception("拖曳調整工單模板順序失敗")
            messagebox.showerror("排序失敗", str(exc), parent=self)

    def _group_for_template(self, template: dict[str, str]) -> str:
        group = template.get("_ui_group", DEFAULT_TEMPLATE_GROUP)
        return group if group in TEMPLATE_GROUPS else DEFAULT_TEMPLATE_GROUP

    def _select_group(self, group: str) -> None:
        if group not in TEMPLATE_GROUPS:
            return
        self.active_group = group
        self.group_title_var.set(group)
        self._update_group_tabs()
        self._populate_cards()
        self.card_canvas.yview_moveto(0)

    def _set_group_tab_hover(self, group: str, hovering: bool) -> None:
        if group == self.active_group:
            return
        widgets = self.group_buttons.get(group)
        if not widgets:
            return
        bg = (
            self.colors.get("card_hover", "#F0F5FD")
            if hovering
            else self.colors.get("surface", "#FFFFFF")
        )
        widgets["frame"].configure(background=bg)
        widgets["inner"].configure(background=bg)
        widgets["name"].configure(background=bg)
        widgets["count"].configure(background=bg)

    def _update_group_tabs(self) -> None:
        counts = {group: 0 for group in TEMPLATE_GROUPS}
        for template in self.templates:
            counts[self._group_for_template(template)] += 1

        card_bg = self.colors.get("surface", "#FFFFFF")
        selected_bg = self.colors.get("button_active", "#EEF2F7")
        border_color = self.colors.get("border", "#E4E9F0")
        primary_color = self.colors.get("primary", "#2D6CDF")
        text_color = self.colors.get("text", "#172033")
        muted_color = self.colors.get("text_muted", "#98A2B3")

        for group, widgets in self.group_buttons.items():
            active = group == self.active_group
            bg = selected_bg if active else card_bg
            border = primary_color if active else border_color
            widgets["frame"].configure(background=bg, highlightbackground=border)
            widgets["inner"].configure(background=bg)
            widgets["name"].configure(
                text=group,
                background=bg,
                foreground=primary_color if active else text_color,
                font=(FONT_FAMILY, self.s(9.5), "bold" if active else "normal"),
            )
            widgets["count"].configure(
                text=str(counts[group]),
                background=bg,
                foreground=primary_color if active else muted_color,
                font=(FONT_FAMILY, self.s(9)),
            )

    def on_show(self) -> None:
        self.after(50, self.card_canvas.focus_set)

    def _load_templates(self) -> None:
        self.selected_template_indices.clear()
        self.selected_index = None
        try:
            self.templates = self.repository.load_templates()
            if self.templates:
                groups_with_items = [
                    g
                    for g in TEMPLATE_GROUPS
                    if any(self._group_for_template(t) == g for t in self.templates)
                ]
                if groups_with_items and self.active_group not in groups_with_items:
                    self.active_group = groups_with_items[0]
                    self.group_title_var.set(self.active_group)
        except Exception as exc:
            logger.exception("載入工單模板失敗")
            self.templates = []
            messagebox.showerror("載入模板失敗", str(exc), parent=self)
        self._refresh_tree()

    def _refresh_tree(self, selected_index: int | None = None) -> None:
        if selected_index is not None and 0 <= selected_index < len(self.templates):
            self.selected_index = selected_index
        elif self.selected_index is not None and self.selected_index >= len(self.templates):
            self.selected_index = None
        self._sync_selection_bubbles()
        self._update_group_tabs()
        self._populate_cards()
        self._on_selection_changed()

    def _on_selection_changed(self) -> None:
        selected_count = len(self.selected_template_indices)
        has_selection = selected_count > 0
        self.selection_var.set(
            "尚未選取模板（點擊卡片即可加入待開單佇列，支援重複加入）"
            if not has_selection
            else f"已加入待開單佇列：{selected_count} 筆"
        )
        self.run_button.configure(
            state="normal" if has_selection and not self._is_running() else "disabled"
        )

    def _get_single_selected_index(self) -> int | None:
        if self.selected_index is None:
            messagebox.showwarning(
                "請選擇模板",
                "請先點選一張工單模板卡片再進行複製或編輯。",
                parent=self,
            )
            return None
        return self.selected_index

    def _add_template(self) -> None:
        if self._is_running():
            return
        dialog = TicketTemplateDialog(
            self,
            default_group=self.active_group,
            repository=self.repository,
        )
        self.wait_window(dialog)
        if dialog.action != "save" or dialog.result is None:
            return
        try:
            template = dict(dialog.result)
            template["_ui_group"] = dialog.result_group
            self.repository.add_template(template)
            self.active_group = dialog.result_group
            self.group_title_var.set(self.active_group)
            self._load_templates()
        except Exception as exc:
            logger.exception("新增工單模板失敗")
            messagebox.showerror("新增失敗", str(exc), parent=self)

    def _copy_template(self) -> None:
        if self._is_running():
            return
        index = self._get_single_selected_index()
        if index is None:
            return

        dialog = TicketTemplateDialog(
            self,
            template=self.templates[index],
            copy_mode=True,
            repository=self.repository,
        )
        self.wait_window(dialog)
        if dialog.action != "save" or dialog.result is None:
            return

        try:
            template = dict(dialog.result)
            template["_ui_group"] = dialog.result_group
            self.repository.add_template(template)
            self.active_group = dialog.result_group
            self.group_title_var.set(self.active_group)
            self._load_templates()
        except Exception as exc:
            logger.exception("複製工單模板失敗")
            messagebox.showerror("複製失敗", str(exc), parent=self)

    def _edit_template_at(self, index: int) -> None:
        self.selected_index = index
        self._edit_template()

    def _edit_template(self) -> None:
        if self._is_running():
            return
        index = self._get_single_selected_index()
        if index is None:
            return
        dialog = TicketTemplateDialog(
            self,
            template=self.templates[index],
            repository=self.repository,
        )
        self.wait_window(dialog)

        if dialog.action == "save" and dialog.result is not None:
            try:
                template = dict(dialog.result)
                template["_ui_group"] = dialog.result_group
                self.repository.update_template(index, template)
                self.active_group = dialog.result_group
                self.group_title_var.set(self.active_group)
                self.templates = self.repository.load_templates()
                self._refresh_tree(index)
            except Exception as exc:
                logger.exception("編輯工單模板失敗")
                messagebox.showerror("編輯失敗", str(exc), parent=self)
        elif dialog.action == "delete":
            try:
                self.repository.delete_template(index)
                self._load_templates()
            except Exception as exc:
                logger.exception("刪除工單模板失敗")
                messagebox.showerror("刪除失敗", str(exc), parent=self)

    def _prepare_selected_templates(self) -> list[dict[str, str]] | None:
        if not self.selected_template_indices:
            messagebox.showwarning("尚未選擇模板", "請至少加入一筆模板至開單佇列。", parent=self)
            return None

        prepared: list[dict[str, str]] = []
        total = len(self.selected_template_indices)
        for number, index in enumerate(self.selected_template_indices, start=1):
            if not 0 <= index < len(self.templates):
                continue
            template = self.templates[index]
            dialog = RuntimeTicketConfirmDialog(
                self,
                template=template,
                template_number=number,
                total_count=total,
                repository=self.repository,
            )
            self.wait_window(dialog)
            if dialog.result is None:
                return None
            prepared.append(dialog.result)
        return prepared

    def _start_submit(self) -> None:
        if self._is_running() or self._is_preparing:
            return

        if self.automation_worker is None:
            messagebox.showerror("錯誤", "AutomationWorker 尚未初始化", parent=self)
            return

        self._is_preparing = True
        self.run_button.configure(text="確認開單內容中…", state="disabled")

        try:
            prepared_templates = self._prepare_selected_templates()
            if not prepared_templates:
                return

            base_url = getattr(self.app, "sandbox_base_url", "http://127.0.0.1:8000")
            creds = (
                self.app.credential_store.load() if hasattr(self.app, "credential_store") else None
            )
            storage = getattr(self.app, "storage", None)

            self.current_future = self.automation_worker.submit(
                run_batch_tickets,
                prepared_templates,
                base_url,
                creds,
                storage,
            )
            self._set_running_state(True)
            self.app.update_browser_status(
                f"瀏覽器自動化：正在執行服務台批次開單（共 {len(prepared_templates)} 筆）...",
                state="running",
            )
            self._toplevel.after(180, self._poll_future)
        finally:
            self._is_preparing = False
            if self.current_future is None and self._is_view_alive():
                self.run_button.configure(text="執行批次開單")
                self._on_selection_changed()

    def _is_view_alive(self) -> bool:
        try:
            return bool(self.winfo_exists())
        except tk.TclError:
            return False

    def _poll_future(self) -> None:
        if self.current_future is None or getattr(self.app, "closing", False):
            return
        if not self.current_future.done():
            try:
                if self._toplevel.winfo_exists():
                    self._toplevel.after(180, self._poll_future)
            except tk.TclError:
                pass
            return

        view_alive = self._is_view_alive()
        if view_alive:
            self._set_running_state(False)
        try:
            result = self.current_future.result()
        except Exception as exc:
            logger.exception("取得批次開單結果失敗")
            self.app.update_browser_status("瀏覽器自動化：批次開單執行失敗", state="off")
            messagebox.showerror(
                "執行失敗", str(exc), parent=self if view_alive else self._toplevel
            )
        else:
            self._handle_result(result, view_alive=view_alive)
        finally:
            self.current_future = None
            if view_alive:
                self._on_selection_changed()

    def _handle_result(self, result: Any, *, view_alive: bool = True) -> None:
        dialog_parent = self if view_alive else self._toplevel
        if not isinstance(result, ServiceResult):
            messagebox.showerror("結果錯誤", "工單自動化回傳格式不正確。", parent=dialog_parent)
            return

        if hasattr(self.app, "refresh_usage_stats"):
            self.app.refresh_usage_stats()

        if result.status == "success":
            self.app.update_browser_status(f"瀏覽器自動化：{result.message}", state="ready")
            if view_alive:
                self.selected_template_indices.clear()
                self.selected_index = None
                self._sync_selection_bubbles()
                self._populate_cards()
                self._on_selection_changed()
        elif result.status == "manual_confirmation":
            self.app.update_browser_status(f"瀏覽器自動化：{result.message}", state="ready")
            messagebox.showinfo("請確認", result.message, parent=dialog_parent)
        else:
            self.app.update_browser_status("瀏覽器自動化：批次開單失敗", state="off")
            detail = result.message
            if result.error:
                detail += f"\n\n錯誤內容：\n{result.error}"
            messagebox.showerror("執行失敗", detail, parent=dialog_parent)

    def _set_running_state(self, running: bool) -> None:
        if running:
            self.run_button.configure(text="自動開單執行中，請稍候…", state="disabled")
            self.add_button.configure(state="disabled")
            self.copy_button.configure(state="disabled")
            self.demo_button.configure(state="disabled")
        else:
            self.run_button.configure(text="執行批次開單")
            self.add_button.configure(state="normal")
            self.copy_button.configure(state="normal")
            self.demo_button.configure(state="normal")
            self._on_selection_changed()

    def _is_running(self) -> bool:
        return self.current_future is not None and not self.current_future.done()

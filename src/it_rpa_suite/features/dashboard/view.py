"""Dashboard overview view displaying efficiency statistics and feature navigation cards."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk
from typing import Any

from it_rpa_suite.app.theme import FONT_FAMILY, scale


class DashboardView(ttk.Frame):
    """Home dashboard with 2 merged monthly KPI cards and 3 feature navigation groups."""

    STATISTICS = (
        (
            "本月節省時間",
            "this_month_saved_minutes",
            "上月節省",
            "last_month_saved_minutes",
            "分鐘",
            "#16A36A",
        ),
        (
            "本月完成開單",
            "this_month_tickets",
            "上月開單",
            "last_month_tickets",
            "件",
            "#E79A24",
        ),
    )

    FEATURE_GROUPS = (
        (
            "基礎作業",
            (
                ("設備借用歸還", "本專案的起源", "show_asset_loan"),
                ("員工入職離職", "鉤子功能（Hook Feature）", "show_onboarding"),
                ("網路權限開通", "老式 frameset 網站", "show_nac_access"),
                ("批量信件通知", "Excel 報表分析與寄信", "show_batch_notify"),
            ),
        ),
        (
            "進階工具",
            (
                ("IT 服務台開單", "模板管理介面", "show_ticket_helper"),
                ("個人自訂工具箱", "快速開發小工具", "show_toolbox"),
                ("📞 觸發模擬來電", "Windows 訊息偵測與通知", "trigger_mock_call"),
            ),
        ),
        (
            "系統設定",
            (
                ("系統憑證設定", "敏感資訊 DPAPI 加密", "show_credentials"),
                ("檢查更新", "三階段安全更新程序", "run_updater"),
            ),
        ),
    )

    def __init__(self, parent: tk.Misc, app: Any) -> None:
        super().__init__(parent, style="Content.TFrame")
        self.app = app
        self.colors: dict[str, str] = app.colors
        self.sf: float = float(app.scale_factor)

        if hasattr(self.app, "refresh_usage_stats"):
            self.app.refresh_usage_stats()

        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self._build_main_content()

    def s(self, value: float) -> int:
        return scale(value, self.sf)

    def _build_main_content(self) -> None:
        content = ttk.Frame(
            self,
            style="Content.TFrame",
            padding=(self.s(30), self.s(24), self.s(30), self.s(28)),
        )
        content.grid(row=0, column=0, sticky="nsew")
        content.columnconfigure(0, weight=1)
        content.rowconfigure(2, weight=1)

        self._build_header(content)
        self._build_statistics(content)
        self._build_feature_buttons(content)

    def _build_header(self, parent: ttk.Frame) -> None:
        header = ttk.Frame(parent, style="Content.TFrame")
        header.grid(row=0, column=0, sticky="ew", pady=(0, self.s(22)))
        header.columnconfigure(0, weight=1)

        box = ttk.Frame(header, style="Content.TFrame")
        box.grid(row=0, column=0)
        ttk.Label(box, text="IT 自動化工作區", style="Title.TLabel", anchor="center").pack(
            anchor="center"
        )

    def _build_statistics(self, parent: ttk.Frame) -> None:
        section = ttk.Frame(parent, style="Content.TFrame")
        section.grid(row=1, column=0, sticky="ew", pady=(0, self.s(22)))
        total_cols = len(self.STATISTICS)
        ttk.Label(section, text="效率統計", style="SectionTitle.TLabel").grid(
            row=0, column=0, columnspan=total_cols, sticky="w", pady=(0, self.s(12))
        )

        stats = getattr(self.app, "feature_usage_stats", {}) or {}
        for column in range(total_cols):
            section.columnconfigure(column, weight=1, uniform="statistics")

        for column, (
            label,
            stat_key,
            last_label,
            last_stat_key,
            unit,
            color,
        ) in enumerate(self.STATISTICS):
            value = stats.get(stat_key, 0)
            last_value = stats.get(last_stat_key, 0)
            self._create_stat_card(
                section,
                column,
                label,
                value,
                last_label,
                last_value,
                unit,
                color,
            )

    def _create_stat_card(
        self,
        parent: ttk.Frame,
        column: int,
        label: str,
        value: int | float,
        last_label: str,
        last_value: int | float,
        unit: str,
        accent_color: str,
    ) -> None:
        total_cols = len(self.STATISTICS)
        card = tk.Frame(
            parent,
            background=self.colors["surface"],
            highlightbackground=self.colors["border"],
            highlightthickness=1,
        )
        card.grid(
            row=1,
            column=column,
            sticky="nsew",
            padx=(
                0 if column == 0 else self.s(7),
                0 if column == total_cols - 1 else self.s(7),
            ),
        )
        tk.Frame(card, background=accent_color, width=self.s(4)).pack(side="left", fill="y")
        body = tk.Frame(
            card,
            background=self.colors["surface"],
            padx=self.s(16),
            pady=self.s(15),
        )
        body.pack(side="left", fill="both", expand=True)

        tk.Label(
            body,
            text=label,
            font=(FONT_FAMILY, self.s(9)),
            foreground=self.colors["text_secondary"],
            background=self.colors["surface"],
        ).pack(anchor="w")

        value_row = tk.Frame(body, background=self.colors["surface"])
        value_row.pack(fill="x", pady=(self.s(8), 0))
        tk.Label(
            value_row,
            text=str(value),
            font=(FONT_FAMILY, self.s(22), "bold"),
            foreground=self.colors["text"],
            background=self.colors["surface"],
        ).pack(side="left")
        tk.Label(
            value_row,
            text=unit,
            font=(FONT_FAMILY, self.s(9)),
            foreground=self.colors["text_muted"],
            background=self.colors["surface"],
        ).pack(side="left", padx=(self.s(6), 0), pady=(self.s(9), 0))
        tk.Label(
            value_row,
            text=f"{last_label}：{last_value} {unit}",
            font=(FONT_FAMILY, self.s(9)),
            foreground=self.colors["text_muted"],
            background=self.colors["surface"],
        ).pack(side="right", pady=(self.s(9), 0))

    def _build_feature_buttons(self, parent: ttk.Frame) -> None:
        section = ttk.Frame(parent, style="Content.TFrame")
        section.grid(row=2, column=0, sticky="nsew")
        for column in range(3):
            section.columnconfigure(column, weight=1)

        ttk.Label(section, text="常用功能", style="SectionTitle.TLabel").grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, self.s(12))
        )
        for column, (title, features) in enumerate(self.FEATURE_GROUPS):
            group = self._create_feature_group(section, title, column)
            for feature_title, description, method_name in features:
                command = getattr(self.app, method_name, None)
                if callable(command):
                    self._add_feature_button(group, feature_title, description, command)

    def _create_feature_group(self, parent: ttk.Frame, title: str, column: int) -> tk.Frame:
        frame = tk.Frame(
            parent,
            background=self.colors["surface_soft"],
            highlightbackground=self.colors["border"],
            highlightthickness=1,
            padx=self.s(12),
            pady=self.s(12),
        )
        frame.grid(
            row=1,
            column=column,
            sticky="nsew",
            padx=(
                0 if column == 0 else self.s(7),
                0 if column == 2 else self.s(7),
            ),
        )
        tk.Label(
            frame,
            text=title,
            font=(FONT_FAMILY, self.s(10), "bold"),
            foreground=self.colors["text_secondary"],
            background=self.colors["surface_soft"],
        ).pack(fill="x", anchor="w", padx=self.s(4), pady=(0, self.s(8)))
        return frame

    def _add_feature_button(
        self,
        parent: tk.Frame,
        title: str,
        description: str,
        command: Callable[[], Any],
    ) -> None:
        surface = self.colors["surface"]
        card = tk.Frame(
            parent,
            background=surface,
            highlightbackground=self.colors["border"],
            highlightthickness=1,
            cursor="hand2",
        )
        card.pack(fill="x", pady=self.s(5))
        card.columnconfigure(0, weight=1)

        text_frame = tk.Frame(card, background=surface, cursor="hand2")
        text_frame.grid(row=0, column=0, sticky="ew", padx=self.s(14), pady=self.s(11))

        title_label = tk.Label(
            text_frame,
            text=title,
            font=(FONT_FAMILY, self.s(10), "bold"),
            foreground=self.colors["text"],
            background=surface,
            cursor="hand2",
        )
        title_label.pack(anchor="w")

        desc_label = tk.Label(
            text_frame,
            text=description,
            font=(FONT_FAMILY, self.s(8.5)),
            foreground=self.colors["text_muted"],
            background=surface,
            cursor="hand2",
        )
        desc_label.pack(anchor="w", pady=(self.s(4), 0))

        arrow = tk.Label(
            card,
            text="›",
            font=(FONT_FAMILY, self.s(18)),
            foreground=self.colors["text_muted"],
            background=surface,
            cursor="hand2",
        )
        arrow.grid(row=0, column=1, padx=(self.s(5), self.s(13)))

        widgets = (card, text_frame, title_label, desc_label, arrow)

        def set_hover(hovered: bool) -> None:
            bg = self.colors["card_hover"] if hovered else surface
            for w in widgets:
                w.configure(background=bg)
            title_label.configure(foreground=self.colors["primary" if hovered else "text"])
            arrow.configure(foreground=self.colors["primary" if hovered else "text_muted"])

        for w in widgets:
            w.bind("<Enter>", lambda _e: set_hover(True))
            w.bind("<Leave>", lambda _e: set_hover(False))
            w.bind("<Button-1>", lambda _e: command())

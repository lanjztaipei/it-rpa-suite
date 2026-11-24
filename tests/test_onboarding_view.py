"""Unit tests for OnboardingView dynamic input field toggling."""

from __future__ import annotations

import tkinter as tk
from unittest.mock import MagicMock

import pytest

from it_rpa_suite.features.onboarding.view import OnboardingView


@pytest.fixture
def tk_root():
    root = tk.Tk()
    root.deiconify()
    yield root
    try:
        root.destroy()
    except Exception:
        pass


def test_onboarding_view_default_four_inputs_and_conditional_reduction(tk_root: tk.Tk) -> None:
    mock_app = MagicMock()
    mock_app.scale_factor = 1.0
    mock_app.colors = {}

    view = OnboardingView(tk_root, mock_app)
    view.pack()
    tk_root.update()

    # 1. 預設顯示四個輸入框（螢幕資產編號欄位預設在 grid 顯示中）
    assert view.monitor_row_frame.winfo_manager() == "grid"
    assert view.monitor_row_frame.winfo_ismapped() == 1

    # 2. 輸入 1 開頭桌機 (IT-100002)，維持四個輸入框
    view.computer_tag_var.set("IT-100002")
    tk_root.update()
    assert view.monitor_row_frame.winfo_manager() == "grid"
    assert view.monitor_row_frame.winfo_ismapped() == 1

    # 3. 輸入 3 開頭筆電 (IT-300002)，符合免配螢幕條件，自動減少到三個輸入框（隱藏螢幕欄位）
    view.monitor_tag_var.set("IT-200002")
    view.computer_tag_var.set("IT-300002")
    tk_root.update()
    assert view.monitor_row_frame.winfo_manager() == ""
    assert view.monitor_row_frame.winfo_ismapped() == 0
    assert view.monitor_tag_var.get() == ""

    # 4. 清空電腦編號，回復預設狀態（四個輸入框）
    view.computer_tag_var.set("")
    tk_root.update()
    assert view.monitor_row_frame.winfo_manager() == "grid"
    assert view.monitor_row_frame.winfo_ismapped() == 1

    # 5. 測試 Enter 鍵焦點移動行為
    # 預設狀態 (4 個輸入框) -> 電腦編號按 Enter 應移動至螢幕編號輸入框
    view.computer_tag_var.set("IT-100002")
    tk_root.update()
    assert view._focus_after_computer_tag() == "break"
    tk_root.update()
    assert tk_root.focus_get() == view.monitor_tag_entry

    # 筆電狀態 (3 個輸入框) -> 電腦編號按 Enter 應跳過螢幕，移動至話機單選按鈕
    view.computer_tag_var.set("IT-300002")
    view.new_deskphone_var.set("Y")
    tk_root.update()
    assert view._focus_after_computer_tag() == "break"
    tk_root.update()
    assert tk_root.focus_get() == view.new_phone_yes_btn

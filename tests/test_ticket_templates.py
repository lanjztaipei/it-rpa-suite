"""Unit and integration tests for Service Desk ticket templates, '__' marker resolution, and Caller ID lookup."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path

import pytest

from it_rpa_suite.adapters.browser_worker import AutomationWorker
from it_rpa_suite.adapters.paths import get_app_paths
from it_rpa_suite.adapters.storage import AppStorage
from it_rpa_suite.features.caller_id.monitor import (
    is_incoming_call_window_title,
    lookup_caller_directory,
    parse_caller_text,
)
from it_rpa_suite.features.ticket_helper.service import (
    CATEGORY_INCIDENT,
    CATEGORY_ROUTINE,
    TemplateRepository,
    find_first_placeholder_marker,
    run_batch_tickets,
)
from it_rpa_suite.mock_server.server import MockEnterpriseServer


def test_template_normalization_and_validation() -> None:
    """Verify schema normalization, category validation, and email/required field checks."""
    inc = TemplateRepository.normalize_template(
        {
            "category": "Incident Request",
            "email": "alex.chen@enterprise.local",
            "title": "VPN 連線異常排除",
            "type": "Network",
            "sub_type": "VPN Client Access",
            "corp": "Enterprise-HQ",
            "resolve": "已重設憑證並確認連線正常。",
            "_ui_group": "電腦相關",
        }
    )
    assert inc["category"] == CATEGORY_INCIDENT
    assert inc["sub_type"] == "VPN Client Access"
    assert inc["corp"] == "Enterprise-HQ"
    assert inc["_ui_group"] == "電腦相關"

    # Routine Task clears sub_type and corp automatically
    rtn = TemplateRepository.normalize_template(
        {
            "category": "Routine Task",
            "email": "brian.wang@enterprise.local",
            "title": "核心機房例行巡檢",
            "type": "Data Center Inspection",
            "sub_type": "ShouldBeCleared",
            "corp": "Enterprise-HQ",
            "resolve": "完成巡檢，溫溼度與 UPS 正常。",
        }
    )
    assert rtn["category"] == CATEGORY_ROUTINE
    assert rtn["sub_type"] == ""
    assert rtn["corp"] == ""
    assert rtn["_ui_group"] == "未分類"

    # Invalid category
    with pytest.raises(ValueError, match="不支援"):
        TemplateRepository.normalize_template(
            {
                "category": "Unknown Category",
                "email": "alex.chen@enterprise.local",
                "title": "測試",
                "type": "Hardware",
                "resolve": "完成",
            }
        )

    # Invalid email
    with pytest.raises(ValueError, match="Email"):
        TemplateRepository.normalize_template(
            {
                "category": "Incident Request",
                "email": "invalid-email-without-at",
                "title": "測試",
                "type": "Hardware",
                "resolve": "完成",
            }
        )

    # Missing required field
    with pytest.raises(ValueError, match="不可空白"):
        TemplateRepository.normalize_template(
            {
                "category": "Incident Request",
                "email": "alex.chen@enterprise.local",
                "title": "   ",
                "type": "Hardware",
                "resolve": "完成",
            }
        )


def test_template_repository_crud_sorting_and_atomic_write(tmp_path: Path) -> None:
    """Verify CRUD operations, up/down sorting, default seeding, and .tmp atomic write safety."""
    paths = get_app_paths(base_dir=tmp_path)
    repo = TemplateRepository(paths=paths)

    # 1. Default templates seeded automatically from assets/default_ticket_templates.json
    initial = repo.load_templates()
    assert len(initial) >= 4

    # 2. Reset to clean list and test Add / Duplicate / Update / Move / Delete
    repo.save_templates([])
    assert repo.load_templates() == []

    t1 = repo.add_template(
        {
            "category": "Incident Request",
            "email": "alex.chen@enterprise.local",
            "title": "第一筆工單模板",
            "type": "Hardware",
            "sub_type": "RAM / Storage Upgrade",
            "corp": "Enterprise-HQ",
            "resolve": "更換記憶體模組。",
            "_ui_group": "電腦相關",
        }
    )
    assert t1["title"] == "第一筆工單模板"

    t2 = repo.duplicate_template(0, overrides={"title": "第二筆複製模板"})
    assert t2["title"] == "第二筆複製模板"

    t3 = repo.add_template(
        {
            "category": "Routine Task",
            "email": "irene.lin@enterprise.local",
            "title": "第三筆例行模板",
            "type": "Data Center Inspection",
            "resolve": "機房溫溼度檢查正常。",
            "_ui_group": "例行事項",
        }
    )
    assert t3["category"] == CATEGORY_ROUTINE

    # Update index 1
    repo.update_template(
        1,
        {
            **t2,
            "title": "第二筆已更新模板",
        },
    )
    loaded = repo.load_templates()
    assert [t["title"] for t in loaded] == [
        "第一筆工單模板",
        "第二筆已更新模板",
        "第三筆例行模板",
    ]

    # Move index 2 up (-1) -> swaps index 2 and index 1
    new_idx = repo.move_template(2, -1)
    assert new_idx == 1
    assert [t["title"] for t in repo.load_templates()] == [
        "第一筆工單模板",
        "第三筆例行模板",
        "第二筆已更新模板",
    ]

    # Out-of-bounds move at top (index 0, direction -1) is a safe no-op
    assert repo.move_template(0, -1) == 0

    # Delete index 0
    deleted = repo.delete_template(0)
    assert deleted["title"] == "第一筆工單模板"
    assert len(repo.load_templates()) == 2

    # Ensure no leftover .tmp file exists after atomic saves
    tmp_file = Path(f"{repo.template_path}.tmp")
    assert not tmp_file.exists()


def test_find_first_placeholder_marker_priority_and_cursor_index() -> None:
    """Verify '__' placeholder detection prioritizes email over title and calculates exact cursor offset."""
    # 1. Both email and title have '__' -> email wins
    both = {
        "email": "emp__@enterprise.local",
        "title": "IT-__ 工作站記憶體升級",
    }
    target1 = find_first_placeholder_marker(both)
    assert target1.field == "email"
    assert target1.found_marker is True
    assert target1.cursor_index == 3
    assert target1.cleaned_text == "emp@enterprise.local"

    # Tuple unpacking compatibility
    field, cursor_idx, cleaned_text = target1
    assert (field, cursor_idx, cleaned_text) == ("email", 3, "emp@enterprise.local")

    # 2. Only title has '__' (e.g. "IT__工作站記憶體升級" or "__機房例行巡檢")
    title_only = {
        "email": "alex.chen@enterprise.local",
        "title": "IT__工作站記憶體升級",
    }
    target2 = find_first_placeholder_marker(title_only)
    assert target2.field == "title"
    assert target2.found_marker is True
    assert target2.cursor_index == 2
    assert target2.cleaned_text == "IT工作站記憶體升級"

    leading_marker = {
        "email": "alex.chen@enterprise.local",
        "title": "__機房例行巡檢",
    }
    target3 = find_first_placeholder_marker(leading_marker)
    assert target3.field == "title"
    assert target3.found_marker is True
    assert target3.cursor_index == 0
    assert target3.cleaned_text == "機房例行巡檢"

    # 3. Multiple '__' in same field -> only first '__' is removed
    multi_marker = {
        "email": "alex.chen@enterprise.local",
        "title": "申請單__設備__配發",
    }
    target4 = find_first_placeholder_marker(multi_marker)
    assert target4.field == "title"
    assert target4.cursor_index == 3
    assert target4.cleaned_text == "申請單設備__配發"

    # 4. No '__' marker -> fallback to end of title
    no_marker = {
        "email": "alex.chen@enterprise.local",
        "title": "VPN 連線異常排除",
    }
    target5 = find_first_placeholder_marker(no_marker)
    assert target5.field == "title"
    assert target5.found_marker is False
    assert target5.cursor_index == len("VPN 連線異常排除")
    assert target5.cleaned_text == "VPN 連線異常排除"


def test_caller_id_parsing_and_sandbox_directory_api() -> None:
    """Verify incoming call title matching, caller number extraction, and /api/directory lookup."""
    assert is_incoming_call_window_title("Incoming Call - 來電通知 (50211)") is True
    assert is_incoming_call_window_title("來電自 50212") is True
    assert is_incoming_call_window_title("IT RPA Suite") is False

    assert parse_caller_text(["Incoming Call - 來電通知 (50211)"]) == "50211"
    assert parse_caller_text(["Incoming Call from 50213"]) == "50213"
    assert parse_caller_text(["來電自 EMP104"]) == "EMP104"

    server = MockEnterpriseServer(preferred_port=8014)
    base_url = server.start()
    try:
        info = lookup_caller_directory(base_url, "50211")
        assert info["emp_id"] == "EMP101"
        assert "陳建宏" in info["name"]
        assert info["dept"] == "雲端基礎架構部"
        assert info["location"] == "HQ-8F-A12"
    finally:
        server.stop()


def test_batch_tickets_end_to_end_playwright(tmp_path: Path) -> None:
    """Verify end-to-end Playwright execution for Incident Request & Routine Task tickets."""
    storage = AppStorage(base_dir=tmp_path)
    server = MockEnterpriseServer(preferred_port=8015)
    base_url = server.start()
    worker = AutomationWorker(headless=True)

    prepared_templates = [
        {
            "category": "Incident Request",
            "email": "alex.chen@enterprise.local",
            "title": "IT-100001 工作站記憶體升級與硬體檢測",
            "type": "Hardware",
            "sub_type": "RAM / Storage Upgrade",
            "corp": "Enterprise-HQ",
            "resolve": "已完成記憶體擴充與穩定度燒機測試。",
            "_ui_group": "電腦相關",
        },
        {
            "category": "Routine Task",
            "email": "brian.wang@enterprise.local",
            "title": "核心機房例行巡檢與溫溼度紀錄",
            "type": "Data Center Inspection",
            "sub_type": "",
            "corp": "",
            "resolve": "完成核心機房溫溼度、UPS 負載與空調查核。",
            "_ui_group": "例行事項",
        },
    ]

    try:
        worker.start()
        future = worker.submit(
            run_batch_tickets,
            prepared_templates,
            base_url,
            None,
            storage,
        )
        result = future.result(timeout=35)
        assert result.is_success is True
        assert result.data["completed_count"] == 2

        stats = storage.get_usage_stats()
        assert stats["this_month_tickets"] == 2
        # 1 * incident_ticket (3.0) + 1 * routine_ticket (3.0) = 6.0
        assert stats["this_month_saved_minutes"] == 6
    finally:
        worker.shutdown(wait=True, timeout=10)
        server.stop()


def test_runtime_dialog_placeholder_focus_and_mock_call_uia_detection(
    tmp_path: Path,
    tk_root: tk.Tk,
) -> None:
    """Verify GUI RuntimeTicketConfirmDialog '__' caret placement and pywinauto mock call detection."""
    from it_rpa_suite.adapters.paths import get_app_paths
    from it_rpa_suite.features.caller_id.monitor import (
        CallerIdMonitor,
        show_caller_toast,
        spawn_mock_incoming_call,
    )
    from it_rpa_suite.features.ticket_helper.view import (
        RuntimeTicketConfirmDialog,
    )

    paths = get_app_paths(base_dir=tmp_path)
    repo = TemplateRepository(paths=paths)

    root = tk_root
    root.withdraw()

    # 1. Test RuntimeTicketConfirmDialog '__' focus in title ("IT__工作站記憶體升級")
    dlg = RuntimeTicketConfirmDialog(
        root,
        template={
            "category": "Incident Request",
            "email": "alex.chen@enterprise.local",
            "title": "IT__工作站記憶體升級",
            "type": "Hardware",
            "sub_type": "RAM / Storage Upgrade",
            "corp": "Enterprise-HQ",
            "resolve": "完成升級。",
            "_ui_group": "電腦相關",
        },
        template_number=1,
        total_count=2,
        repository=repo,
    )
    root.update_idletasks()
    target = dlg._focus_runtime_placeholder()
    assert target.field == "title"
    assert target.cursor_index == 2
    assert dlg.title_var.get() == "IT工作站記憶體升級"
    assert int(dlg.title_entry.index(tk.INSERT)) == 2
    dlg.destroy()

    # 2. Test spawn_mock_incoming_call + pywinauto UIA window detection + CallerToast
    default_mock_win = spawn_mock_incoming_call(root, auto_close_ms=5000)
    root.update_idletasks()
    default_labels = [
        str(widget.cget("text"))
        for frame in default_mock_win.winfo_children()
        for widget in frame.winfo_children()
        if isinstance(widget, tk.Label)
    ]
    assert len(default_labels) == 3
    assert default_labels[1].startswith("Incoming Call from ")
    default_ext = default_labels[1].removeprefix("Incoming Call from ")
    assert default_labels[2] == f"來電自 {default_ext}"
    assert all("沙盒對應" not in text for text in default_labels)
    default_mock_win.destroy()

    mock_win = spawn_mock_incoming_call(root, caller_ext="50212", auto_close_ms=5000)
    root.update_idletasks()
    mock_win.update()
    mock_labels = [
        str(widget.cget("text"))
        for frame in mock_win.winfo_children()
        for widget in frame.winfo_children()
        if isinstance(widget, tk.Label)
    ]
    assert "來電自 50212" in mock_labels
    assert all("沙盒對應" not in text for text in mock_labels)

    monitor = CallerIdMonitor(root=root, enabled=True)
    detected = monitor._scan_incoming_call_window()
    assert detected is not None
    assert detected[1] == "50212"

    toast = show_caller_toast(
        root,
        {
            "emp_id": "EMP102",
            "name": "林雅婷 (Irene Lin)",
            "dept": "數位產品研發部",
            "title": "資深前端工程師",
            "ext": "50212",
            "location": "HQ-6F-B08",
            "manager": "張家豪 (EMP002)",
        },
        raw_query="50212",
        duration_ms=2000,
    )
    root.update_idletasks()
    assert toast.winfo_exists()
    toast.destroy()
    mock_win.destroy()


def _collect_widget_texts(root: tk.Misc) -> list[str]:
    texts: list[str] = []
    for child in root.winfo_children():
        try:
            text = str(child.cget("text"))
        except tk.TclError:
            text = ""
        if text:
            texts.append(text)
        texts.extend(_collect_widget_texts(child))
    return texts


def test_ticket_template_dialog_create_edit_and_copy_modes(
    tmp_path: Path,
    tk_root: tk.Tk,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify TicketTemplateDialog distinguishes add mode from edit/copy modes."""
    from unittest.mock import MagicMock

    from it_rpa_suite.features.ticket_helper.view import (
        TicketHelperView,
        TicketTemplateDialog,
    )

    paths = get_app_paths(base_dir=tmp_path)
    repo = TemplateRepository(paths=paths)
    existing_template = {
        "category": "Incident Request",
        "email": "alex.chen@enterprise.local",
        "title": "VPN 連線異常排除",
        "type": "Network",
        "sub_type": "VPN Client Access",
        "corp": "Enterprise-HQ",
        "resolve": "已重設憑證並確認連線正常。",
        "_ui_group": "電腦相關",
    }

    tk_root.withdraw()

    # 1. Create mode via default_group
    add_dlg = TicketTemplateDialog(tk_root, default_group="電腦相關", repository=repo)
    tk_root.update_idletasks()
    add_texts = _collect_widget_texts(add_dlg)
    assert add_dlg.is_edit_mode is False
    assert add_dlg.title() == "新增工單模板"
    assert "建立新工單模板" in add_texts
    assert "刪除模板" not in add_texts
    assert add_dlg.template_group_var.get() == "電腦相關"
    add_dlg.destroy()

    # 2. Create mode even if caller passes metadata-only {"_ui_group": ...}
    meta_only_dlg = TicketTemplateDialog(
        tk_root,
        template={"_ui_group": "開給同仁"},
        repository=repo,
    )
    tk_root.update_idletasks()
    meta_only_texts = _collect_widget_texts(meta_only_dlg)
    assert meta_only_dlg.is_edit_mode is False
    assert meta_only_dlg.title() == "新增工單模板"
    assert "建立新工單模板" in meta_only_texts
    assert "刪除模板" not in meta_only_texts
    assert meta_only_dlg.template_group_var.get() == "開給同仁"
    meta_only_dlg.destroy()

    # 3. Edit mode for existing template
    edit_dlg = TicketTemplateDialog(tk_root, template=existing_template, repository=repo)
    tk_root.update_idletasks()
    edit_texts = _collect_widget_texts(edit_dlg)
    assert edit_dlg.is_edit_mode is True
    assert edit_dlg.title() == "編輯工單模板"
    assert "編輯工單模板" in edit_texts
    assert "刪除模板" in edit_texts
    edit_dlg.destroy()

    # 4. Copy mode hides delete button and shows copy title
    copy_dlg = TicketTemplateDialog(
        tk_root,
        template=existing_template,
        copy_mode=True,
        repository=repo,
    )
    tk_root.update_idletasks()
    copy_texts = _collect_widget_texts(copy_dlg)
    assert copy_dlg.is_edit_mode is False
    assert copy_dlg.title() == "複製工單模板"
    assert "複製工單模板" in copy_texts
    assert "刪除模板" not in copy_texts
    copy_dlg.destroy()

    # 5. TicketHelperView._add_template opens add mode with active_group pre-selected
    mock_app = MagicMock()
    mock_app.scale_factor = 1.0
    mock_app.colors = {}
    mock_app.paths = paths
    view = TicketHelperView(tk_root, mock_app, repository=repo)
    view._select_group("開給同仁")

    captured_title: str | None = None
    captured_is_edit_mode: bool | None = None
    captured_group: str | None = None
    captured_texts: list[str] = []

    def _capture_and_close(dialog: tk.Misc | None = None) -> None:
        nonlocal captured_title, captured_is_edit_mode, captured_group, captured_texts
        assert isinstance(dialog, TicketTemplateDialog)
        tk_root.update_idletasks()
        captured_title = dialog.title()
        captured_is_edit_mode = dialog.is_edit_mode
        captured_group = dialog.template_group_var.get()
        captured_texts = _collect_widget_texts(dialog)
        dialog.destroy()

    monkeypatch.setattr(view, "wait_window", _capture_and_close)
    view._add_template()
    assert captured_title == "新增工單模板"
    assert captured_is_edit_mode is False
    assert captured_group == "開給同仁"
    assert "建立新工單模板" in captured_texts
    assert "刪除模板" not in captured_texts
    view.destroy()

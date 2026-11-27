# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller onedir specification for IT RPA Suite (src/ layout)."""

from pathlib import Path
import sys

from PyInstaller.utils.hooks import collect_submodules

spec_dir = Path(SPECPATH).resolve()
project_dir = spec_dir.parent if spec_dir.name.casefold() == "scripts" else spec_dir
src_dir = project_dir / "src"
main_file = src_dir / "it_rpa_suite" / "__main__.py"

if not main_file.is_file():
    raise FileNotFoundError(
        f"找不到主程式入口：{main_file}\n"
        f"請確認專案目錄結構是否完整。"
    )

# ---------------------------------------------------------
# 必要靜態資源與工具檔案檢查
# ---------------------------------------------------------
required_files = [
    project_dir / "assets" / "default_settings.json",
    project_dir / "assets" / "default_ticket_templates.json",
    project_dir / "assets" / "sample_borrow_report.xlsx",
    project_dir / "assets" / "sample_form_audit_report.xlsx",
    project_dir / "assets" / "icons" / "Icon.ico",
    project_dir / "assets" / "icons" / "corner_icon.png",
    project_dir / "assets" / "icons" / "moon.png",
    project_dir / "assets" / "icons" / "sun.png",
    project_dir / "tools" / "tool_sdk.py",
    project_dir / "tools" / "_tool_template.py",
    project_dir / "tools" / "ext_provision_demo.py",
    project_dir / "tools" / "async_form_audit_demo.py",
    project_dir / "tools" / "updater" / "updater.py",
]

missing_files = [
    str(file_path)
    for file_path in required_files
    if not file_path.is_file()
]

if missing_files:
    raise FileNotFoundError(
        "以下打包必要檔案不存在：\n" + "\n".join(missing_files)
    )

sys.path.insert(0, str(src_dir))

# ---------------------------------------------------------
# 隱藏匯入 (Hidden Imports)
# ---------------------------------------------------------
hiddenimports = sorted(
    set(
        [
            *collect_submodules("it_rpa_suite"),
            # Excel (openpyxl)
            *collect_submodules("openpyxl"),
            # Windows COM / DPAPI
            "pythoncom",
            "pywintypes",
            "win32api",
            "win32con",
            "win32crypt",
            "win32gui",
            "win32com",
            "win32com.client",
            "win32com.server",
            "win32com.server.util",
            # Playwright
            "playwright",
            "playwright.async_api",
            "playwright.sync_api",
            "playwright._impl",
            "playwright._impl._driver",
            "playwright._impl._connection",
            "playwright._impl._browser",
            "playwright._impl._browser_context",
            "playwright._impl._page",
            # UI Automation (Caller ID)
            "pywinauto",
            "pywinauto.application",
            "pywinauto.controls",
            "pywinauto.controls.uiawrapper",
            "pywinauto.controls.win32_controls",
            "pywinauto.findwindows",
            "pywinauto.timings",
        ]
    )
)

# 若已預先編譯 tools/updater/updater.exe，則直接打入 _internal/updater.exe
updater_exe_path = project_dir / "tools" / "updater" / "updater.exe"
binaries = []
if updater_exe_path.is_file():
    binaries.append((str(updater_exe_path), "."))

datas = [
    (str(project_dir / "assets" / "default_settings.json"), "assets"),
    (str(project_dir / "assets" / "default_ticket_templates.json"), "assets"),
    (str(project_dir / "assets" / "sample_borrow_report.xlsx"), "assets"),
    (str(project_dir / "assets" / "sample_form_audit_report.xlsx"), "assets"),
    (str(project_dir / "assets" / "icons" / "Icon.ico"), "assets/icons"),
    (str(project_dir / "assets" / "icons" / "corner_icon.png"), "assets/icons"),
    (str(project_dir / "assets" / "icons" / "moon.png"), "assets/icons"),
    (str(project_dir / "assets" / "icons" / "sun.png"), "assets/icons"),
    # 供首次啟動與三階段 Updater Stage 3 植入／同步至 tools/
    (str(project_dir / "tools" / "tool_sdk.py"), "tools"),
    (str(project_dir / "tools" / "_tool_template.py"), "tools"),
    (str(project_dir / "tools" / "ext_provision_demo.py"), "tools"),
    (str(project_dir / "tools" / "async_form_audit_demo.py"), "tools"),
    (str(project_dir / "tools" / "updater" / "updater.py"), "."),
]

a = Analysis(
    [str(main_file)],
    pathex=[str(src_dir)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    noarchive=True,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ITRPASuite",
    console=False,
    icon=str(project_dir / "assets" / "icons" / "Icon.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    upx=False,
    name="ITRPASuite",
)

# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- 導入 `uv`（`.python-version` + `uv.lock`）與 PEP 735 `[dependency-groups]` 現代套件管理。
- 補齊靜態品質閘門：Ruff（lint + format LF）、Mypy（全專案 0 錯誤）、Pytest markers 與 Coverage 基線門檻、`pip-audit` 依賴安全掃描。
- 新增跨平台換行與本機防護設定：`.gitattributes`、`.editorconfig`、`.pre-commit-config.yaml`、`.env.example`。
- 新增 GitHub Actions CI（`lint-and-format`、`typecheck`、`security-audit`、`tests`）與 Dependabot 自動更新配置。

## [0.6.0] - 2026-11-24

### Added
- **離線企業沙盒伺服器（Mock Server）**：內建多執行緒本機 HTTP Server，完整模擬資產、人事、電話簿、電信分機、NAC 與服務台 8 大企業系統端點，支援 100% 離線展示與端對端驗證。
- **核心業務模組**：
  - 設備短期／專案借用、歸還與跨系統保管人反查（支援 `IT-` / `EMP` 簡碼正規化與膠囊標籤清單）。
  - 新人到職標準出庫（依筆電／桌機首碼動態縮減表單）與員工離職跨系統查核。
  - NAC 老式雙層 `iframe` 網路存取控制單／雙網卡自動解鎖。
  - IT 服務台工單模板管理（五大分類、拖曳排序、`__` 佔位符自動聚焦批次開單）。
  - 背景來電即時身分識別（`pywinauto` UIA 監聽、企業目錄查詢與無邊框置頂懸浮通知）。
  - 自訂腳本工具箱與共用開發套件（`tools/tool_sdk.py`、電信分機自動選號範例腳本）。
- **基礎建設與打包發布**：
  - Playwright 專屬背景執行緒（`AutomationWorker`）、FIFO 序列化任務佇列與延遲啟動機制。
  - Outlook COM 郵件草稿自動組裝，並內建無 Classic Outlook 環境下的 `HTMLPreviewDialog` 安全降級預覽。
  - Windows DPAPI 本機加密憑證庫（`data/credentials.dat`）與設定檔原子寫入（Atomic Write）。
  - SQLite 量化效益儀表板、深淺色主題即時切換與 DPI 防抖動態視窗縮放。
  - PyInstaller 一鍵打包腳本（`build_release.bat` / `scripts/build_release.ps1`）與具備 Zip Slip 防護的三階段自動更新機制（`tools/updater/updater.py`）。
- **自動化測試**：建立 36 項單元、GUI 與 Playwright 端對端整合測試，涵蓋核心驗證邏輯、更新器安全防護與主要業務流程。

## [0.5.0] - Historical Milestone (ver5)

### Changed
- 由命令列轉型為 Tkinter / ttk 現代化 GUI 桌面應用程式，導入非同步任務架構與 SQLite 操作效益統計。

## [0.4.0] - Historical Milestone (ver4)

### Changed
- 進行前後端職責分離與模組化重構，以 Playwright 取代 Selenium 並導入外部工具箱擴充機制。

## [0.3.0] - Historical Milestone (ver3)

### Added
- 導入多人實務部署支援、自動發布更新機制、跨系統 Outlook 郵件草稿與 `pywinauto` 背景來電監聽。

## [0.2.0] - Historical Milestone (ver2)

### Changed
- 改善互動體驗與初始化流程，重構程式碼並調整打包發布方式以提升迭代效率。

## [0.1.0] - Historical Milestone (ver1)

### Added
- 建立命令列 MVP，完成資產借還、新人／離職作業與例行表單流程的概念驗證。

[Unreleased]: https://github.com/lanjztaipei/it-rpa-suite/compare/v0.6.0...HEAD
[0.6.0]: https://github.com/lanjztaipei/it-rpa-suite/releases/tag/v0.6.0

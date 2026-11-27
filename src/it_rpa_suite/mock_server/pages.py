"""Sandbox data store and HTML/JS page templates for simulated enterprise IT systems."""

from __future__ import annotations

import copy
import html
import json

INITIAL_EMPLOYEES: dict[str, dict[str, str]] = {
    "EMP101": {
        "emp_id": "EMP101",
        "name": "陳建宏 (Alex Chen)",
        "dept": "雲端基礎架構部",
        "title": "資深系統工程師",
        "ext": "50211",
        "email": "alex.chen@enterprise.local",
        "manager": "林志遠 (EMP001)",
        "manager_email": "zhiyuan.lin@enterprise.local",
        "location": "HQ-8F-A12",
    },
    "EMP102": {
        "emp_id": "EMP102",
        "name": "林雅婷 (Irene Lin)",
        "dept": "數位產品研發部",
        "title": "資深前端工程師",
        "ext": "50212",
        "email": "irene.lin@enterprise.local",
        "manager": "張家豪 (EMP002)",
        "manager_email": "jiahao.zhang@enterprise.local",
        "location": "HQ-6F-B08",
    },
    "EMP103": {
        "emp_id": "EMP103",
        "name": "王柏翰 (Brian Wang)",
        "dept": "資訊安全管理部",
        "title": "資安分析師",
        "ext": "50213",
        "email": "brian.wang@enterprise.local",
        "manager": "林志遠 (EMP001)",
        "manager_email": "zhiyuan.lin@enterprise.local",
        "location": "HQ-8F-C03",
    },
    "EMP104": {
        "emp_id": "EMP104",
        "name": "張心怡 (Claire Chang)",
        "dept": "企業應用服務部",
        "title": "系統分析師",
        "ext": "50214",
        "email": "claire.chang@enterprise.local",
        "manager": "張家豪 (EMP002)",
        "manager_email": "jiahao.zhang@enterprise.local",
        "location": "HQ-5F-A05",
    },
    "IT-STOCK": {
        "emp_id": "IT-STOCK",
        "name": "IT 設備庫房",
        "dept": "IT 維運服務台",
        "title": "設備庫房專責帳號",
        "ext": "50200",
        "email": "it.stock@enterprise.local",
        "manager": "IT Service Desk",
        "manager_email": "servicedesk@enterprise.local",
        "location": "HQ-B1-STOCK",
    },
}

INITIAL_ASSETS: dict[str, dict[str, str]] = {
    "IT-100001": {
        "tag": "IT-100001",
        "type": "Desktop",
        "model": "OptiPlex 7010 Tower",
        "holder": "EMP101",
        "location": "員工保管 (HQ-8F-A12)",
        "mac_wired": "00:1A:2B:10:00:01",
        "mac_wifi": "",
    },
    "IT-100002": {
        "tag": "IT-100002",
        "type": "Desktop",
        "model": "OptiPlex 7010 Tower",
        "holder": "IT-STOCK",
        "location": "IT 設備庫房",
        "mac_wired": "00:1A:2B:10:00:02",
        "mac_wifi": "",
    },
    "IT-200001": {
        "tag": "IT-200001",
        "type": "Monitor",
        "model": "UltraSharp 27 U2723QE",
        "holder": "EMP101",
        "location": "員工保管 (HQ-8F-A12)",
        "mac_wired": "",
        "mac_wifi": "",
    },
    "IT-200002": {
        "tag": "IT-200002",
        "type": "Monitor",
        "model": "UltraSharp 27 U2723QE",
        "holder": "IT-STOCK",
        "location": "IT 設備庫房",
        "mac_wired": "",
        "mac_wifi": "",
    },
    "IT-300001": {
        "tag": "IT-300001",
        "type": "Laptop",
        "model": "Latitude 7440 Ultralight",
        "holder": "EMP102",
        "location": "員工保管 (HQ-6F-B08)",
        "mac_wired": "00:1A:2B:30:00:01",
        "mac_wifi": "00:1A:2B:30:FF:01",
    },
    "IT-300002": {
        "tag": "IT-300002",
        "type": "Laptop",
        "model": "Latitude 7440 Ultralight",
        "holder": "IT-STOCK",
        "location": "IT 設備庫房",
        "mac_wired": "00:1A:2B:30:00:02",
        "mac_wifi": "00:1A:2B:30:FF:02",
    },
    "IT-300003": {
        "tag": "IT-300003",
        "type": "Laptop",
        "model": "Latitude 7440 Ultralight",
        "holder": "IT-STOCK",
        "location": "IT 設備庫房",
        "mac_wired": "00:1A:2B:30:00:03",
        "mac_wifi": "00:1A:2B:30:FF:03",
    },
    "IT-300004": {
        "tag": "IT-300004",
        "type": "Laptop",
        "model": "ThinkPad X1 Carbon Gen 11",
        "holder": "EMP103",
        "location": "員工保管 (HQ-8F-C03)",
        "mac_wired": "00:1A:2B:30:00:04",
        "mac_wifi": "00:1A:2B:30:FF:04",
    },
}

STANDARD_ACCESSORIES: dict[str, dict[str, str]] = {
    "ACC-MOUSE-USB": {
        "tag": "ACC-MOUSE-USB",
        "type": "Accessory",
        "model": "USB 光學滑鼠 (Standard Mouse)",
    },
    "ACC-HEADSET-USB": {
        "tag": "ACC-HEADSET-USB",
        "type": "Accessory",
        "model": "USB 雙耳降噪耳麥 (ENC Headset)",
    },
    "ACC-CABLE-CAT6": {
        "tag": "ACC-CABLE-CAT6",
        "type": "Accessory",
        "model": "Cat.6 網路跳線 5M (Ethernet Cable)",
    },
    "ACC-KEYBOARD-USB": {
        "tag": "ACC-KEYBOARD-USB",
        "type": "Accessory",
        "model": "標準 104 鍵 USB 鍵盤 (USB Keyboard)",
    },
    "ACC-PHONE-IP": {
        "tag": "ACC-PHONE-IP",
        "type": "Accessory",
        "model": "企業網路電話機 (IP Desk Phone)",
    },
}

INITIAL_EXTENSIONS: list[dict[str, str]] = [
    {
        "ext": "50200",
        "area_code": "502",
        "status": "Available",
        "emp_id": "",
        "emp_name": "",
        "dept": "IT 預留分機 (尾碼重複)",
        "phone_type": "Unassigned",
        "mac": "",
    },
    {
        "ext": "50211",
        "area_code": "502",
        "status": "Assigned",
        "emp_id": "EMP101",
        "emp_name": "陳建宏 (Alex Chen)",
        "dept": "雲端基礎架構部",
        "phone_type": "IP Desk Phone",
        "mac": "00:1A:2B:10:00:01",
    },
    {
        "ext": "50212",
        "area_code": "502",
        "status": "Assigned",
        "emp_id": "EMP102",
        "emp_name": "林雅婷 (Irene Lin)",
        "dept": "數位產品研發部",
        "phone_type": "Softphone",
        "mac": "",
    },
    {
        "ext": "50213",
        "area_code": "502",
        "status": "Assigned",
        "emp_id": "EMP103",
        "emp_name": "王柏翰 (Brian Wang)",
        "dept": "資訊安全管理部",
        "phone_type": "Softphone",
        "mac": "",
    },
    {
        "ext": "50214",
        "area_code": "502",
        "status": "Assigned",
        "emp_id": "EMP104",
        "emp_name": "張心怡 (Claire Chang)",
        "dept": "企業應用服務部",
        "phone_type": "IP Desk Phone",
        "mac": "00:1A:2B:10:00:02",
    },
    {
        "ext": "50222",
        "area_code": "502",
        "status": "Available",
        "emp_id": "",
        "emp_name": "",
        "dept": "待配發池 (尾碼重複)",
        "phone_type": "Unassigned",
        "mac": "",
    },
    {
        "ext": "50234",
        "area_code": "502",
        "status": "Available",
        "emp_id": "",
        "emp_name": "",
        "dept": "待配發池 (尾碼不重複)",
        "phone_type": "Unassigned",
        "mac": "",
    },
    {
        "ext": "50238",
        "area_code": "502",
        "status": "Available",
        "emp_id": "",
        "emp_name": "",
        "dept": "待配發池 (尾碼不重複)",
        "phone_type": "Unassigned",
        "mac": "",
    },
]

AUDIT_FORM_COUNT = 1000
_AUDIT_SITES = ("台中總部", "台北廠", "新北廠", "桃園廠", "台南廠", "高雄廠")
_AUDIT_APPLICANTS = (
    "EMP101 陳建宏",
    "EMP102 林雅婷",
    "EMP103 王柏翰",
    "EMP104 張心怡",
    "EMP105 周明德",
    "EMP106 黃佳穎",
    "EMP107 劉俊傑",
    "EMP108 許怡君",
    "EMP109 鄭雅文",
    "EMP110 謝冠宇",
    "EMP111 洪佩珊",
    "EMP112 蘇家豪",
)
_AUDIT_REQUEST_TYPES = (
    "VPN 遠端存取",
    "資料庫唯讀權限",
    "網段放行申請",
    "ERP 模組授權",
    "雲端帳號開通",
    "檔案伺服器權限",
)
_AUDIT_COMMENT_TEMPLATES = (
    "已確認直屬主管同意，待補簽資安連線切結書",
    "需指定對應 Schema 與到期日，已退請申請人補件",
    "跨 VLAN 測試需求已通過資安初審，排程變更中",
    "授權席次待系統管理者釋出後開通",
    "專案成本中心代碼待確認，已電聯窗口補登",
    "部門共享資料夾屬機密等級，轉請單位主管覆核",
    "外勤支援短期連線，MFA 裝置已完成綁定",
    "稽核報表查詢用途，預定本週五前完成授權",
    "新任窗口接替原權限，舊帳號同步排程停用",
    "產線量測機台對接 MES，等待廠務停機視窗套用",
    "已建置測試環境角色，待申請人確認登入正常",
    "專案結案移交資料夾，已開立唯讀權限供備查",
)


def _build_initial_audit_forms(count: int = AUDIT_FORM_COUNT) -> dict[str, dict[str, str]]:
    """Deterministically generate `count` desensitized overdue form records (`FRM-1001`..)."""
    forms: dict[str, dict[str, str]] = {}
    for idx in range(count):
        form_no = f"FRM-{1001 + idx}"
        req_type = _AUDIT_REQUEST_TYPES[idx % len(_AUDIT_REQUEST_TYPES)]
        comment_base = _AUDIT_COMMENT_TEMPLATES[idx % len(_AUDIT_COMMENT_TEMPLATES)]
        forms[form_no] = {
            "form_no": form_no,
            "site": _AUDIT_SITES[idx % len(_AUDIT_SITES)],
            "applicant": _AUDIT_APPLICANTS[idx % len(_AUDIT_APPLICANTS)],
            "days_overdue": str(4 + (idx % 12)),
            "request_type": req_type,
            "review_comment": f"[{form_no}] {comment_base}",
        }
    return forms


INITIAL_AUDIT_FORMS: dict[str, dict[str, str]] = _build_initial_audit_forms()


class SandboxState:
    """Thread-safe in-memory state container for the enterprise IT sandbox."""

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.employees: dict[str, dict[str, str]] = copy.deepcopy(INITIAL_EMPLOYEES)
        self.assets: dict[str, dict[str, str]] = copy.deepcopy(INITIAL_ASSETS)
        self.accessories: dict[str, dict[str, str]] = copy.deepcopy(STANDARD_ACCESSORIES)
        self.extensions: list[dict[str, str]] = copy.deepcopy(INITIAL_EXTENSIONS)
        self.audit_forms: dict[str, dict[str, str]] = copy.deepcopy(INITIAL_AUDIT_FORMS)
        self.nac_policies: dict[str, str] = {}

    def query_directory(self, keyword: str) -> list[dict[str, str]]:
        q = (keyword or "").strip().lower()
        results: list[dict[str, str]] = []
        for emp in self.employees.values():
            ext_val = str(emp.get("ext", "")).lower()
            matched = not q or any(
                q in str(emp.get(field, "")).lower()
                for field in (
                    "emp_id",
                    "name",
                    "dept",
                    "title",
                    "ext",
                    "email",
                    "manager",
                    "location",
                )
            )
            if not matched and ext_val and ext_val in q:
                matched = True
            if matched:
                results.append(emp)
        return results


BASE_CSS = """
:root {
  --primary: #2563eb;
  --primary-dark: #1d4ed8;
  --success: #16a34a;
  --warning: #d97706;
  --danger: #dc2626;
  --surface: #ffffff;
  --bg: #f1f5f9;
  --text: #0f172a;
  --muted: #64748b;
  --border: #cbd5e1;
  font-family: "Microsoft JhengHei UI", "Segoe UI", system-ui, sans-serif;
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--text); }
header {
  background: linear-gradient(135deg, #0f172a 0%, #1e3a8a 100%);
  color: #fff; padding: 20px 32px;
  display: flex; align-items: center; justify-content: space-between;
}
header h1 { margin: 0; font-size: 20px; font-weight: 700; }
header p { margin: 4px 0 0; font-size: 13px; opacity: 0.85; }
header a.nav-home {
  color: #fff; text-decoration: none; font-size: 13px;
  border: 1px solid rgba(255,255,255,0.3); padding: 6px 14px; border-radius: 6px;
}
main { max-width: 1120px; margin: 24px auto; padding: 0 20px 48px; }
.card {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 12px; padding: 22px 24px; margin-bottom: 20px;
  box-shadow: 0 1px 3px rgba(15,23,42,0.06);
}
.card h2 { margin: 0 0 14px; font-size: 17px; }
.grid-2 { display: grid; grid-template-columns: repeat(2, 1fr); gap: 14px; }
.grid-3 { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; }
.grid-4 { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
label { display: block; font-size: 13px; font-weight: 600; margin-bottom: 6px; color: #334155; }
input[type="text"], input[type="password"], select {
  width: 100%; height: 40px; border: 1px solid var(--border);
  border-radius: 8px; padding: 6px 12px; font-size: 14px; background: #fff;
}
button, .btn {
  display: inline-flex; align-items: center; justify-content: center;
  height: 40px; padding: 0 18px; border-radius: 8px; border: none;
  background: var(--primary); color: #fff; font-weight: 600; font-size: 14px;
  cursor: pointer; text-decoration: none;
}
button:hover, .btn:hover { background: var(--primary-dark); }
button.secondary { background: #475569; }
button.success { background: var(--success); }
button.danger { background: var(--danger); height: 32px; padding: 0 12px; font-size: 12px; }
table { width: 100%; border-collapse: collapse; margin-top: 12px; }
th, td { padding: 10px 12px; border-bottom: 1px solid #e2e8f0; text-align: left; font-size: 13.5px; }
th { background: #f8fafc; color: var(--muted); font-weight: 700; font-size: 12px; text-transform: uppercase; }
.badge {
  display: inline-block; padding: 3px 10px; border-radius: 99px;
  font-size: 12px; font-weight: 600; background: #dbeafe; color: #1e40af;
}
.status-banner {
  margin-top: 14px; padding: 12px 16px; border-radius: 8px;
  border-left: 4px solid var(--success); background: #f0fdf4; color: #166534; font-weight: 600;
}
.hidden { display: none !important; }
/* Custom Searchable Select */
.searchable-select-container { position: relative; }
.searchable-select-trigger {
  display: flex; align-items: center; justify-content: space-between;
  height: 40px; padding: 0 12px; border: 1px solid var(--border);
  border-radius: 8px; background: #fff; cursor: pointer; font-size: 14px; color: #0f172a;
}
.searchable-select-trigger:hover { border-color: var(--primary); }
.searchable-select-dropdown {
  position: absolute; top: 44px; left: 0; right: 0; z-index: 50;
  background: #fff; border: 1px solid var(--primary); border-radius: 8px;
  padding: 8px; box-shadow: 0 10px 25px rgba(15,23,42,0.12);
}
.searchable-select-list {
  max-height: 180px; overflow-y: auto; margin-top: 6px; padding: 0; list-style: none;
}
.searchable-select-item {
  padding: 8px 10px; border-radius: 6px; cursor: pointer; font-size: 13px;
}
.searchable-select-item:hover { background: #eff6ff; color: var(--primary); }
"""


def _render_layout(title: str, subtitle: str, body_html: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
  <meta charset="utf-8" />
  <title>{html.escape(title)} - Enterprise IT Sandbox</title>
  <style>{BASE_CSS}</style>
</head>
<body>
  <header>
    <div>
      <h1>{html.escape(title)}</h1>
      <p>{html.escape(subtitle)}</p>
    </div>
    <a class="nav-home" href="/">返回沙盒首頁</a>
  </header>
  <main>
    {body_html}
  </main>
</body>
</html>"""


def _render_portal_login_gate(is_authenticated: bool, workspace_html: str) -> str:
    """Wrap portal workspace with an inline login gate when portal_auth=1 cookie is absent."""
    login_hidden = "hidden" if is_authenticated else ""
    workspace_hidden = "" if is_authenticated else "hidden"
    return f"""
    <div id="login-box" class="card {login_hidden}" style="max-width: 460px; margin: 28px auto;">
      <h2>Enterprise IT Portal 系統登入</h2>
      <p style="color: var(--muted); font-size: 13px; margin-bottom: 16px;">
        請輸入企業入口網工程師帳號密碼以存取資產管理系統（沙盒測試可輸入任意非空帳密）。
      </p>
      <div style="margin-bottom: 12px;">
        <label for="login-username">帳號 (Username)</label>
        <input id="login-username" type="text" placeholder="例如 it.admin" />
      </div>
      <div style="margin-bottom: 16px;">
        <label for="login-password">密碼 (Password)</label>
        <input id="login-password" type="password" placeholder="輸入密碼" />
      </div>
      <button id="btn-login" type="button" style="width: 100%;">登入系統</button>
    </div>

    <div id="portal-workspace" class="{workspace_hidden}">
      {workspace_html}
    </div>

    <script>
      (function() {{
        const loginBox = document.getElementById('login-box');
        const workspace = document.getElementById('portal-workspace');
        const btnLogin = document.getElementById('btn-login');
        if (document.cookie.includes('portal_auth=1')) {{
          loginBox.classList.add('hidden');
          workspace.classList.remove('hidden');
        }}
        if (btnLogin) {{
          btnLogin.addEventListener('click', function() {{
            const u = document.getElementById('login-username').value.trim();
            const p = document.getElementById('login-password').value.trim();
            if (!u || !p) {{
              alert('請輸入帳號與密碼');
              return;
            }}
            document.cookie = 'portal_auth=1; path=/';
            loginBox.classList.add('hidden');
            workspace.classList.remove('hidden');
          }});
        }}
      }})();
    </script>
    """


def render_home_page(state: SandboxState) -> str:
    asset_rows = "".join(
        f"<tr><td><strong>{a['tag']}</strong></td><td>{a['type']}</td>"
        f"<td>{a['model']}</td><td>{a['holder']}</td><td>{a['location']}</td>"
        f"<td><code>{a['mac_wired'] or '-'}</code></td><td><code>{a['mac_wifi'] or '-'}</code></td></tr>"
        for a in state.assets.values()
    )
    emp_rows = "".join(
        f"<tr><td><strong>{e['emp_id']}</strong></td><td>{e['name']}</td>"
        f"<td>{e['dept']}</td><td>{e['title']}</td><td><code>{e['ext']}</code></td>"
        f"<td>{e['location']}</td></tr>"
        for e in state.employees.values()
    )
    body = f"""
    <div class="card">
      <h2>模擬企業內部系統入口 (Offline Enterprise Sandbox)</h2>
      <div class="grid-3">
        <a class="btn" href="/portal/assets/issue">1. 資產借用與配發 (/portal/assets/issue)</a>
        <a class="btn" href="/portal/assets/return">2. 資產歸還系統 (/portal/assets/return)</a>
        <a class="btn" href="/portal/assets/search">3. 資產編號查詢 (/portal/assets/search)</a>
        <a class="btn secondary" href="/portal/directory">4. 企業通訊錄 (/portal/directory)</a>
        <a class="btn secondary" href="/portal/hr/offboarding">5. HR 離職清點 (/portal/hr/offboarding)</a>
        <a class="btn secondary" href="/portal/telecom/extensions">6. 電信分機管理 (/portal/telecom/extensions)</a>
        <a class="btn secondary" href="/network/console">7. 網管控制台 (/network/console)</a>
        <a class="btn secondary" href="/servicedesk/new?template=incident">8. IT 服務台開單 (/servicedesk/new)</a>
        <a class="btn secondary" href="/portal/reports/borrow-overdue">9. 逾期借用報表中心 (/portal/reports/borrow-overdue)</a>
        <a class="btn secondary" href="/portal/forms/login">10. 簽核表單查詢中心 (/portal/forms/login)</a>
      </div>
    </div>
    <div class="card">
      <h2>沙盒預設資產清單 (Assets)</h2>
      <table>
        <thead>
          <tr><th>資產編號</th><th>類型</th><th>型號</th><th>目前保管人</th><th>位置</th><th>Wired MAC</th><th>Wi-Fi MAC</th></tr>
        </thead>
        <tbody>{asset_rows}</tbody>
      </table>
    </div>
    <div class="card">
      <h2>沙盒預設員工通訊錄 (Directory)</h2>
      <table>
        <thead>
          <tr><th>工號</th><th>姓名</th><th>部門</th><th>職稱</th><th>分機</th><th>座位</th></tr>
        </thead>
        <tbody>{emp_rows}</tbody>
      </table>
    </div>
    """
    return _render_layout("Enterprise IT Sandbox", "本機離線自動化測試沙盒伺服器", body)


def render_asset_issue_page(state: SandboxState, is_authenticated: bool) -> str:
    employees_json = json.dumps(list(state.employees.values()), ensure_ascii=False)
    merged_catalog = {**state.accessories, **state.assets}
    assets_json = json.dumps(merged_catalog, ensure_ascii=False)

    workspace = f"""
    <div class="card">
      <h2>資產出庫、借用與新人配發作業 (Asset Issue & Loan)</h2>
      <div class="grid-3" style="align-items: end;">
        <div>
          <label for="select-issue-purpose">作業目的 (Movement Purpose)</label>
          <select id="select-issue-purpose">
            <option value="Short Term Loan">Short Term Loan</option>
            <option value="Project Loan">Project Loan</option>
            <option value="New Hire Assignment">New Hire Assignment</option>
          </select>
        </div>
        <div>
          <label for="input-request-no">申請單號 (Request No.)</label>
          <input id="input-request-no" type="text" placeholder="專案借用或入職單號 (例如 260101)" />
        </div>
        <div>
          <button id="btn-load-purpose" type="button" style="width: 100%;">載入表單設定 (Load Data)</button>
        </div>
      </div>
      <div id="purpose-loaded-banner" class="status-banner hidden"></div>
    </div>

    <div class="card">
      <h2>新增異動設備明細</h2>
      <div class="grid-4" style="align-items: end;">
        <div class="searchable-select-container">
          <label>借用人 / 保管員工 (Custodian)</label>
          <input id="selected-borrower-id" type="hidden" value="" />
          <div id="borrower-select-trigger" class="searchable-select-trigger">
            <span id="borrower-select-label">點擊搜尋並選擇員工工號...</span>
            <span>▾</span>
          </div>
          <div id="borrower-select-dropdown" class="searchable-select-dropdown hidden">
            <input id="borrower-select-input" class="searchable-select-input" type="text" placeholder="輸入工號或姓名按 Enter (如 EMP101)" />
            <ul id="borrower-select-list" class="searchable-select-list"></ul>
          </div>
        </div>

        <div>
          <label for="input-asset-tag">資產編號 (Asset Tag)</label>
          <div style="display: flex; gap: 6px;">
            <input id="input-asset-tag" type="text" placeholder="例如 IT-300002" />
            <button id="btn-search-asset" type="button" class="secondary" style="white-space: nowrap;">查詢</button>
          </div>
        </div>

        <div>
          <label for="select-usage-type">使用性質 (Usage Type)</label>
          <select id="select-usage-type">
            <option value="Loan">Loan</option>
            <option value="Assign">Assign</option>
          </select>
        </div>

        <div>
          <button id="btn-add-asset-row" type="button" class="success" style="width: 100%;">加入設備清單 (Add)</button>
        </div>
      </div>
      <div id="asset-lookup-hint" style="margin-top: 10px; font-size: 13px; color: var(--muted);"></div>

      <table id="movement-table">
        <thead>
          <tr>
            <th>#</th>
            <th>資產編號 / 品項</th>
            <th>設備類型</th>
            <th>借用人工號</th>
            <th>性質</th>
            <th>電腦名稱 (Hostname)</th>
            <th>網路區域 (Network)</th>
            <th>端點防護 (EDR)</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody id="movement-items-body"></tbody>
      </table>

      <div style="margin-top: 18px; display: flex; justify-content: flex-end; gap: 12px;">
        <button id="btn-submit-issue" type="button">確認送出借用/配發單</button>
      </div>
      <div id="issue-submit-banner" class="status-banner hidden"></div>
    </div>

    <script>
      const EMPLOYEES = {employees_json};
      const ASSETS = {assets_json};
      let movementRows = [];
      let activeBorrowerId = '';

      const trigger = document.getElementById('borrower-select-trigger');
      const dropdown = document.getElementById('borrower-select-dropdown');
      const searchInput = document.getElementById('borrower-select-input');
      const listEl = document.getElementById('borrower-select-list');
      const labelEl = document.getElementById('borrower-select-label');
      const hiddenBorrower = document.getElementById('selected-borrower-id');

      function selectBorrower(emp) {{
        activeBorrowerId = emp.emp_id;
        hiddenBorrower.value = emp.emp_id;
        labelEl.textContent = emp.emp_id + ' - ' + emp.name;
        dropdown.classList.add('hidden');
      }}

      function renderEmployeeList(filterText) {{
        const q = (filterText || '').trim().toUpperCase();
        listEl.innerHTML = '';
        const matches = EMPLOYEES.filter(e =>
          !q || e.emp_id.toUpperCase().includes(q) || e.name.toUpperCase().includes(q)
        );
        matches.forEach(emp => {{
          const li = document.createElement('li');
          li.className = 'searchable-select-item';
          li.textContent = emp.emp_id + ' — ' + emp.name + ' (' + emp.dept + ')';
          li.addEventListener('click', () => selectBorrower(emp));
          listEl.appendChild(li);
        }});
        return matches;
      }}

      trigger.addEventListener('click', () => {{
        dropdown.classList.toggle('hidden');
        if (!dropdown.classList.contains('hidden')) {{
          searchInput.value = '';
          renderEmployeeList('');
          searchInput.focus();
        }}
      }});

      searchInput.addEventListener('input', () => renderEmployeeList(searchInput.value));
      searchInput.addEventListener('keydown', (e) => {{
        if (e.key === 'Enter') {{
          e.preventDefault();
          const matches = renderEmployeeList(searchInput.value);
          if (matches.length > 0) {{
            selectBorrower(matches[0]);
          }} else if (searchInput.value.trim()) {{
            const raw = searchInput.value.trim().toUpperCase();
            selectBorrower({{ emp_id: raw, name: '指定員工 (' + raw + ')' }});
          }}
        }}
      }});

      function renderMovementTable() {{
        const tbody = document.getElementById('movement-items-body');
        tbody.innerHTML = '';
        movementRows.forEach((row, idx) => {{
          const tr = document.createElement('tr');
          const isComputer = row.tag.startsWith('IT-1') || row.tag.startsWith('IT-3');
          const hostHtml = isComputer
            ? `<input id="input-hostname-${{idx}}" type="text" value="${{row.hostname || ''}}" placeholder="輸入電腦名稱" />`
            : `<span style="color:var(--muted)">不適用</span>`;
          const netHtml = isComputer
            ? `<select id="select-network-zone-${{idx}}">
                 <option value="">請選擇</option>
                 <option value="Corporate-LAN" ${{row.network === 'Corporate-LAN' ? 'selected' : ''}}>Corporate-LAN</option>
                 <option value="Lab-VLAN" ${{row.network === 'Lab-VLAN' ? 'selected' : ''}}>Lab-VLAN</option>
               </select>`
            : `<span style="color:var(--muted)">-</span>`;
          const edrHtml = isComputer
            ? `<select id="select-endpoint-edr-${{idx}}">
                 <option value="">請選擇</option>
                 <option value="Enabled" ${{row.edr === 'Enabled' ? 'selected' : ''}}>Enabled</option>
                 <option value="Exempt" ${{row.edr === 'Exempt' ? 'selected' : ''}}>Exempt</option>
               </select>`
            : `<span style="color:var(--muted)">-</span>`;

          tr.innerHTML = `
            <td>${{idx + 1}}</td>
            <td><strong>${{row.tag}}</strong> <span style="color:var(--muted);font-size:12px;">${{row.model}}</span></td>
            <td><span class="badge">${{row.type}}</span></td>
            <td>${{row.borrower}}</td>
            <td>${{row.usageType}}</td>
            <td>${{hostHtml}}</td>
            <td>${{netHtml}}</td>
            <td>${{edrHtml}}</td>
            <td><button type="button" class="danger btn-remove-row" id="btn-remove-row-${{idx}}" data-idx="${{idx}}">刪除</button></td>
          `;
          tbody.appendChild(tr);

          if (isComputer) {{
            document.getElementById(`input-hostname-${{idx}}`).addEventListener('input', (ev) => {{
              movementRows[idx].hostname = ev.target.value;
            }});
            document.getElementById(`select-network-zone-${{idx}}`).addEventListener('change', (ev) => {{
              movementRows[idx].network = ev.target.value;
            }});
            document.getElementById(`select-endpoint-edr-${{idx}}`).addEventListener('change', (ev) => {{
              movementRows[idx].edr = ev.target.value;
            }});
          }}
        }});

        document.querySelectorAll('.btn-remove-row').forEach(btn => {{
          btn.addEventListener('click', () => {{
            const i = parseInt(btn.getAttribute('data-idx'), 10);
            movementRows.splice(i, 1);
            renderMovementTable();
          }});
        }});
      }}

      document.getElementById('btn-load-purpose').addEventListener('click', () => {{
        const purpose = document.getElementById('select-issue-purpose').value;
        const reqNo = document.getElementById('input-request-no').value.trim();
        const banner = document.getElementById('purpose-loaded-banner');
        movementRows = [];

        if (purpose === 'Project Loan' && reqNo) {{
          selectBorrower(EMPLOYEES[0]);
        }} else if (purpose === 'New Hire Assignment') {{
          selectBorrower(EMPLOYEES[1]);
          movementRows.push(
            {{ tag: 'ACC-DEFAULT-BAG', type: 'Accessory', model: '舊版預設公事包 (冗餘項目)', borrower: activeBorrowerId || 'EMP102', usageType: 'Assign' }},
            {{ tag: 'ACC-DEFAULT-LOCK', type: 'Accessory', model: '舊版預設電腦鎖 (冗餘項目)', borrower: activeBorrowerId || 'EMP102', usageType: 'Assign' }}
          );
        }}
        renderMovementTable();
        banner.textContent = `已載入「${{purpose}}」表單模式` + (reqNo ? `（單號：${{reqNo}}）` : '');
        banner.classList.remove('hidden');
      }});

      document.getElementById('btn-search-asset').addEventListener('click', () => {{
        const tag = document.getElementById('input-asset-tag').value.trim().toUpperCase();
        const hint = document.getElementById('asset-lookup-hint');
        const info = ASSETS[tag];
        if (info) {{
          hint.textContent = `已驗證資產：${{info.tag}} (${{info.type}} - ${{info.model}})，目前位置：${{info.location}}`;
        }} else if (tag) {{
          hint.textContent = `已驗證資產／配件：${{tag}}`;
        }}
      }});

      document.getElementById('btn-add-asset-row').addEventListener('click', () => {{
        const tag = document.getElementById('input-asset-tag').value.trim().toUpperCase();
        if (!tag) return;
        const usageType = document.getElementById('select-usage-type').value;
        const info = ASSETS[tag] || {{
          tag: tag,
          type: tag.startsWith('IT-1') ? 'Desktop' : (tag.startsWith('IT-3') ? 'Laptop' : (tag.startsWith('IT-2') ? 'Monitor' : 'Accessory')),
          model: 'Enterprise Standard Equipment'
        }};
        movementRows.push({{
          tag: tag,
          type: info.type,
          model: info.model,
          borrower: activeBorrowerId || 'EMP101',
          usageType: usageType,
          hostname: '',
          network: '',
          edr: ''
        }});
        document.getElementById('input-asset-tag').value = '';
        renderMovementTable();
      }});

      document.getElementById('btn-submit-issue').addEventListener('click', () => {{
        const submitBanner = document.getElementById('issue-submit-banner');
        submitBanner.textContent = `表單已成功送出！共處理 ${{movementRows.length}} 筆設備異動。`;
        submitBanner.classList.remove('hidden');
      }});
    </script>
    """
    return _render_layout(
        "Asset Portal — 設備借用與配發",
        "模擬企業資產管理系統 (/portal/assets/issue)",
        _render_portal_login_gate(is_authenticated, workspace),
    )


def render_asset_search_page(state: SandboxState, is_authenticated: bool) -> str:
    assets_json = json.dumps(state.assets, ensure_ascii=False)
    employees_json = json.dumps(state.employees, ensure_ascii=False)

    workspace = f"""
    <div class="card">
      <h2>企業資產主檔查詢 (Asset Master Query)</h2>
      <div style="display: flex; gap: 10px; max-width: 560px; align-items: end;">
        <div style="flex: 1;">
          <label for="input-search-tag">資產編號 (Asset Tag)</label>
          <input id="input-search-tag" type="text" placeholder="輸入資產編號 (例如 IT-300001)" />
        </div>
        <button id="btn-query-asset" type="button">查詢資產</button>
      </div>

      <table id="asset-search-results">
        <thead>
          <tr>
            <th>資產編號 (點擊開啟新分頁明細)</th>
            <th>設備類型</th>
            <th>型號</th>
            <th>目前保管人</th>
            <th>所在位置</th>
          </tr>
        </thead>
        <tbody id="asset-search-tbody"></tbody>
      </table>
    </div>

    <script>
      const ASSETS = {assets_json};
      const EMPLOYEES = {employees_json};

      function doQuery() {{
        const q = document.getElementById('input-search-tag').value.trim().toUpperCase();
        const tbody = document.getElementById('asset-search-tbody');
        tbody.innerHTML = '';
        const list = Object.values(ASSETS).filter(a => !q || a.tag.toUpperCase().includes(q));
        list.forEach((asset, idx) => {{
          const emp = EMPLOYEES[asset.holder] || {{ name: asset.holder }};
          const tr = document.createElement('tr');
          tr.innerHTML = `
            <td>
              <a id="asset-link-${{idx}}" href="/portal/assets/detail?tag=${{encodeURIComponent(asset.tag)}}" target="_blank" style="font-weight:700; color:var(--primary);">
                ${{asset.tag}}
              </a>
            </td>
            <td><span class="badge">${{asset.type}}</span></td>
            <td>${{asset.model}}</td>
            <td>${{asset.holder}} (${{emp.name}})</td>
            <td>${{asset.location}}</td>
          `;
          tbody.appendChild(tr);
        }});
      }}

      document.getElementById('btn-query-asset').addEventListener('click', doQuery);
      doQuery();
    </script>
    """
    return _render_layout(
        "Asset Portal — 資產主檔查詢",
        '點擊資產編號連結將以 target="_blank" 開啟跨分頁資產明細 (/portal/assets/search)',
        _render_portal_login_gate(is_authenticated, workspace),
    )


def render_asset_detail_page(state: SandboxState, tag: str) -> str:
    cleaned_tag = (tag or "IT-300001").strip().upper()
    asset = state.assets.get(
        cleaned_tag,
        {
            "tag": cleaned_tag,
            "type": "Laptop" if cleaned_tag.startswith("IT-3") else "Desktop",
            "model": "Enterprise Standard System",
            "holder": "EMP101",
            "location": "員工保管 (HQ-8F-A12)",
            "mac_wired": "00:1A:2B:99:00:01",
            "mac_wifi": "00:1A:2B:99:FF:01" if cleaned_tag.startswith("IT-3") else "",
        },
    )
    holder_id = asset["holder"]
    emp = state.employees.get(holder_id, {"name": holder_id, "dept": "IT", "ext": "50200"})

    body = f"""
    <div class="card">
      <h2>資產硬體與保管人明細 — <span id="detail-asset-tag">{html.escape(asset["tag"])}</span></h2>
      <div class="grid-2">
        <div>
          <label>目前保管人工號 (Custodian ID)</label>
          <div id="holder-emp-id" style="padding: 10px 12px; background: #f8fafc; border: 1px solid var(--border); border-radius: 8px; font-weight: 700;">{html.escape(holder_id)}</div>
        </div>
        <div>
          <label>保管人姓名與部門</label>
          <div id="holder-name" style="padding: 10px 12px; background: #f8fafc; border: 1px solid var(--border); border-radius: 8px;">{html.escape(emp.get("name", ""))} ({html.escape(emp.get("dept", ""))})</div>
        </div>
        <div>
          <label for="input-mac-wired">有線網卡實體位址 (Wired MAC Address)</label>
          <input id="input-mac-wired" type="text" value="{html.escape(asset.get("mac_wired", ""))}" readonly />
        </div>
        <div>
          <label for="input-mac-wifi">無線網卡實體位址 (Wi-Fi MAC Address)</label>
          <input id="input-mac-wifi" type="text" value="{html.escape(asset.get("mac_wifi", ""))}" readonly />
        </div>
      </div>
    </div>
    """
    return _render_layout(
        f"資產明細 {asset['tag']}",
        "Asset Detail Popup Tab (/portal/assets/detail)",
        body,
    )


def render_asset_return_page(state: SandboxState, is_authenticated: bool) -> str:
    employees_json = json.dumps(list(state.employees.values()), ensure_ascii=False)
    assets_json = json.dumps(list(state.assets.values()), ensure_ascii=False)
    accessories_json = json.dumps(state.accessories, ensure_ascii=False)

    workspace = f"""
    <div class="card">
      <h2>設備歸還與入庫點收作業 (Asset Return & Clearance)</h2>
      <div class="grid-4" style="align-items: end;">
        <div>
          <label for="select-return-purpose">歸還類別 (Return Purpose)</label>
          <select id="select-return-purpose">
            <option value="Loan Return">Loan Return</option>
            <option value="Offboarding Return">Offboarding Return</option>
          </select>
        </div>

        <div>
          <label for="input-return-req-no">關聯單號 (Request / Offboard No.)</label>
          <input id="input-return-req-no" type="text" placeholder="離職單號或歸還單號 (選填)" />
        </div>

        <div class="searchable-select-container">
          <label>歸還員工工號 (Returning Employee)</label>
          <input id="selected-returner-id" type="hidden" value="" />
          <div id="returner-select-trigger" class="searchable-select-trigger">
            <span id="returner-select-label">點擊搜尋並選擇歸還人工號...</span>
            <span>▾</span>
          </div>
          <div id="returner-select-dropdown" class="searchable-select-dropdown hidden">
            <input id="returner-select-input" class="searchable-select-input" type="text" placeholder="輸入保管人工號按 Enter (如 EMP102)" />
            <ul id="returner-select-list" class="searchable-select-list"></ul>
          </div>
        </div>

        <div>
          <button id="btn-load-return-list" type="button" style="width: 100%;">載入名下保管設備 (Load Assets)</button>
        </div>
      </div>

      <div class="grid-3" style="align-items: end; margin-top: 14px; padding-top: 14px; border-top: 1px dashed var(--border);">
        <div style="grid-column: span 2;">
          <label for="select-return-accessory">附加歸還標準配件 (Standard Accessories Return)</label>
          <select id="select-return-accessory">
            <option value="ACC-MOUSE-USB">ACC-MOUSE-USB — USB 光學滑鼠 (Standard Mouse)</option>
            <option value="ACC-HEADSET-USB">ACC-HEADSET-USB — USB 雙耳降噪耳麥 (ENC Headset)</option>
            <option value="ACC-CABLE-CAT6">ACC-CABLE-CAT6 — Cat.6 網路跳線 5M (Ethernet Cable)</option>
            <option value="ACC-KEYBOARD-USB">ACC-KEYBOARD-USB — 標準 104 鍵 USB 鍵盤 (USB Keyboard)</option>
            <option value="ACC-PHONE-IP">ACC-PHONE-IP — 企業網路電話機 (IP Desk Phone)</option>
          </select>
        </div>
        <div>
          <button id="btn-add-return-accessory" type="button" class="secondary" style="width: 100%;">加入歸還配件 (Add Accessory)</button>
        </div>
      </div>

      <table id="return-assets-table">
        <thead>
          <tr>
            <th>勾選歸還</th>
            <th>資產編號 / 品項</th>
            <th>設備類型</th>
            <th>型號</th>
            <th>目前保管人</th>
            <th>狀態</th>
          </tr>
        </thead>
        <tbody id="return-items-body"></tbody>
      </table>

      <div id="return-loaded-banner" class="status-banner hidden"></div>
    </div>

    <script>
      const EMPLOYEES = {employees_json};
      const ASSETS = {assets_json};
      const ACCESSORIES = {accessories_json};
      let selectedReturner = '';
      let returnRows = [];

      const trigger = document.getElementById('returner-select-trigger');
      const dropdown = document.getElementById('returner-select-dropdown');
      const searchInput = document.getElementById('returner-select-input');
      const listEl = document.getElementById('returner-select-list');
      const labelEl = document.getElementById('returner-select-label');

      function chooseReturner(empId, empName) {{
        selectedReturner = empId;
        document.getElementById('selected-returner-id').value = empId;
        labelEl.textContent = empId + (empName ? ' - ' + empName : '');
        dropdown.classList.add('hidden');
      }}

      function renderReturnerList(q) {{
        const query = (q || '').trim().toUpperCase();
        listEl.innerHTML = '';
        const matches = EMPLOYEES.filter(e =>
          !query || e.emp_id.toUpperCase().includes(query) || e.name.toUpperCase().includes(query)
        );
        matches.forEach(emp => {{
          const li = document.createElement('li');
          li.className = 'searchable-select-item';
          li.textContent = emp.emp_id + ' — ' + emp.name;
          li.addEventListener('click', () => chooseReturner(emp.emp_id, emp.name));
          listEl.appendChild(li);
        }});
        return matches;
      }}

      function renderReturnTable() {{
        const tbody = document.getElementById('return-items-body');
        tbody.innerHTML = '';
        returnRows.forEach((asset, idx) => {{
          const tr = document.createElement('tr');
          tr.innerHTML = `
            <td><input type="checkbox" id="chk-return-${{idx}}" checked /></td>
            <td><strong>${{asset.tag}}</strong></td>
            <td><span class="badge">${{asset.type}}</span></td>
            <td>${{asset.model}}</td>
            <td>${{asset.holder}}</td>
            <td>待點收歸還</td>
          `;
          tbody.appendChild(tr);
        }});
      }}

      trigger.addEventListener('click', () => {{
        dropdown.classList.toggle('hidden');
        if (!dropdown.classList.contains('hidden')) {{
          searchInput.value = '';
          renderReturnerList('');
          searchInput.focus();
        }}
      }});

      searchInput.addEventListener('input', () => renderReturnerList(searchInput.value));
      searchInput.addEventListener('keydown', (e) => {{
        if (e.key === 'Enter') {{
          e.preventDefault();
          const matches = renderReturnerList(searchInput.value);
          if (matches.length > 0) {{
            chooseReturner(matches[0].emp_id, matches[0].name);
          }} else if (searchInput.value.trim()) {{
            chooseReturner(searchInput.value.trim().toUpperCase(), '');
          }}
        }}
      }});

      document.getElementById('btn-load-return-list').addEventListener('click', () => {{
        const banner = document.getElementById('return-loaded-banner');
        const reqNo = document.getElementById('input-return-req-no').value.trim();
        returnRows = ASSETS
          .filter(a => !selectedReturner || a.holder.toUpperCase() === selectedReturner.toUpperCase())
          .map(a => ({{ ...a }}));
        renderReturnTable();
        banner.textContent = `已載入員工 ${{selectedReturner || '全部'}} 名下共 ${{returnRows.length}} 筆保管設備` + (reqNo ? `（單號：${{reqNo}}）` : '') + '，請確認後完成點收。';
        banner.classList.remove('hidden');
      }});

      document.getElementById('btn-add-return-accessory').addEventListener('click', () => {{
        const accKey = document.getElementById('select-return-accessory').value;
        const info = ACCESSORIES[accKey] || {{ tag: accKey, type: 'Accessory', model: accKey }};
        returnRows.push({{
          tag: info.tag,
          type: info.type,
          model: info.model,
          holder: selectedReturner || 'EMP103'
        }});
        renderReturnTable();
      }});
    </script>
    """
    return _render_layout(
        "Asset Portal — 設備歸還作業",
        "模擬企業資產歸還系統 (/portal/assets/return)",
        _render_portal_login_gate(is_authenticated, workspace),
    )


def render_directory_page(state: SandboxState, initial_query: str = "") -> str:
    employees_json = json.dumps(list(state.employees.values()), ensure_ascii=False)
    escaped_q = html.escape(initial_query)
    body = f"""
    <div class="card">
      <h2>企業員工通訊錄與分機查詢 (Enterprise Directory)</h2>
      <div style="display: flex; gap: 10px; max-width: 580px; align-items: end;">
        <div style="flex: 1;">
          <label for="input-directory-query">搜尋工號、姓名、分機或部門</label>
          <input id="input-directory-query" type="text" value="{escaped_q}" placeholder="輸入工號或分機 (例如 EMP102 或 50212)" />
        </div>
        <button id="btn-directory-search" type="button">搜尋通訊錄</button>
      </div>

      <table id="directory-table">
        <thead>
          <tr>
            <th>工號</th>
            <th>姓名</th>
            <th>部門</th>
            <th>職稱</th>
            <th>分機號碼 (Extension)</th>
            <th>Email</th>
            <th>直屬主管</th>
            <th>座位位置</th>
          </tr>
        </thead>
        <tbody id="directory-results-body"></tbody>
      </table>
    </div>

    <script>
      const EMPLOYEES = {employees_json};
      function searchDirectory() {{
        const q = document.getElementById('input-directory-query').value.trim().toLowerCase();
        const tbody = document.getElementById('directory-results-body');
        tbody.innerHTML = '';
        const matches = EMPLOYEES.filter(e =>
          !q ||
          e.emp_id.toLowerCase().includes(q) ||
          e.name.toLowerCase().includes(q) ||
          e.ext.toLowerCase().includes(q) ||
          e.dept.toLowerCase().includes(q)
        );
        matches.forEach(emp => {{
          const tr = document.createElement('tr');
          tr.innerHTML = `
            <td class="dir-emp-id"><strong>${{emp.emp_id}}</strong></td>
            <td class="dir-emp-name">${{emp.name}}</td>
            <td>${{emp.dept}}</td>
            <td>${{emp.title}}</td>
            <td class="dir-emp-ext"><span class="badge">${{emp.ext}}</span></td>
            <td>${{emp.email}}</td>
            <td>${{emp.manager}}</td>
            <td>${{emp.location}}</td>
          `;
          tbody.appendChild(tr);
        }});
      }}
      document.getElementById('btn-directory-search').addEventListener('click', searchDirectory);
      document.getElementById('input-directory-query').addEventListener('keydown', (e) => {{
        if (e.key === 'Enter') searchDirectory();
      }});
      searchDirectory();
    </script>
    """
    return _render_layout(
        "Enterprise Directory — 企業通訊錄",
        "提供員工分機、部門、座位與直屬主管聯查 (/portal/directory)",
        body,
    )


def render_hr_offboarding_page(
    state: SandboxState,
    is_authenticated: bool = True,
) -> str:
    """Render HR Offboarding clearance lookup page (/portal/hr/offboarding)."""
    employees_json = json.dumps(state.employees, ensure_ascii=False)
    assets_json = json.dumps(list(state.assets.values()), ensure_ascii=False)

    workspace = f"""
    <div class="card">
      <h2>HR 人事離職交接與資訊權限清點系統 (HR Offboarding Clearance)</h2>
      <div style="display: flex; gap: 10px; max-width: 560px; align-items: end;">
        <div style="flex: 1;">
          <label for="input-offboard-emp-id">離職員工工號 (Employee ID)</label>
          <input id="input-offboard-emp-id" type="text" placeholder="輸入離職員工工號 (例如 EMP103)" />
        </div>
        <button id="btn-query-offboard" type="button">查詢離職單</button>
      </div>
    </div>

    <div id="offboard-result-card" class="card hidden">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
        <h2 style="margin: 0;">離職交接清點明細</h2>
        <div>
          <span style="font-size: 13px; color: var(--muted);">離職申請單號：</span>
          <span id="offboard-req-no" class="badge" style="font-size: 14px;">260303</span>
        </div>
      </div>

      <div id="offboard-checklist-wrapper">
        <table id="offboard-checklist-table" style="border: 1px solid #cbd5e1; border-collapse: collapse; width: 100%;">
          <thead>
            <tr style="background: #f1f5f9;">
              <th style="border: 1px solid #cbd5e1; padding: 8px 12px;">離職單號</th>
              <th style="border: 1px solid #cbd5e1; padding: 8px 12px;">員工工號</th>
              <th style="border: 1px solid #cbd5e1; padding: 8px 12px;">姓名 / 部門</th>
              <th style="border: 1px solid #cbd5e1; padding: 8px 12px;">分機號碼</th>
              <th style="border: 1px solid #cbd5e1; padding: 8px 12px;">名下保管資產</th>
              <th style="border: 1px solid #cbd5e1; padding: 8px 12px;">IT 權限停用項目</th>
              <th style="border: 1px solid #cbd5e1; padding: 8px 12px;">查核狀態</th>
            </tr>
          </thead>
          <tbody id="offboard-checklist-tbody"></tbody>
        </table>
      </div>
    </div>

    <script>
      const EMPLOYEES = {employees_json};
      const ASSETS = {assets_json};

      function queryOffboarding() {{
        const rawInput = document.getElementById('input-offboard-emp-id').value.trim().toUpperCase();
        if (!rawInput) return;
        const rawId = /^\\d+$/.test(rawInput) ? ('EMP' + rawInput) : rawInput.replace(/^EMP-/, 'EMP');
        document.getElementById('input-offboard-emp-id').value = rawId;

        const emp = EMPLOYEES[rawId] || {{
          emp_id: rawId,
          name: '離職人員 (' + rawId + ')',
          dept: '產品工程部',
          title: '工程師',
          ext: '50219',
          manager: '部門主管'
        }};

        const digits = rawId.replace(/\\D/g, '') || '103';
        const reqNo = ('260' + digits.slice(-3).padStart(3, '0')).slice(0, 6);
        document.getElementById('offboard-req-no').textContent = reqNo;

        const heldAssets = ASSETS.filter(a => a.holder.toUpperCase() === rawId);
        const assetSummary = heldAssets.length > 0
          ? heldAssets.map(a => a.tag + ' (' + a.type + ')').join(', ')
          : 'IT-300004 (Laptop)';

        const tbody = document.getElementById('offboard-checklist-tbody');
        tbody.innerHTML = `
          <tr>
            <td style="border: 1px solid #cbd5e1; padding: 8px 12px;"><strong>${{reqNo}}</strong></td>
            <td style="border: 1px solid #cbd5e1; padding: 8px 12px;">${{emp.emp_id}}</td>
            <td style="border: 1px solid #cbd5e1; padding: 8px 12px;">${{emp.name}} / ${{emp.dept}}</td>
            <td style="border: 1px solid #cbd5e1; padding: 8px 12px;">${{emp.ext}}</td>
            <td style="border: 1px solid #cbd5e1; padding: 8px 12px;">${{assetSummary}}</td>
            <td style="border: 1px solid #cbd5e1; padding: 8px 12px;">AD 網域帳號、VPN 遠端存取、企業信箱與內部系統權限回收</td>
            <td style="border: 1px solid #cbd5e1; padding: 8px 12px; color: #166534; font-weight: 700;">待 IT 執行停權與點收</td>
          </tr>
        `;
        document.getElementById('offboard-result-card').classList.remove('hidden');
      }}

      document.getElementById('btn-query-offboard').addEventListener('click', queryOffboarding);
      document.getElementById('input-offboard-emp-id').addEventListener('keydown', (e) => {{
        if (e.key === 'Enter') queryOffboarding();
      }});
    </script>
    """
    return _render_layout(
        "HR Offboarding — 人事離職交接系統",
        "提供離職單號查詢與 IT 權限/設備交接清點表擷取 (/portal/hr/offboarding)",
        _render_portal_login_gate(is_authenticated, workspace),
    )


def render_telecom_extensions_page(state: SandboxState) -> str:
    """Render Telecom Extensions Management page (/portal/telecom/extensions).

    Supports both:
    - Offboarding lookup by employee ID (`#input-telecom-emp-id` / `input[name="owner_id"]`)
    - `ext_provision_demo.py` area code (`502`) search, non-repeating last-2-digit scan,
      and extension provisioning form (`#telecom-provision-panel`).
    """
    extensions_json = json.dumps(state.extensions, ensure_ascii=False)

    body = f"""
    <div class="card">
      <h2>企業電信分機管理系統 (Telecom Extension Console)</h2>
      <div class="grid-4" style="align-items: end;">
        <div>
          <label for="input-area-code">分機區碼 (Area Prefix)</label>
          <input id="input-area-code" name="area_code" type="text" placeholder="例如 502" />
        </div>
        <div>
          <label for="input-telecom-emp-id">員工工號查詢 (Owner Employee ID)</label>
          <input id="input-telecom-emp-id" name="owner_id" type="text" placeholder="輸入員工工號 (如 EMP103)" />
        </div>
        <div>
          <label for="select-ext-status">配發狀態 (Status Filter)</label>
          <select id="select-ext-status" name="ext_status">
            <option value="ALL">全部狀態 (All)</option>
            <option value="Available">未配發可用 (Available)</option>
            <option value="Assigned">已配發使用中 (Assigned)</option>
          </select>
        </div>
        <div>
          <button id="btn-telecom-search" type="button" style="width: 100%;">查詢分機</button>
        </div>
      </div>

      <table id="telecom-extensions-table">
        <thead>
          <tr>
            <th>分機號碼 (點擊選取配置)</th>
            <th>狀態</th>
            <th>持有人員</th>
            <th>部門 / 備註</th>
            <th>話機類型</th>
            <th>設備 MAC</th>
          </tr>
        </thead>
        <tbody id="telecom-extensions-tbody"></tbody>
      </table>
    </div>

    <div id="telecom-provision-panel" class="card hidden">
      <h2>分機配號與話機設定 — 分機 <span id="selected-ext-display" class="badge"></span></h2>
      <div class="grid-3">
        <div>
          <label for="select-telecom-company">所屬公司別 (Company)</label>
          <select id="select-telecom-company" name="company">
            <option value="Enterprise-HQ">Enterprise-HQ (企業總部)</option>
            <option value="Enterprise-Branch">Enterprise-Branch (研發分部)</option>
          </select>
        </div>
        <div>
          <label for="select-telecom-user-type">使用者類別 (User Type)</label>
          <select id="select-telecom-user-type" name="user_type">
            <option value="Regular">一般正式員工 (Regular)</option>
            <option value="Shared">公共區域電話 (Shared)</option>
          </select>
        </div>
        <div>
          <label for="select-telecom-status">啟用狀態 (Status)</label>
          <select id="select-telecom-status" name="status">
            <option value="Active">啟用中 (Active)</option>
            <option value="Suspended">停用保留 (Suspended)</option>
          </select>
        </div>
        <div>
          <label for="select-telecom-phone-type">話機設備類型 (Phone Type)</label>
          <select id="select-telecom-phone-type" name="phone_type">
            <option value="IP-Phone">企業網路電話 (IP Desk Phone)</option>
            <option value="Softphone">軟體電話客戶端 (Softphone)</option>
          </select>
        </div>
        <div>
          <label for="input-telecom-site">所在的廠區/樓層 (Site Location)</label>
          <input id="input-telecom-site" name="site_location" type="text" placeholder="例如 HQ-Taipei" />
        </div>
        <div>
          <label for="input-telecom-assign-emp-id">配發員工工號 (Employee ID)</label>
          <input id="input-telecom-assign-emp-id" name="assign_emp_id" type="text" placeholder="例如 EMP104" />
        </div>
        <div>
          <label for="input-telecom-assign-emp-name">配發員工姓名 (Employee Name)</label>
          <input id="input-telecom-assign-emp-name" name="assign_emp_name" type="text" placeholder="例如 張心怡" />
        </div>
        <div>
          <label for="input-telecom-mac">實體話機 MAC 位址 (選填)</label>
          <input id="input-telecom-mac" name="mac_addr" type="text" placeholder="留白則自動啟用 Softphone" />
        </div>
        <div style="display: flex; align-items: center; padding-top: 24px;">
          <label style="display: flex; align-items: center; gap: 8px; cursor: pointer; margin: 0;">
            <input id="chk-telecom-softphone" name="softphone" type="checkbox" value="true" style="width: 18px; height: 18px;" />
            <span>啟用桌面 Softphone 軟體話機 (無實體話機 MAC)</span>
          </label>
        </div>
      </div>
      <div style="margin-top: 16px; display: flex; justify-content: flex-end;">
        <button id="btn-telecom-save-provision" type="button" class="success">儲存分機配置 (Save Provisioning)</button>
      </div>
      <div id="telecom-provision-banner" class="status-banner hidden"></div>
    </div>

    <script>
      const EXTENSIONS = {extensions_json};
      let activeExt = '';

      function openProvisionPanel(extObj) {{
        activeExt = extObj.ext;
        document.getElementById('selected-ext-display').textContent = extObj.ext;
        document.getElementById('input-telecom-assign-emp-id').value = extObj.emp_id || '';
        document.getElementById('input-telecom-assign-emp-name').value = extObj.emp_name || '';
        document.getElementById('input-telecom-mac').value = extObj.mac || '';
        document.getElementById('chk-telecom-softphone').checked = false;
        document.getElementById('telecom-provision-banner').classList.add('hidden');
        document.getElementById('telecom-provision-panel').classList.remove('hidden');
      }}

      function renderExtensions() {{
        const area = document.getElementById('input-area-code').value.trim();
        const rawOwner = document.getElementById('input-telecom-emp-id').value.trim().toUpperCase();
        const owner = rawOwner ? (/^\\d+$/.test(rawOwner) ? ('EMP' + rawOwner) : rawOwner.replace(/^EMP-/, 'EMP')) : '';
        if (owner && rawOwner !== owner) {{
          document.getElementById('input-telecom-emp-id').value = owner;
        }}
        const statusFilter = document.getElementById('select-ext-status').value;
        const tbody = document.getElementById('telecom-extensions-tbody');
        tbody.innerHTML = '';

        const filtered = EXTENSIONS.filter(item => {{
          if (area && !item.ext.startsWith(area)) return false;
          if (owner && item.emp_id.toUpperCase() !== owner) return false;
          if (statusFilter !== 'ALL' && item.status !== statusFilter) return false;
          return true;
        }});

        filtered.forEach((item, idx) => {{
          const tr = document.createElement('tr');
          tr.className = 'telecom-ext-row';
          tr.setAttribute('data-ext', item.ext);
          tr.setAttribute('data-status', item.status);
          tr.innerHTML = `
            <td>
              <button type="button" class="secondary btn-select-ext" id="btn-ext-${{idx}}" data-ext="${{item.ext}}" style="height: 30px; padding: 0 12px; font-weight: 700;">
                ${{item.ext}}
              </button>
            </td>
            <td><span class="badge">${{item.status}}</span></td>
            <td class="ext-owner-cell">${{item.emp_id ? (item.emp_id + ' ' + item.emp_name) : '-'}}</td>
            <td>${{item.dept}}</td>
            <td>${{item.phone_type}}</td>
            <td><code>${{item.mac || '-'}}</code></td>
          `;
          tbody.appendChild(tr);

          tr.querySelector('.btn-select-ext').addEventListener('click', () => openProvisionPanel(item));
        }});
      }}

      document.getElementById('btn-telecom-search').addEventListener('click', renderExtensions);
      document.getElementById('btn-telecom-save-provision').addEventListener('click', () => {{
        const empId = document.getElementById('input-telecom-assign-emp-id').value.trim();
        const empName = document.getElementById('input-telecom-assign-emp-name').value.trim();
        const mac = document.getElementById('input-telecom-mac').value.trim();
        const soft = document.getElementById('chk-telecom-softphone').checked;
        const banner = document.getElementById('telecom-provision-banner');
        banner.textContent = `已完成分機 ${{activeExt}} 配號設定：員工 ${{empId}} (${{empName}})，模式：${{soft ? 'Softphone' : ('MAC ' + mac)}}`;
        banner.classList.remove('hidden');
      }});

      renderExtensions();
    </script>
    """
    return _render_layout(
        "Telecom Console — 電信分機管理系統",
        "提供員工分機清查與新進人員自動化選號配置 (/portal/telecom/extensions)",
        body,
    )


def render_nac_console_page() -> str:
    """Render Network Access Control dual-iframe console (/network/console)."""
    return f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
  <meta charset="utf-8" />
  <title>Network Access Control — 網路存取控制中心</title>
  <style>
    {BASE_CSS}
    .nac-frames-layout {{
      display: grid;
      grid-template-columns: 320px 1fr;
      gap: 16px;
      height: calc(100vh - 120px);
      min-height: 520px;
    }}
    iframe.nac-frame {{
      width: 100%;
      height: 100%;
      border: 1px solid var(--border);
      border-radius: 12px;
      background: #ffffff;
    }}
  </style>
</head>
<body>
  <header>
    <div>
      <h1>Network Access Control — 網路存取控制中心</h1>
      <p>模擬雙層 Frame 架構 (navFrame + mainFrame) 與彈出式權限變更視窗 (/network/console)</p>
    </div>
    <a class="nav-home" href="/">返回沙盒首頁</a>
  </header>
  <main style="max-width: 1360px;">
    <div id="nac-login-box" class="card" style="max-width: 460px; margin: 28px auto;">
      <h2>網管控制台登入</h2>
      <p style="color: var(--muted); font-size: 13px; margin-bottom: 16px;">
        請輸入網管帳號與密碼以進行設備 MAC 查詢與維修放行。
      </p>
      <div style="margin-bottom: 12px;">
        <label for="nac-login-username">網管帳號 (Username)</label>
        <input id="nac-login-username" type="text" placeholder="例如 it.admin" />
      </div>
      <div style="margin-bottom: 16px;">
        <label for="nac-login-password">網管密碼 (Password)</label>
        <input id="nac-login-password" type="password" placeholder="輸入網管密碼" />
      </div>
      <button id="btn-nac-login" type="button" style="width: 100%;">登入網管控制台</button>
    </div>

    <div id="nac-frames-container" class="nac-frames-layout hidden">
      <iframe id="nav-frame" name="navFrame" class="nac-frame" src="/network/nav_frame"></iframe>
      <iframe id="main-frame" name="mainFrame" class="nac-frame" src="/network/main_frame"></iframe>
    </div>
  </main>

  <script>
    (function() {{
      const loginBox = document.getElementById('nac-login-box');
      const framesContainer = document.getElementById('nac-frames-container');
      const btnLogin = document.getElementById('btn-nac-login');

      if (document.cookie.includes('nac_auth=1')) {{
        loginBox.classList.add('hidden');
        framesContainer.classList.remove('hidden');
      }}

      btnLogin.addEventListener('click', function() {{
        const u = document.getElementById('nac-login-username').value.trim();
        const p = document.getElementById('nac-login-password').value.trim();
        if (!u || !p) {{
          alert('請輸入網管帳號與密碼');
          return;
        }}
        document.cookie = 'nac_auth=1; path=/';
        loginBox.classList.add('hidden');
        framesContainer.classList.remove('hidden');
      }});
    }})();
  </script>
</body>
</html>"""


def render_nac_nav_frame() -> str:
    """Render left navigation & MAC search iframe (`iframe[name="navFrame"]`)."""
    return f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
  <meta charset="utf-8" />
  <title>Network Navigation Frame</title>
  <style>{BASE_CSS}</style>
</head>
<body style="background: #ffffff; padding: 18px;">
  <h2 style="margin: 0 0 12px; font-size: 16px;">MAC 實體位址檢索 (navFrame)</h2>
  <p style="font-size: 12.5px; color: var(--muted); margin-bottom: 14px;">
    輸入設備有線或無線網卡 MAC 位址，搜尋結果將連動更新右側 <code>mainFrame</code>。
  </p>
  <div style="margin-bottom: 12px;">
    <label for="input-mac-query">目標設備 MAC Address</label>
    <input id="input-mac-query" type="text" placeholder="例如 00:1A:2B:30:00:01" />
  </div>
  <button id="btn-mac-search" type="button" style="width: 100%;">搜尋 MAC 政策</button>

  <script>
    function triggerSearch() {{
      const mac = document.getElementById('input-mac-query').value.trim().toUpperCase();
      if (window.parent && window.parent.frames && window.parent.frames['mainFrame']) {{
        window.parent.frames['mainFrame'].location.href = '/network/main_frame?mac=' + encodeURIComponent(mac);
      }}
    }}
    document.getElementById('btn-mac-search').addEventListener('click', triggerSearch);
    document.getElementById('input-mac-query').addEventListener('keydown', (e) => {{
      if (e.key === 'Enter') triggerSearch();
    }});
  </script>
</body>
</html>"""


def render_nac_main_frame(
    state: SandboxState,
    mac_query: str = "",
    updated_policy: str = "",
) -> str:
    """Render right policy results iframe (`iframe[name="mainFrame"]`)."""
    cleaned_mac = (mac_query or "").strip().upper()
    if cleaned_mac and updated_policy:
        state.nac_policies[cleaned_mac] = updated_policy

    rows_data: list[dict[str, str]] = []
    for asset in state.assets.values():
        for nic_label, mac_val in (
            ("Wired", asset.get("mac_wired", "")),
            ("Wi-Fi", asset.get("mac_wifi", "")),
        ):
            if not mac_val:
                continue
            mac_upper = mac_val.upper()
            if cleaned_mac and cleaned_mac not in mac_upper:
                continue
            policy = state.nac_policies.get(mac_upper, "Restricted / Standard")
            rows_data.append(
                {
                    "mac": mac_upper,
                    "tag": asset["tag"],
                    "nic": nic_label,
                    "holder": asset["holder"],
                    "policy": policy,
                }
            )

    if cleaned_mac and not rows_data:
        policy = state.nac_policies.get(cleaned_mac, "Restricted / Standard")
        rows_data.append(
            {
                "mac": cleaned_mac,
                "tag": "IT-CUSTOM",
                "nic": "Ethernet/WLAN",
                "holder": "IT-ADMIN",
                "policy": policy,
            }
        )

    rows_html = ""
    for idx, item in enumerate(rows_data):
        is_repair = "repair" in item["policy"].lower()
        badge_style = (
            "background: #dcfce7; color: #166534;"
            if is_repair
            else "background: #fef3c7; color: #92400e;"
        )
        policy_label = "Repair Access (IT 維修放行)" if is_repair else item["policy"]
        escaped_mac = html.escape(item["mac"])
        rows_html += f"""
        <tr>
          <td id="mac-cell-{idx}"><code><strong>{escaped_mac}</strong></code></td>
          <td>{html.escape(item["tag"])} ({html.escape(item["nic"])})</td>
          <td>{html.escape(item["holder"])}</td>
          <td><span id="policy-badge-{idx}" class="badge" style="{badge_style}">{html.escape(policy_label)}</span></td>
          <td>
            <a id="btn-open-policy-{idx}"
               class="btn status-link btn-open-policy"
               href="/network/edit_popup?mac={escaped_mac}"
               onclick="window.open(this.href, 'nac_policy_popup_{idx}', 'width=560,height=460'); return false;"
               style="height: 32px; padding: 0 14px; font-size: 13px;">
              修改存取權限 (Edit Policy)
            </a>
          </td>
        </tr>
        """

    banner_html = ""
    if cleaned_mac and updated_policy:
        banner_html = f"""
        <div id="nac-updated-banner" class="status-banner" style="margin-bottom: 14px;">
          已成功更新網卡 <code>{html.escape(cleaned_mac)}</code> 存取策略為：<strong>IT 維修放行 (Repair Access)</strong>
        </div>
        """

    return f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
  <meta charset="utf-8" />
  <title>Network Main Policy Frame</title>
  <style>{BASE_CSS}</style>
</head>
<body style="background: #ffffff; padding: 18px;">
  <h2 style="margin: 0 0 12px; font-size: 16px;">網路端點存取策略清單 (mainFrame)</h2>
  {banner_html}
  <table id="nac-policy-table">
    <thead>
      <tr>
        <th>MAC Address</th>
        <th>關聯資產編號</th>
        <th>保管人</th>
        <th>目前存取群組 (Policy)</th>
        <th>操作 (點擊彈出視窗)</th>
      </tr>
    </thead>
    <tbody>
      {rows_html}
    </tbody>
  </table>
</body>
</html>"""


def render_nac_edit_popup(mac: str = "") -> str:
    """Render network policy modification popup window (/network/edit_popup)."""
    cleaned_mac = (mac or "00:1A:2B:30:00:01").strip().upper()
    escaped_mac = html.escape(cleaned_mac)
    return f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
  <meta charset="utf-8" />
  <title>修改網卡存取策略 — {escaped_mac}</title>
  <style>{BASE_CSS}</style>
</head>
<body style="padding: 20px;">
  <div class="card" style="max-width: 520px; margin: 0 auto;">
    <h2>變更端點 MAC 網路存取授權</h2>
    <p style="font-size: 13.5px; color: var(--muted);">
      目標網卡實體位址：<strong id="popup-mac-display">{escaped_mac}</strong>
    </p>

    <div style="margin: 18px 0; display: flex; flex-direction: column; gap: 12px;">
      <label style="display: flex; align-items: center; gap: 10px; cursor: pointer; font-weight: 500;">
        <input id="radio-access-quarantine" type="radio" name="nac_policy" value="Quarantine" />
        <span>隔離觀察網段 (Quarantine VLAN)</span>
      </label>
      <label style="display: flex; align-items: center; gap: 10px; cursor: pointer; font-weight: 500;">
        <input id="radio-access-standard" type="radio" name="nac_policy" value="Standard" checked />
        <span>一般辦公網段 (Corporate Standard VLAN)</span>
      </label>
      <label style="display: flex; align-items: center; gap: 10px; cursor: pointer; font-weight: 700; color: var(--primary);">
        <input id="radio-access-repair" type="radio" name="nac_policy" value="Repair Access" />
        <span>IT 維修與系統重灌放行 (Repair / Provisioning Access)</span>
      </label>
    </div>

    <div style="display: flex; justify-content: flex-end; gap: 10px; margin-top: 20px;">
      <button id="btn-apply-policy" type="button" class="success" style="width: 100%;">套用存取策略並關閉 (Apply Policy)</button>
    </div>
    <div id="popup-status-banner" class="status-banner hidden"></div>
  </div>

  <script>
    document.getElementById('btn-apply-policy').addEventListener('click', function() {{
      const mac = {json.dumps(cleaned_mac)};
      const selected = document.querySelector('input[name="nac_policy"]:checked');
      const policy = selected ? selected.value : 'Repair Access';
      const banner = document.getElementById('popup-status-banner');
      banner.textContent = '已套用策略：' + policy;
      banner.classList.remove('hidden');

      try {{
        if (window.opener && !window.opener.closed) {{
          window.opener.location.href = '/network/main_frame?mac=' + encodeURIComponent(mac) + '&updated=' + encodeURIComponent(policy);
        }}
      }} catch (e) {{}}

      setTimeout(function() {{
        window.close();
      }}, 120);
    }});
  </script>
</body>
</html>"""


def render_servicedesk_page(
    state: SandboxState,
    template_mode: str = "incident",
    is_authenticated: bool = True,
) -> str:
    """Render Service Desk Portal ticket creation page (/servicedesk/new?template=incident|routine).

    Simulated enterprise automation challenges:
    - Multiple dynamic searchable select dropdowns (`.searchable-select-trigger` / `.searchable-select-input`).
    - Native JavaScript `confirm("是否同步更新請求人所在部門與位置？")` when selecting a requester.
    - Rich-text resolution editor hosted inside `iframe#resolution-editor-frame` (`body.editor-body[contenteditable="true"]`).
    """
    mode = "routine" if (template_mode or "").strip().lower() == "routine" else "incident"
    is_incident = mode == "incident"
    employees_json = json.dumps(list(state.employees.values()), ensure_ascii=False)

    incident_active_style = (
        "background: var(--primary); color: #fff;"
        if is_incident
        else "background: #e2e8f0; color: #334155;"
    )
    routine_active_style = (
        "background: var(--primary); color: #fff;"
        if not is_incident
        else "background: #e2e8f0; color: #334155;"
    )
    mode_badge_text = (
        "Incident Request (故障報修與服務需求單)"
        if is_incident
        else "Routine Task (IT 例行維運作業單)"
    )

    incident_extra_fields = """
        <div class="searchable-select-container" id="control-subtype">
          <label>服務細項 (Service Item / Sub-Type)</label>
          <input id="selected-subtype-value" type="hidden" value="" />
          <div id="subtype-select-trigger" class="searchable-select-trigger">
            <span id="subtype-select-label">點擊選擇服務細項...</span>
            <span>▾</span>
          </div>
          <div id="subtype-select-dropdown" class="searchable-select-dropdown hidden">
            <input id="subtype-select-input" class="searchable-select-input" type="text" placeholder="輸入細項關鍵字按 Enter..." />
            <ul id="subtype-select-list" class="searchable-select-list"></ul>
          </div>
        </div>

        <div class="searchable-select-container" id="control-corp">
          <label>所屬廠區 / 公司別 (Site / Entity)</label>
          <input id="selected-corp-value" type="hidden" value="" />
          <div id="corp-select-trigger" class="searchable-select-trigger">
            <span id="corp-select-label">點擊選擇廠區別...</span>
            <span>▾</span>
          </div>
          <div id="corp-select-dropdown" class="searchable-select-dropdown hidden">
            <input id="corp-select-input" class="searchable-select-input" type="text" placeholder="例如 Enterprise-HQ" />
            <ul id="corp-select-list" class="searchable-select-list"></ul>
          </div>
        </div>

        <div class="searchable-select-container" id="control-tech">
          <label>指派處理工程師 (Assigned Technician)</label>
          <input id="selected-tech-value" type="hidden" value="" />
          <div id="tech-select-trigger" class="searchable-select-trigger">
            <span id="tech-select-label">點擊選擇處理工程師...</span>
            <span>▾</span>
          </div>
          <div id="tech-select-dropdown" class="searchable-select-dropdown hidden">
            <input id="tech-select-input" class="searchable-select-input" type="text" placeholder="輸入工程師姓名或帳號按 Enter..." />
            <ul id="tech-select-list" class="searchable-select-list"></ul>
          </div>
        </div>
    """

    routine_extra_fields = """
        <div>
          <label for="input-scheduled-date">排程完成日期 (Scheduled Date)</label>
          <div style="display: flex; gap: 6px;">
            <input id="input-scheduled-date" type="text" placeholder="YYYY-MM-DD" />
            <button id="btn-fill-today-date" type="button" class="secondary" style="white-space: nowrap;">帶入今日</button>
          </div>
        </div>

        <div class="searchable-select-container" id="control-group" style="grid-column: span 2;">
          <label>負責維運群組 (Support Group)</label>
          <input id="selected-group-value" type="hidden" value="" />
          <div id="group-select-trigger" class="searchable-select-trigger">
            <span id="group-select-label">點擊選擇負責群組...</span>
            <span>▾</span>
          </div>
          <div id="group-select-dropdown" class="searchable-select-dropdown hidden">
            <input id="group-select-input" class="searchable-select-input" type="text" placeholder="例如 IT-Site-Service" />
            <ul id="group-select-list" class="searchable-select-list"></ul>
          </div>
        </div>
    """

    extra_fields_html = incident_extra_fields if is_incident else routine_extra_fields
    type_label_text = (
        "服務子分類 (Service Category / Type)"
        if is_incident
        else "例行作業類別 (Routine Task Type)"
    )

    iframe_srcdoc = html.escape(
        '<!DOCTYPE html><html lang="zh-TW"><head><meta charset="utf-8" />'
        "<style>"
        'body.editor-body { margin: 0; padding: 12px 14px; font-family: "Microsoft JhengHei UI", "Segoe UI", sans-serif; '
        "font-size: 14px; line-height: 1.55; color: #0f172a; background: #ffffff; min-height: 110px; outline: none; }"
        "</style></head>"
        '<body contenteditable="true" class="editor-body"></body></html>',
        quote=True,
    )

    workspace = f"""
    <div class="card">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
        <div>
          <h2 style="margin: 0;">建立服務台工單 — <span id="current-template-mode" class="badge">{html.escape(mode_badge_text)}</span></h2>
        </div>
        <div style="display: flex; gap: 8px;">
          <a id="tab-mode-incident" class="btn" style="{incident_active_style}" href="/servicedesk/new?template=incident">Incident Request</a>
          <a id="tab-mode-routine" class="btn" style="{routine_active_style}" href="/servicedesk/new?template=routine">Routine Task</a>
        </div>
      </div>

      <div class="grid-3" style="margin-bottom: 14px;">
        <div class="searchable-select-container" id="control-requester">
          <label>請求人信箱 (Requester Email)</label>
          <input id="selected-requester-value" type="hidden" value="" />
          <div id="requester-select-trigger" class="searchable-select-trigger">
            <span id="requester-select-label">點擊搜尋並選擇請求人 Email...</span>
            <span>▾</span>
          </div>
          <div id="requester-select-dropdown" class="searchable-select-dropdown hidden">
            <input id="requester-select-input" class="searchable-select-input" type="text" placeholder="輸入 Email 或工號按 Enter" />
            <ul id="requester-select-list" class="searchable-select-list"></ul>
          </div>
        </div>

        <div>
          <label>自動帶入部門 (Requester Dept)</label>
          <input id="requester-dept-display" type="text" value="尚未同步" readonly style="background: #f8fafc; color: var(--muted);" />
        </div>

        <div>
          <label>自動帶入位置 (Location)</label>
          <input id="requester-location-display" type="text" value="尚未同步" readonly style="background: #f8fafc; color: var(--muted);" />
        </div>
      </div>

      <div class="grid-2" style="margin-bottom: 14px;">
        <div>
          <label for="input-ticket-subject">工單主題 (Subject / Title)</label>
          <input id="input-ticket-subject" type="text" placeholder="請輸入事件或例行作業主題" />
        </div>

        <div class="searchable-select-container" id="control-type">
          <label>{html.escape(type_label_text)}</label>
          <input id="selected-type-value" type="hidden" value="" />
          <div id="type-select-trigger" class="searchable-select-trigger">
            <span id="type-select-label">點擊搜尋並選擇分類...</span>
            <span>▾</span>
          </div>
          <div id="type-select-dropdown" class="searchable-select-dropdown hidden">
            <input id="type-select-input" class="searchable-select-input" type="text" placeholder="輸入分類關鍵字按 Enter..." />
            <ul id="type-select-list" class="searchable-select-list"></ul>
          </div>
        </div>
      </div>

      <div class="grid-3" style="margin-bottom: 16px; align-items: end;">
        {extra_fields_html}
      </div>

      <div style="margin-bottom: 16px;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
          <label style="margin: 0;">處理紀錄與解決方案 (Resolution Rich-Text Editor inside iframe)</label>
          <span style="font-size: 12px; color: var(--muted);">iframe#resolution-editor-frame &gt; body.editor-body[contenteditable="true"]</span>
        </div>
        <iframe
          id="resolution-editor-frame"
          title="Resolution Rich Text Editor"
          srcdoc="{iframe_srcdoc}"
          style="width: 100%; height: 145px; border: 1px solid var(--border); border-radius: 8px; background: #fff;"
        ></iframe>
      </div>

      <div style="display: flex; justify-content: flex-end; gap: 12px;">
        <button id="btn-submit-ticket" name="save-form" type="button" class="success">儲存並送出工單 (Submit Ticket)</button>
      </div>
      <div id="ticket-submit-banner" class="status-banner hidden"></div>
    </div>

    <script>
      const EMPLOYEES = {employees_json};
      const IS_INCIDENT = {"true" if is_incident else "false"};

      function initSearchableDropdown(prefix, presetItems, onSelected) {{
        const trigger = document.getElementById(prefix + '-select-trigger');
        const dropdown = document.getElementById(prefix + '-select-dropdown');
        const input = document.getElementById(prefix + '-select-input');
        const list = document.getElementById(prefix + '-select-list');
        const label = document.getElementById(prefix + '-select-label');
        const hidden = document.getElementById('selected-' + prefix + '-value');
        if (!trigger || !dropdown || !input || !list || !label || !hidden) return;

        function choose(itemObj) {{
          hidden.value = itemObj.value;
          label.textContent = itemObj.label || itemObj.value;
          dropdown.classList.add('hidden');
          if (typeof onSelected === 'function') {{
            onSelected(itemObj);
          }}
        }}

        function renderOptions(filterText) {{
          const q = (filterText || '').trim().toLowerCase();
          list.innerHTML = '';
          const matched = presetItems.filter(it =>
            !q ||
            it.value.toLowerCase().includes(q) ||
            (it.label && it.label.toLowerCase().includes(q))
          );
          if (q && matched.length === 0) {{
            const rawVal = filterText.trim();
            matched.push({{ value: rawVal, label: rawVal }});
          }}
          matched.forEach(itemObj => {{
            const li = document.createElement('li');
            li.className = 'searchable-select-item';
            li.textContent = itemObj.label || itemObj.value;
            li.addEventListener('click', () => choose(itemObj));
            list.appendChild(li);
          }});
          return matched;
        }}

        trigger.addEventListener('click', () => {{
          dropdown.classList.toggle('hidden');
          if (!dropdown.classList.contains('hidden')) {{
            input.value = '';
            renderOptions('');
            input.focus();
          }}
        }});

        input.addEventListener('input', () => renderOptions(input.value));
        input.addEventListener('keydown', (e) => {{
          if (e.key === 'Enter') {{
            e.preventDefault();
            const matches = renderOptions(input.value);
            if (matches.length > 0) {{
              choose(matches[0]);
            }} else if (input.value.trim()) {{
              const raw = input.value.trim();
              choose({{ value: raw, label: raw }});
            }}
          }}
        }});
      }}

      const requesterPresets = EMPLOYEES.map(emp => ({{
        value: emp.email,
        label: emp.email + ' (' + emp.name + ' - ' + emp.dept + ')',
        dept: emp.dept,
        location: emp.location
      }}));

      initSearchableDropdown('requester', requesterPresets, function(itemObj) {{
        const shouldSync = window.confirm('是否同步更新請求人所在部門與位置？');
        if (shouldSync) {{
          document.getElementById('requester-dept-display').value = itemObj.dept || '企業總部資訊處';
          document.getElementById('requester-location-display').value = itemObj.location || 'HQ-8F-A01';
        }}
      }});

      const typePresets = IS_INCIDENT
        ? [
            {{ value: 'Hardware', label: 'Hardware — 電腦與硬體周邊維運' }},
            {{ value: 'Network', label: 'Network — 企業網路與 VPN 連線' }},
            {{ value: 'Software', label: 'Software — 標準辦公與研發軟體' }},
            {{ value: 'Security', label: 'Security — 資安端點與權限管理' }}
          ]
        : [
            {{ value: 'Data Center Inspection', label: 'Data Center Inspection — 機房環控與設備例行巡檢' }},
            {{ value: 'Security Compliance', label: 'Security Compliance — 資安合規與端點健康檢查' }},
            {{ value: 'Backup Verification', label: 'Backup Verification — 備份完整性驗證與演練' }},
            {{ value: 'Asset Audit', label: 'Asset Audit — 季度資產盤點與庫房清查' }}
          ];
      initSearchableDropdown('type', typePresets);

      if (IS_INCIDENT) {{
        initSearchableDropdown('subtype', [
          {{ value: 'RAM / Storage Upgrade', label: 'RAM / Storage Upgrade — 記憶體與硬碟擴充升級' }},
          {{ value: 'VPN Client Access', label: 'VPN Client Access — 遠端 VPN 憑證與連線設定' }},
          {{ value: 'Standard Office Suite', label: 'Standard Office Suite — 標準辦公軟體與印表機' }},
          {{ value: 'Firewall & VLAN Policy', label: 'Firewall & VLAN Policy — 跨網段與 VLAN 存取開通' }},
          {{ value: 'General Support', label: 'General Support — 一般桌邊技術支援' }}
        ]);
        initSearchableDropdown('corp', [
          {{ value: 'Enterprise-HQ', label: 'Enterprise-HQ (企業總部)' }},
          {{ value: 'Enterprise-Branch', label: 'Enterprise-Branch (研發分部)' }},
          {{ value: 'Enterprise-Cloud', label: 'Enterprise-Cloud (雲端資料中心)' }}
        ]);
        initSearchableDropdown('tech', [
          {{ value: 'alex.chen', label: 'alex.chen — 陳建宏 (資深系統工程師)' }},
          {{ value: 'irene.lin', label: 'irene.lin — 林雅婷 (資深前端工程師)' }},
          {{ value: 'brian.wang', label: 'brian.wang — 王柏翰 (資安分析師)' }}
        ]);
      }} else {{
        const btnToday = document.getElementById('btn-fill-today-date');
        const dateInput = document.getElementById('input-scheduled-date');
        if (btnToday && dateInput) {{
          btnToday.addEventListener('click', () => {{
            const now = new Date();
            const yyyy = now.getFullYear();
            const mm = String(now.getMonth() + 1).padStart(2, '0');
            const dd = String(now.getDate()).padStart(2, '0');
            dateInput.value = `${{yyyy}}-${{mm}}-${{dd}}`;
          }});
        }}
        initSearchableDropdown('group', [
          {{ value: 'IT-Site-Service', label: 'IT-Site-Service (企業現場維運工程組)' }},
          {{ value: 'IT-Infra-Ops', label: 'IT-Infra-Ops (核心機房與雲端維運組)' }}
        ]);
      }}

      document.getElementById('btn-submit-ticket').addEventListener('click', function() {{
        const requester = document.getElementById('selected-requester-value').value || 'alex.chen@enterprise.local';
        const subject = document.getElementById('input-ticket-subject').value.trim();
        const typeVal = document.getElementById('selected-type-value').value || 'General';
        const iframe = document.getElementById('resolution-editor-frame');
        let resolutionText = '';
        try {{
          if (iframe && iframe.contentDocument && iframe.contentDocument.body) {{
            resolutionText = iframe.contentDocument.body.innerText.trim();
          }}
        }} catch (e) {{}}

        const prefix = IS_INCIDENT ? 'INC' : 'RTN';
        const ticketNo = prefix + '-' + Math.floor(100000 + Math.random() * 900000);
        const banner = document.getElementById('ticket-submit-banner');
        banner.textContent = `已成功建立工單 ${{ticketNo}}！請求人：${{requester}} ｜ 主題：${{subject}} ｜ 分類：${{typeVal}} ｜ 解決方案字數：${{resolutionText.length}}`;
        banner.classList.remove('hidden');
      }});
    </script>
    """
    return _render_layout(
        "Service Desk Portal — IT 服務台工單系統",
        "模擬多組動態搜尋下拉選單、原生 JS Confirm 與 iframe 富文本編輯器 (/servicedesk/new)",
        _render_portal_login_gate(is_authenticated, workspace),
    )


def render_borrow_report_page(is_authenticated: bool) -> str:
    workspace = """
    <div class="card">
      <h2>短期借用設備報表匯出中心 (Overdue Loan Report)</h2>
      <p style="color: var(--muted); font-size: 13.5px; margin-bottom: 18px;">
        點擊下方按鈕匯出最新六都廠區短期借用追蹤明細報表（<code>sample_borrow_report.xlsx</code>）。
      </p>
      <div style="display: flex; align-items: center; gap: 12px;">
        <button id="btn-export-excel" type="button" class="success">匯出 Excel 報表 (.xlsx)</button>
        <span id="export-status" style="font-size: 13px; color: var(--muted);">就緒，可下載最新報表</span>
      </div>
    </div>
    <script>
      document.getElementById('btn-export-excel').addEventListener('click', function() {
        const statusEl = document.getElementById('export-status');
        if (statusEl) {
          statusEl.textContent = '已觸發報表下載...';
        }
        window.location.href = '/portal/reports/borrow-overdue/download';
      });
    </script>
    """
    return _render_layout(
        "Asset Report Portal — 逾期借用報表中心",
        "模擬企業報表網站匯出 Excel 檔案供 Playwright 攔截下載 (/portal/reports/borrow-overdue)",
        _render_portal_login_gate(is_authenticated, workspace),
    )


def render_forms_login_page(state: SandboxState, is_authenticated: bool) -> str:
    """Render Workflow eForm Portal login & form index page (/portal/forms/login)."""
    total_forms = len(state.audit_forms)
    preview_forms = list(state.audit_forms.values())[:20]
    links_html = "".join(
        f'<tr><td><strong><a href="/portal/forms/view?id={html.escape(f["form_no"])}">'
        f"{html.escape(f['form_no'])}</a></strong></td>"
        f"<td>{html.escape(f['site'])}</td>"
        f"<td>{html.escape(f['applicant'])}</td>"
        f"<td>{html.escape(f['days_overdue'])} 天</td></tr>"
        for f in preview_forms
    )
    workspace = f"""
    <div class="card">
      <h2>企業電子簽核表單查詢中心 (Workflow eForm Portal)</h2>
      <p id="forms-login-status" class="status-banner">
        已通過身分驗證（Session Cookie 生效），系統共有 <strong>{total_forms:,}</strong> 筆逾期表單，可由同一個 BrowserContext 多分頁併發查閱（下方預覽前 {len(preview_forms)} 筆）。
      </p>
      <table>
        <thead>
          <tr><th>表單編號</th><th>廠區</th><th>申請人</th><th>逾期天數</th></tr>
        </thead>
        <tbody>{links_html}</tbody>
      </table>
    </div>
    """
    return _render_layout(
        "Workflow eForm Portal — 簽核表單查詢中心",
        "模擬單次登入共享 Context 與 iframe 內嵌表單明細 (/portal/forms/login)",
        _render_portal_login_gate(is_authenticated, workspace),
    )


def render_form_view_page(
    state: SandboxState,
    form_no: str,
    is_authenticated: bool,
) -> str:
    """Render outer form wrapper hosting an iframe detail view (/portal/forms/view?id=...)."""
    cleaned_id = (form_no or "").strip().upper()
    escaped_id = html.escape(cleaned_id)
    workspace = f"""
    <div class="card">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
        <h2 style="margin: 0;">表單明細檢視 — <span id="view-form-no" class="badge">{escaped_id}</span></h2>
        <a class="btn secondary" href="/portal/forms/login" style="height: 34px; font-size: 13px;">返回表單清單</a>
      </div>
      <iframe
        id="form-frame"
        name="formFrame"
        src="/portal/forms/frame?id={escaped_id}"
        style="width: 100%; height: 360px; border: 1px solid var(--border); border-radius: 8px; background: #fff;"
      ></iframe>
    </div>
    """
    return _render_layout(
        f"表單檢視 {cleaned_id} — Workflow eForm Portal",
        "透過 iframe 載入電子表單欄位供 Playwright 跨 Frame 擷取 (/portal/forms/view)",
        _render_portal_login_gate(is_authenticated, workspace),
    )


def render_form_detail_frame(
    state: SandboxState,
    form_no: str,
    is_authenticated: bool,
) -> str:
    """Render inner iframe form fields (/portal/forms/frame?id=...)."""
    if not is_authenticated:
        return """<!DOCTYPE html>
<html lang="zh-TW">
<head><meta charset="utf-8" /><title>Unauthorized</title></head>
<body style="font-family: sans-serif; padding: 20px; color: #dc2626;">
  <h3>尚未登入簽核系統，請先至 /portal/forms/login 完成登入。</h3>
</body>
</html>"""

    cleaned_id = (form_no or "").strip().upper()
    record = state.audit_forms.get(cleaned_id)
    if record is None:
        return f"""<!DOCTYPE html>
<html lang="zh-TW">
<head><meta charset="utf-8" /><title>Not Found</title><style>{BASE_CSS}</style></head>
<body style="background: #fff; padding: 20px;">
  <h3 style="color: var(--danger);">查無表單編號：{html.escape(cleaned_id)}</h3>
</body>
</html>"""

    request_types = [
        "VPN 遠端存取",
        "資料庫唯讀權限",
        "網段放行申請",
        "ERP 模組授權",
        "雲端帳號開通",
        "檔案伺服器權限",
    ]
    options_html = "".join(
        f'<option value="{html.escape(opt)}"{" selected" if opt == record["request_type"] else ""}>'
        f"{html.escape(opt)}</option>"
        for opt in request_types
    )

    return f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
  <meta charset="utf-8" />
  <title>Form Detail Frame — {html.escape(cleaned_id)}</title>
  <style>{BASE_CSS}</style>
</head>
<body style="background: #ffffff; padding: 18px 20px;">
  <div class="grid-3" style="margin-bottom: 14px;">
    <div>
      <label>表單編號 (Form No)</label>
      <input id="field-form-no" type="text" value="{html.escape(record["form_no"])}" readonly />
    </div>
    <div>
      <label>廠區 (Site)</label>
      <input id="field-site" type="text" value="{html.escape(record["site"])}" readonly />
    </div>
    <div>
      <label>申請人 (Applicant)</label>
      <input id="field-applicant" type="text" value="{html.escape(record["applicant"])}" readonly />
    </div>
  </div>

  <div style="margin-bottom: 14px;">
    <label for="request-type">申請類型 (Request Type)</label>
    <select id="request-type" disabled>
      {options_html}
    </select>
  </div>

  <div>
    <label for="review-comment">審核備註 (Review Comment)</label>
    <textarea
      id="review-comment"
      readonly
      rows="3"
      style="width: 100%; border: 1px solid var(--border); border-radius: 8px; padding: 8px 12px; font-size: 14px; font-family: inherit;"
    >{html.escape(record["review_comment"])}</textarea>
  </div>
</body>
</html>"""

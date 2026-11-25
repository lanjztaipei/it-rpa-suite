"""Windows DPAPI credential encryption/decryption and data/credentials.dat storage."""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path

import win32crypt

from it_rpa_suite.adapters.logger import get_logger
from it_rpa_suite.adapters.paths import AppPaths, get_app_paths
from it_rpa_suite.adapters.result import ValidationResult

logger = get_logger(__name__)

CREDENTIAL_FIELDS: dict[str, str] = {
    "email": "工程師 Email",
    "portal_account": "企業入口網帳號",
    "portal_password": "企業入口網密碼",
    "nac_account": "網管帳號",
    "nac_password": "網管密碼",
}


class CredentialError(RuntimeError):
    """Raised when DPAPI credentials are missing, invalid, or fail decryption outside sandbox mode."""


def is_sandbox_mode() -> bool:
    """Return True when sandbox defaults are allowed (`IT_SUITE_SANDBOX_MODE`, default True)."""
    raw = os.environ.get("IT_SUITE_SANDBOX_MODE", "true").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def encrypt_credentials(data: dict[str, str]) -> str:
    """Encrypt a dictionary using Windows DPAPI (CryptProtectData) and return Base64 text."""
    try:
        json_bytes = json.dumps(data, ensure_ascii=False).encode("utf-8")
        encrypted_blob = win32crypt.CryptProtectData(
            json_bytes,
            None,
            None,
            None,
            None,
            0,
        )
        return base64.b64encode(encrypted_blob).decode("utf-8")
    except Exception as exc:
        raise CredentialError(f"DPAPI 加密失敗：{exc}") from exc


def decrypt_credentials(encrypted_text: str) -> dict[str, str]:
    """Decrypt Base64 text using Windows DPAPI (CryptUnprotectData) and return dict."""
    try:
        encrypted_blob = base64.b64decode(encrypted_text.strip().encode("utf-8"))
        _, raw_bytes = win32crypt.CryptUnprotectData(
            encrypted_blob,
            None,
            None,
            None,
            0,
        )
        parsed = json.loads(raw_bytes.decode("utf-8"))
        if not isinstance(parsed, dict):
            raise CredentialError("憑證內容格式不正確（非 JSON 物件）")
        return {str(k): str(v) for k, v in parsed.items()}
    except CredentialError:
        raise
    except Exception as exc:
        raise CredentialError(f"DPAPI 解密失敗：{exc}") from exc


def validate_credentials(data: dict[str, str]) -> ValidationResult:
    """Validate credential fields and email format."""
    for key, label in CREDENTIAL_FIELDS.items():
        value = data.get(key, "")
        if not isinstance(value, str):
            return ValidationResult(valid=False, message=f"{label}格式不正確")
        if not value.strip():
            return ValidationResult(valid=False, message=f"請輸入{label}")

    email = data["email"].strip()
    if "@" not in email:
        return ValidationResult(valid=False, message="工程師 Email 格式不正確")

    local_part, domain_part = email.rsplit("@", 1)
    if (
        not local_part
        or "." not in domain_part
        or domain_part.startswith(".")
        or domain_part.endswith(".")
    ):
        return ValidationResult(valid=False, message="工程師 Email 格式不正確")

    cleaned = {
        "email": email,
        "portal_account": data["portal_account"].strip(),
        "portal_password": data["portal_password"],
        "nac_account": data["nac_account"].strip(),
        "nac_password": data["nac_password"],
    }
    return ValidationResult(valid=True, value=cleaned)


class CredentialStore:
    """Manages DPAPI-encrypted credentials in data/credentials.dat."""

    def __init__(
        self,
        paths: AppPaths | None = None,
        base_dir: str | Path | None = None,
    ) -> None:
        if paths is not None:
            self.paths = paths
            self.paths.ensure_directories()
        else:
            self.paths = get_app_paths(base_dir=base_dir)

    @property
    def file_path(self) -> Path:
        return self.paths.credentials_file

    def exists(self) -> bool:
        return self.file_path.is_file() and self.file_path.stat().st_size > 0

    def load(self, *, raise_on_error: bool = False) -> dict[str, str]:
        """Load and decrypt existing credentials.

        When `raise_on_error=True`, decryption failures or corrupted files raise `CredentialError`
        instead of returning an empty dict.
        """
        if not self.exists():
            return {}
        try:
            encrypted_text = self.file_path.read_text(encoding="utf-8").strip()
            if not encrypted_text:
                if raise_on_error:
                    raise CredentialError(f"系統憑證檔內容為空：{self.file_path}")
                return {}
            return decrypt_credentials(encrypted_text)
        except CredentialError:
            logger.exception("讀取或解密憑證檔失敗: %s", self.file_path)
            if raise_on_error:
                raise
            return {}
        except Exception as exc:
            logger.exception("讀取或解密憑證檔失敗: %s", self.file_path)
            if raise_on_error:
                raise CredentialError(f"讀取或解密憑證檔失敗：{exc}") from exc
            return {}

    def save(self, credentials: dict[str, str]) -> None:
        """Encrypt and atomically write credentials to data/credentials.dat."""
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        encrypted_text = encrypt_credentials(credentials)
        temp_path = self.file_path.with_suffix(".dat.tmp")
        try:
            temp_path.write_text(encrypted_text, encoding="utf-8")
            os.replace(temp_path, self.file_path)
            logger.info("已加密並儲存憑證設定檔: %s", self.file_path)
        except Exception:
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except OSError:
                    pass
            raise

    @staticmethod
    def validate(credentials: dict[str, str]) -> ValidationResult:
        return validate_credentials(credentials)


def resolve_login_credentials(
    credentials: dict[str, str] | None,
    *,
    account_keys: tuple[str, ...],
    password_keys: tuple[str, ...],
    default_account: str,
    default_password: str,
    store: CredentialStore | None = None,
    system_name: str = "系統",
) -> tuple[str, str]:
    """Resolve login username/password, enforcing fail-fast when outside sandbox mode."""
    sandbox = is_sandbox_mode()
    creds = (
        credentials
        if credentials is not None
        else (store or CredentialStore()).load(raise_on_error=not sandbox)
    )

    username = next(
        (str(creds.get(key) or "").strip() for key in account_keys if creds.get(key)), ""
    )
    password = next((str(creds.get(key) or "") for key in password_keys if creds.get(key)), "")

    if username and password:
        return username, password

    if sandbox:
        return username or default_account, password or default_password

    raise CredentialError(
        f"找不到有效的{system_name}憑證，請先至「系統憑證設定」重新設定並加密儲存"
        "（非沙盒模式下禁止自動退回預設範例帳密）"
    )

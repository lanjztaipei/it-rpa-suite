"""Low-level adapters for filesystem paths, logging, storage, DPAPI credentials, and browser worker."""

from it_rpa_suite.adapters.credentials_dpapi import (
    CredentialStore,
    decrypt_credentials,
    encrypt_credentials,
    validate_credentials,
)
from it_rpa_suite.adapters.logger import get_logger
from it_rpa_suite.adapters.paths import AppPaths, get_app_paths
from it_rpa_suite.adapters.result import (
    ServiceResult,
    ValidationResult,
    normalize_asset_tag,
    normalize_employee_id,
    validate_asset_tag,
    validate_asset_tag_lines,
    validate_device_type,
    validate_employee_id,
    validate_request_no,
    validate_required_text,
    validate_yes_no,
)
from it_rpa_suite.adapters.storage import AppStorage

__all__ = [
    "AppPaths",
    "AppStorage",
    "CredentialStore",
    "ServiceResult",
    "ValidationResult",
    "decrypt_credentials",
    "encrypt_credentials",
    "get_app_paths",
    "get_logger",
    "normalize_asset_tag",
    "normalize_employee_id",
    "validate_asset_tag",
    "validate_asset_tag_lines",
    "validate_credentials",
    "validate_device_type",
    "validate_employee_id",
    "validate_request_no",
    "validate_required_text",
    "validate_yes_no",
]

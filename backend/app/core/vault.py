"""HashiCorp Vault client for secrets management.

Provides secure storage and retrieval of credentials:
- OAuth tokens (Gmail, Google Drive)
- API keys (Paheko)
- Login credentials (Free, Free Mobile)

Vault Secret Structure:
    secret/
    ├── sources/
    │   ├── gmail/{source_id}/
    │   │   ├── credentials.json    # OAuth client credentials
    │   │   └── token.json          # OAuth access/refresh tokens
    │   ├── free/{source_id}/
    │   │   ├── login
    │   │   └── password
    │   └── ...
    ├── exporters/
    │   ├── paheko/{exporter_id}/
    │   │   ├── api_url
    │   │   └── api_key
    │   ├── gdrive/{exporter_id}/
    │   │   ├── credentials.json
    │   │   └── token.json
    │   └── ...
"""

import json
from collections.abc import Callable
from functools import wraps
from typing import Any, ParamSpec, TypeVar

import hvac
from hvac.exceptions import InvalidPath

from app.core.config import settings

P = ParamSpec("P")
R = TypeVar("R")


class VaultError(Exception):
    """Raised when Vault operations fail."""

    pass


class VaultClient:
    """HashiCorp Vault client for secrets management."""

    def __init__(self, url: str | None = None, token: str | None = None):
        """Initialize Vault client.

        Args:
            url: Vault server URL
            token: Authentication token
        """
        self.url = url or settings.VAULT_URL
        self.token = token or settings.VAULT_TOKEN
        self.client = hvac.Client(url=self.url, token=self.token)

    def is_authenticated(self) -> bool:
        """Check if client is authenticated with Vault."""
        try:
            return self.client.is_authenticated()
        except Exception:
            return False

    def get_secret(self, path: str) -> dict[str, Any]:
        """Get secret as dict from Vault KV v2.

        Args:
            path: Secret path (e.g., 'sources/gmail/123')

        Returns:
            Secret data as dict

        Raises:
            VaultError: If secret not found or access denied
        """
        try:
            response = self.client.secrets.kv.v2.read_secret_version(
                path=path,
                mount_point="secret",
            )
            return response["data"]["data"]
        except InvalidPath:
            raise VaultError(f"Secret not found at path: {path}")
        except Exception as e:
            raise VaultError(f"Failed to get secret: {e}") from e

    def store_secret(self, path: str, data: dict[str, Any]) -> None:
        """Store secret dict in Vault KV v2.

        Args:
            path: Secret path
            data: Secret data to store

        Raises:
            VaultError: If storage fails
        """
        try:
            self.client.secrets.kv.v2.create_or_update_secret(
                path=path,
                secret=data,
                mount_point="secret",
            )
        except Exception as e:
            raise VaultError(f"Failed to store secret: {e}") from e

    def delete_secret(self, path: str) -> None:
        """Delete secret from Vault.

        Args:
            path: Secret path to delete

        Raises:
            VaultError: If deletion fails
        """
        try:
            self.client.secrets.kv.v2.delete_metadata_and_all_versions(
                path=path,
                mount_point="secret",
            )
        except Exception as e:
            raise VaultError(f"Failed to delete secret: {e}") from e

    def get_json_file(self, path: str) -> dict[str, Any]:
        """Get JSON file content from Vault.

        Useful for token.json, credentials.json files.

        Args:
            path: Secret path

        Returns:
            Parsed JSON content
        """
        secret = self.get_secret(path)
        content = secret.get("content", "{}")
        return json.loads(content)

    def store_json_file(self, path: str, content: dict[str, Any]) -> None:
        """Store JSON file content in Vault.

        Args:
            path: Secret path
            content: Dict to store as JSON
        """
        self.store_secret(path, {"content": json.dumps(content)})

    # Convenience methods for common credential patterns

    def get_gmail_tokens(self, source_id: str) -> dict[str, Any]:
        """Get Gmail OAuth tokens for a source."""
        return self.get_json_file(f"sources/gmail/{source_id}/token")

    def store_gmail_tokens(self, source_id: str, tokens: dict[str, Any]) -> None:
        """Store Gmail OAuth tokens (called after OAuth flow)."""
        self.store_json_file(f"sources/gmail/{source_id}/token", tokens)

    def get_gmail_credentials(self, source_id: str) -> dict[str, Any]:
        """Get Gmail OAuth client credentials."""
        return self.get_json_file(f"sources/gmail/{source_id}/credentials")

    def get_paheko_credentials(self, exporter_id: str) -> dict[str, Any]:
        """Get Paheko API credentials."""
        return self.get_secret(f"exporters/paheko/{exporter_id}")

    def store_paheko_credentials(
        self,
        exporter_id: str,
        api_url: str,
        api_key: str,
        api_user: str | None = None,
    ) -> None:
        """Store Paheko API credentials."""
        data = {"api_url": api_url, "api_key": api_key}
        if api_user:
            data["api_user"] = api_user
        self.store_secret(f"exporters/paheko/{exporter_id}", data)

    def get_gdrive_tokens(self, exporter_id: str) -> dict[str, Any]:
        """Get Google Drive OAuth tokens for an exporter."""
        return self.get_json_file(f"exporters/gdrive/{exporter_id}/token")

    def store_gdrive_tokens(self, exporter_id: str, tokens: dict[str, Any]) -> None:
        """Store Google Drive OAuth tokens."""
        self.store_json_file(f"exporters/gdrive/{exporter_id}/token", tokens)

    def get_gdrive_credentials(self, exporter_id: str) -> dict[str, Any]:
        """Get Google Drive OAuth client credentials."""
        return self.get_json_file(f"exporters/gdrive/{exporter_id}/credentials")

    def get_paheko_api_key(self, exporter_id: str) -> str:
        """Get Paheko API key."""
        creds = self.get_paheko_credentials(exporter_id)
        return creds.get("api_key", "")


# Global vault client instance
_vault: VaultClient | None = None


def get_vault() -> VaultClient:
    """Get or create Vault client singleton."""
    global _vault
    if _vault is None:
        _vault = VaultClient()
    return _vault


def get_credential(path: str, key: str | None = None) -> str | dict[str, Any]:
    """Simple credential retrieval utility.

    Usage:
        api_key = get_credential("exporters/paheko/123", "api_key")
        tokens = get_credential("sources/gmail/456/token")

    Args:
        path: Vault secret path
        key: Optional key to extract from secret dict

    Returns:
        Full secret dict or specific key value
    """
    vault = get_vault()
    secret = vault.get_secret(path)
    if key:
        return secret.get(key, "")
    return secret


def with_credentials(*credential_paths: str) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorator that injects credentials into function kwargs.

    Path templates can use {kwarg_name} placeholders that will be
    resolved from the function's kwargs.

    Usage:
        @with_credentials("sources/gmail/{source_id}/token")
        async def fetch_emails(source_id: str, token_creds: dict = None):
            # token_creds is automatically populated from Vault
            pass

    The credential key name is derived from the last path segment:
        - "sources/gmail/{source_id}/token" -> "token_creds"
        - "exporters/paheko/{id}" -> "paheko_creds"
    """

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @wraps(func)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            vault = get_vault()
            for path_template in credential_paths:
                # Resolve path templates with kwargs
                path = path_template.format(**kwargs)
                # Derive key name from last path segment
                key_name = path.split("/")[-1].replace(".json", "") + "_creds"
                kwargs[key_name] = vault.get_secret(path)
            return func(*args, **kwargs)

        @wraps(func)
        async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            vault = get_vault()
            for path_template in credential_paths:
                path = path_template.format(**kwargs)
                key_name = path.split("/")[-1].replace(".json", "") + "_creds"
                kwargs[key_name] = vault.get_secret(path)
            return await func(*args, **kwargs)  # type: ignore

        # Return appropriate wrapper based on function type
        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        return sync_wrapper  # type: ignore

    return decorator

"""HashiCorp Vault client for secrets management."""

import logging
import os
from typing import Optional, Dict, Any
from threading import Thread
import time

import hvac
from hvac.exceptions import InvalidRequest

logger = logging.getLogger(__name__)


class VaultClient:
    """Client for HashiCorp Vault with AppRole authentication."""

    def __init__(
        self,
        vault_addr: str,
        role_id: str,
        secret_id: str,
        dev_mode: bool = False,
    ):
        """Initialize Vault client.

        Args:
            vault_addr: Vault server address (e.g., http://localhost:8200)
            role_id: AppRole role_id
            secret_id: AppRole secret_id
            dev_mode: If True, fall back to environment variables
        """
        self.vault_addr = vault_addr
        self.role_id = role_id
        self.secret_id = secret_id
        self.dev_mode = dev_mode
        self.client = None
        self.token = None
        self._refresh_thread = None
        self._stop_refresh = False

    def connect(self) -> bool:
        """Connect to Vault and authenticate with AppRole.

        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            self.client = hvac.Client(url=self.vault_addr)

            if self.dev_mode:
                logger.warning("Vault in DEV mode - using environment variables")
                self.token = os.getenv("VAULT_TOKEN")
                if self.token:
                    self.client.token = self.token
                    logger.info("Vault: using token from environment")
                    return True
                return False

            # Authenticate with AppRole
            auth_response = self.client.auth.approle.login(
                role_id=self.role_id,
                secret_id=self.secret_id,
            )
            self.token = auth_response["auth"]["client_token"]
            self.client.token = self.token

            # Start token refresh thread
            self._start_token_refresh()

            logger.info("Vault: authenticated with AppRole")
            return True

        except Exception as e:
            logger.error(f"Vault connection failed: {e}")
            return False

    def _start_token_refresh(self):
        """Start background thread for token refresh."""
        if self._refresh_thread is not None:
            return

        self._refresh_thread = Thread(target=self._refresh_token_loop, daemon=True)
        self._refresh_thread.start()

    def _refresh_token_loop(self):
        """Periodically refresh the Vault token."""
        while not self._stop_refresh:
            try:
                time.sleep(3600)  # Refresh every hour
                auth_response = self.client.auth.approle.login(
                    role_id=self.role_id,
                    secret_id=self.secret_id,
                )
                self.token = auth_response["auth"]["client_token"]
                self.client.token = self.token
                logger.info("Vault: token refreshed")
            except Exception as e:
                logger.warning(f"Vault token refresh failed: {e}")

    def get_secret(self, path: str) -> Optional[Dict[str, Any]]:
        """Get a secret from Vault.

        Args:
            path: Secret path (e.g., "secret/data/fakturenn/free/credentials")

        Returns:
            Dict with secret data, or None if not found
        """
        if self.dev_mode:
            # In dev mode, try to get from environment
            env_key = path.replace("/", "_").replace("secret_data_", "").upper()
            logger.warning(f"Vault DEV: would load {path} from {env_key}")
            return None

        try:
            response = self.client.secrets.kv.v2.read_secret_version(path=path)
            return response["data"]["data"]
        except InvalidRequest:
            logger.warning(f"Vault secret not found: {path}")
            return None
        except Exception as e:
            logger.error(f"Vault get_secret failed: {e}")
            return None

    def set_secret(self, path: str, secret_data: Dict[str, Any]) -> bool:
        """Set a secret in Vault.

        Args:
            path: Secret path
            secret_data: Data to store

        Returns:
            bool: True if successful
        """
        if self.dev_mode:
            logger.warning(f"Vault DEV: would save {path}")
            return False

        try:
            self.client.secrets.kv.v2.create_or_update_secret(
                path=path,
                secret=secret_data,
            )
            logger.info(f"Vault: secret stored at {path}")
            return True
        except Exception as e:
            logger.error(f"Vault set_secret failed: {e}")
            return False

    def get_user_secret(self, user_id: int, key: str) -> Optional[str]:
        """Get a user-specific secret.

        Args:
            user_id: User ID
            key: Secret key

        Returns:
            Secret value or None
        """
        path = f"secret/data/fakturenn/users/{user_id}/{key}"
        secret = self.get_secret(path)
        if secret:
            return secret.get(key)
        return None

    def set_user_secret(self, user_id: int, key: str, value: str) -> bool:
        """Set a user-specific secret.

        Args:
            user_id: User ID
            key: Secret key
            value: Secret value

        Returns:
            bool: True if successful
        """
        path = f"secret/data/fakturenn/users/{user_id}/{key}"
        return self.set_secret(path, {key: value})

    def close(self):
        """Close Vault connection and stop refresh thread."""
        self._stop_refresh = True
        if self._refresh_thread:
            self._refresh_thread.join(timeout=5)
        logger.info("Vault connection closed")


# Global vault client instance
_vault_client = None


def get_vault_client() -> VaultClient:
    """Get the global Vault client instance.

    Returns:
        VaultClient: The initialized Vault client

    Raises:
        RuntimeError: If Vault client not initialized
    """
    if _vault_client is None:
        raise RuntimeError("Vault client not initialized. Call init_vault() first.")
    return _vault_client


def init_vault(
    vault_addr: str = None,
    role_id: str = None,
    secret_id: str = None,
    dev_mode: bool = False,
) -> VaultClient:
    """Initialize the global Vault client.

    Args:
        vault_addr: Vault server address (default: from env VAULT_ADDR)
        role_id: AppRole role_id (default: from env VAULT_ROLE_ID)
        secret_id: AppRole secret_id (default: from env VAULT_SECRET_ID)
        dev_mode: If True, use environment variables instead of Vault

    Returns:
        VaultClient: The initialized Vault client
    """
    global _vault_client

    vault_addr = vault_addr or os.getenv("VAULT_ADDR", "http://localhost:8200")
    role_id = role_id or os.getenv("VAULT_ROLE_ID", "")
    secret_id = secret_id or os.getenv("VAULT_SECRET_ID", "")

    _vault_client = VaultClient(vault_addr, role_id, secret_id, dev_mode=dev_mode)

    if not _vault_client.connect():
        if not dev_mode:
            logger.warning("Vault connection failed, trying dev mode")
            _vault_client.dev_mode = True

    return _vault_client

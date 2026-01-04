"""Google Drive exporter implementation.

Provides connectivity to Google Drive API for uploading invoice files.
"""

import io
from typing import Any

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseUpload

from app.core.vault import VaultError, get_vault
from app.exports.base import (
    AuthenticationError,
    BaseExporter,
    ConnectionError,
    DuplicateError,
    ExportError,
)


class GDriveExporter(BaseExporter):
    """Google Drive exporter for uploading invoice files.

    Configuration (from Exporter.config):
        root_folder_id: Google Drive folder ID for uploads
        folder_structure: Subfolder pattern (e.g., "{year}/{month}")
        create_folders: Auto-create folders if missing (default: true)
        vault_credentials_path: Path to OAuth credentials (auto-filled)
        duplicate_check: Check for existing files (default: true)
        duplicate_action: Action on duplicate (skip, replace, rename)

    Vault paths:
        exporters/gdrive/{exporter_id}/credentials - OAuth client credentials
        exporters/gdrive/{exporter_id}/token - OAuth access/refresh tokens
    """

    def __init__(self, exporter_id: str, config: dict[str, Any]):
        super().__init__(exporter_id, config)
        self._service = None
        self._credentials = None
        self._folder_cache: dict[str, str] = {}  # path -> folder_id

    async def connect(self) -> None:
        """Connect to Google Drive API using OAuth credentials from Vault."""
        try:
            vault = get_vault()

            # Load OAuth tokens from Vault
            token_data = vault.get_gdrive_tokens(self.exporter_id)
            if not token_data:
                raise AuthenticationError(
                    "No OAuth tokens found. Please complete OAuth flow first.",
                    {"exporter_id": self.exporter_id},
                )

            # Build credentials object
            self._credentials = Credentials(
                token=token_data.get("access_token"),
                refresh_token=token_data.get("refresh_token"),
                token_uri="https://oauth2.googleapis.com/token",
                client_id=token_data.get("client_id"),
                client_secret=token_data.get("client_secret"),
                scopes=["https://www.googleapis.com/auth/drive.file"],
            )

            # Check if token needs refresh
            if self._credentials.expired and self._credentials.refresh_token:
                from google.auth.transport.requests import Request

                self._credentials.refresh(Request())
                # Save refreshed tokens back to Vault
                vault.store_gdrive_tokens(
                    self.exporter_id,
                    {
                        "access_token": self._credentials.token,
                        "refresh_token": self._credentials.refresh_token,
                        "client_id": token_data.get("client_id"),
                        "client_secret": token_data.get("client_secret"),
                    },
                )

            # Build Drive service
            self._service = build("drive", "v3", credentials=self._credentials)
            self._connected = True

        except VaultError as e:
            raise AuthenticationError(
                f"Failed to load credentials from Vault: {e}",
                {"exporter_id": self.exporter_id},
            ) from e
        except HttpError as e:
            raise ConnectionError(
                f"Failed to connect to Google Drive API: {e}",
                {"exporter_id": self.exporter_id, "error": str(e)},
            ) from e

    async def disconnect(self) -> None:
        """Disconnect from Google Drive API."""
        self._service = None
        self._credentials = None
        self._folder_cache = {}
        self._connected = False

    async def create_entry(self, data: dict[str, Any]) -> str:
        """Upload a file to Google Drive.

        Args:
            data: File data with keys:
                - filename: Name for the uploaded file
                - content: File content as bytes
                - content_type: MIME type (default: application/pdf)
                - folder_id: Target folder ID (optional, uses root_folder_id)
                - description: File description (optional)

        Returns:
            ID of uploaded file

        Raises:
            ExportError: If upload fails
            DuplicateError: If file already exists (when duplicate_check enabled)
        """
        if not self._service:
            raise ConnectionError("Not connected to Google Drive API")

        filename = data.get("filename", "")
        if not filename:
            raise ExportError("Filename is required")

        content = data.get("content")
        if not content:
            raise ExportError("File content is required")

        # Determine target folder
        folder_id = data.get("folder_id") or self.config.get("root_folder_id")
        if not folder_id:
            raise ExportError("No folder_id specified and no root_folder_id configured")

        # Check for duplicates if enabled
        if self.config.get("duplicate_check", True):
            if await self.check_duplicate(filename):
                action = self.config.get("duplicate_action", "skip")
                if action == "skip":
                    raise DuplicateError(
                        f"File '{filename}' already exists",
                        {"filename": filename},
                    )
                elif action == "rename":
                    # Add timestamp to filename
                    import time
                    base, ext = filename.rsplit(".", 1) if "." in filename else (filename, "")
                    filename = f"{base}_{int(time.time())}.{ext}" if ext else f"{base}_{int(time.time())}"
                # action == "replace" falls through to upload

        try:
            # Prepare file metadata
            file_metadata = {
                "name": filename,
                "parents": [folder_id],
            }
            if data.get("description"):
                file_metadata["description"] = data["description"]

            # Prepare media
            content_type = data.get("content_type", "application/pdf")
            media = MediaIoBaseUpload(
                io.BytesIO(content),
                mimetype=content_type,
                resumable=True,
            )

            # Upload file
            file = (
                self._service.files()
                .create(
                    body=file_metadata,
                    media_body=media,
                    fields="id",
                )
                .execute()
            )

            return file.get("id", "")

        except HttpError as e:
            raise ExportError(
                f"Failed to upload file: {e}",
                {"filename": filename, "error": str(e)},
            ) from e

    async def check_duplicate(self, identifier: str) -> bool:
        """Check if a file with given name exists in the target folder.

        Args:
            identifier: Filename to check

        Returns:
            True if file exists, False otherwise
        """
        if not self._service:
            raise ConnectionError("Not connected to Google Drive API")

        folder_id = self.config.get("root_folder_id")
        if not folder_id:
            return False

        try:
            # Search for file with same name in folder
            query = f"name = '{identifier}' and '{folder_id}' in parents and trashed = false"
            response = (
                self._service.files()
                .list(
                    q=query,
                    spaces="drive",
                    fields="files(id, name)",
                    pageSize=1,
                )
                .execute()
            )

            return len(response.get("files", [])) > 0

        except HttpError:
            return False

    async def get_or_create_folder(self, path: str, parent_id: str | None = None) -> str:
        """Get or create a folder at the given path.

        Args:
            path: Folder path (e.g., "2024/01")
            parent_id: Parent folder ID (uses root_folder_id if not specified)

        Returns:
            Folder ID
        """
        if not self._service:
            raise ConnectionError("Not connected to Google Drive API")

        parent_id = parent_id or self.config.get("root_folder_id")
        if not parent_id:
            raise ExportError("No parent folder specified")

        # Check cache first
        cache_key = f"{parent_id}/{path}"
        if cache_key in self._folder_cache:
            return self._folder_cache[cache_key]

        # Split path into parts and create each level
        parts = path.strip("/").split("/")
        current_parent = parent_id

        for part in parts:
            if not part:
                continue

            # Check if folder exists
            folder_id = await self._find_folder(part, current_parent)
            if folder_id:
                current_parent = folder_id
            elif self.config.get("create_folders", True):
                # Create folder
                folder_id = await self._create_folder(part, current_parent)
                current_parent = folder_id
            else:
                raise ExportError(f"Folder '{part}' not found and create_folders is disabled")

        # Cache result
        self._folder_cache[cache_key] = current_parent
        return current_parent

    async def _find_folder(self, name: str, parent_id: str) -> str | None:
        """Find a folder by name in parent."""
        try:
            query = (
                f"name = '{name}' and "
                f"'{parent_id}' in parents and "
                f"mimeType = 'application/vnd.google-apps.folder' and "
                f"trashed = false"
            )
            response = (
                self._service.files()
                .list(
                    q=query,
                    spaces="drive",
                    fields="files(id)",
                    pageSize=1,
                )
                .execute()
            )

            files = response.get("files", [])
            return files[0]["id"] if files else None

        except HttpError:
            return None

    async def _create_folder(self, name: str, parent_id: str) -> str:
        """Create a folder in parent."""
        try:
            file_metadata = {
                "name": name,
                "mimeType": "application/vnd.google-apps.folder",
                "parents": [parent_id],
            }

            folder = (
                self._service.files()
                .create(body=file_metadata, fields="id")
                .execute()
            )

            return folder.get("id", "")

        except HttpError as e:
            raise ExportError(f"Failed to create folder: {e}") from e

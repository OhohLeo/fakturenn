"""Gmail source implementation.

Provides connectivity to Gmail API for fetching emails and attachments.
Uses OAuth2 credentials stored in Vault.
"""

import base64
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Any

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.core.vault import get_vault, VaultError
from app.sources.base import (
    AuthenticationError,
    BaseSource,
    ConnectionError,
    FetchError,
)
from app.sources.models import RawAttachment, RawEmail


class GmailSource(BaseSource[RawEmail]):
    """Gmail API source for fetching emails.

    Configuration (from Source.config):
        query: Gmail search query (optional)
        sender_from: Filter by sender email (optional)
        subject_contains: Filter by subject text (optional)
        max_results: Maximum emails per fetch (default: 100)
        after_date: Only fetch emails after this date (optional)
        label_ids: Gmail labels to search (default: ["INBOX"])

    Vault paths:
        sources/gmail/{source_id}/credentials - OAuth client credentials
        sources/gmail/{source_id}/token - OAuth access/refresh tokens
    """

    def __init__(self, source_id: str, config: dict[str, Any]):
        super().__init__(source_id, config)
        self._service = None
        self._credentials = None

    async def connect(self) -> None:
        """Connect to Gmail API using OAuth credentials from Vault."""
        try:
            vault = get_vault()

            # Load OAuth tokens from Vault
            token_data = vault.get_gmail_tokens(self.source_id)
            if not token_data:
                raise AuthenticationError(
                    "No OAuth tokens found. Please complete OAuth flow first.",
                    {"source_id": self.source_id},
                )

            # Build credentials object
            self._credentials = Credentials(
                token=token_data.get("access_token"),
                refresh_token=token_data.get("refresh_token"),
                token_uri="https://oauth2.googleapis.com/token",
                client_id=token_data.get("client_id"),
                client_secret=token_data.get("client_secret"),
                scopes=["https://www.googleapis.com/auth/gmail.readonly"],
            )

            # Check if token needs refresh
            if self._credentials.expired and self._credentials.refresh_token:
                from google.auth.transport.requests import Request

                self._credentials.refresh(Request())
                # Save refreshed tokens back to Vault
                vault.store_gmail_tokens(
                    self.source_id,
                    {
                        "access_token": self._credentials.token,
                        "refresh_token": self._credentials.refresh_token,
                        "client_id": token_data.get("client_id"),
                        "client_secret": token_data.get("client_secret"),
                    },
                )

            # Build Gmail service
            self._service = build("gmail", "v1", credentials=self._credentials)
            self._connected = True

        except VaultError as e:
            raise AuthenticationError(
                f"Failed to load credentials from Vault: {e}",
                {"source_id": self.source_id},
            ) from e
        except HttpError as e:
            raise ConnectionError(
                f"Failed to connect to Gmail API: {e}",
                {"source_id": self.source_id, "error": str(e)},
            ) from e

    async def disconnect(self) -> None:
        """Disconnect from Gmail API."""
        self._service = None
        self._credentials = None
        self._connected = False

    def _build_query(self, filters: dict[str, Any] | None = None) -> str:
        """Build Gmail search query from config and filters."""
        query_parts = []

        # Start with base query from config
        if self.config.get("query"):
            query_parts.append(self.config["query"])

        # Add sender filter
        sender = (filters or {}).get("from") or self.config.get("sender_from")
        if sender:
            query_parts.append(f"from:{sender}")

        # Add subject filter
        subject = (filters or {}).get("subject_contains") or self.config.get(
            "subject_contains"
        )
        if subject:
            query_parts.append(f"subject:{subject}")

        # Add date filter
        after_date = (filters or {}).get("after_date") or self.config.get("after_date")
        if after_date:
            # Convert to Gmail format (YYYY/MM/DD)
            if isinstance(after_date, str):
                after_date = after_date.replace("-", "/")
            query_parts.append(f"after:{after_date}")

        return " ".join(query_parts)

    async def list_items(
        self,
        filters: dict[str, Any] | None = None,
        limit: int = 100,
    ) -> list[RawEmail]:
        """List emails matching the configured filters.

        Args:
            filters: Additional filters to apply
            limit: Maximum number of emails to return

        Returns:
            List of RawEmail objects with metadata (no body content)
        """
        if not self._connected or not self._service:
            raise ConnectionError("Not connected to Gmail API")

        try:
            # Build search query
            query = self._build_query(filters)
            label_ids = self.config.get("label_ids", ["INBOX"])
            max_results = min(limit, self.config.get("max_results", 100))

            # Fetch message list
            results = (
                self._service.users()
                .messages()
                .list(
                    userId="me",
                    q=query if query else None,
                    labelIds=label_ids,
                    maxResults=max_results,
                )
                .execute()
            )

            messages = results.get("messages", [])
            emails = []

            # Fetch metadata for each message
            for msg in messages:
                try:
                    email = await self._fetch_email_metadata(msg["id"])
                    emails.append(email)
                except FetchError:
                    # Skip individual failures
                    continue

            return emails

        except HttpError as e:
            raise FetchError(
                f"Failed to list emails: {e}",
                {"source_id": self.source_id, "error": str(e)},
            ) from e

    async def _fetch_email_metadata(self, message_id: str) -> RawEmail:
        """Fetch email metadata (headers only, no body)."""
        result = (
            self._service.users()
            .messages()
            .get(userId="me", id=message_id, format="metadata")
            .execute()
        )

        headers = {h["name"]: h["value"] for h in result.get("payload", {}).get("headers", [])}

        # Parse date
        date_str = headers.get("Date", "")
        try:
            email_date = parsedate_to_datetime(date_str)
        except (ValueError, TypeError):
            email_date = datetime.now()

        return RawEmail(
            id=result["id"],
            thread_id=result["threadId"],
            subject=headers.get("Subject", ""),
            from_address=headers.get("From", ""),
            to_address=headers.get("To", ""),
            date=email_date,
            snippet=result.get("snippet", ""),
            label_ids=result.get("labelIds", []),
            headers=headers,
        )

    async def get_item(self, item_id: str) -> RawEmail:
        """Get full email content including body and attachments.

        Args:
            item_id: Gmail message ID

        Returns:
            RawEmail with full body and attachment list
        """
        if not self._connected or not self._service:
            raise ConnectionError("Not connected to Gmail API")

        try:
            result = (
                self._service.users()
                .messages()
                .get(userId="me", id=item_id, format="full")
                .execute()
            )

            headers = {
                h["name"]: h["value"]
                for h in result.get("payload", {}).get("headers", [])
            }

            # Parse date
            date_str = headers.get("Date", "")
            try:
                email_date = parsedate_to_datetime(date_str)
            except (ValueError, TypeError):
                email_date = datetime.now()

            # Extract body and attachments
            body_html, body_text, attachments = self._parse_payload(
                result.get("payload", {})
            )

            return RawEmail(
                id=result["id"],
                thread_id=result["threadId"],
                subject=headers.get("Subject", ""),
                from_address=headers.get("From", ""),
                to_address=headers.get("To", ""),
                date=email_date,
                snippet=result.get("snippet", ""),
                label_ids=result.get("labelIds", []),
                headers=headers,
                body_html=body_html,
                body_text=body_text,
                attachments=attachments,
            )

        except HttpError as e:
            raise FetchError(
                f"Failed to fetch email {item_id}: {e}",
                {"source_id": self.source_id, "message_id": item_id, "error": str(e)},
            ) from e

    def _parse_payload(
        self, payload: dict[str, Any]
    ) -> tuple[str | None, str | None, list[RawAttachment]]:
        """Parse email payload to extract body and attachments."""
        body_html = None
        body_text = None
        attachments = []

        def process_part(part: dict[str, Any]) -> None:
            nonlocal body_html, body_text

            mime_type = part.get("mimeType", "")
            body_data = part.get("body", {})
            filename = part.get("filename", "")

            # Check for attachment
            if body_data.get("attachmentId"):
                attachments.append(
                    RawAttachment(
                        id=body_data["attachmentId"],
                        filename=filename,
                        mime_type=mime_type,
                        size=body_data.get("size", 0),
                    )
                )
            elif body_data.get("data"):
                # Decode body content
                content = base64.urlsafe_b64decode(body_data["data"]).decode(
                    "utf-8", errors="replace"
                )
                if mime_type == "text/html":
                    body_html = content
                elif mime_type == "text/plain":
                    body_text = content

            # Process nested parts
            for sub_part in part.get("parts", []):
                process_part(sub_part)

        process_part(payload)
        return body_html, body_text, attachments

    async def download_attachment(
        self,
        item_id: str,
        attachment_id: str,
    ) -> bytes:
        """Download an attachment from an email.

        Args:
            item_id: Gmail message ID
            attachment_id: Attachment ID

        Returns:
            Attachment content as bytes
        """
        if not self._connected or not self._service:
            raise ConnectionError("Not connected to Gmail API")

        try:
            result = (
                self._service.users()
                .messages()
                .attachments()
                .get(userId="me", messageId=item_id, id=attachment_id)
                .execute()
            )

            data = result.get("data", "")
            return base64.urlsafe_b64decode(data)

        except HttpError as e:
            raise FetchError(
                f"Failed to download attachment: {e}",
                {
                    "source_id": self.source_id,
                    "message_id": item_id,
                    "attachment_id": attachment_id,
                    "error": str(e),
                },
            ) from e

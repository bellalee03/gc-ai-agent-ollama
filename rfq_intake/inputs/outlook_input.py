"""
inputs/outlook_input.py
──────────────────────────────────────────────────────────────────────────────
Input source that reads emails from a specific Outlook folder via Microsoft Graph.

For Phase 1 local MVP, this reads recent emails synchronously (no webhook).
You run the script manually — it fetches the latest N emails from the folder,
normalizes them into RawRequest objects, and feeds them into the pipeline.

Prerequisites:
  - AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET in .env
  - OUTLOOK_USER_ID: the mailbox email address
  - OUTLOOK_FOLDER_NAME: the Outlook folder to read from (default: RFQ_BOT)
  - Azure App Registration must have Mail.Read application permission (admin consented)

Example usage:
    source = OutlookEmailInput(max_emails=10)
    requests = source.fetch()
"""

import json
import logging
import os
import httpx
from datetime import datetime, timezone
from typing import Optional
import re

from inputs.base import BaseInputSource
from core.models import RawRequest
from core.config import settings

logger = logging.getLogger(__name__)

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
TOKEN_URL = f"https://login.microsoftonline.com/{settings.AZURE_TENANT_ID}/oauth2/v2.0/token"
DELTA_LINK_FILE = "outlook_delta_link.json"


class OutlookEmailInput(BaseInputSource):

    def __init__(self, max_emails: int = 20, use_delta: bool = True, skip_already_seen: set = None):
        """
        Args:
            max_emails:        How many recent emails to fetch (newest first).
            use_delta:         If True, use delta query to fetch only new emails.
            skip_already_seen: Optional set of message IDs to skip (dedup).
        """
        self.max_emails = max_emails
        self.use_delta = use_delta
        self.skip_already_seen = skip_already_seen or set()
        self._token: Optional[str] = None

    # ─────────────────────────────────────────────
    # Public interface
    # ─────────────────────────────────────────────

    def fetch(self) -> list[RawRequest]:
        """Fetches emails synchronously and returns normalized RawRequest list."""
        if not settings.AZURE_CLIENT_ID or not settings.OUTLOOK_USER_ID:
            raise RuntimeError(
                "Outlook input requires AZURE_TENANT_ID, AZURE_CLIENT_ID, "
                "AZURE_CLIENT_SECRET, and OUTLOOK_USER_ID in your .env"
            )

        self._token = self._get_token()
        folder_id = self._get_folder_id(settings.OUTLOOK_FOLDER_NAME)

        if not folder_id:
            logger.error(f"Folder '{settings.OUTLOOK_FOLDER_NAME}' not found in mailbox.")
            return []

        messages = self._list_messages(folder_id)
        requests = []

        for msg in messages:
            mid = msg.get("id", "")
            if mid in self.skip_already_seen:
                logger.info(f"Skipping already-seen message: {mid}")
                continue

            full_msg = self._get_full_message(mid)
            if not full_msg:
                continue

            raw = self._normalize(full_msg)
            if raw:
                requests.append(raw)

        logger.info(f"OutlookEmailInput: prepared {len(requests)} request(s)")
        return requests

    # ─────────────────────────────────────────────
    # Graph API helpers (synchronous / httpx)
    # ─────────────────────────────────────────────

    def _get_token(self) -> str:
        resp = httpx.post(
            TOKEN_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": settings.AZURE_CLIENT_ID,
                "client_secret": settings.AZURE_CLIENT_SECRET,
                "scope": "https://graph.microsoft.com/.default",
            },
        )
        resp.raise_for_status()
        return resp.json()["access_token"]

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._token}"}

    def _get_folder_id(self, folder_name: str) -> Optional[str]:
        url = f"{GRAPH_BASE}/users/{settings.OUTLOOK_USER_ID}/mailFolders"
        resp = httpx.get(url, headers=self._headers(), params={"$top": "50"})
        if resp.status_code != 200:
            logger.error(f"Failed to list folders: {resp.status_code}")
            return None
        for f in resp.json().get("value", []):
            if f.get("displayName", "").lower() == folder_name.lower():
                return f["id"]
        return None

    def _load_delta_link(self, folder_id: str) -> Optional[str]:
        """로컬 파일에서 저장된 delta link 읽어오기. 파일 없으면 None 반환."""
        if not os.path.exists(DELTA_LINK_FILE):
            return None
        try:
            with open(DELTA_LINK_FILE, "r") as f:
                data = json.load(f)
            return data.get(folder_id)
        except Exception:
            return None

    def _save_delta_link(self, folder_id: str, delta_link: str) -> None:
        """delta link를 로컬 파일에 저장. folder_id를 키로 사용해서 여러 폴더 지원 가능."""
        data = {}
        if os.path.exists(DELTA_LINK_FILE):
            try:
                with open(DELTA_LINK_FILE, "r") as f:
                    data = json.load(f)
            except Exception:
                pass
        data[folder_id] = delta_link
        with open(DELTA_LINK_FILE, "w") as f:
            json.dump(data, f)

    def _list_messages(self, folder_id: str) -> list[dict]:
        """
        use_delta=True 이면 delta query로 변경분만 가져옴.
        use_delta=False 이면 기존 방식으로 최근 N개 가져옴.
        """
        if not self.use_delta:
            # 기존 방식
            url = (
                f"{GRAPH_BASE}/users/{settings.OUTLOOK_USER_ID}"
                f"/mailFolders/{folder_id}/messages"
            )
            params = {
                "$top": str(self.max_emails),
                "$orderby": "receivedDateTime desc",
                "$select": "id,subject,from,receivedDateTime,conversationId",
            }
            resp = httpx.get(url, headers=self._headers(), params=params)
            if resp.status_code != 200:
                logger.error(f"Failed to list messages: {resp.status_code}")
                return []
            return resp.json().get("value", [])

        # delta query 방식
        delta_link = self._load_delta_link(folder_id)

        if delta_link:
            logger.info("Using delta link — fetching new messages only.")
            url = delta_link
        else:
            logger.info("No delta link found — fetching full message list.")
            url = (
                f"{GRAPH_BASE}/users/{settings.OUTLOOK_USER_ID}"
                f"/mailFolders/{folder_id}/messages/delta"
            )

        params = {"$select": "id,subject,from,receivedDateTime,conversationId"}
        all_messages = []

        while url:
            resp = httpx.get(url, headers=self._headers(), params=params)
            params = {}  # 두 번째 요청부터 params 불필요

            if resp.status_code != 200:
                logger.error(f"Delta query failed: {resp.status_code} {resp.text}")
                break

            data = resp.json()
            all_messages.extend(data.get("value", []))

            if "@odata.nextLink" in data:
                url = data["@odata.nextLink"]
            elif "@odata.deltaLink" in data:
                self._save_delta_link(folder_id, data["@odata.deltaLink"])
                logger.info(f"Delta link saved. {len(all_messages)} new message(s) found.")
                break
            else:
                break

        return all_messages

    def _get_full_message(self, message_id: str) -> Optional[dict]:
        url = f"{GRAPH_BASE}/users/{settings.OUTLOOK_USER_ID}/messages/{message_id}"
        params = {"$select": "id,subject,from,receivedDateTime,body"}
        resp = httpx.get(url, headers=self._headers(), params=params)
        if resp.status_code == 200:
            return resp.json()
        logger.error(f"Failed to fetch message {message_id}: {resp.status_code}")
        return None

    # ─────────────────────────────────────────────
    # Normalization
    # ─────────────────────────────────────────────

    def _normalize(self, msg: dict) -> Optional[RawRequest]:
        sender          = msg.get("from", {}).get("emailAddress", {}).get("address", "")
        subject         = msg.get("subject", "")
        received        = msg.get("receivedDateTime", "")
        body_html       = msg.get("body", {}).get("content", "")
        body_text       = _strip_html(body_html)
        conversation_id = msg.get("conversationId", "")

        full_content = f"SUBJECT: {subject}\n\nBODY:\n{body_text}"

        if not body_text.strip():
            return None

        return RawRequest(
            content=full_content,
            source_type="email",
            source_name=settings.OUTLOOK_FOLDER_NAME,
            received_time=received,
            sender=sender,
            subject=subject,
            conversation_id=conversation_id,
        )


def _strip_html(html: str) -> str:
    """Minimal HTML tag stripper for email bodies."""
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

"""
inputs/manual_input.py
──────────────────────────────────────────────────────────────────────────────
Input source for non-email content. Supports four patterns:

  1. Inline text   — pass a string directly in code (good for testing)
  2. Text file(s)  — pass a .txt file path or a directory of .txt files
  3. Google Doc    — pass a Google Doc ID; content is fetched via Docs API
  4. Stdin         — pipe text in from the terminal

All four normalize into RawRequest objects that feed into the same
Claude parsing pipeline as Outlook emails.

Example usage:
    # Inline text
    ManualTextInput(text="Shipment from Dallas TX to Phoenix AZ...")

    # File or folder
    ManualTextInput(file_path="sample_data/")
    ManualTextInput(file_path="rfq_notes.txt")

    # Google Doc (doc_id from URL: .../document/d/DOC_ID/edit)
    ManualTextInput(google_doc_id="1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74...")

    # Stdin (pipe text in or type interactively)
    ManualTextInput(use_stdin=True)
"""

import os
import sys
import logging
from datetime import datetime, timezone
from typing import Optional

from inputs.base import BaseInputSource
from core.models import RawRequest

logger = logging.getLogger(__name__)


class ManualTextInput(BaseInputSource):

    def __init__(
        self,
        text: Optional[str] = None,
        texts: Optional[list[str]] = None,
        file_path: Optional[str] = None,
        google_doc_id: Optional[str] = None,
        use_stdin: bool = False,
        source_name: str = "manual_text",
        google_service_account_json: Optional[str] = None,
    ):
        self.text = text
        self.texts = texts
        self.file_path = file_path
        self.google_doc_id = google_doc_id
        self.use_stdin = use_stdin
        self.source_name = source_name
        self.google_service_account_json = google_service_account_json

        if not any([text, texts, file_path, google_doc_id, use_stdin]):
            raise ValueError(
                "ManualTextInput requires at least one of: "
                "text, texts, file_path, google_doc_id, or use_stdin=True"
            )

    def fetch(self) -> list[RawRequest]:
        requests = []
        now = datetime.now(tz=timezone.utc).isoformat()

        if self.text:
            requests += self._from_inline(self.text, now)

        if self.texts:
            for i, t in enumerate(self.texts):
                if t.strip():
                    requests.append(RawRequest(
                        content=t.strip(),
                        source_type="manual_text",
                        source_name=f"{self.source_name}[{i+1}]",
                        received_time=now,
                    ))

        if self.file_path:
            requests += self._from_file(self.file_path, now)

        if self.google_doc_id:
            result = self._from_google_doc(self.google_doc_id, now)
            if result:
                requests.append(result)

        if self.use_stdin:
            result = self._from_stdin(now)
            if result:
                requests.append(result)

        logger.info(f"ManualTextInput: prepared {len(requests)} request(s)")
        return requests

    # ─────────────────────────────────────────────
    # Source handlers
    # ─────────────────────────────────────────────

    def _from_inline(self, text: str, now: str) -> list[RawRequest]:
        if not text.strip():
            return []
        return [RawRequest(
            content=text.strip(),
            source_type="manual_text",
            source_name=self.source_name,
            received_time=now,
        )]

    def _from_file(self, path: str, now: str) -> list[RawRequest]:
        results = []
        if os.path.isdir(path):
            txt_files = sorted(f for f in os.listdir(path) if f.endswith(".txt"))
            if not txt_files:
                logger.warning(f"No .txt files found in: {path}")
            for fname in txt_files:
                content = _read_file(os.path.join(path, fname))
                if content:
                    results.append(RawRequest(
                        content=content,
                        source_type="manual_text",
                        source_name=fname,
                        received_time=now,
                    ))
        elif os.path.isfile(path):
            content = _read_file(path)
            if content:
                results.append(RawRequest(
                    content=content,
                    source_type="manual_text",
                    source_name=os.path.basename(path),
                    received_time=now,
                ))
        else:
            logger.error(f"Path not found: {path}")
        return results

    def _from_google_doc(self, doc_id: str, now: str) -> Optional[RawRequest]:
        """
        Reads the plain text content of a Google Doc by document ID.
        Requires the service account to have Viewer access to the document.
        Enable the Google Docs API in your Google Cloud project first.
        """
        from core.config import settings
        sa_file = self.google_service_account_json or settings.GOOGLE_SERVICE_ACCOUNT_JSON

        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build

            creds = service_account.Credentials.from_service_account_file(
                sa_file,
                scopes=["https://www.googleapis.com/auth/documents.readonly"],
            )
            service = build("docs", "v1", credentials=creds, cache_discovery=False)
            doc = service.documents().get(documentId=doc_id).execute()

            title = doc.get("title", "Untitled Google Doc")
            text = _extract_google_doc_text(doc)

            if not text.strip():
                logger.warning(f"Google Doc '{title}' appears to be empty.")
                return None

            logger.info(f"Loaded Google Doc: '{title}' ({len(text)} chars)")
            return RawRequest(
                content=text.strip(),
                source_type="google_doc",
                source_name=title,
                received_time=now,
            )

        except Exception as e:
            logger.error(f"Failed to read Google Doc {doc_id}: {e}")
            return None

    def _from_stdin(self, now: str) -> Optional[RawRequest]:
        """
        Reads text from stdin.
        Works with piped input: echo "RFQ text" | python main.py
        Or interactively: type/paste then Ctrl+D (Mac/Linux) or Ctrl+Z (Windows).
        """
        try:
            if sys.stdin.isatty():
                print("Paste your shipment request text below.")
                print("Press Enter twice, then Ctrl+D (Mac/Linux) or Ctrl+Z then Enter (Windows):\n")

            text = sys.stdin.read().strip()
            if not text:
                logger.warning("No text received from stdin.")
                return None

            logger.info(f"Received {len(text)} chars from stdin.")
            return RawRequest(
                content=text,
                source_type="manual_text",
                source_name="stdin",
                received_time=now,
            )
        except Exception as e:
            logger.error(f"Failed to read from stdin: {e}")
            return None


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _read_file(path: str) -> Optional[str]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read().strip()
        if not content:
            logger.warning(f"File is empty: {path}")
            return None
        return content
    except OSError as e:
        logger.error(f"Could not read file {path}: {e}")
        return None


def _extract_google_doc_text(doc: dict) -> str:
    """
    Google Docs 문서에서 텍스트 추출.
    일반 텍스트 + 표 셀 내용 모두 포함.
    """
    texts = []

    def extract_from_content(content_list):
        for element in content_list:
            if "paragraph" in element:
                para = element["paragraph"]
                for elem in para.get("elements", []):
                    text_run = elem.get("textRun", {})
                    t = text_run.get("content", "")
                    if t:
                        texts.append(t)

            elif "table" in element:
                table = element["table"]
                for row in table.get("tableRows", []):
                    row_texts = []
                    for cell in row.get("tableCells", []):
                        cell_text = []
                        for cell_elem in cell.get("content", []):
                            if "paragraph" in cell_elem:
                                para = cell_elem["paragraph"]
                                for elem in para.get("elements", []):
                                    text_run = elem.get("textRun", {})
                                    t = text_run.get("content", "").strip()
                                    if t:
                                        cell_text.append(t)
                        if cell_text:
                            row_texts.append(" ".join(cell_text))
                    if row_texts:
                        if len(row_texts) == 2:
                            texts.append(f"{row_texts[0]}: {row_texts[1]}\n")
                        else:
                            texts.append(" | ".join(row_texts) + "\n")

    body = doc.get("body", {})
    extract_from_content(body.get("content", []))

    return "".join(texts)


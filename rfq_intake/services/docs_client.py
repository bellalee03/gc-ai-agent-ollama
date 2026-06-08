"""
services/docs_client.py
Google Docs 내용을 완전히 비우는 클라이언트.
archive.py 에서 매일 밤 호출됨.
"""

import logging
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from core.config import settings

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/spreadsheets",
]


class DocsClient:
    def __init__(self):
        creds = service_account.Credentials.from_service_account_file(
            settings.GOOGLE_SERVICE_ACCOUNT_JSON,
            scopes=SCOPES,
        )
        service = build("docs", "v1", credentials=creds, cache_discovery=False)
        self._docs = service.documents()

    def clear_document(self, doc_id: str) -> bool:
        """
        Google Doc 내용을 완전히 비움.
        헤더/푸터는 유지, 본문 텍스트만 삭제.
        성공 여부 반환.
        """
        try:
            # 현재 문서 읽기
            doc = self._docs.get(documentId=doc_id).execute()
            body = doc.get("body", {})
            content = body.get("content", [])

            if not content:
                logger.info("Document is already empty.")
                return True

            # 문서 전체 텍스트 길이 계산
            end_index = content[-1].get("endIndex", 1)

            # 본문이 1자 이하면 이미 빔
            if end_index <= 1:
                logger.info("Document is already empty.")
                return True

            # 본문 전체 삭제 (index 1부터 end_index-1까지)
            requests = [{
                "deleteContentRange": {
                    "range": {
                        "startIndex": 1,
                        "endIndex": end_index - 1,
                    }
                }
            }]

            self._docs.batchUpdate(
                documentId=doc_id,
                body={"requests": requests}
            ).execute()

            logger.info(f"Document cleared: {doc_id}")
            return True

        except HttpError as e:
            logger.error(f"Failed to clear document {doc_id}: {e}")
            return False

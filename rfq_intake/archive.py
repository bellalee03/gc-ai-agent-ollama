"""
archive.py
──────────────────────────────────────────────────────
매일 11:59 PM에 Windows 작업 스케줄러가 자동 실행.
RFQ_Output 데이터를 RFQ_Database로 이동하고
RFQ_Output은 헤더만 남기고 초기화.
"""

import sys
import logging
from datetime import datetime

from utils.logger import setup_logging
setup_logging()

logger = logging.getLogger(__name__)

from core.config import settings
from services.sheets_client import SheetsClient


def main():
    print("=" * 55)
    print("  RFQ Archive + Reset")
    print(f"  {datetime.now().strftime('%Y-%m-%d  %H:%M:%S')}")
    print("=" * 55)

    try:
        # ── 1. Sheets 아카이브 + 리셋 ─────────────────
        sheets = SheetsClient()
        count = sheets.archive_and_reset()

        if count == 0:
            print("\n  오늘 Sheets 데이터 없음 — 아카이브 스킵")
        else:
            print(f"\n  ✅  {count}개 행 → RFQ_Database 이동 완료")
            print("  ✅  RFQ_Output 초기화 완료")

        # ── 2. Google Doc 비우기 ───────────────────────
        doc_id = settings.GOOGLE_DOC_ID
        if doc_id:
            from services.docs_client import DocsClient
            docs = DocsClient()
            success = docs.clear_document(doc_id)
            if success:
                print("  ✅  Google Doc 초기화 완료")
            else:
                print("  ⚠️   Google Doc 초기화 실패 — 수동 확인 필요")
        else:
            print("  ⏭️   GOOGLE_DOC_ID 미설정 — Doc 초기화 스킵")

        print(f"\n  완료: {datetime.now().strftime('%H:%M:%S')}")
        print("=" * 55)

    except Exception as e:
        logger.exception(f"Archive failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

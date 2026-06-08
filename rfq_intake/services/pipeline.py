import logging

from core.models import RawRequest, QuotedRFQ
from services.claude_parser import ClaudeParser
from services.rate_matcher import RateMatcher
from services.sheets_client import SheetsClient

logger = logging.getLogger(__name__)


class Pipeline:
    def __init__(self, parser: ClaudeParser, matcher: RateMatcher, sheets: SheetsClient):
        self.parser  = parser
        self.matcher = matcher
        self.sheets  = sheets
        self._quote_counter = 0  # 배치 시작 전 초기화

    def run_one(self, raw: RawRequest) -> list[QuotedRFQ]:
        parsed_list = self.parser.parse(raw)
        results = []

        for parsed in parsed_list:
            from datetime import datetime, timezone
            now = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

            conversation_id = getattr(raw, "conversation_id", None)
            lead_id = conversation_id[:12] if conversation_id else None

            existing = None
            if lead_id:
                existing = self.sheets.find_by_lead_id(lead_id)

            if existing:
                # 팔로업 → RFQ_Database row 업데이트
                result = self.matcher.price(parsed)
                result.lead_id = lead_id
                result.last_updated = now
                self.sheets.update_null_fields(existing, result)
            else:
                # 새 RFQ → Quote ID 생성 후 RFQ_Output 추가
                result = self.matcher.price(parsed)
                result.lead_id = lead_id
                result.thread_count = 1
                result.last_updated = now
                result.received_time = raw.received_time
                self._quote_counter += 1
                result.quote_id = self.sheets.generate_quote_id(self._quote_counter)
                self.sheets.append_result(result)

            results.append(result)

        return results

    def run_batch(self, raw_requests: list[RawRequest]) -> list[QuotedRFQ]:
        # 배치 시작 시 한 번만 DB에서 마지막 번호 읽기
        self._quote_counter = self.sheets.get_last_quote_number()
        logger.info(f"Quote counter initialized: {self._quote_counter}")

        all_results = []
        total = len(raw_requests)
        for i, raw in enumerate(raw_requests, 1):
            logger.info(f"─── Processing {i}/{total} ───")
            try:
                results = self.run_one(raw)
                all_results.extend(results)
            except Exception as e:
                logger.exception(f"Error on request {i}/{total}: {e}")
        logger.info(f"─── Batch complete: {len(all_results)} result(s) ───")
        return all_results

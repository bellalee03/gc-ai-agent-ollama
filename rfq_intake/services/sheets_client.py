import logging
from typing import Optional

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from core.config import settings
from core.models import RateRecord, QuotedRFQ

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/documents",
]

SHEET_HEADERS = [
    "Quote ID",              # A
    "Requested Date",        # B
    "담당 영업팀",             # C
    "Partner/Customer",      # D
    "Customer",              # E
    "Mode",                  # F
    "POL",                   # G
    "POD",                   # H
    "Delivery To",           # I
    "Pickup From",           # J
    "Item",                  # K
    "물동량",                  # L
    "Incoterms",             # M
    "Additional Info",       # N
    "Estimated Quote ($)",   # O
    "Pricing Notes",         # P
    "Status",                # Q
    "Last Updated",          # R
    "Lead ID",               # S
    "Thread Count",          # T
]

RATE_COL_ORIGIN         = 0
RATE_COL_DEST           = 1
RATE_COL_MODE           = 2
RATE_COL_BASE_RATE      = 3
RATE_COL_SURCHARGE      = 4
RATE_COL_MINIMUM        = 5
RATE_COL_NOTES          = 6
RATE_COL_EFFECTIVE_DATE = 7


class SheetsClient:
    def __init__(self):
        creds = service_account.Credentials.from_service_account_file(
            settings.GOOGLE_SERVICE_ACCOUNT_JSON,
            scopes=SCOPES,
        )
        service = build("sheets", "v4", credentials=creds, cache_discovery=False)
        self._sheet = service.spreadsheets()
        self._sheet_id = settings.GOOGLE_SHEET_ID
        self._ensure_output_headers()

    def load_rates(self) -> list[RateRecord]:
        tab = settings.RATE_MASTER_TAB
        try:
            result = self._sheet.values().get(
                spreadsheetId=self._sheet_id,
                range=f"{tab}!B:I",
            ).execute()
        except HttpError as e:
            logger.error(f"Failed to read Rate_Master: {e}")
            return []

        rows = result.get("values", [])
        if not rows:
            logger.warning("Rate_Master tab is empty.")
            return []

        records = []
        for i, row in enumerate(rows[1:], start=2):
            row = row + [""] * (8 - len(row))

            origin = row[RATE_COL_ORIGIN].strip()
            dest   = row[RATE_COL_DEST].strip()
            mode   = row[RATE_COL_MODE].strip()

            if not origin or not dest or not mode:
                logger.debug(f"Rate_Master row {i}: skipping incomplete row")
                continue

            records.append(RateRecord(
                origin=origin,
                destination=dest,
                mode=mode,
                base_rate=_to_float(row[RATE_COL_BASE_RATE]),
                surcharge=_to_float(row[RATE_COL_SURCHARGE]),
                minimum_charge=_to_float(row[RATE_COL_MINIMUM]),
                notes=row[RATE_COL_NOTES].strip(),
                effective_date=row[RATE_COL_EFFECTIVE_DATE].strip(),
            ))

        logger.info(f"Loaded {len(records)} rate record(s) from Rate_Master.")
        return records

    def append_result(self, result: QuotedRFQ) -> None:
        tab = settings.RFQ_OUTPUT_TAB
        try:
            self._sheet.values().append(
                spreadsheetId=self._sheet_id,
                range=f"{tab}!B2",
                valueInputOption="RAW",
                insertDataOption="INSERT_ROWS",
                body={"values": [result.to_sheet_row()]},
            ).execute()
            logger.info(f"Row written: {result.quote_id} | {result.customer} | {result.status}")
        except HttpError as e:
            logger.error(f"Failed to append row: {e}")
            raise

    def find_by_lead_id(self, lead_id: str) -> Optional[dict]:
        """
        RFQ_Database 탭에서 Lead ID 로 기존 row 검색.
        status 관계없이 일치하는 row 반환.
        없으면 None 반환.
        """
        tab = settings.RFQ_ARCHIVE_TAB
        try:
            result = self._sheet.values().get(
                spreadsheetId=self._sheet_id,
                range=f"{tab}!B:U",
            ).execute()
        except HttpError as e:
            logger.error(f"Failed to read {tab}: {e}")
            return None

        rows = result.get("values", [])
        if len(rows) <= 1:
            return None

        header = rows[0]
        try:
            lead_id_col = header.index("Lead ID")
        except ValueError:
            logger.error("Lead ID column not found")
            return None

        for i, row in enumerate(rows[1:], start=3):
            row = row + [""] * (len(header) - len(row))
            if row[lead_id_col] == lead_id:
                return {
                    "row_index": i,
                    "values": row,
                    "header": header,
                    "tab": tab,
                }

        return None

    def update_null_fields(self, existing: dict, rfq: QuotedRFQ) -> None:
        """
        팔로업 이메일이 오면 항상 최신 값으로 덮어씀.
        단, Received Date / Lead ID 는 처음 값 유지.
        Thread Count 는 +1.
        Last Updated 는 항상 현재 시간으로 갱신.
        """
        tab       = existing["tab"]
        row_index = existing["row_index"]
        values    = existing["values"]
        header    = existing["header"]
        new_row   = rfq.to_sheet_row()

        updated_row = list(values)
        updated_row = updated_row + [""] * (len(header) - len(updated_row))

        PRESERVE = ["Requested Date", "Lead ID"]

        for i, col_name in enumerate(header):
            new_val = new_row[i] if i < len(new_row) else ""

            if col_name in PRESERVE:
                continue

            if col_name == "Thread Count":
                try:
                    updated_row[i] = int(updated_row[i] or 0) + 1
                except ValueError:
                    updated_row[i] = 2
                continue

            if new_val:
                updated_row[i] = new_val

        try:
            self._sheet.values().update(
                spreadsheetId=self._sheet_id,
                range=f"{tab}!B{row_index}",
                valueInputOption="RAW",
                body={"values": [updated_row]},
            ).execute()
            logger.info(f"Row {row_index} updated with latest data")
        except HttpError as e:
            logger.error(f"Failed to update row {row_index}: {e}")

    def archive_and_reset(self) -> int:
        """
        RFQ_Output 탭의 데이터를 RFQ_Database 탭으로 복사하고
        RFQ_Output은 헤더만 남기고 초기화.
        복사된 행 수를 반환.
        """
        output_tab  = settings.RFQ_OUTPUT_TAB
        archive_tab = settings.RFQ_ARCHIVE_TAB

        # 1. RFQ_Output 전체 읽기
        try:
            result = self._sheet.values().get(
                spreadsheetId=self._sheet_id,
                range=f"{output_tab}!B:Z",
            ).execute()
        except HttpError as e:
            logger.error(f"Failed to read {output_tab}: {e}")
            return 0

        rows = result.get("values", [])
        if len(rows) <= 1:
            logger.info("RFQ_Output has no data rows to archive.")
            return 0

        header = rows[0]
        data_rows = rows[1:]

        # 2. RFQ_Database 탭 없으면 자동 생성
        self._ensure_archive_tab(archive_tab, header)

        # 3. RFQ_Database에 데이터 행 추가
        try:
            self._sheet.values().append(
                spreadsheetId=self._sheet_id,
                range=f"{archive_tab}!B2",
                valueInputOption="RAW",
                insertDataOption="INSERT_ROWS",
                body={"values": data_rows},
            ).execute()
            logger.info(f"Archived {len(data_rows)} row(s) to {archive_tab}.")
        except HttpError as e:
            logger.error(f"Failed to append to {archive_tab}: {e}")
            return 0

        # 4. RFQ_Output 초기화 (헤더만 남김)
        try:
            self._sheet.values().clear(
                spreadsheetId=self._sheet_id,
                range=f"{output_tab}!B3:Z10000",
            ).execute()
            logger.info(f"{output_tab} cleared. Header preserved.")
        except HttpError as e:
            logger.error(f"Failed to clear {output_tab}: {e}")

        return len(data_rows)

    def _ensure_archive_tab(self, tab_name: str, header: list) -> None:
        """
        RFQ_Database 탭이 없으면 자동으로 생성하고 헤더 씀.
        있으면 아무것도 안 함.
        """
        try:
            result = self._sheet.values().get(
                spreadsheetId=self._sheet_id,
                range=f"{tab_name}!B2:B2",
            ).execute()
            # 탭 존재함
            if not result.get("values"):
                # 탭은 있는데 헤더 없음
                self._sheet.values().update(
                    spreadsheetId=self._sheet_id,
                    range=f"{tab_name}!B2",
                    valueInputOption="RAW",
                    body={"values": [header]},
                ).execute()
        except HttpError:
            # 탭 없음 → 생성
            requests = [{
                "addSheet": {
                    "properties": {"title": tab_name}
                }
            }]
            self._sheet.batchUpdate(
                spreadsheetId=self._sheet_id,
                body={"requests": requests}
            ).execute()
            # 헤더 쓰기
            self._sheet.values().update(
                spreadsheetId=self._sheet_id,
                range=f"{tab_name}!B2",
                valueInputOption="RAW",
                body={"values": [header]},
            ).execute()
            logger.info(f"Created new tab: {tab_name}")

    def _ensure_output_headers(self) -> None:
        tab = settings.RFQ_OUTPUT_TAB
        try:
            result = self._sheet.values().get(
                spreadsheetId=self._sheet_id,
                range=f"{tab}!B2:U2",
            ).execute()
            if not result.get("values"):
                self._sheet.values().update(
                    spreadsheetId=self._sheet_id,
                    range=f"{tab}!B2",
                    valueInputOption="RAW",
                    body={"values": [SHEET_HEADERS]},
                ).execute()
                logger.info(f"Header row written to {tab}.")
        except HttpError as e:
            logger.error(f"Failed to check/write headers: {e}")


    def get_last_quote_number(self) -> int:
        """
        현재 RFQ_Output 과 RFQ_Database 에서
        가장 높은 Quote ID 번호를 반환.
        없으면 0 반환.
        """
        last_num = 0
        for tab in [settings.RFQ_OUTPUT_TAB, settings.RFQ_ARCHIVE_TAB]:
            try:
                result = self._sheet.values().get(
                    spreadsheetId=self._sheet_id,
                    range=f"{tab}!B:B",
                ).execute()
                rows = result.get("values", [])
                for row in rows[1:]:
                    if not row:
                        continue
                    cell = str(row[0]).strip()
                    if cell.startswith("GC-"):
                        try:
                            num = int(cell.replace("GC-", ""))
                            if num > last_num:
                                last_num = num
                        except ValueError:
                            continue
            except Exception as e:
                logger.warning(f"get_last_quote_number: {e}")
                continue
        return last_num

    def generate_quote_id(self, current_counter: int) -> str:
        """
        외부에서 관리하는 카운터 기반으로 Quote ID 생성.
        배치 처리 중 중복 방지.
        """
        return f"GC-{current_counter:04d}"


def _to_float(value: str) -> Optional[float]:
    if not value:
        return None
    cleaned = value.replace("$", "").replace(",", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return None

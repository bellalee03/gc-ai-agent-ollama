"""One-time script: update D1 header from 'Platform' to 'Partner/Customer' in both tabs."""
import sys
from google.oauth2 import service_account
from googleapiclient.discovery import build
from core.config import settings

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
]

creds = service_account.Credentials.from_service_account_file(
    settings.GOOGLE_SERVICE_ACCOUNT_JSON, scopes=SCOPES
)
service = build("sheets", "v4", credentials=creds, cache_discovery=False)
sheet = service.spreadsheets()

tabs = [settings.RFQ_OUTPUT_TAB, settings.RFQ_ARCHIVE_TAB]

for tab in tabs:
    try:
        result = sheet.values().get(
            spreadsheetId=settings.GOOGLE_SHEET_ID,
            range=f"{tab}!E2",
        ).execute()
        current = result.get("values", [[""]])[0][0] if result.get("values") else ""
        if current != "Partner/Customer":
            sheet.values().update(
                spreadsheetId=settings.GOOGLE_SHEET_ID,
                range=f"{tab}!E2",
                valueInputOption="RAW",
                body={"values": [["Partner/Customer"]]},
            ).execute()
            print(f"[{tab}] D1: '{current}' -> 'Partner/Customer'")
        else:
            print(f"[{tab}] D1: already 'Partner/Customer', skipped")
    except Exception as e:
        print(f"[{tab}] Error: {e}", file=sys.stderr)

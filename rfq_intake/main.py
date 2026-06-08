"""
main.py
──────────────────────────────────────────────────────────────────────────────
RFQ Intake + Quote Estimation  —  Phase 1 Local MVP

Run this script manually to process RFQ requests.
Configure your input source(s) in the INPUT CONFIGURATION section below.

USAGE:
    python main.py

SUPPORTED INPUT SOURCES (configure below):
    A. Inline text    — paste text directly in this file
    B. Text file(s)   — point to a .txt file or folder of .txt files
    C. Google Doc     — provide a Google Doc ID
    D. Stdin          — pipe text in from the terminal
    E. Outlook email  — reads from your RFQ_BOT Outlook folder

You can mix and match — add multiple sources and all results go to the
same RFQ_Output sheet.
"""

import sys
from datetime import datetime

# ── Logging must be set up first, before any other imports ────────────────────
from utils.logger import setup_logging
setup_logging()

import logging
logger = logging.getLogger(__name__)

# ── Application imports ───────────────────────────────────────────────────────
from core.models import RawRequest
from inputs.manual_input import ManualTextInput
from services.claude_parser import ClaudeParser
from services.sheets_client import SheetsClient
from services.rate_matcher import RateMatcher
from services.pipeline import Pipeline
from core.config import settings


def main():
    print("=" * 65)
    print("  RFQ Intake + Quote Estimation  —  Phase 1 MVP")
    print(f"  {datetime.now().strftime('%Y-%m-%d  %H:%M:%S')}")
    print("=" * 65)

    # ══════════════════════════════════════════════════════════════════════
    # INPUT CONFIGURATION
    # ══════════════════════════════════════════════════════════════════════
    # Uncomment the source(s) you want to use.
    # All sources collect into raw_requests — then the pipeline runs once.
    # ══════════════════════════════════════════════════════════════════════

    raw_requests: list[RawRequest] = []

    # ── SOURCE A: Inline text ─────────────────────────────────────────────
    # Best for: quick testing, one-off jobs, pasting from emails or chats.
    # Add as many strings to `texts` as you need. Each becomes one request.

    # source_a = ManualTextInput(
    #     texts=[
    #         """
    #         RFQ Request — Need quote ASAP
    #
    #         Pickup: Dallas, TX
    #         Delivery: Phoenix, AZ
    #         Equipment: 53-ft dry van, full truckload
    #         Weight: 38,500 lbs
    #         Pallets: 24
    #         Ready date: tomorrow morning
    #         No special requirements.
    #         """,
    #
    #         # Add more requests here — each string is one RFQ:
    #         # """
    #         # Another request text here
    #         # """,
    #     ],
    #     source_name="inline_text",
    # )
    # raw_requests.extend(source_a.fetch())

    # ── SOURCE B: Text file(s) ────────────────────────────────────────────
    # Best for: processing saved RFQ notes or a batch of .txt files.
    # Supports a single file or an entire folder (all .txt files in it).

    # source_b = ManualTextInput(
    #     file_path="sample_data/",   # folder: processes all .txt files
    #     source_name="sample_data",
    # )
    # raw_requests.extend(source_b.fetch())

    # ── SOURCE C: Google Doc ──────────────────────────────────────────────
    # Best for: RFQs written up in Google Docs by your team.
    # The doc_id is in the URL: docs.google.com/document/d/DOC_ID/edit
    # Your Google service account must have Viewer access to the doc.
    # The Google Docs API must be enabled in your Google Cloud project.

    source_c = ManualTextInput(
        google_doc_id=settings.GOOGLE_DOC_ID,
        source_name="google_doc",
    )
    raw_requests.extend(source_c.fetch())

    # ── SOURCE D: Stdin ───────────────────────────────────────────────────
    # Best for: piping text directly from the terminal.
    # Usage: echo "RFQ text here" | python main.py
    # Or: python main.py  (then paste text, press Ctrl+D)

    # source_d = ManualTextInput(use_stdin=True)
    # raw_requests.extend(source_d.fetch())

    # ── SOURCE E: Outlook email ───────────────────────────────────────────
    # Best for: processing emails from your RFQ_BOT Outlook folder.
    # Requires Azure credentials in .env (AZURE_TENANT_ID, etc.)

    # from inputs.outlook_input import OutlookEmailInput
    # source_e = OutlookEmailInput(max_emails=20)
    # raw_requests.extend(source_e.fetch())

    # ══════════════════════════════════════════════════════════════════════
    # PIPELINE
    # ══════════════════════════════════════════════════════════════════════

    if not raw_requests:
        print("\n⚠️   No input requests found. Nothing to process.")
        print("    Add or uncomment a source in main.py and try again.")
        return

    print(f"\n📥  {len(raw_requests)} request(s) loaded\n")

    # ── Initialize services ───────────────────────────────────────────────
    logger.info("Connecting to Google Sheets...")
    sheets = SheetsClient()

    logger.info("Loading Rate_Master...")
    rate_records = sheets.load_rates()

    if not rate_records:
        print(
            "⚠️   Rate_Master tab is empty or could not be read.\n"
            "     Requests will be parsed and written to the sheet,\n"
            "     but estimated_quote will be blank until you add rates.\n"
        )

    parser   = ClaudeParser()
    matcher  = RateMatcher(rate_records)
    pipeline = Pipeline(parser=parser, matcher=matcher, sheets=sheets)

    # ── Run ───────────────────────────────────────────────────────────────
    print("🚀  Starting pipeline...\n")
    results = pipeline.run_batch(raw_requests)

    # ── Summary ───────────────────────────────────────────────────────────
    print("\n" + "=" * 65)
    print("  RESULTS SUMMARY")
    print("=" * 65)

    counts = {"priced": 0, "review_needed": 0, "parsed": 0}
    for r in results:
        counts[r.status] = counts.get(r.status, 0) + 1

    print(f"  Total    : {len(results)}")
    print(f"  Priced   : {counts['priced']}")
    print(f"  Review   : {counts['review_needed']}")
    print(f"  Parsed   : {counts['parsed']}")
    print()

    for i, r in enumerate(results, 1):
        conf  = f"{r.confidence:.2f}" if r.confidence is not None else "—"
        quote = f"${r.estimated_quote:,.2f}" if r.estimated_quote is not None else "—"
        flag  = "⚠️ " if r.status == "review_needed" else "✅"
        print(
            f"  {flag} [{i}] {r.pickup_from or r.pol or '?'} → {r.delivery_to or r.pod or '?'}"
            f"  |  mode={r.mode or '?'}"
            f"  |  conf={conf}"
            f"  |  quote={quote}"
            f"  |  {r.status}"
        )
        if r.pricing_notes:
            print(f"       {r.pricing_notes}")

    print()
    print("✅  All results written to RFQ_Output in Google Sheets.")
    print("=" * 65)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nCancelled.")
        sys.exit(0)

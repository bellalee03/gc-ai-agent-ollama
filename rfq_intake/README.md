# RFQ Intake + Quote Estimation — Phase 1 MVP

An internal automation tool that reads logistics RFQ requests from multiple sources, extracts structured shipment data using Claude AI, matches against a maintained rate sheet, calculates a preliminary estimate, and writes the result to Google Sheets.

---

## Architecture

```
INPUT SOURCES                    PIPELINE                     OUTPUT
─────────────────                ────────────────────         ──────────────
Inline text   ──┐
Text files    ──┤──→  RawRequest  ──→  ClaudeParser  ──→  ParsedRFQ
Google Doc    ──┤                           ↓
Stdin         ──┤                    (structured JSON,          ↓
Outlook email ──┘                     null if unclear)    RateMatcher
                                                               ↓
                                                         (Rate_Master tab)
                                                               ↓
                                                          QuotedRFQ
                                                               ↓
                                                        SheetsWriter
                                                               ↓
                                                       RFQ_Output tab
```

**Claude's job:** Read unstructured text, extract structured fields, return JSON. Never invent values — return null if missing or unclear.

**Python's job:** All math, all business logic, all I/O. Claude touches nothing except the text-to-JSON extraction.

---

## File Structure

```
rfq_intake/
├── main.py                         # Entry point — run this manually
├── requirements.txt
├── .env.example                    # Copy to .env and fill in
├── .gitignore
│
├── core/
│   ├── config.py                   # All settings (reads from .env)
│   └── models.py                   # Shared dataclasses: RawRequest, ParsedRFQ,
│                                   #   RateRecord, QuotedRFQ
│
├── inputs/
│   ├── base.py                     # BaseInputSource abstract class
│   ├── manual_input.py             # Text, files, Google Docs, stdin
│   └── outlook_input.py            # Outlook email via Microsoft Graph
│
├── services/
│   ├── claude_parser.py            # Claude API → structured JSON
│   ├── rate_matcher.py             # Rate_Master lookup + quote calculation
│   ├── sheets_client.py            # Google Sheets read/write
│   └── pipeline.py                 # Orchestrates the four steps
│
├── utils/
│   └── logger.py                   # Logging setup
│
└── sample_data/
    ├── sample_01_ftl_email.txt     # Well-structured FTL example
    ├── sample_02_ltl_messy.txt     # Casual/messy LTL example
    └── sample_03_incomplete.txt    # Ambiguous example (tests null behavior)
```

---

## Environment Variables

Copy `.env.example` to `.env` and fill in your values.

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | ✅ Always | From console.anthropic.com |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | ✅ Always | Path to service account key file |
| `GOOGLE_SHEET_ID` | ✅ Always | Spreadsheet ID from the URL |
| `RATE_MASTER_TAB` | ✅ Always | Tab name for rate reference (default: `Rate_Master`) |
| `RFQ_OUTPUT_TAB` | ✅ Always | Tab name for results (default: `RFQ_Output`) |
| `MIN_CONFIDENCE_FOR_PRICING` | ✅ Always | Confidence threshold for pricing (default: `0.5`) |
| `AZURE_TENANT_ID` | Only for Outlook | Azure AD tenant ID |
| `AZURE_CLIENT_ID` | Only for Outlook | App registration client ID |
| `AZURE_CLIENT_SECRET` | Only for Outlook | App registration secret |
| `OUTLOOK_USER_ID` | Only for Outlook | Mailbox email or object ID |
| `OUTLOOK_FOLDER_NAME` | Only for Outlook | Folder to read from (default: `RFQ_BOT`) |
| `GOOGLE_DOC_ID` | Only for Google Docs | Doc ID from the Google Docs URL |
| `LOG_LEVEL` | Optional | `DEBUG`, `INFO`, `WARNING` (default: `INFO`) |

---

## Setup Checklist

### Step 1 — Python environment

```bash
git clone <your-repo>
cd rfq_intake
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Step 2 — Anthropic API key

1. Go to [console.anthropic.com](https://console.anthropic.com)
2. Create an API key
3. Add to `.env`: `ANTHROPIC_API_KEY=sk-ant-...`

### Step 3 — Google Sheets setup

**Create the spreadsheet:**
1. Go to [sheets.google.com](https://sheets.google.com) → create a new spreadsheet
2. Rename the first tab to `Rate_Master`
3. Add a second tab named `RFQ_Output`
4. Copy the Spreadsheet ID from the URL and add to `.env`

**Rate_Master tab — add your column headers in row 1:**

| A | B | C | D | E | F | G | H |
|---|---|---|---|---|---|---|---|
| origin | destination | mode | base_rate | surcharge | minimum_charge | notes | effective_date |

Then add your rate rows. The origin and destination values are used as **keywords** for matching — they don't need to be exact full addresses. Examples:

| origin | destination | mode | base_rate | surcharge | minimum_charge | notes | effective_date |
|---|---|---|---|---|---|---|---|
| Dallas | Phoenix | FTL | 2400 | 150 | 2000 | Dry van | 2026-01-01 |
| Chicago | Atlanta | LTL | 850 | 75 | 600 | Per shipment | 2026-01-01 |
| Houston | Los Angeles | FTL | 3100 | 200 | 2800 | | 2026-01-01 |

**Create a service account:**
1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Create a project (or use existing)
3. Enable **Google Sheets API** — APIs & Services → Enable APIs → search "Sheets"
4. (Optional, for Google Docs source) Enable **Google Docs API** the same way
5. Go to **IAM & Admin → Service Accounts → Create Service Account**
6. Name it `rfq-intake-writer` — click through defaults
7. Click the service account → **Keys → Add Key → JSON** → download the file
8. Save the file as `google_service_account.json` in your project root
9. **Share your Google Sheet** with the service account email
   - The email looks like: `rfq-intake-writer@your-project.iam.gserviceaccount.com`
   - Give it **Editor** access

### Step 4 — Copy and fill in your .env

```bash
cp .env.example .env
# Open .env and fill in all required values
```

### Step 5 — (Optional) Outlook email source

Only needed if you want to use the Outlook input source. Skip this if you're starting with manual text or files only.

1. Go to [portal.azure.com](https://portal.azure.com)
2. **Azure Active Directory → App registrations → New registration**
3. Name it `rfq-intake`, leave defaults, click Register
4. Note your **Application (client) ID** and **Directory (tenant) ID**
5. Go to **Certificates & secrets → New client secret** → copy the value immediately
6. Go to **API permissions → Add permission → Microsoft Graph → Application permissions**
7. Add `Mail.Read` → **Grant admin consent** (requires Global Admin)
8. Create the `RFQ_BOT` folder in Outlook and set up an email rule to move platform emails there
9. Fill in the `AZURE_*` and `OUTLOOK_*` variables in `.env`

---

## Running the Tool

### Quickstart — test with sample files

```bash
# Edit main.py: uncomment source_b, set file_path="sample_data/"
python main.py
```

### Process inline text

Edit the `texts=[...]` list in `main.py` Source A block, then:

```bash
python main.py
```

### Process a Google Doc

```bash
# Edit main.py: uncomment source_c, fill in your google_doc_id
python main.py
```

### Process Outlook emails

```bash
# Edit main.py: uncomment source_e
python main.py
```

### Pipe text from terminal

```bash
echo "Shipment Dallas TX to Phoenix AZ, FTL, 40000 lbs" | python main.py
# Edit main.py first: uncomment source_d (use_stdin=True)
```

---

## Google Sheets Output

Each processed request adds one row to the `RFQ_Output` tab:

| Column | Description |
|---|---|
| Source Type | `email`, `google_doc`, or `manual_text` |
| Source Name | Folder name, filename, doc title, etc. |
| Received Time | Timestamp (from email) or processing time |
| Sender | Email address if available |
| Subject | Subject line if available |
| Platform | Freight platform name if identified |
| Origin | Pickup location |
| Destination | Delivery location |
| Pallets | Integer or blank |
| Weight (lbs) | Integer or blank |
| Mode | FTL, LTL, etc. |
| Special Notes | Hazmat, temp, liftgate, etc. |
| Confidence | 0.0 – 1.0 |
| Matched Rate ($) | Base rate from Rate_Master |
| Estimated Quote ($) | Calculated estimate |
| Pricing Notes | What was used in the calculation |
| Status | `priced`, `review_needed`, or `parsed` |

**Status meanings:**
- `priced` — fully extracted and estimated; ready for review
- `review_needed` — low confidence, missing fields, or no rate match found
- `parsed` — Claude extracted data but pricing was not attempted

---

## Rate Matching Logic (Phase 1)

The matching logic is intentionally simple for Phase 1.

A rate record matches a request when:
1. The `mode` matches exactly (case-insensitive)
2. The rate's `origin` keyword appears anywhere in the RFQ's origin string
3. The rate's `destination` keyword appears anywhere in the RFQ's destination string

**Example:**
- Rate record: `origin=Dallas`, `destination=Phoenix`, `mode=FTL`
- RFQ: `origin=Dallas, TX 75201`, `destination=Phoenix, AZ 85001`, `mode=FTL`
- Result: ✅ Match

If multiple records match, the most specific (longest keyword) wins.

**Estimate formula:**
```
subtotal       = base_rate + surcharge
estimated_quote = max(subtotal, minimum_charge)
```

Weight and pallets are not factored into Phase 1 pricing. That's a Phase 2 enhancement.

---

## Phase 2 Ideas (not in scope now)

- Weight-adjusted pricing (`base_rate_per_lb × weight_lbs`)
- Fuzzy lane matching (handle abbreviations, alternate city names)
- Auto-reject rules (over-weight, out-of-lane, etc.)
- Status categories: quoteable / review / reject
- Database storage instead of flat Sheets
- 24/7 webhook-based automation (Azure Functions)
- Email reply drafting with estimated quote
- Multi-platform rate comparison

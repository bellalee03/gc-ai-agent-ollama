# GC AI Agent

**GC AI Agent** is a logistics AI agent for RFQ intake, shipment detail extraction, and preliminary quote review.

The current version is built around a local LLM workflow using **Ollama**. The LLM layer is designed to be flexible, so it can also be connected to Claude, OpenAI, or other external API-based models if needed.

This project focuses on automating the first layer of logistics RFQ review by converting messy, unstructured email or document text into structured, reviewable data.

> This is a personal prototype project. All sample data is fictional and does not include real customer information, confidential business data, or proprietary pricing.

---

## Overview

Freight forwarding and 3PL teams receive RFQs in many different formats.

Some requests are written clearly. Others are buried inside forwarded email chains, mixed Korean and English, formatted like broken tables, or missing key shipment details.

A human pricing or sales user usually needs to read the full message, identify the actual shipment request, extract the cargo and routing details, check whether anything looks risky, and then prepare the request for pricing or follow-up.

**GC AI Agent** was built to support that workflow.

The agent reads unstructured RFQ text, applies logistics-specific rules, and creates a structured output that can be reviewed by a human user.

It is not just a basic text parser. It is designed to behave more like an RFQ intake assistant that understands logistics context.

---

## What This Project Does

GC AI Agent can:

* Read unstructured RFQ email or document text
* Extract shipment details from inconsistent formats
* Handle Korean and English mixed content
* Normalize extracted fields into structured English output
* Classify shipment mode
* Identify import, export, domestic, or cross-border direction
* Separate pickup, delivery, POL, and POD information
* Detect potential cargo risk based on item description, size, weight, and context
* Flag hazmat, oversized, temperature-controlled, or special-handling cargo for review
* Detect missing or unclear shipment information
* Check extracted lanes against a rate master
* Generate preliminary pricing notes
* Capture email or thread metadata for follow-up tracking
* Update existing RFQ records when a follow-up email belongs to the same thread
* Produce structured output for Google Sheets, CSV, or database storage

---

## Why This Exists

RFQ intake is often repetitive, inconsistent, and context-heavy.

A real RFQ may look like this:

* The customer mixes Korean and English
* The sender forwards a previous email chain
* The newest request is hidden above old replies
* The cargo description is vague
* The item may require hazmat or special-handling review
* The pickup or delivery address is incomplete
* The customer asks for multiple options, such as air and ocean
* The shipment may be import, export, domestic, or drayage depending on the actual cargo movement
* The email may be a follow-up to an existing RFQ, not a brand-new request

This project was built to reduce the manual work required to read, interpret, and organize those requests.

---

## Manual Process vs. GC AI Agent

| Manual Process                            | With GC AI Agent                                                               |
| ----------------------------------------- | ------------------------------------------------------------------------------ |
| Read each RFQ email manually              | AI reads the RFQ text and extracts shipment details                            |
| Manually translate Korean shipment notes  | Korean and English content is normalized into structured output                |
| Decide whether the email is a real RFQ    | The agent filters administrative emails and keeps shipment-related requests    |
| Identify import/export direction manually | The agent classifies shipment direction based on physical cargo movement       |
| Catch hazmat or oversized cargo by eye    | The agent flags potential cargo risk based on item, size, weight, and keywords |
| Look up rates in a spreadsheet            | The agent checks Rate_Master and adds pricing notes                            |
| Manually track follow-up emails           | Email ID and thread ID can be used to update existing RFQ records              |
| Manually list missing information         | The agent creates missing information and follow-up notes                      |

---

## Core Workflow

```text
Raw RFQ Email / Document Text
        ↓
Ollama / LLM Parser
        ↓
Structured JSON Extraction
        ↓
Logistics Rule Validation
        ↓
Cargo Risk & Direction Classification
        ↓
Rate_Master Matching
        ↓
Google Sheets / CSV Output
        ↓
Follow-Up Tracking
```

---

## LLM Backend

The current GitHub version uses **Ollama** as the local LLM backend.

The parsing layer is designed to be model-flexible. This means the same workflow can be connected to other LLM providers, such as Claude, OpenAI, or other API-based models, without changing the overall business logic.

### Current approach

* Local-first LLM processing with Ollama
* Python-based batch pipeline
* Structured JSON output
* Business-rule validation after AI extraction

### Optional future approach

* Replace or supplement Ollama with Claude, OpenAI, or another LLM API
* Use model routing depending on data sensitivity, cost, and extraction quality
* Keep logistics validation logic separate from the model provider

---

## Architecture

```text
gc-ai-agent/
│
├── main.py
├── archive.py
├── requirements.txt
├── .env.example
│
├── core/
│   ├── config.py
│   └── models.py
│
├── inputs/
│   ├── manual_input.py
│   └── outlook_input.py
│
├── services/
│   ├── llm_parser.py
│   ├── rate_matcher.py
│   ├── sheets_client.py
│   ├── docs_client.py
│   └── pipeline.py
│
├── utils/
│   └── logger.py
│
├── data/
│   ├── sample_emails/
│   ├── sample_rate_master.csv
│   └── sample_output.csv
│
└── docs/
    └── sample_outputs.md
```

---

## Tech Stack

* **Python** — main pipeline logic
* **Ollama** — local LLM backend for RFQ parsing
* **Google Sheets API** — output and rate master storage
* **Google Docs API** — manual intake source and document handling
* **Microsoft Graph API** — optional Outlook email integration
* **rapidfuzz** — fuzzy matching for lane and location lookup
* **JSON** — structured extraction format
* **CSV / Google Sheets** — reviewable output format

---

## Data Model

### Rate_Master

The `Rate_Master` table stores reference rates used for preliminary quote estimation.

| Field          | Description           |
| -------------- | --------------------- |
| origin         | Origin or POL         |
| destination    | Destination or POD    |
| mode           | Shipment mode         |
| base_rate      | Base rate             |
| surcharge      | Additional charge     |
| minimum_charge | Minimum charge        |
| notes          | Pricing or lane notes |
| effective_date | Rate effective date   |

---

### RFQ Output

The output table stores structured RFQ records.

| Field           | Description                                        |
| --------------- | -------------------------------------------------- |
| quote_id        | Auto-generated quote reference                     |
| requested_date  | Date the RFQ was received                          |
| sales_team      | Manually assigned sales team                       |
| partner         | Forwarding agent or logistics partner              |
| customer        | Actual shipper or cargo owner                      |
| mode            | Shipment mode                                      |
| pol             | Port of loading                                    |
| pod             | Port of discharge                                  |
| delivery_to     | Final delivery location                            |
| pickup_from     | Pickup location                                    |
| item            | Cargo description                                  |
| volume          | Quantity, pallet count, container count, or weight |
| incoterms       | EXW, FOB, DDP, etc.                                |
| additional_info | Structured notes                                   |
| estimated_quote | Preliminary quote estimate                         |
| pricing_notes   | Rate matching or manual review notes               |
| status          | priced or review_needed                            |
| last_updated    | Last updated timestamp                             |
| lead_id         | Email thread or lead identifier                    |
| thread_count    | Number of related follow-up messages               |

---

## Custom Business Logic

The most important part of this project is the logistics-specific rule layer.

The agent is not only extracting text. It is applying operational judgment rules that a human RFQ reviewer would normally apply manually.

---

### 1. RFQ Filtering

The agent decides whether a message should be processed as an RFQ.

Emails are skipped only when they contain no shipment-related information and are purely administrative.

Examples of emails that may be skipped:

* Internal scheduling only
* “Still checking”
* “Will update soon”
* General status message without shipment details

If the email contains any shipment information, the agent processes it even if some fields are incomplete.

---

### 2. Partner vs. Customer Identification

The agent distinguishes between:

* **Partner**: forwarding agent, broker, vendor, or logistics company sending the RFQ
* **Customer**: actual shipper, cargo owner, or end customer

This is important because forwarded RFQs often include multiple parties.

The sender of the email is not always the actual customer.

---

### 3. Import / Export Direction Logic

The agent classifies shipment direction based on physical cargo movement, not simply based on words like “import” or “export.”

For example:

| Cargo Movement         | Direction                   |
| ---------------------- | --------------------------- |
| Korea → USA            | Import                      |
| USA → Korea            | Export                      |
| California → Texas     | Domestic                    |
| USA → Mexico           | Cross-border                |
| Port → Inland delivery | Drayage / Domestic delivery |

This prevents errors caused by sender perspective.

For example, a Korean sender may call a shipment “export,” but from a U.S. operation perspective, the same shipment may be an import.

---

### 4. Mode Classification

The agent classifies shipment mode based on cargo movement and shipment context.

Example mode categories:

| Mode   | Meaning                        |
| ------ | ------------------------------ |
| AI     | Air Import                     |
| AO     | Air Export                     |
| SI     | Sea Import                     |
| SO     | Sea Export                     |
| DR     | Drayage                        |
| OTR    | Over-the-road trucking         |
| WH     | Warehouse                      |
| CC     | Customs clearance              |
| BORDER | Cross-border                   |
| OOG    | Out-of-gauge / oversized cargo |

The agent also applies constraints.

For example, if the RFQ mentions a 40HC, 40HQ, 20GP, 40FR, or 45HC container, the shipment should not be classified as air mode.

---

### 5. Cargo Risk and Special Handling Detection

The agent reviews the cargo description, item type, dimensions, weight, and wording to determine whether the shipment may require additional review.

This is not limited to exact keywords like “hazmat.”

The agent can flag cargo when the item or context suggests possible risk.

Examples of risk indicators:

* Battery-related parts
* Chemicals
* Liquids
* Aerosols
* Flammable goods
* Engines or auto parts with fluids
* Temperature-sensitive cargo
* Oversized cargo
* Heavy machinery
* Unusually large dimensions
* Unusually heavy weight
* Cargo with unclear item description

The agent does not make the final hazmat or compliance decision.

Instead, it flags the RFQ for human review while still preserving the extracted shipment details.

Example logic:

```text
If the email clearly says "hazmat" → mark as Hazmat
If the email clearly says "non-hazmat" → mark as Non-Hazmat
If the email says "not sure if hazmat" → mark as Hazmat Confirmation Required
If the item appears potentially regulated → mark as Potential Hazmat / Review Required
If the cargo is oversized or unusually heavy → mark as Special Handling Review Required
If no risk information is available → mark as Not Specified
```

---

### 6. Negation-Aware Detection

The agent is designed to avoid false positives when the email contains negated wording.

For example:

| Text                             | Expected Handling                          |
| -------------------------------- | ------------------------------------------ |
| “This is hazmat”                 | Flag as Hazmat                             |
| “This is not hazmat”             | Do not flag as Hazmat                      |
| “Not classified as DG”           | Do not flag as Hazmat                      |
| “DG status pending confirmation” | Flag as Confirmation Required              |
| “May contain lithium battery”    | Flag as Potential Hazmat / Review Required |

This avoids incorrectly flagging a shipment just because the word “hazmat” or “DG” appears in the email.

---

### 7. Pickup / Delivery / POL / POD Separation

The agent separates different routing fields instead of treating every location as the same.

| Field       | Meaning                      |
| ----------- | ---------------------------- |
| pickup_from | Actual pickup location       |
| delivery_to | Final delivery location      |
| pol         | Port of loading              |
| pod         | Port of discharge            |
| origin      | General shipment origin      |
| destination | General shipment destination |

This is important because a shipment may involve both international and domestic transportation.

Example:

```text
Pickup: Busan supplier
POL: Busan
POD: Los Angeles
Delivery To: Dallas, TX
```

The agent preserves these as separate fields.

---

### 8. Mixed-Language Handling

The agent can process RFQs that contain both Korean and English.

Example input:

```text
한국에서 미국 Dallas 쪽으로 보내는 건입니다.
Pickup은 Busan 근처이고 delivery는 Dallas, TX 입니다.
가능하면 DDP 조건으로 견적 부탁드립니다.
```

Example normalized output:

```json
{
  "origin": "Busan, Korea",
  "destination": "Dallas, TX",
  "direction": "Import",
  "incoterms": "DDP"
}
```

---

### 9. Vertical Table Parsing

Many RFQs arrive as copied email tables where labels and values are separated across multiple lines.

Example:

```text
POL
BUSAN
POD
CHARLESTON
INCOTERMS
DDP
```

The preprocessing logic helps normalize this into a more readable structure before extraction.

Example:

```text
POL: BUSAN
POD: CHARLESTON
INCOTERMS: DDP
```

This improves extraction accuracy for email formats copied from tables or forwarded documents.

---

### 10. Email Thread and Follow-Up Tracking

The agent can use email metadata to track whether an incoming message is a new RFQ or a follow-up to an existing RFQ.

Tracked metadata may include:

* Email ID
* Thread ID
* Sender
* Subject
* Received date
* Lead ID
* Thread count

If the same thread appears again, the agent can update the existing RFQ record instead of creating a duplicate.

The newest message is prioritized when conflicting values appear across the email thread.

---

### 11. Missing Information Detection

The agent checks whether important RFQ details are missing or unclear.

Common missing items include:

* Exact pickup address
* Final delivery address
* Cargo weight
* Cargo dimensions
* Pallet count
* Container type
* Incoterms
* Hazmat confirmation
* HS code
* Requested delivery date
* Final packing details

The agent creates follow-up notes so the user can quickly request clarification from the customer or partner.

---

### 12. Rate Matching

The agent compares extracted lane and mode information against a `Rate_Master`.

The matcher uses fuzzy location matching to reduce failures caused by spelling variations or formatting differences.

Examples:

| Variation | Normalized Match |
| --------- | ---------------- |
| Pusan     | Busan            |
| Kimpo     | Gimpo            |
| LA        | Los Angeles      |
| LAX area  | Los Angeles      |

If a matching lane is found, the agent adds an estimated quote and pricing notes.

If no matching lane is found, the agent marks the record for manual review.

Special handling flags do not block quote estimation. If a lane rate exists, the estimated quote can still be populated while the record is marked as review_needed.

---

## Example Input

### Clean RFQ Example

```text
Hi team,

Could you please provide a quote for the shipment below?

Origin: Los Angeles, CA
Destination: Dallas, TX
Commodity: Auto parts
Quantity: 4 pallets
Dimensions: 48 x 40 x 60 inches each
Weight: 3,200 lbs total
Mode: Trucking
Incoterms: DDP
Requested delivery: Next Friday

Thank you.
```

---

### Messy RFQ Example

```text
Hi,

Can you check if we can move this sometime next week?

한국에서 미국 Dallas 쪽으로 보내는 건입니다.
Pickup은 Busan 근처인데 exact address는 아직 confirm 안됐고,
delivery는 Dallas, TX 쪽 warehouse로 들어갈 예정입니다.

Item은 battery-related parts라고 들었는데,
hazmat 여부는 shipper한테 다시 확인해야 할 것 같습니다.
아마 non-hazmat일 것 같긴 한데 확실하지 않습니다.

수량은 3 or 4 pallets 정도이고,
weight는 total 2,500~3,000 lbs 정도 예상됩니다.
Dims는 standard pallet size라고 하는데 final packing detail은 아직 없습니다.

가능하면 DDP 조건으로 확인 부탁드리고,
air랑 ocean 둘 다 option이 있으면 비교 부탁드립니다.

Also, please let us know what information is missing from our side.

Thanks.
```

---

## Example Output for Messy RFQ

```json
{
  "quote_id": "GC-0002",
  "email_id": "sample-email-12345",
  "thread_id": "sample-thread-789",
  "received_date": "2026-06-22",
  "sender_email": "sample.sender@example.com",
  "subject": "RFQ Request - Korea to Dallas",
  "partner": "Unknown",
  "customer": "Unknown",
  "mode": "AI / SI options requested",
  "direction": "Import",
  "origin": "Busan, Korea",
  "destination": "Dallas, TX",
  "pickup_from": "Busan area, exact address not confirmed",
  "delivery_to": "Warehouse in Dallas, TX",
  "pol": "Busan, Korea",
  "pod": "Not specified",
  "item": "Battery-related parts",
  "volume": "3 or 4 pallets / approximately 2,500 to 3,000 lbs total",
  "dimensions": "Standard pallet size, not confirmed",
  "incoterms": "DDP",
  "hazmat_status": "Hazmat Confirmation Required",
  "cargo_risk_flag": "Potential Hazmat / Review Required",
  "special_handling_flag": "Review Required",
  "missing_information": [
    "Exact pickup address",
    "Final delivery warehouse address",
    "Confirmed pallet count",
    "Confirmed weight",
    "Confirmed dimensions",
    "Hazmat confirmation",
    "POD",
    "HS code"
  ],
  "estimated_quote": null,
  "pricing_notes": "RFQ requires follow-up before final pricing. Cargo may require hazmat or special handling review. Final cargo details and routing information are not fully confirmed.",
  "status": "review_needed",
  "follow_up_required": true,
  "follow_up_notes": [
    "Confirm exact pickup address in Busan",
    "Confirm final delivery address in Dallas",
    "Confirm whether the battery-related parts are hazmat or non-hazmat",
    "Confirm final pallet count, weight, and dimensions",
    "Confirm HS code",
    "Confirm preferred mode between air and ocean"
  ],
  "lead_id": "sample-thread-789",
  "thread_count": 1,
  "last_updated": "2026-06-22"
}
```

---

## Status Logic

| Status        | Meaning                                            |
| ------------- | -------------------------------------------------- |
| priced        | Rate was found and preliminary quote was generated |
| review_needed | RFQ requires manual review                         |
| no_rate_found | No matching rate was found                         |
| need_info     | Required shipment information is missing           |
| completed     | RFQ was reviewed or processed                      |

---

## How to Run

### 1. Clone the repository

```bash
git clone https://github.com/your-username/gc-ai-agent.git
cd gc-ai-agent
```

### 2. Create a virtual environment

```bash
python -m venv venv
```

For Mac:

```bash
source venv/bin/activate
```

For Windows:

```bash
venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Set environment variables

Create a `.env` file based on `.env.example`.

```env
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=your-local-model-name
GOOGLE_SHEETS_ID=
GOOGLE_SERVICE_ACCOUNT_JSON=
```

Optional external LLM provider settings:

```env
LLM_PROVIDER=ollama
CLAUDE_API_KEY=
OPENAI_API_KEY=
```

### 5. Run the pipeline

```bash
python main.py
```

---

## Current Status

Current working features:

* Ollama-based local LLM parsing
* Manual RFQ intake
* Korean / English mixed text handling
* Structured JSON extraction
* Vertical table normalization
* Logistics-specific validation rules
* Import / export direction logic
* Cargo risk and special-handling detection
* Rate_Master lookup
* Google Sheets output
* Quote ID generation
* Email / thread-based follow-up tracking
* Nightly archive concept for moving daily output into a permanent database sheet

Planned or optional features:

* Claude, OpenAI, or other external LLM provider connection
* Real-time Outlook intake
* Automated follow-up email draft
* PDF / Excel attachment extraction
* Web dashboard for review_needed items
* Internal database migration
* More advanced rate recommendation logic

---

## What I Learned

This project helped me understand how AI can support real business operations where the input data is messy, incomplete, and context-heavy.

Key takeaways:

* RFQ automation requires more than text extraction
* Logistics-specific business rules are critical for useful output
* Local LLMs can be used for private or internal prototypes
* The LLM provider should be replaceable without rewriting business logic
* Hazmat and special-handling logic should assist human review, not replace it
* Mixed-language emails require normalization before review
* Email metadata is important for follow-up and duplicate prevention
* Clean rate master data is essential for reliable quote estimation
* Human review is still required for final pricing, compliance, and customer communication

---

## Disclaimer

This project is a personal prototype created for learning and portfolio purposes.

It does not include real customer data, confidential company information, or proprietary rate information.

All examples and sample data are fictional.

The agent is designed to assist RFQ intake and preliminary quote review. Final pricing, hazmat classification, compliance decisions, and customer communication should always be reviewed by a human user.

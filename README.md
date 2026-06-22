# GC AI AGENT

**GC AI AGENT** is a logistics AI agent designed to automate and support the RFQ intake process.

It reads unstructured logistics quote request emails, understands the shipment context, applies customized logistics rules, and converts messy email information into structured, reviewable RFQ data.

This project is not just a basic email parser. It is designed to act like an AI intake assistant for logistics operations by identifying shipment details, detecting potential risk factors, classifying import/export direction, handling Korean and English mixed emails, tracking email metadata, and preparing RFQs for pricing or follow-up.

> This is a personal prototype project. All sample data is fictional and does not include real customer information, confidential business data, or proprietary pricing.

---

## Overview

In logistics operations, RFQ emails often arrive in inconsistent and incomplete formats.

Some emails are clearly written with all shipment details. Others may be vague, informal, or written in a mix of Korean and English. Important information such as pickup location, delivery location, cargo details, weight, dimensions, Incoterms, hazmat status, shipment mode, and requested delivery date may be missing or unclear.

A human user usually needs to read the email carefully, understand the logistics context, determine what information is usable, decide what is missing, and prepare the request for pricing or follow-up.

**GC AI AGENT** was built to assist with this process.

The agent reads the RFQ email, extracts key information, applies logistics-specific judgment rules, and creates structured output that can be reviewed by a sales, operations, or pricing user.

The goal is not to replace human decision-making.

The goal is to reduce repetitive intake work and help users review RFQs faster and more consistently.

---

## What This Project Does

GC AI AGENT can:

* Read unstructured RFQ email text
* Extract shipment details from inconsistent email formats
* Understand Korean and English mixed RFQ content
* Translate and normalize key information into structured English output
* Classify shipment mode such as truck, ocean, air, warehouse, or multi-option request
* Identify import, export, domestic, or cross-border shipment direction
* Separate pickup, delivery, POL, and POD information
* Detect potential hazmat or special handling indicators based on item description and context
* Flag oversized, heavy, unclear, or high-risk cargo for review
* Identify missing or unclear RFQ information
* Check whether a matching rate or lane exists in a sample rate master
* Store email ID, thread ID, sender, subject, and received date for follow-up tracking
* Create follow-up notes based on missing information
* Generate structured output for pricing, sales review, or reporting

---

## Why I Built This

RFQ intake is not always straightforward.

A real RFQ email may include partial information, informal wording, unclear shipment terms, mixed languages, or multiple service options.

For example, a customer may write:

* “Pickup is around LA, exact address not confirmed yet”
* “Maybe 3 or 4 pallets”
* “한국에서 미국으로 보내는 건입니다”
* “DDP 가능한지 확인 부탁드립니다”
* “Item is battery-related parts”
* “Not sure if it is hazmat”
* “Please check both air and ocean options”
* “Dims are not final yet”
* “Can you follow up on the previous email?”

A basic parser may only extract words from the email.

GC AI AGENT is designed to go further by applying logistics-specific rules and creating an RFQ record that is actually useful for business review.

---

## Key Customizations

This project includes customized business logic for logistics RFQ handling.

### 1. Cargo Risk and Hazmat Judgment

The agent does not only look for the exact word “hazmat.”

It reviews the item description, shipment context, and related wording to determine whether the cargo may require additional review.

For example, the agent can flag cargo for review when the email mentions or implies items such as:

* Batteries
* Chemicals
* Liquids
* Aerosols
* Engines
* Auto parts with fluids
* Electronics with lithium batteries
* Flammable goods
* Heavy machinery
* Oversized cargo
* Cargo with unclear commodity description

The agent does not make the final hazmat decision.

Instead, it assigns a review flag when the cargo appears risky, unclear, oversized, or likely to require special handling.

Example logic:

```text
If the email clearly says "hazmat" → mark as Hazmat
If the email clearly says "non-hazmat" → mark as Non-Hazmat
If the email says "not sure if hazmat" → mark as Hazmat Confirmation Required
If the item appears potentially regulated, such as batteries or chemicals → mark as Potential Hazmat / Review Required
If the cargo is oversized or unusually heavy → mark as Special Handling Review Required
If no risk information is provided → mark as Not Specified
```

This helps the user know when a shipment should be reviewed more carefully before quoting.

---

### 2. Import / Export / Domestic Classification

The agent classifies the shipment direction based on the routing information provided in the email.

It reviews origin, destination, pickup location, delivery location, POL, and POD to determine whether the shipment is:

| Direction    | Meaning                                       |
| ------------ | --------------------------------------------- |
| Import       | Shipment moving into the U.S.                 |
| Export       | Shipment moving out of the U.S.               |
| Domestic     | Shipment moving within the same country       |
| Cross-border | Shipment moving between neighboring countries |
| Unknown      | Direction cannot be clearly determined        |

This helps users quickly understand which operational flow may apply.

---

### 3. Mixed Korean / English RFQ Handling

Many RFQ emails are not written in one clean format or one language.

GC AI AGENT can process RFQ text that includes both Korean and English.

Example:

```text
한국에서 미국 Dallas 쪽으로 보내는 건입니다.
Pickup은 Busan 근처이고 delivery는 Dallas, TX 입니다.
가능하면 DDP 조건으로 견적 부탁드립니다.
```

The agent can normalize this into structured output:

```json
{
  "origin": "Busan, Korea",
  "destination": "Dallas, TX",
  "direction": "Import",
  "incoterms": "DDP"
}
```

This makes the output easier to review even when the original request is written informally.

---

### 4. Pickup / Delivery / POL / POD Separation

The agent separates routing fields instead of treating all locations as the same.

This is important because logistics emails may include both inland and international routing information.

| Field       | Meaning                      |
| ----------- | ---------------------------- |
| Pickup From | Actual pickup location       |
| Delivery To | Final delivery location      |
| POL         | Port of Loading              |
| POD         | Port of Discharge            |
| Origin      | General shipment origin      |
| Destination | General shipment destination |

For example, an email may say the cargo is picked up in Busan, loaded at Busan port, discharged at Los Angeles, and delivered to Dallas.

The agent is designed to preserve these distinctions when the information is available.

---

### 5. Email Metadata and Follow-Up Tracking

The agent captures email-related metadata so the structured RFQ record can be connected back to the original conversation.

Tracked metadata may include:

* Email ID
* Thread ID
* Sender email
* Subject line
* Received date
* Thread count
* Lead ID
* Last updated timestamp

This allows the user to follow up on the correct email thread, track the request history, and avoid losing context.

---

### 6. Missing Information Detection

The agent checks whether important RFQ fields are missing or unclear.

Examples of missing information include:

* Exact pickup address
* Final delivery address
* Cargo weight
* Cargo dimensions
* Pallet count
* Incoterms
* Hazmat confirmation
* HS code
* Requested delivery date
* Shipment mode
* Final packing details

Instead of simply leaving fields blank, the agent creates a list of missing information and follow-up items.

---

### 7. Rate and Lane Check

The agent can compare extracted lane information against a sample rate master.

If a matching lane exists, the agent can return a pricing note.

If no matching lane is found, the RFQ is flagged for manual review.

Example:

```text
No rate found for lane: Busan, Korea → Dallas, TX.
Please review manually or update the rate master.
```

This helps separate RFQs that can move forward quickly from RFQs that require manual pricing review.

---

### 8. Follow-Up Note Generation

When required information is missing, the agent creates follow-up notes.

Example:

```text
Please confirm the exact pickup address in Busan.
Please confirm whether the battery-related parts are hazmat or non-hazmat.
Please provide final pallet count, weight, and dimensions.
Please confirm the HS code.
```

This helps the user respond to the customer faster and more consistently.

---

## Workflow

```text
RFQ Email
   ↓
Email Metadata Capture
   ↓
AI Extraction
   ↓
Logistics Context Review
   ↓
Cargo Risk / Hazmat Judgment
   ↓
Import / Export Classification
   ↓
Missing Information Check
   ↓
Rate / Lane Check
   ↓
Structured RFQ Output
   ↓
Follow-Up Tracking
```

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
  "quote_id": "Q-2026-0002",
  "email_id": "sample-email-12345",
  "thread_id": "sample-thread-789",
  "received_date": "2026-06-22",
  "sender_email": "sample.sender@example.com",
  "subject": "RFQ Request - Korea to Dallas",
  "customer": "Unknown",
  "mode": "Air / Ocean options requested",
  "direction": "Import",
  "origin": "Busan, Korea",
  "destination": "Dallas, TX",
  "pickup_from": "Busan area, exact address not confirmed",
  "delivery_to": "Warehouse in Dallas, TX",
  "pol": "Busan, Korea",
  "pod": "Not specified",
  "item": "Battery-related parts",
  "quantity": "3 or 4 pallets",
  "dimensions": "Standard pallet size, not confirmed",
  "weight": "Approximately 2,500 to 3,000 lbs total",
  "incoterms": "DDP",
  "hazmat_status": "Hazmat Confirmation Required",
  "cargo_risk_flag": "Potential Hazmat / Review Required",
  "special_handling_flag": "Review Required",
  "requested_delivery_date": "Sometime next week",
  "additional_info": "Customer requested both air and ocean options.",
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
  "status": "Need Info",
  "pricing_notes": "RFQ requires follow-up before final pricing. Cargo may require hazmat or special handling review. Final cargo details and routing information are not fully confirmed.",
  "follow_up_required": true,
  "follow_up_notes": [
    "Confirm exact pickup address in Busan",
    "Confirm final delivery address in Dallas",
    "Confirm whether the battery-related parts are hazmat or non-hazmat",
    "Confirm final pallet count, weight, and dimensions",
    "Confirm HS code",
    "Confirm preferred mode between air and ocean"
  ],
  "last_updated": "2026-06-22"
}
```

---

## Output Fields

| Field                 | Description                                                      |
| --------------------- | ---------------------------------------------------------------- |
| quote_id              | Unique RFQ reference number                                      |
| email_id              | Original email ID for follow-up tracking                         |
| thread_id             | Email thread ID                                                  |
| received_date         | Date the RFQ was received                                        |
| sender_email          | Sender email address                                             |
| subject               | Email subject line                                               |
| customer              | Customer or prospect name                                        |
| mode                  | Shipment mode                                                    |
| direction             | Import, export, domestic, cross-border, or unknown               |
| origin                | General shipment origin                                          |
| destination           | General shipment destination                                     |
| pickup_from           | Actual pickup location                                           |
| delivery_to           | Final delivery location                                          |
| pol                   | Port of Loading                                                  |
| pod                   | Port of Discharge                                                |
| item                  | Commodity or cargo description                                   |
| quantity              | Pallet, box, container, or unit count                            |
| dimensions            | Cargo dimensions                                                 |
| weight                | Shipment weight                                                  |
| incoterms             | DDP, EXW, FOB, FCA, etc.                                         |
| hazmat_status         | Hazmat, non-hazmat, not specified, or confirmation required      |
| cargo_risk_flag       | Indicates whether the item may require additional review         |
| special_handling_flag | Indicates oversized, heavy, unclear, or special cargo conditions |
| missing_information   | List of missing or unclear fields                                |
| status                | RFQ processing status                                            |
| pricing_notes         | Rate check or manual review notes                                |
| follow_up_required    | Whether follow-up is needed                                      |
| follow_up_notes       | Suggested follow-up questions                                    |
| last_updated          | Last update timestamp                                            |

---

## Status Logic

Each RFQ is assigned a status based on the extracted information and validation results.

| Status          | Meaning                                    |
| --------------- | ------------------------------------------ |
| New             | RFQ was received and parsed                |
| Need Info       | Required information is missing or unclear |
| Rate Found      | Matching rate or lane exists               |
| No Rate Found   | No matching rate was found                 |
| Review Required | Human review is needed                     |
| Completed       | RFQ has been reviewed or processed         |

---

## Sample Validation Rules

```text
If origin is missing → status = Need Info
If destination is missing → status = Need Info
If pickup address is missing → add to missing_information
If delivery address is missing → add to missing_information
If weight is missing → add to missing_information
If dimensions are missing → add to missing_information
If Incoterms are missing → add to missing_information
If item description suggests possible hazmat → flag as Potential Hazmat / Review Required
If item description includes batteries, chemicals, liquids, aerosols, or flammable goods → flag for cargo risk review
If cargo is oversized or unusually heavy → flag for special handling review
If hazmat status is unclear → add to missing_information
If lane is not found in rate master → status = No Rate Found
If multiple modes are requested → flag as Multi-Option Quote
```

---

## Tech Stack

* Python
* LLM-based text extraction
* JSON output formatting
* Email metadata handling
* CSV / Google Sheets output
* Validation logic
* Sample rate master lookup
* Logistics-specific rule customization

---

## Project Structure

```text
gc-ai-agent/
│
├── README.md
├── requirements.txt
├── .env.example
│
├── data/
│   ├── sample_emails/
│   ├── sample_rate_master.csv
│   └── sample_output.csv
│
├── src/
│   ├── main.py
│   ├── parser.py
│   ├── validation.py
│   ├── rate_matcher.py
│   ├── email_metadata.py
│   └── utils.py
│
├── prompts/
│   └── rfq_extraction_prompt.txt
│
└── docs/
    └── sample_outputs.md
```

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

### 4. Add environment variables

Create a `.env` file based on `.env.example`.

```env
LLM_API_KEY=
GOOGLE_SHEETS_ID=
```

### 5. Run the project

```bash
python src/main.py
```

---

## Sample Use Case

A logistics team receives an RFQ email from a customer.

Instead of manually reviewing the full email and copying shipment details into a spreadsheet, the user can run the email text through GC AI AGENT.

The agent extracts key shipment details, reviews the logistics context, checks for possible cargo risk, identifies missing information, assigns a status, and creates structured output for sales or pricing review.

If important information is missing, the agent also creates follow-up notes so the user can return to the original email thread and request clarification.

---

## What I Learned

This project helped me understand how AI can be applied to real business operations where the input data is messy, inconsistent, and context-heavy.

Key takeaways:

* AI output needs validation before being used in operations
* Structured JSON output makes data easier to review and store
* Logistics workflows require context-aware judgment, not just text extraction
* Hazmat and special handling indicators require careful review
* Mixed-language RFQs require normalization before review
* Email metadata is important for follow-up and tracking
* Missing information detection is just as important as extraction
* Human review is still necessary for pricing decisions
* Clean master data is important for reliable rate matching
* AI can reduce repetitive intake work, but it should support rather than replace operational decision-making

---

## Future Improvements

Potential future improvements include:

* PDF RFQ extraction
* Excel file extraction
* Email attachment parsing
* Duplicate RFQ detection
* Confidence score for extracted fields
* Web dashboard
* Automatic follow-up email draft
* Improved rate recommendation logic
* Database storage instead of spreadsheet output
* User login and role-based review flow
* Better multi-language normalization
* More advanced import/export logic
* Historical RFQ search and reporting
* More detailed cargo risk classification

---

## Disclaimer

This project is a personal prototype created for learning and portfolio purposes.

It does not include real customer data, confidential company information, or proprietary rate information.

All examples and sample data are fictional.

The agent is designed to assist RFQ intake and review. Final pricing, hazmat classification, and business decisions should always be reviewed by a human user.

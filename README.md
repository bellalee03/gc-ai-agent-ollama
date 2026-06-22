# GC AI AGENT

**GC AI AGENT** is a logistics AI agent designed to automate and support the RFQ intake process.

It converts unstructured logistics quote request emails into structured, reviewable data so that users can quickly extract shipment details, identify missing information, classify shipment conditions, and prepare RFQs for pricing or follow-up.

This project is more than a basic email parser. It includes logistics-specific business rules such as hazmat detection, import/export classification, mixed-language handling, lane and rate checking, missing field validation, and email-based follow-up tracking.

> This is a personal prototype project. All sample data is fictional and does not include real customer information, confidential business data, or proprietary pricing.

---

## Overview

In logistics operations, RFQ emails often arrive in inconsistent formats.

Some emails are clear and complete. Others may be vague, incomplete, or written in a mix of Korean and English. Important details such as origin, destination, cargo type, weight, dimensions, Incoterms, hazmat status, pickup address, delivery address, or requested delivery date may be missing or unclear.

Manually reviewing each RFQ can be repetitive and time-consuming.

**GC AI AGENT** helps automate the first review step by reading RFQ email text, extracting key information, applying logistics-specific validation rules, and organizing the request into a structured format.

The goal is not to replace human pricing or sales review.

The goal is to help users process RFQs faster, reduce manual intake work, and make follow-up easier.

---

## What This Project Does

GC AI AGENT can:

* Read unstructured RFQ email text
* Extract key shipment details
* Identify missing or unclear information
* Classify shipment mode
* Detect hazmat-related wording
* Identify import, export, or domestic shipment direction
* Handle Korean / English mixed RFQ content
* Separate pickup, delivery, POL, and POD information
* Check whether a matching rate or lane exists
* Add pricing or manual review notes
* Store email ID or thread information for follow-up tracking
* Generate structured output for review, tracking, and reporting

---

## Why I Built This

RFQ intake is often messy.

A single email can include shipment details, customer notes, partial cargo information, unclear routing, and follow-up questions all in one message.

For example, a customer may say:

* “Pickup is around LA, exact address not confirmed yet”
* “Maybe 3 or 4 pallets”
* “Not sure if it is hazmat”
* “Please check both air and ocean”
* “한국에서 미국으로 보내는 건입니다”
* “DDP 가능한지 확인 부탁드립니다”

These requests require more than simple keyword extraction.

The system needs to understand logistics context, identify what is missing, and organize the RFQ in a way that sales or pricing teams can actually use.

This project was built to explore how AI can assist with that process.

---

## Core Customization Details

This project includes several customized rules and logic designed specifically for logistics RFQ workflows.

### 1. Hazmat Detection

The agent checks whether the RFQ includes hazmat-related information.

It does not assume the cargo is hazmat or non-hazmat unless clearly stated.

Example logic:

```text
If the email says "hazmat" → flag as Hazmat
If the email says "non-hazmat" → flag as Non-Hazmat
If the email says "not sure if hazmat" → flag as Hazmat Confirmation Required
If hazmat status is not mentioned → mark as Not Specified
```

This is important because hazmat status can affect pricing, carrier availability, documentation, and handling requirements.

---

### 2. Import / Export / Domestic Classification

The agent classifies the shipment direction based on the origin, destination, POL, POD, pickup, and delivery details.

Example categories:

| Direction    | Meaning                                       |
| ------------ | --------------------------------------------- |
| Import       | Shipment moving into the U.S.                 |
| Export       | Shipment moving out of the U.S.               |
| Domestic     | Shipment moving within the same country       |
| Cross-border | Shipment moving between neighboring countries |
| Unknown      | Direction cannot be clearly determined        |

This helps users quickly understand what type of operation or team may need to review the RFQ.

---

### 3. Mixed-Language Handling

RFQ emails may include both Korean and English.

The agent is designed to extract and normalize information even when the request is written in mixed language.

Example:

```text
한국에서 미국 Dallas 쪽으로 보내는 건이고,
가능하면 DDP 조건으로 견적 부탁드립니다.
Pickup은 Busan 근처이고 delivery는 Dallas, TX 입니다.
```

The agent can convert this into structured English output:

```json
{
  "origin": "Busan, Korea",
  "destination": "Dallas, TX",
  "incoterms": "DDP",
  "direction": "Import"
}
```

---

### 4. Pickup / Delivery / POL / POD Separation

In logistics emails, origin and destination can be vague.

The agent separates different routing fields when possible:

| Field       | Meaning                      |
| ----------- | ---------------------------- |
| Pickup From | Actual pickup location       |
| Delivery To | Final delivery location      |
| POL         | Port of Loading              |
| POD         | Port of Discharge            |
| Origin      | General shipment origin      |
| Destination | General shipment destination |

This is important because a shipment may have both inland and ocean/air routing information.

---

### 5. Email ID and Follow-Up Tracking

The agent can store email-related metadata so that the RFQ record can be connected back to the original email.

Tracked fields may include:

* Email ID
* Thread ID
* Sender email
* Received date
* Subject line
* Thread count
* Lead ID
* Last updated date

This makes it easier to follow up on the original request, track conversation history, and avoid duplicate handling.

---

### 6. Missing Information Detection

The agent checks whether important RFQ information is missing.

Examples:

```text
If pickup address is missing → add to missing_information
If delivery address is missing → add to missing_information
If cargo weight is missing → add to missing_information
If dimensions are missing → add to missing_information
If Incoterms are missing → add to missing_information
If hazmat status is unclear → add to missing_information
```

This allows the user to quickly identify whether the RFQ is ready for pricing or requires follow-up.

---

### 7. Rate and Lane Check

The agent can compare extracted lane information against a sample rate master.

If a matching lane exists, it can add a pricing note.

If no matching lane is found, the RFQ is flagged for manual review.

Example:

```text
No rate found for lane: Busan, Korea → Dallas, TX.
Please review manually or update the rate master.
```

---

## Workflow

```text
RFQ Email
   ↓
Email Metadata Capture
   ↓
AI Extraction
   ↓
Logistics Rule Validation
   ↓
Hazmat / Direction / Mode Classification
   ↓
Missing Information Check
   ↓
Rate / Lane Check
   ↓
Structured Output
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
  "customer": "Unknown",
  "sender_email": "sample.sender@example.com",
  "subject": "RFQ Request - Korea to Dallas",
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
  "hazmat_status": "Hazmat confirmation required",
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
  "pricing_notes": "RFQ requires follow-up before final pricing. Hazmat status, final cargo details, and routing information are not fully confirmed.",
  "follow_up_required": true,
  "follow_up_notes": [
    "Confirm exact pickup address in Busan",
    "Confirm final delivery address in Dallas",
    "Confirm hazmat or non-hazmat status",
    "Confirm final pallet count, weight, and dimensions",
    "Confirm HS code for battery-related parts"
  ],
  "last_updated": "2026-06-22"
}
```

---

## Output Fields

| Field               | Description                                                 |
| ------------------- | ----------------------------------------------------------- |
| quote_id            | Unique RFQ reference number                                 |
| email_id            | Original email ID for follow-up tracking                    |
| thread_id           | Email thread ID                                             |
| received_date       | Date the RFQ was received                                   |
| customer            | Customer or prospect name                                   |
| sender_email        | Sender email address                                        |
| subject             | Email subject line                                          |
| mode                | Shipment mode                                               |
| direction           | Import, export, domestic, cross-border, or unknown          |
| origin              | General shipment origin                                     |
| destination         | General shipment destination                                |
| pickup_from         | Actual pickup location                                      |
| delivery_to         | Final delivery location                                     |
| pol                 | Port of Loading                                             |
| pod                 | Port of Discharge                                           |
| item                | Commodity or cargo description                              |
| quantity            | Pallet, box, container, or unit count                       |
| dimensions          | Cargo dimensions                                            |
| weight              | Shipment weight                                             |
| incoterms           | DDP, EXW, FOB, FCA, etc.                                    |
| hazmat_status       | Hazmat, non-hazmat, not specified, or confirmation required |
| missing_information | List of missing or unclear fields                           |
| status              | RFQ processing status                                       |
| pricing_notes       | Rate check or manual review notes                           |
| follow_up_required  | Whether follow-up is needed                                 |
| follow_up_notes     | Suggested follow-up items                                   |
| last_updated        | Last update timestamp                                       |

---

## Status Logic

Each RFQ is assigned a status based on extracted information and validation results.

| Status          | Meaning                            |
| --------------- | ---------------------------------- |
| New             | RFQ was received and parsed        |
| Need Info       | Required information is missing    |
| Rate Found      | Matching rate or lane exists       |
| No Rate Found   | No matching rate was found         |
| Review Required | Human review is needed             |
| Completed       | RFQ has been reviewed or processed |

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

Instead of manually copying shipment details into a spreadsheet, the user can run the email text through GC AI AGENT.

The agent extracts key shipment details, checks for missing information, applies logistics-specific rules, assigns a status, and creates structured output for sales or pricing review.

If important information is missing, the agent also provides follow-up notes so the user can return to the original email thread and request clarification.

---

## What I Learned

This project helped me understand how AI can be applied to real business operations where the input data is messy, inconsistent, and context-heavy.

Key takeaways:

* AI output needs validation before being used in operations
* Structured JSON output makes data easier to review and store
* Missing information detection is just as important as extraction
* Hazmat and Incoterms require careful handling and should not be assumed
* Mixed-language RFQs require normalization before review
* Email metadata is important for follow-up and tracking
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

---

## Disclaimer

This project is a personal prototype created for learning and portfolio purposes.

It does not include real customer data, confidential company information, or proprietary rate information.

All examples and sample data are fictional.

Final pricing and business decisions should always be reviewed by a human user.

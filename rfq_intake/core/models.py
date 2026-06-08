from dataclasses import dataclass
from typing import Optional


@dataclass
class RawRequest:
    content: str
    source_type: str = "manual_text"
    source_name: str = ""
    received_time: Optional[str] = None
    sender: Optional[str] = None
    subject: Optional[str] = None
    conversation_id: Optional[str] = None
    image_data: Optional[str] = None
    image_media_type: Optional[str] = None


@dataclass
class ParsedRFQ:
    source_type: str = ""
    source_name: str = ""
    received_time: Optional[str] = None
    sender: Optional[str] = None
    subject: Optional[str] = None

    # Claude 추출
    partner: Optional[str] = None
    customer: Optional[str] = None
    mode: Optional[str] = None
    pol: Optional[str] = None
    pod: Optional[str] = None
    delivery_to: Optional[str] = None
    pickup_from: Optional[str] = None
    item: Optional[str] = None
    volume: Optional[str] = None        # 자유 텍스트 통합 물동량
    incoterms: Optional[str] = None
    additional_info: Optional[str] = None
    confidence: Optional[float] = None

    # Post-processing detected signals
    hazmat_status: Optional[str] = None            # confirmed | pending_confirmation | cleared | detected
    vendor_response_status: Optional[str] = None   # vendor_declined | rate_not_competitive | manual_follow_up_required
    extracted_rate_lines: Optional[str] = None     # Rate lines extracted from vendor quotes


@dataclass
class RateRecord:
    origin: str = ""
    destination: str = ""
    mode: str = ""
    base_rate: Optional[float] = None
    surcharge: Optional[float] = None
    minimum_charge: Optional[float] = None
    notes: str = ""
    effective_date: str = ""


@dataclass
class QuotedRFQ:
    # 메타
    quote_id: Optional[str] = None
    requested_date: Optional[str] = None
    source_type: str = ""
    source_name: str = ""
    received_time: Optional[str] = None

    # Claude 추출
    partner: Optional[str] = None
    customer: Optional[str] = None
    mode: Optional[str] = None
    pol: Optional[str] = None
    pod: Optional[str] = None
    delivery_to: Optional[str] = None
    pickup_from: Optional[str] = None
    item: Optional[str] = None
    volume: Optional[str] = None
    incoterms: Optional[str] = None
    additional_info: Optional[str] = None
    confidence: Optional[float] = None

    # Post-processing detected signals
    hazmat_status: Optional[str] = None
    vendor_response_status: Optional[str] = None
    extracted_rate_lines: Optional[str] = None

    # 코드 자동
    estimated_quote: Optional[float] = None
    pricing_notes: str = ""
    status: str = "review_needed"
    last_updated: Optional[str] = None
    lead_id: Optional[str] = None
    thread_count: int = 1

    @classmethod
    def from_parsed(cls, p: ParsedRFQ) -> "QuotedRFQ":
        return cls(
            source_type=p.source_type,
            source_name=p.source_name,
            received_time=p.received_time,
            partner=p.partner,
            customer=p.customer,
            mode=p.mode,
            pol=p.pol,
            pod=p.pod,
            delivery_to=p.delivery_to,
            pickup_from=p.pickup_from,
            item=p.item,
            volume=p.volume,
            incoterms=p.incoterms,
            additional_info=p.additional_info,
            confidence=p.confidence,
            hazmat_status=p.hazmat_status,
            vendor_response_status=p.vendor_response_status,
            extracted_rate_lines=p.extracted_rate_lines,
        )

    def to_sheet_row(self) -> list:
        def _val(v):
            return "" if v is None else v

        # Requested Date MM/DD/YYYY 포맷
        received = _val(self.received_time)
        if received:
            try:
                from datetime import datetime
                if "T" in received:
                    dt = datetime.fromisoformat(received.replace("Z", "+00:00"))
                    received = dt.strftime("%m/%d/%Y")
                elif "-" in received:
                    dt = datetime.strptime(received[:10], "%Y-%m-%d")
                    received = dt.strftime("%m/%d/%Y")
            except Exception:
                pass

        return [
            _val(self.quote_id),             # A Quote ID
            received,                         # B Requested Date
            "",                               # C 담당 영업팀 (공란)
            _val(self.partner),               # D Partner
            _val(self.customer),             # E Customer
            _val(self.mode),                 # F Mode
            _val(self.pol),                  # G POL
            _val(self.pod),                  # H POD
            _val(self.delivery_to),          # I Delivery To
            _val(self.pickup_from),          # J Pickup From
            _val(self.item),                 # K Item
            _val(self.volume),               # L 물동량
            _val(self.incoterms),            # M Incoterms
            _val(self.additional_info),      # N Additional Info
            _val(self.estimated_quote),      # O Estimated Quote ($)
            _val(self.pricing_notes),        # P Pricing Notes
            _val(self.status),               # Q Status
            _val(self.last_updated),         # R Last Updated
            _val(self.lead_id),              # S Lead ID
            _val(self.thread_count),         # T Thread Count
        ]

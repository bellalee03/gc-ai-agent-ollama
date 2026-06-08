import logging
import re
from typing import Optional

from rapidfuzz import fuzz, process

from core.models import ParsedRFQ, RateRecord, QuotedRFQ
from core.config import settings

logger = logging.getLogger(__name__)

SPECIAL_HANDLING_FLAGS = {
    "temperature": [
        "reefer", "frozen", "refrigerat",
        "temperature", "temp control", "cold chain",
        "chilled", "keep cold", "below zero",
        "maintain above", "maintain below",
    ],
    "hazmat": [
        "hazmat",
        "hazardous material",
        "hazardous cargo",
        "dangerous goods",
        "un number",
        "imdg",
        "msds",
        "sds sheet",
        "class 1 hazmat",
        "class 2 hazmat",
        "class 3 hazmat",
        "class 4 hazmat",
        "class 5 hazmat",
        "class 6 hazmat",
        "class 7 hazmat",
        "class 8 hazmat",
        "class 9 hazmat",
    ],
    "oog": [
        "oog", "out of gauge", "oversize",
        "overdimensional", "wide load",
        "heavy lift", "super load",
        "over height", "over width",
        "heavy and bulky", "overweight",
        "abnormal load", "exceptional cargo",
        "project cargo",
    ],
}


class RateMatcher:
    def __init__(self, rate_records: list[RateRecord]):
        self.rate_records = rate_records
        self._origin_candidates = list({r.origin for r in rate_records if r.origin})
        self._dest_candidates   = list({r.destination for r in rate_records if r.destination})
        logger.info(f"RateMatcher initialized with {len(rate_records)} rate record(s)")

    def _fuzzy_match_location(self, query: str, candidates: list[str], threshold: int = 80) -> str | None:
        """
        query와 가장 유사한 candidate 반환.
        유사도가 threshold 미만이면 None 반환.
        """
        if not query or not candidates:
            return None
        query = re.sub(r"[^\w\s]", " ", query.lower().strip())
        query = re.sub(r"\s+", " ", query).strip()
        candidates_lower = [
            re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", c.lower().strip())).strip()
            for c in candidates
        ]
        result = process.extractOne(
            query,
            candidates_lower,
            scorer=fuzz.token_set_ratio
        )
        if result and result[1] >= threshold:
            original_idx = candidates_lower.index(result[0])
            return candidates[original_idx]
        return None

    def _check_special_handling(self, parsed: ParsedRFQ) -> Optional[str]:
        """special handling 키워드 감지. 감지된 flag 이름 반환, 없으면 None."""
        combined = (parsed.additional_info or "").lower()
        negation_words = [
            "no ", "not ", "non-", "non ", "without ",
            "removed", "cleared", "confirmed no",
            "not classified", "pending confirmation",
            "not applicable", "n/a",
            "not classified as hazmat", "not classified as dg",
            "not classified as dangerous",
            "non-dg", "non dg", "not dg",
            "dg status pending", "dg confirmation pending", "pending dg",
        ]
        for flag, keywords in SPECIAL_HANDLING_FLAGS.items():
            for kw in keywords:
                pos = combined.find(kw)
                if pos < 0:
                    continue
                ctx_start = max(0, pos - 50)
                ctx_end   = min(len(combined), pos + len(kw) + 50)
                context   = combined[ctx_start:ctx_end]
                if not any(neg in context for neg in negation_words):
                    return flag
        return None

    def price(self, parsed: ParsedRFQ) -> QuotedRFQ:
        result = QuotedRFQ.from_parsed(parsed)

        # Vendor response override — carrier/co-loader replied they can't match rate.
        # Runs before confidence gate because vendor intent is clear regardless of field completeness.
        if parsed.vendor_response_status:
            result.status = parsed.vendor_response_status
            notes_parts = [f"Vendor response: {parsed.vendor_response_status.replace('_', ' ')}"]
            if parsed.extracted_rate_lines:
                notes_parts.append(f"Quoted rates: {parsed.extracted_rate_lines}")
            result.pricing_notes = " | ".join(notes_parts)
            return result

        # Confidence gate
        confidence = parsed.confidence or 0.0
        if confidence < settings.MIN_CONFIDENCE_FOR_PRICING:
            result.status = "review_needed"
            result.pricing_notes = (
                f"Confidence too low ({confidence:.2f} < "
                f"{settings.MIN_CONFIDENCE_FOR_PRICING}). Manual review required."
            )
            return result

        # Special handling 감지 (조기 return 없이 flag만 기록)
        special_flag = self._check_special_handling(parsed)

        # Required fields check — WH mode only needs some location context (no POL/POD required)
        missing = []
        if parsed.mode != 'WH':
            if not (parsed.pol or parsed.pickup_from):
                missing.append("origin (POL/Pickup From)")
            if not (parsed.pod or parsed.delivery_to):
                missing.append("destination (POD/Delivery To)")
        if not parsed.mode:
            missing.append("mode")

        if missing:
            result.status = "review_needed"
            result.pricing_notes = f"Missing required fields: {', '.join(missing)}"
            return result

        # Rate matching
        match = self._find_best_match(parsed)

        if not match:
            origin_str = parsed.pol or parsed.pickup_from or ""
            dest_str   = parsed.pod or parsed.delivery_to or ""
            base_note  = (
                f"No rate found for lane: {origin_str} → {dest_str} "
                f"({parsed.mode}). Add to Rate_Master or review manually."
            )
            # Include extracted vendor rate lines if available (helps manual review)
            rate_lines_note = (
                f" | Vendor rates in email: {parsed.extracted_rate_lines}"
                if parsed.extracted_rate_lines else ""
            )
            special_note = (
                f" | Special handling: [{special_flag.upper()}]. Manual review required."
                if special_flag else ""
            )
            result.status = "review_needed"
            result.pricing_notes = base_note + rate_lines_note + special_note
            return result

        # Calculate
        estimated, notes = self._calculate(match)
        result.estimated_quote = estimated

        if special_flag:
            result.status        = "review_needed"
            result.pricing_notes = (
                notes + f" | Special handling: [{special_flag.upper()}]. Manual review required."
            )
        else:
            result.status        = "priced"
            result.pricing_notes = notes

        return result

    def _get_origins(self, origin: str) -> list[str]:
        """쉼표로 구분된 복수 origin을 리스트로 반환"""
        if not origin:
            return []
        return [o.strip() for o in origin.split(",") if o.strip()]

    def _find_best_match(self, parsed: ParsedRFQ) -> Optional[RateRecord]:
        # Rate 매칭은 항상 POL/POD 기준 (항구/도시)
        # pickup_from/delivery_to는 전체 주소라 매칭 불가
        rfq_origin = (parsed.pol or parsed.pickup_from or "").strip()
        rfq_dest   = (parsed.pod or parsed.delivery_to or "").strip()
        rfq_mode   = (parsed.mode or "").lower().strip()

        matched_dest = self._fuzzy_match_location(rfq_dest, self._dest_candidates)
        if not matched_dest:
            return None

        matched_origin = None
        for orig in self._get_origins(rfq_origin):
            m = self._fuzzy_match_location(orig, self._origin_candidates)
            if m:
                matched_origin = m
                break

        logger.debug(
            f"Fuzzy origin: '{rfq_origin}' -> '{matched_origin}' | "
            f"dest: '{rfq_dest}' -> '{matched_dest}'"
        )

        if not matched_origin:
            return None

        candidates = []
        for record in self.rate_records:
            if record.mode.lower().strip() != rfq_mode:
                continue
            if record.origin.lower().strip() != matched_origin.lower().strip():
                continue
            if record.destination.lower().strip() != matched_dest.lower().strip():
                continue
            candidates.append(record)

        if not candidates:
            return None

        candidates.sort(
            key=lambda r: len(r.origin) + len(r.destination),
            reverse=True,
        )
        return candidates[0]

    def _calculate(self, rate: RateRecord) -> tuple[float, str]:
        base      = rate.base_rate or 0.0
        surcharge = rate.surcharge or 0.0
        minimum   = rate.minimum_charge or 0.0
        subtotal  = base + surcharge
        estimated = max(subtotal, minimum)

        parts = [f"base_rate=${base:,.2f}"]
        if surcharge:
            parts.append(f"surcharge=${surcharge:,.2f}")
        if minimum and estimated == minimum:
            parts.append(f"minimum_charge applied=${minimum:,.2f}")
        if rate.notes:
            parts.append(f"note: {rate.notes}")

        return round(estimated, 2), " | ".join(parts)

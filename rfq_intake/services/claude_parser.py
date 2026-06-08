import dataclasses
import json
import logging
import re
import time
from typing import Optional

import requests

from core.config import settings
from core.models import RawRequest, ParsedRFQ

OLLAMA_BASE_URL = settings.OLLAMA_BASE_URL.rstrip("/")
OLLAMA_MODEL = settings.OLLAMA_MODEL_EXTRACTOR
OLLAMA_TIMEOUT = settings.OLLAMA_REQUEST_TIMEOUT

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Geographic databases
# ─────────────────────────────────────────────────────────────────────────────

_KOREA_TOKENS = frozenset({
    'busan', '부산', 'incheon', '인천', 'ulsan', '울산',
    'gwangyang', '광양', 'pyeongtaek', '평택', 'gimpo', '김포',
    'gimhae', '김해', 'hwaseong', '화성', 'asan', '아산', 'inchon',
    'korea', '한국', '경기도', '충남', '경남', '경북', '전남',
    'gyeonggi', 'icn', 'pus', 'south korea',
    'nampo', '남포', 'rajin', '라진', 'wonsan', '원산',
    'chungcheong', '충청', 'jeolla', '전라', 'gyeongsang', '경상',
    'jeju', '제주', 'gangwon', '강원',
})

_CHINA_TOKENS = frozenset({
    'shanghai', '상해', 'guangzhou', '광저우', 'dalian', '대련', 'dalina',
    'tianjin', '천진', 'qingdao', '청도', 'ningbo', '닝보',
    'shenzhen', '선전', 'beijing', '북경', 'china', '중국',
    'chengdu', 'wuhan', 'nanjing', 'suzhou', 'foshan', 'xiamen',
})

_JAPAN_TOKENS = frozenset({
    'tokyo', 'osaka', 'nagoya', 'yokohama', 'kobe', 'fukuoka',
    'japan', '일본', 'tyo', 'nrt', 'kix', 'osa',
})

_OTHER_FOREIGN_TOKENS = frozenset({
    'ukraine', 'kyiv', 'germany', 'berlin', 'hamburg', 'frankfurt', 'munich', 'bremen',
    'vietnam', 'hanoi', 'ho chi minh', 'hcmc', 'haiphong',
    'thailand', 'bangkok', 'laem chabang',
    'india', 'mumbai', 'chennai', 'nhava sheva', 'kolkata',
    'singapore', 'taiwan', 'taipei', 'kaohsiung', 'keelung',
    'malaysia', 'kuala lumpur', 'port klang', 'penang',
    'canada', 'toronto', 'vancouver', 'montreal',
    'mexico', 'guadalajara', 'monterrey', 'manzanillo', 'veracruz', 'lazaro cardenas',
    'uk', 'united kingdom', 'london', 'felixstowe', 'southampton',
    'netherlands', 'rotterdam', 'amsterdam',
    'antwerp', 'belgium',
    'france', 'le havre', 'marseille',
    'spain', 'barcelona', 'valencia', 'algeciras',
    'italy', 'genoa', 'naples', 'la spezia',
    'turkey', 'istanbul', 'izmir', 'mersin',
    'brazil', 'santos', 'rio de janeiro',
    'australia', 'sydney', 'melbourne', 'brisbane', 'fremantle',
    'indonesia', 'jakarta', 'surabaya', 'tanjung priok',
    'philippines', 'manila',
    'cambodia', 'phnom penh', 'sihanoukville',
    'myanmar', 'yangon', 'thilawa',
    'sri lanka', 'colombo',
    'pakistan', 'karachi',
    'saudi arabia', 'jeddah', 'dammam',
    'uae', 'dubai', 'jebel ali', 'abu dhabi',
    'egypt', 'port said', 'damietta',
    'south africa', 'durban', 'cape town',
    'kenya', 'mombasa',
    'poland', 'gdansk', 'warsaw',
    'czech', 'prague', 'hungary', 'budapest',
    'sweden', 'gothenburg', 'denmark', 'copenhagen',
    'finland', 'helsinki', 'norway', 'oslo',
    'russia', 'vladivostok', 'st. petersburg', 'moscow',
    'new zealand', 'auckland',
})

_FOREIGN_TOKENS = _KOREA_TOKENS | _CHINA_TOKENS | _JAPAN_TOKENS | _OTHER_FOREIGN_TOKENS

_US_STATE_ABBREVS = frozenset({
    'al', 'ak', 'az', 'ar', 'ca', 'co', 'ct', 'de', 'fl', 'ga',
    'hi', 'id', 'il', 'in', 'ia', 'ks', 'ky', 'la', 'me', 'md',
    'ma', 'mi', 'mn', 'ms', 'mo', 'mt', 'ne', 'nv', 'nh', 'nj',
    'nm', 'ny', 'nc', 'nd', 'oh', 'ok', 'or', 'pa', 'ri', 'sc',
    'sd', 'tn', 'tx', 'ut', 'vt', 'va', 'wa', 'wv', 'wi', 'wy',
    'usa', 'u.s.a.',
})

_US_STATE_FULL = frozenset({
    'alabama', 'alaska', 'arizona', 'arkansas', 'california', 'colorado',
    'connecticut', 'delaware', 'florida', 'georgia', 'hawaii', 'idaho',
    'illinois', 'indiana', 'iowa', 'kansas', 'kentucky', 'louisiana',
    'maine', 'maryland', 'massachusetts', 'michigan', 'minnesota',
    'mississippi', 'missouri', 'montana', 'nebraska', 'nevada',
    'new hampshire', 'new jersey', 'new mexico', 'new york',
    'north carolina', 'north dakota', 'ohio', 'oklahoma', 'oregon',
    'pennsylvania', 'rhode island', 'south carolina', 'south dakota',
    'tennessee', 'texas', 'utah', 'vermont', 'virginia', 'washington',
    'west virginia', 'wisconsin', 'wyoming',
})

_US_CITIES = frozenset({
    'los angeles', 'long beach', 'savannah', 'charleston', 'houston',
    'seattle', 'tacoma', 'new york', 'newark', 'baltimore', 'norfolk',
    'miami', 'jacksonville', 'new orleans', 'portland', 'oakland',
    'atlanta', 'chicago', 'dallas', 'denver', 'las vegas', 'phoenix',
    'memphis', 'kansas city', 'columbus', 'cleveland', 'detroit',
    'roanoke', 'pueblo', 'medford', 'hogansville', 'tarboro',
    'chesapeake', 'virginia beach', 'little chute', 'joliet',
    'city of industry', 'carson', 'gardena', 'torrance', 'compton',
    'laredo', 'el paso', 'san antonio', 'fort worth',
    'indianapolis', 'louisville', 'cincinnati', 'pittsburgh',
    'minneapolis', 'milwaukee', 'st. louis', 'saint louis',
    'charlotte', 'raleigh', 'greensboro', 'durham',
    'tampa', 'orlando', 'fort lauderdale', 'west palm beach',
    'salt lake city', 'albuquerque', 'tucson', 'fresno',
    'sacramento', 'san diego', 'san jose', 'san francisco',
    'claremont', 'riverside', 'ontario', 'anaheim',
})

_US_INLAND_CITIES = frozenset({
    # Midwest
    'chicago', 'kansas city', 'memphis', 'st. louis', 'saint louis',
    'minneapolis', 'milwaukee', 'columbus', 'cleveland', 'detroit',
    'indianapolis', 'louisville', 'cincinnati', 'pittsburgh',
    # Mountain / Southwest interior
    'denver', 'salt lake city', 'phoenix', 'las vegas', 'albuquerque', 'tucson',
    # Southeast (no container port)
    'atlanta', 'charlotte', 'raleigh', 'greensboro', 'durham', 'richmond',
    'orlando', 'fort lauderdale', 'west palm beach', 'tampa',
    # Texas interior
    'dallas', 'fort worth', 'san antonio', 'el paso', 'laredo',
    # California interior / LA basin (not the port cities)
    'fresno', 'sacramento', 'riverside', 'ontario', 'anaheim',
    'city of industry', 'carson', 'gardena', 'torrance', 'compton',
    # Other clearly inland
    'roanoke', 'pueblo', 'medford', 'hogansville', 'tarboro',
    'joliet', 'little chute', 'claremont',
    'chesapeake', 'virginia beach',
})

_US_ZIP_RE = re.compile(r'\b\d{5}(-\d{4})?\b')
_US_STATE_RE = re.compile(
    r',\s*(AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD'
    r'|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC'
    r'|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY)\b'
)


def _classify_location(loc: str) -> str:
    """Returns 'US', 'FOREIGN', or 'UNKNOWN'."""
    if not loc:
        return 'UNKNOWN'
    lower = loc.lower()
    if _US_ZIP_RE.search(loc):
        return 'US'
    if _US_STATE_RE.search(loc):
        return 'US'
    tokens = set(re.split(r'[\s,./\-()+]+', lower)) - {''}
    for t in tokens:
        if t in _US_STATE_ABBREVS:
            return 'US'
    for city in _US_CITIES:
        if city in lower:
            return 'US'
    for t in _US_STATE_FULL:
        if t in lower:
            return 'US'
    for t in tokens:
        if t in _FOREIGN_TOKENS:
            return 'FOREIGN'
    for ft in _FOREIGN_TOKENS:
        if len(ft) > 3 and ft in lower:
            return 'FOREIGN'
    return 'UNKNOWN'


def _scan_text_for_foreign(text: str) -> bool:
    lower = text.lower()
    for token in _FOREIGN_TOKENS:
        if len(token) > 3 and token in lower:
            return True
    return False


# ─────────────────────────────────────────────────────────────────────────────
# Company identity
# ─────────────────────────────────────────────────────────────────────────────

_OUR_COMPANY_NAMES = frozenset({
    'fns', 'fns inc', 'fns inc.', 'fns usa', 'fns, inc', 'fns, inc.',
    'cornerstone', 'cornerstone freight lines', 'cnrs',
    'genizipusa', 'geniezip', 'geniezipusa',
})
_OUR_DOMAIN_RE = re.compile(r'@(fnsusa|cnrsusa|geniezipusa)\.com', re.IGNORECASE)
_EMAIL_RE = re.compile(r'^[\w.+\-]+@[\w.\-]+\.[a-z]{2,}$', re.IGNORECASE)
_BARE_DOMAIN_RE = re.compile(r'^[\w.\-]+\.(com|net|org|co|kr|cn|jp|de|io)$', re.IGNORECASE)

_LOGISTICS_CO_RE = re.compile(
    r'\b(logistics|freight|transport|shipping|forwarding|forwarder'
    r'|express|air\s*cargo|ocean\s*cargo|customs|brokerage|trucking|carrier'
    r'|intermodal|로지스틱스|물류|운송|포워딩|통관)\b',
    re.IGNORECASE,
)


def _clean_company(value: Optional[str]) -> Optional[str]:
    """Returns None if value is our company, an email address, or a bare domain."""
    if not value:
        return value
    stripped = value.strip()
    if _EMAIL_RE.match(stripped) or _BARE_DOMAIN_RE.match(stripped):
        logger.info(f"Dropping email/domain artefact: '{stripped}'")
        return None
    if _OUR_DOMAIN_RE.search(stripped):
        return None
    normalized = stripped.lower()
    normalized = re.sub(r'[,.]?\s*(inc|corp|llc|ltd|co)\.?\s*$', '', normalized).strip()
    if normalized in _OUR_COMPANY_NAMES:
        return None
    return stripped


def _validate_partner_customer(
    partner: Optional[str],
    customer: Optional[str],
) -> tuple[Optional[str], Optional[str]]:
    """Partner column always filled first; customer only when a second company is known."""
    # Partner is empty but customer is set → move to partner
    if not partner and customer:
        logger.info(f"Moving customer '{customer}' → partner (partner takes priority)")
        return customer, None
    if partner and customer:
        partner_looks_logistics = bool(_LOGISTICS_CO_RE.search(partner))
        customer_looks_logistics = bool(_LOGISTICS_CO_RE.search(customer))
        if not partner_looks_logistics and customer_looks_logistics:
            logger.info(f"Swapping partner/customer: '{customer}' appears to be the forwarder")
            return customer, partner
    return partner, customer


# ─────────────────────────────────────────────────────────────────────────────
# Cargo signal patterns
# ─────────────────────────────────────────────────────────────────────────────

_VALID_MODES = frozenset({'AI', 'AO', 'SI', 'SO', 'DR', 'TL', 'OTR', 'WH', 'CC', 'BORDER', 'OOG'})
_SEA_CARGO_TERMS = frozenset({'LCL', 'FCL', 'OCEAN', 'SEA', 'VESSEL'})
_AIR_CARGO_TERMS = frozenset({'AIR', 'AIRFREIGHT'})
_DOMESTIC_CARGO_TERMS = frozenset({'TRUCK', 'RAIL', 'GROUND'})

_SEA_CONTAINER_RE = re.compile(
    r"\b(40HC|40HQ|20GP|40FR|45HC|40OT|20OT|40'HC|20'GP|40'HQ|40'FR)\b", re.IGNORECASE
)
_AIR_RE = re.compile(
    r'\b(air\s*freight|airfreight|air\s*cargo|항공화물|air\s*only|항공)\b', re.IGNORECASE
)
_DRAY_RE = re.compile(
    r'\b(drayage|dray|port\s*pickup|ramp\s*pickup|port\s*delivery|rail\s*ramp'
    r'|CFS|container\s*freight\s*station|terminal\s*pickup|port\s*gate)\b',
    re.IGNORECASE,
)
_OOG_RE = re.compile(
    r'\b(flat\s*rack|open\s*top|OOG|out\s*of\s*gauge|oversize|wide\s*load'
    r'|heavy\s*lift|over.?dimension)\b',
    re.IGNORECASE,
)
_TEMP_RE = re.compile(
    r'\b(reefer|refrigerat|frozen|temperature.?controlled|냉동|냉장)\b', re.IGNORECASE
)
_HAZMAT_RE = re.compile(
    r'\b(hazmat|dangerous\s*goods|DG\s*cargo|UN\s*\d{4}|IATA\s*class|IMDG)\b', re.IGNORECASE
)

# ── WH operations keywords (space/handling billing — NOT just delivery to a warehouse building)
_WH_OPERATION_KEYWORDS = frozenset({
    # English — space/capacity billing (clearly WH-specific, not port storage)
    'sqft', 'sq ft', 'square feet', 'square footage',
    'pallet position', 'pallet positions',
    'per pallet per month', 'monthly storage',
    'warehousing rate', 'warehousing fee',
    # English — warehouse-specific operations
    'pick and pack', 'pick & pack',
    'order fulfillment', 'fulfillment service', 'fulfillment center',
    'inventory management service', 'racking service',
    # Korean — clearly WH-specific (port emails don't use these)
    '보관료',       # storage fee
    '입출고료',     # in-out fee
    '창고 임대',    # warehouse rental
    '창고임대',
    '보관 서비스',  # storage service
    '보관서비스',
    # NOTE: 'storage rate/fee/charges', 'warehouse rate' removed —
    # these appear in port/CFS detention contexts and cause false WH classification
})

# ── Vendor decline signals
_VENDOR_DECLINED_RE = re.compile(
    r'(?:'
    r'cannot\s+(?:match|offer|meet|accommodate)\s+(?:the\s+)?(?:rate|price|quote|request)'
    r'|(?:not\s+able|unable)\s+to\s+(?:quote|bid|price|match)'
    r'|(?:we\s+)?(?:need\s+to\s+)?pass\s+on\s+this'
    r'|(?:rate|price|margin)\s+(?:is\s+)?(?:too\s+)?(?:low|thin|slim)\s+(?:for\s+us\s+)?to\s+(?:accept|work\s+with)'
    r'|declining\s+(?:this\s+)?(?:quote|rfq|bid|request)'
    r'|below\s+(?:our\s+)?(?:cost|minimum|floor\s+rate)'
    r'|cannot\s+be\s+competitive\s+on\s+this'
    r'|rate\s+맞추기\s+(?:어렵|힘들)'
    r'|(?:수익|마진)\s*(?:이\s*)?(?:안\s*)?(?:나오|맞지)'
    r')',
    re.IGNORECASE,
)

_RATE_NOT_COMPETITIVE_RE = re.compile(
    r'(?:'
    r'rate\s+(?:is\s+)?not\s+competitive'
    r'|competitor\s+(?:is\s+)?(?:offering|has|at)\s+(?:lower|better|cheaper)'
    r'|(?:we|our\s+rate)\s+(?:is\s+)?(?:higher|more\s+expensive|above\s+market)'
    r'|not\s+matching\s+(?:the\s+)?(?:market|competition)'
    r')',
    re.IGNORECASE,
)

# ── Hazmat classification signals
_HAZMAT_CONFIRMED_RE = re.compile(
    r'(?:'
    r'\bUN\s*\d{4}\b'
    r'|IMDG\s*class'
    r'|IATA\s*(?:DG|dangerous)'
    r'|class\s+[1-9]\s+(?:hazmat|DG|dangerous\s+goods)'
    r'|(?:confirmed|classified)\s+(?:as\s+)?(?:hazmat|DG|dangerous\s+goods)'
    r'|MSDS\s+available\b'
    r')',
    re.IGNORECASE,
)

_HAZMAT_QUESTION_RE = re.compile(
    r'(?:'
    r'DG\s+(?:status|confirmation|info(?:rmation)?)\s+(?:pending|required|needed|TBD)'
    r'|(?:need|waiting\s+for|pending)\s+(?:DG|hazmat|SDS)\s+(?:confirmation|sheet|info)'
    r'|not\s+(?:yet\s+)?confirmed\s+(?:as\s+)?(?:DG|hazmat)'
    r'|pending\s+(?:DG|hazmat|dangerous\s+goods)\s+(?:classification|confirmation)'
    r'|DG\s+confirmation\s+pending'
    r')',
    re.IGNORECASE,
)

# ── Vendor rate line pattern (lines like "Inbound: $8/PLT", "FCL 40HC: $3,500/container")
_RATE_LINE_RE = re.compile(
    r'\$\s*(\d[\d,]*(?:\.\d{1,2})?)'
    r'\s*(?:[/,]?\s*(?:per\s+)?(?:container|shipment|pallet|plt|cbm|m3|kg|lbs|unit|box|carton|ctn|ton|truck|move|shp))',
    re.IGNORECASE,
)


# ─────────────────────────────────────────────────────────────────────────────
# Python extraction helpers (volume, HS, incoterms, docs, timeline, routing)
# ─────────────────────────────────────────────────────────────────────────────

_CONTAINER_PATTERN = re.compile(
    r"((?:40|20)'?\s*(?:HC|GP|HQ|FR|OT))(?:\s*[×x\*]\s*(\d+))?", re.IGNORECASE
)
_MEASUREMENT_RE = re.compile(
    r'(\d{1,6}(?:[,\.]\d+)*)\s*'
    r'(kg|kgs|lbs|lb|cbm|m3|pallets?|pcs|pieces?|boxes?|cartons?'
    r'|crates?|skids?|drums?|rolls?|bags?|bundles?|units?)',
    re.IGNORECASE,
)
_CBM_RE = re.compile(r'(\d+(?:\.\d+)?)\s*(?:cbm|m3|cubic\s*meters?)', re.IGNORECASE)


def _extract_volume_from_text(text: str) -> Optional[str]:
    """Extract volume/quantity measurements from raw text as a fallback."""
    parts: list[str] = []

    # Sea containers (e.g. "40HC x 2")
    for m in _CONTAINER_PATTERN.finditer(text):
        container = m.group(1).strip()
        count = m.group(2)
        parts.append(f"{container} x {count}" if count else container)

    # Numeric quantities with units
    seen: set[str] = set()
    for m in _MEASUREMENT_RE.finditer(text):
        val = m.group(1).replace(',', '')
        unit = m.group(2).lower().rstrip('s')
        key = f"{val} {unit}"
        if key not in seen:
            seen.add(key)
            parts.append(f"{m.group(1)} {m.group(2)}")

    if not parts:
        return None
    return ' / '.join(list(dict.fromkeys(parts))[:6])


_HS_CODE_RE = re.compile(r'\b(\d{4}[\.\-]\d{2}(?:[\.\-]\d{2,4})?)\b')
_INCOTERMS_RE = re.compile(
    r'\b(EXW|FOB|CIF|DDP|DAP|CPT|CIP|FCA|FAS|CFR|DDU|DPU)\b', re.IGNORECASE
)

_DOC_PATTERNS: dict[str, re.Pattern] = {
    'ISF': re.compile(r'\bISF\b', re.IGNORECASE),
    # Require explicit "FTA" + "CO/C.O./certificate" together — bare C/O in addresses is NOT a document
    'FTA CO': re.compile(r'\bFTA\s*C/?O\b|\bFTA\s+certificate\b|certificate\s+of\s+origin|원산지\s*증명', re.IGNORECASE),
    'FDA': re.compile(r'\bFDA\b', re.IGNORECASE),
    'Bond': re.compile(r'\bcustoms?\s+bond\b|\bABI\b', re.IGNORECASE),
    'Duty & Tax': re.compile(r'duty\s*[&and]+\s*tax|관세|유첨서류', re.IGNORECASE),
    'MID': re.compile(r'\bMID\b|manufacturer\s+id', re.IGNORECASE),
}

_DATE_RE = re.compile(
    r'(?:ETD|ETA|pickup|ready|cutoff|deadline|by|until|출발|도착)\s*[:\-]?\s*'
    r'(\d{1,2}[/\-]\d{1,2}(?:[/\-]\d{2,4})?|\w+\s+\d{1,2}(?:st|nd|rd|th)?(?:\s*,?\s*\d{4})?)',
    re.IGNORECASE,
)
_URGENCY_RE = re.compile(r'\b(urgent|asap|immediately|rush|time.?sensitive)\b', re.IGNORECASE)

_FCL_RE = re.compile(r'\bFCL\b', re.IGNORECASE)
_LCL_RE = re.compile(r'\bLCL\b', re.IGNORECASE)
_CFS_RE = re.compile(r'(\w+(?:\s+\w+){0,2})\s+(?:area\s+)?CFS\b', re.IGNORECASE)
_TRANSSHIP_RE = re.compile(r'\btransship|\btransit\s+via\b', re.IGNORECASE)

_STACKABLE_RE = re.compile(r'\bstackable\b', re.IGNORECASE)
_FRAGILE_RE = re.compile(r'\bfragile\b|\bhandle\s+with\s+care\b', re.IGNORECASE)
_SPOT_RE = re.compile(r'\b(spot\s*quote|spot\s*rate|스팟\s*견적|spot)\b', re.IGNORECASE)

# Korean location modifiers to strip before dedup comparison
_KO_MODIFIER_RE = re.compile(r'\s*(?:인근|근처|부근)\s*')
# Service phrases that belong in [Services], not [Routing]
_SERVICE_IN_ROUTING_RE = re.compile(
    r'\b(bonded\s+warehouse\s+delivery|customs\s+exam|door\s+delivery'
    r'|transload(?:ing)?|cross.?dock(?:ing)?|deconsolidation|devan(?:ning)?)\b',
    re.IGNORECASE,
)
# Volume "(total X CBM)" → "X CBM"
_VOLUME_PAREN_RE = re.compile(
    r'\(\s*(?:total\s+)?(\d+(?:[.,]\d+)?)\s*(CBM|m3|KGS?|LBS?|pallets?|pcs|pieces?)\s*\)',
    re.IGNORECASE,
)

# Email Subject: line embedded in message body
_EMAIL_SUBJECT_RE = re.compile(r'^(?:Subject|제목)\s*:\s*(.+)$', re.MULTILINE | re.IGNORECASE)

# US address pattern for signature fallback  (street optional, city+state+zip required)
_US_ADDR_RE = re.compile(
    r'(?:(\d{1,5}\s+[\w][A-Za-z0-9\s\.,#\-]{3,50}?'
    r'(?:St\.?|Ave\.?|Blvd\.?|Drive|Dr\.?|Road|Rd\.?|Way|Lane|Ln\.?|Pkwy\.?|Court|Ct\.?|Place|Pl\.?|Circle|Cir\.?|Highway|Hwy\.?)\.?)'
    r'[,\s]*\n?\s*)?'
    r'([A-Za-z][A-Za-z\s]{1,25}),\s*'
    r'(AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY)\s+'
    r'(\d{5}(?:-\d{4})?)',
    re.IGNORECASE,
)

_DIMENSION_RE = re.compile(
    r'(\d+(?:\.\d+)?)\s*[×xX\*]\s*(\d+(?:\.\d+)?)\s*[×xX\*]\s*(\d+(?:\.\d+)?)\s*'
    r'(cm|mm|inch|in|ft|m)\b',
    re.IGNORECASE,
)


def _detect_hs_code(text: str) -> Optional[str]:
    m = _HS_CODE_RE.search(text)
    return m.group(0) if m else None


def _extract_incoterms(text: str) -> Optional[str]:
    m = _INCOTERMS_RE.search(text)
    return m.group(0).upper() if m else None


def _detect_docs(text: str) -> Optional[str]:
    found = [doc for doc, pat in _DOC_PATTERNS.items() if pat.search(text)]
    return ' | '.join(found) if found else None


def _detect_timeline(text: str) -> Optional[str]:
    parts = [m.group(0).strip() for m in _DATE_RE.finditer(text)]
    if _URGENCY_RE.search(text):
        parts.append('URGENT')
    return ' | '.join(dict.fromkeys(parts)[:3]) if parts else None


def _detect_note(text: str) -> Optional[str]:
    parts: list[str] = []
    if _SPOT_RE.search(text):
        parts.append('Spot quote requested')
    return ' | '.join(parts) if parts else None


def _extract_address_from_text(text: str) -> Optional[str]:
    """Extract the first US street address found in text (used as delivery_to fallback)."""
    for m in _US_ADDR_RE.finditer(text):
        street = (m.group(1) or '').strip().rstrip(',')
        city   = m.group(2).strip()
        state  = m.group(3).upper()
        zipcode = m.group(4)
        addr = f"{street}, {city}, {state} {zipcode}" if street else f"{city}, {state} {zipcode}"
        return re.sub(r'\s+', ' ', addr).strip()
    return None


def _detect_wh_mode(text: str) -> bool:
    """Return True only when text is requesting warehouse OPERATIONS, not just delivering to a warehouse."""
    lower = text.lower()
    return any(kw in lower for kw in _WH_OPERATION_KEYWORDS)


def _detect_hazmat_status(text: str, additional_info: Optional[str] = None) -> Optional[str]:
    """Classify hazmat status from text signals."""
    combined = text + ' ' + (additional_info or '')
    if re.search(
        r'(?:not|non)[- ](?:dg|hazmat|dangerous)|dg\s+(?:not\s+applicable|n/a)|no\s+hazmat',
        combined, re.IGNORECASE,
    ):
        return 'cleared'
    if _HAZMAT_CONFIRMED_RE.search(text):
        return 'confirmed'
    if _HAZMAT_QUESTION_RE.search(text):
        return 'pending_confirmation'
    if _HAZMAT_RE.search(text):
        return 'detected'
    return None


def _detect_vendor_declined(text: str) -> Optional[str]:
    """Detect vendor decline / rate-not-competitive signals from email text."""
    if _VENDOR_DECLINED_RE.search(text):
        return 'vendor_declined'
    if _RATE_NOT_COMPETITIVE_RE.search(text):
        return 'rate_not_competitive'
    return None


def _extract_rate_lines_from_text(text: str) -> Optional[str]:
    """Extract vendor-quoted rate lines (e.g. 'Inbound: $8/PLT') from email text."""
    found = []
    for line in text.split('\n'):
        line = line.strip()
        if not line or len(line) > 200:
            continue
        if _RATE_LINE_RE.search(line):
            found.append(line)
    if not found:
        return None
    seen: set[str] = set()
    deduped: list[str] = []
    for line in found:
        key = line.lower()
        if key not in seen:
            seen.add(key)
            deduped.append(line)
    return ' | '.join(deduped[:8])


def _is_address_abbreviation(s: Optional[str]) -> bool:
    """True when delivery_to is a short all-caps code (e.g. 'HAGA', 'IND') rather than a real address."""
    if not s:
        return True
    s = s.strip()
    return (
        len(s) <= 5        # "HAGA"=4, "IND"=3, "LACC"=4 — excludes "CHICAGO"=7, "NEWARK"=6
        and ' ' not in s
        and ',' not in s
        and not re.search(r'\d', s)
        and s == s.upper()
    )


def _extract_subject_from_content(text: str) -> Optional[str]:
    """Find an email Subject: line embedded in message body (for Doc/manual inputs)."""
    m = _EMAIL_SUBJECT_RE.search(text[:1500])
    return m.group(1).strip() if m else None


def _detect_routing(text: str) -> Optional[str]:
    parts: list[str] = []
    if _FCL_RE.search(text):
        parts.append('FCL')
    if _LCL_RE.search(text):
        parts.append('LCL')
    m = _CFS_RE.search(text)
    if m:
        parts.append(f"via {m.group(1).strip()} CFS")
    if _TRANSSHIP_RE.search(text):
        parts.append('transshipment')
    return ' | '.join(parts) if parts else None


def _detect_special(text: str) -> Optional[str]:
    parts: list[str] = []
    if _OOG_RE.search(text):
        dim = _DIMENSION_RE.search(text)
        desc = f"OOG - {dim.group(0)}" if dim else "OOG"
        parts.append(desc)
    if _TEMP_RE.search(text):
        parts.append('Temperature controlled')
    if _HAZMAT_RE.search(text):
        parts.append('Hazmat/DG')
    if _STACKABLE_RE.search(text):
        parts.append('Stackable')
    if _FRAGILE_RE.search(text):
        parts.append('Fragile')
    return ' | '.join(parts) if parts else None


def _infer_pol_from_text(mode: Optional[str], text: str) -> Optional[str]:
    """
    Infer missing POL by scanning text for origin port/city mentions.
    Pass mode=None to scan unconditionally; otherwise only fires for SI/AI.
    """
    if mode is not None and mode not in ('SI', 'AI'):
        return None
    lower = text.lower()
    # Korea (most common origin)
    if 'busan' in lower or '부산' in lower or 'pus' in lower:
        return 'Busan'
    if 'incheon' in lower or '인천' in lower or 'icn' in lower:
        return 'Incheon'
    if 'gwangyang' in lower or '광양' in lower:
        return 'Gwangyang'
    if 'pyeongtaek' in lower or '평택' in lower:
        return 'Pyeongtaek'
    if 'ulsan' in lower or '울산' in lower:
        return 'Ulsan'
    # China
    if 'shanghai' in lower or '상해' in lower:
        return 'Shanghai'
    if 'shenzhen' in lower or '선전' in lower:
        return 'Shenzhen'
    if 'qingdao' in lower or '청도' in lower:
        return 'Qingdao'
    if 'tianjin' in lower or '천진' in lower:
        return 'Tianjin'
    if 'ningbo' in lower or '닝보' in lower:
        return 'Ningbo'
    if 'dalian' in lower or '대련' in lower:
        return 'Dalian'
    if 'guangzhou' in lower or '광저우' in lower:
        return 'Guangzhou'
    # Japan
    if 'kobe' in lower:
        return 'Kobe'
    if 'yokohama' in lower:
        return 'Yokohama'
    if 'osaka' in lower:
        return 'Osaka'
    if 'nagoya' in lower:
        return 'Nagoya'
    # Vietnam
    if 'haiphong' in lower:
        return 'Haiphong'
    if 'ho chi minh' in lower or 'hcmc' in lower:
        return 'Ho Chi Minh City'
    # Thailand
    if 'laem chabang' in lower:
        return 'Laem Chabang'
    if 'bangkok' in lower:
        return 'Bangkok'
    return None


def _infer_pickup_from(
    existing: Optional[str],
    mode: Optional[str],
    pod: Optional[str],
    text: str,
) -> Optional[str]:
    """Infer pickup_from from CFS mentions or port context when not extracted."""
    if existing:
        return existing
    m = _CFS_RE.search(text)
    if m:
        return f"{m.group(1).strip()} CFS"
    if mode == 'SI' and pod and re.search(r'\bCFS\b|\bCY\b', text, re.IGNORECASE):
        return f"{pod} CFS"
    return None


def _enrich_additional_info(
    existing: Optional[str],
    text: str,
    mode: Optional[str],
    pod: Optional[str],
) -> Optional[str]:
    """
    Parse LLM's additional_info and enrich with Python-detected signals.
    Adds/merges [Cargo], [Routing], [Special], [Docs], [Timeline] sections.
    """
    # Parse existing into dict
    sections: dict[str, str] = {}
    if existing:
        for line in existing.strip().split('\n'):
            line = line.strip()
            m = re.match(r'\[(\w+)\]\s*(.*)', line)
            if m:
                sections[m.group(1)] = m.group(2).strip()

    def _norm(s: str) -> str:
        """Normalize for dedup: strip Korean location modifiers, lowercase, collapse spaces."""
        return re.sub(r'\s+', ' ', _KO_MODIFIER_RE.sub(' ', s)).strip().lower()

    def _merge(key: str, new_val: Optional[str]) -> None:
        if not new_val:
            return
        existing_val = sections.get(key, '')
        norm_existing = _norm(existing_val)
        parts_to_add = []
        for part in new_val.split(' | '):
            norm_part = _norm(part)
            if part and norm_part not in norm_existing:
                parts_to_add.append(part)
                norm_existing = (norm_existing + ' | ' + norm_part).strip(' | ')
        if parts_to_add:
            sections[key] = (
                (existing_val + ' | ' + ' | '.join(parts_to_add)).strip(' | ')
                if existing_val else ' | '.join(parts_to_add)
            )

    def _all_sections_text() -> str:
        return ' '.join(sections.values()).lower()

    # [Cargo] — HS code
    hs = _detect_hs_code(text)
    if hs:
        cargo = sections.get('Cargo', '')
        if 'HS' not in cargo:
            sections['Cargo'] = (f"HS {hs} | " + cargo).strip(' | ') if cargo else f"HS {hs}"

    # [Routing] — FCL/LCL/CFS/transship
    _merge('Routing', _detect_routing(text))

    # [Routing] → [Services]: move service phrases that LLM misplaced in [Routing]
    if 'Routing' in sections:
        routing_parts = [p.strip() for p in sections['Routing'].split(' | ') if p.strip()]
        keep, move = [], []
        for part in routing_parts:
            (move if _SERVICE_IN_ROUTING_RE.search(part) else keep).append(part)
        if move:
            sections['Routing'] = ' | '.join(keep) if keep else ''
            svc = sections.get('Services', '')
            for svc_part in move:
                if _norm(svc_part) not in _norm(svc):
                    svc = (svc + ' | ' + svc_part).strip(' | ') if svc else svc_part
            sections['Services'] = svc
        if not sections.get('Routing'):
            sections.pop('Routing', None)

    # [Special] — OOG/temp/hazmat only; skip stackable/fragile if already in another section
    special_raw = _detect_special(text)
    if special_raw:
        all_text = _all_sections_text()
        filtered = [
            p for p in special_raw.split(' | ')
            if p and (_norm(p) not in _norm(all_text) or p.lower().startswith('oog'))
        ]
        if filtered:
            _merge('Special', ' | '.join(filtered))

    # [Docs] — only if explicitly mentioned in text; never inferred from address context
    if 'Docs' not in sections:
        sections['Docs'] = _detect_docs(text) or ''

    # [Timeline] — dates and urgency
    if 'Timeline' not in sections:
        tl = _detect_timeline(text)
        if tl:
            sections['Timeline'] = tl

    # [Note] — spot quote, repeat shipment, etc.
    if 'Note' not in sections:
        note = _detect_note(text)
        if note:
            sections['Note'] = note

    # Remove empty entries
    sections = {k: v for k, v in sections.items() if v}

    if not sections:
        return existing

    order = ['Cargo', 'Routing', 'Special', 'Services', 'Docs', 'Timeline', 'Note']
    lines = [f"[{k}] {sections[k]}" for k in order if k in sections]
    for k, v in sections.items():
        if k not in order:
            lines.append(f"[{k}] {v}")
    return '\n'.join(lines) if lines else existing


# ─────────────────────────────────────────────────────────────────────────────
# Mode normalization + correction
# ─────────────────────────────────────────────────────────────────────────────

def _normalize_mode(mode: Optional[str]) -> Optional[str]:
    if mode is None:
        return None
    upper = mode.upper().strip()
    if upper in _VALID_MODES:
        return upper
    if upper in _SEA_CARGO_TERMS:
        return '_SEA'
    if upper in _AIR_CARGO_TERMS:
        return '_AIR'
    if upper in _DOMESTIC_CARGO_TERMS:
        return '_DOM'
    logger.info(f"Unrecognised mode '{mode}' → null")
    return None


def _correct_mode(
    mode: Optional[str],
    pol: Optional[str],
    pod: Optional[str],
    pickup_from: Optional[str],
    delivery_to: Optional[str],
    text: str,
) -> Optional[str]:
    mode = _normalize_mode(mode)
    if mode is None:
        return None

    has_sea_container = bool(_SEA_CONTAINER_RE.search(text))
    has_air = bool(_AIR_RE.search(text))
    has_dray = bool(_DRAY_RE.search(text))

    if mode == '_SEA':
        mode = 'SI'
    elif mode == '_AIR':
        mode = 'AI'
    elif mode == '_DOM':
        return 'DR' if (has_sea_container or has_dray) else 'OTR'

    # Sea containers → never AI/AO
    if has_sea_container and mode in ('AI', 'AO'):
        new_mode = 'SI' if mode == 'AI' else 'SO'
        logger.info(f"Mode {mode}→{new_mode}: sea container cannot be air")
        return new_mode

    # Classify pol and pickup_from separately so a foreign pol is not swamped
    # by a US pickup_from (e.g., Busan → Charleston CFS → NC warehouse).
    # Priority: pol > pickup_from for origin; pod > delivery_to for destination.
    pol_cls     = _classify_location(pol) if pol else 'UNKNOWN'
    pickup_cls  = _classify_location(pickup_from) if pickup_from else 'UNKNOWN'
    pod_cls     = _classify_location(pod) if pod else 'UNKNOWN'
    deliv_cls   = _classify_location(delivery_to) if delivery_to else 'UNKNOWN'

    origin_cls = pol_cls if pol_cls != 'UNKNOWN' else pickup_cls
    dest_cls   = pod_cls if pod_cls != 'UNKNOWN' else deliv_cls

    if origin_cls == 'UNKNOWN' and _scan_text_for_foreign(text):
        origin_cls = 'FOREIGN'

    # Both US → not international
    if origin_cls == 'US' and dest_cls == 'US' and mode in ('SI', 'SO', 'AI', 'AO'):
        new_mode = 'DR' if (has_sea_container or has_dray) else 'OTR'
        logger.info(f"Mode {mode}→{new_mode}: both origin and destination are US")
        return new_mode

    # Both foreign → no US leg
    if origin_cls == 'FOREIGN' and dest_cls == 'FOREIGN' and mode in ('SI', 'SO', 'AI', 'AO'):
        logger.info(f"Mode {mode}→null: both locations are foreign")
        return None

    # Foreign → US must be inbound
    if origin_cls == 'FOREIGN' and dest_cls in ('US', 'UNKNOWN'):
        if mode in ('SO', 'AO'):
            new_mode = 'SI' if (mode == 'SO' or has_sea_container) else 'AI'
            logger.info(f"Mode {mode}→{new_mode}: foreign→US must be inbound")
            return new_mode
        if mode in ('DR', 'OTR'):
            new_mode = 'AI' if (has_air and not has_sea_container) else 'SI'
            logger.info(f"Mode {mode}→{new_mode}: foreign origin → inbound, not domestic")
            return new_mode

    # US → foreign must be outbound
    if origin_cls == 'US' and dest_cls == 'FOREIGN':
        if mode in ('SI', 'AI'):
            new_mode = 'SO' if (mode == 'SI' or has_sea_container) else 'AO'
            logger.info(f"Mode {mode}→{new_mode}: US→foreign must be outbound")
            return new_mode

    return mode


def _correct_inland_pod(
    pod: Optional[str],
    delivery_to: Optional[str],
    mode: Optional[str],
) -> tuple[Optional[str], Optional[str]]:
    """
    If the LLM put an inland US city as POD for SI/AI mode and delivery_to is
    NOT already set, move pod → delivery_to and clear pod.
    If delivery_to is already set (e.g. Roanoke, IN), keep pod as-is —
    forwarders commonly use inland ICD cities (Chicago, etc.) as LCL POD.
    """
    if not pod or mode not in ('SI', 'AI'):
        return pod, delivery_to
    city_part = pod.split(',')[0].strip().lower()
    if city_part in _US_INLAND_CITIES:
        if not delivery_to:
            logger.info(f"POD '{pod}' is inland city → moved to delivery_to; pod=None")
            return None, pod
        else:
            logger.info(f"POD '{pod}' is inland city but delivery_to already set — keeping for rate matching")
    return pod, delivery_to


# ─────────────────────────────────────────────────────────────────────────────
# POD / POL normalization
# ─────────────────────────────────────────────────────────────────────────────

_TERMINAL_TO_CITY: dict[str, str] = {
    # US East Coast
    'wando': 'Charleston', 'north charleston': 'Charleston',
    'garden city': 'Savannah', 'ocean terminal': 'Savannah',
    'barbours cut': 'Houston', 'bayport': 'Houston',
    'gct bayonne': 'New York', 'gct': 'New York',
    'pnct': 'New York', 'maher': 'New York',
    'apm newark': 'Newark',
    'seagirt': 'Baltimore', 'cct': 'Baltimore',
    'nit': 'Norfolk', 'nnmt': 'Norfolk', 'vit': 'Norfolk',
    # US West Coast
    'lbct': 'Long Beach', 'cts': 'Long Beach', 'pier t': 'Long Beach',
    'its long beach': 'Long Beach',
    'apm terminal los angeles': 'Los Angeles', 'apm terminal': 'Los Angeles',
    'everport': 'Los Angeles', 'trapac': 'Los Angeles',
    'yusen': 'Los Angeles', 'pier 400': 'Los Angeles',
    # Pacific Northwest
    't30': 'Tacoma', 't46': 'Tacoma', 't18': 'Seattle',
}

_POL_POD_STRIP_RE = re.compile(
    r'\s*[,\-]?\s*(?:CFS|CY|인근|near|area|terminal|port|harbor|pier|gate|ramp|facility)\b.*',
    re.IGNORECASE,
)


def _clean_pod_pol(loc: Optional[str]) -> Optional[str]:
    """Normalize POD/POL: map terminal names to port cities, strip CFS/area suffixes."""
    if not loc:
        return loc
    lower = loc.lower().strip()
    # Longest match first (most specific terminal names)
    for terminal in sorted(_TERMINAL_TO_CITY, key=len, reverse=True):
        if terminal in lower:
            return _TERMINAL_TO_CITY[terminal]
    # Strip trailing "CFS", "인근", "terminal", etc.
    cleaned = _POL_POD_STRIP_RE.sub('', loc).strip()
    return cleaned if cleaned else loc


# ─────────────────────────────────────────────────────────────────────────────
# Korean → English normalization (safety net for LLM output)
# ─────────────────────────────────────────────────────────────────────────────

_KO_LOC_REPLACEMENTS: list[tuple[str, str]] = [
    ('인근', 'area'),
    ('근처', 'vicinity'),
    ('부근', 'area'),
    ('항구', 'port'),
    ('공항', 'airport'),
    ('창고', 'warehouse'),
]

_KO_COMPANY_MAP: dict[str, str] = {
    '선진 로지스틱스': 'Sunjin Logistics',
    '선진로지스틱스': 'Sunjin Logistics',
    '현대위아': 'Hyundai Wia',
    '현대 위아': 'Hyundai Wia',
    '현대글로비스': 'Hyundai Glovis',
    '현대 글로비스': 'Hyundai Glovis',
    '한진': 'Hanjin',
    '삼성전자': 'Samsung Electronics',
    '삼성물산': 'Samsung C&T',
    '엘지전자': 'LG Electronics',
    'lg전자': 'LG Electronics',
    '포스코': 'POSCO',
    '두산': 'Doosan',
    '롯데': 'Lotte',
    '기아': 'Kia',
    '현대자동차': 'Hyundai Motor',
    '한화': 'Hanwha',
    '코오롱': 'Kolon',
    '동부': 'Dongbu',
    '세방': 'Sebang',
    '범한': 'Bumhan',
}
# Korean character range (Hangul syllables + Jamo)
_HAS_KOREAN_RE = re.compile(r'[가-힣ᄀ-ᇿ㄰-㆏]')


def _ko_to_en_company(name: Optional[str]) -> Optional[str]:
    """Map known Korean company names to English; return unchanged if unknown."""
    if not name:
        return name
    lower = name.strip().lower()
    for ko, en in _KO_COMPANY_MAP.items():
        if ko.lower() in lower:
            return en
    return name


def _ko_to_en_location(loc: Optional[str]) -> Optional[str]:
    """Replace Korean location modifiers with English equivalents."""
    if not loc:
        return loc
    for ko, en in _KO_LOC_REPLACEMENTS:
        loc = loc.replace(ko, f' {en} ')  # pad with spaces to avoid merging with adjacent text
    return re.sub(r'\s+', ' ', loc).strip()


def _strip_korean(value: Optional[str]) -> Optional[str]:
    """
    If a string still contains Korean characters after LLM processing,
    attempt known replacements; return None if entirely Korean and unmappable.
    """
    if not value or not _HAS_KOREAN_RE.search(value):
        return value
    # Apply company map
    mapped = _ko_to_en_company(value)
    if mapped != value:
        return mapped
    # Apply location replacements
    cleaned = _ko_to_en_location(value)
    return cleaned


# ─────────────────────────────────────────────────────────────────────────────
# Pre-screening
# ─────────────────────────────────────────────────────────────────────────────

_SHIPMENT_SIGNALS = re.compile(
    r'\b(POL|POD|FCL|LCL|EXW|FOB|CIF|DDP|DAP'
    r'|40HC|40HQ|20GP|40FR|45HC'
    r'|drayage|dray|transload|airfreight'
    r'|kg|lbs|cbm|pallet|pcs|carton|crate|container'
    r'|busan|incheon|ulsan|gwangyang|shanghai|guangzhou|dalian|tianjin|qingdao|shenzhen'
    r'|los angeles|long beach|savannah|charleston|houston|seattle|tacoma|norfolk'
    r'|부산|인천|울산|광양|상해|청도|대련|천진)\b',
    re.IGNORECASE,
)
_ADMIN_PHRASES = (
    '확인하였습니다', '확인했습니다', '알겠습니다', '알겠어요',
    '수고하세요', '수고하십시오', '고맙습니다',
    'isf 신고 완료', '신고 완료했습니다',
    'out of office', 'auto-reply', 'automatic reply',
    'i am out of the office', 'i will be out',
)


def _prescreen(text: str) -> Optional[dict]:
    if _SHIPMENT_SIGNALS.search(text):
        return None
    lower = text.strip().lower()
    for phrase in _ADMIN_PHRASES:
        if phrase in lower and len(text.strip()) < 300:
            return {"skip": True, "reason": "Admin-only message: no shipment details"}
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Prompt hint builders
# ─────────────────────────────────────────────────────────────────────────────

def _extract_subject_hints(subject: Optional[str]) -> list[str]:
    """Return LLM hints extracted from an email subject line."""
    if not subject:
        return []
    hints: list[str] = []
    # Korean company name in subject
    for ko, en in _KO_COMPANY_MAP.items():
        if ko in subject:
            hints.append(f"Subject mentions customer/company: {en} ('{ko}')")
            return hints
    # Dot/slash separated tokens that look like English company names
    for part in re.split(r'[./\-]', subject):
        part = part.strip()
        if part and not _HAS_KOREAN_RE.search(part) and 2 < len(part) < 50:
            if re.match(r'^[A-Z][A-Za-z0-9\s&,]+$', part):
                hints.append(f"Subject mentions: {part}")
    return hints


def _build_mode_hint(text: str) -> str:
    hints = []
    if _SEA_CONTAINER_RE.search(text):
        hints.append("sea container → mode: SI/SO/DR only, never AI/AO")
    elif _AIR_RE.search(text):
        hints.append("air freight → mode: AI or AO")
    if _OOG_RE.search(text):
        hints.append("OOG/oversize cargo")
    if _TEMP_RE.search(text):
        hints.append("temperature-controlled")
    if _HAZMAT_RE.search(text):
        hints.append("hazmat/dangerous goods")
    if _DRAY_RE.search(text):
        hints.append("drayage/port move → consider DR")
    return " | ".join(hints)


def _build_extraction_hints(text: str) -> list[str]:
    """Pre-extract structured patterns to help the smaller LLM."""
    hints = []
    vol = _extract_volume_from_text(text)
    if vol:
        hints.append(f"Quantities detected: {vol}")
    inc = _extract_incoterms(text)
    if inc:
        hints.append(f"Incoterms detected: {inc}")
    hs = _detect_hs_code(text)
    if hs:
        hints.append(f"HS code detected: {hs}")
    docs = _detect_docs(text)
    if docs:
        hints.append(f"Documents referenced: {docs}")
    mode_h = _build_mode_hint(text)
    if mode_h:
        hints.append(f"Mode signal: {mode_h}")
    return hints


# ─────────────────────────────────────────────────────────────────────────────
# System prompt — compact with one-shot example
# ─────────────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a freight logistics data extractor for a US 3PL company.
Return ONLY valid JSON. No markdown, no explanation, no code fences.
ALL OUTPUT VALUES MUST BE IN ENGLISH. Translate Korean company names to their official English name (e.g. 현대위아→Hyundai Wia, 선진 로지스틱스→Sunjin Logistics, 현대글로비스→Hyundai Glovis, 한진→Hanjin). Translate Korean location terms (인근→area, 근처→vicinity). Translate Korean item/commodity names to English.

FIELDS:
- partner: freight forwarder or agent sending this RFQ. If WE ask a vendor for rates → partner = that vendor.
- customer: actual cargo owner or shipper. null if not stated or same as partner.
- mode: AI | AO | SI | SO | DR | TL | OTR | WH | CC | BORDER | OOG
    AI=air inbound→USA  AO=air outbound USA→foreign
    SI=sea inbound→USA  SO=sea outbound USA→foreign
    DR=drayage (port/CFS/ramp to local destination)  OTR=domestic US truck (53' dry van)
    WH=warehouse OPERATIONS only (storage fees/sqft/in-out handling). Delivering TO a warehouse → SI/DR/OTR, NOT WH.
  → Direction = PHYSICAL CARGO MOVEMENT only. Ignore "export/수출/import/수입" — sender's perspective.
  → Sea containers (40HC/40HQ/20GP/40FR/45HC) → SI/SO/DR only. Never AI/AO.
  → Port terminal (Bayport, Barbours Cut, APM, LBCT, ITS, GCT) → treat as associated US port city.
  → null if undetermined.
- pol: port of loading city (in DEPARTURE country). Korea cargo → Korean city. US cargo → US city.
- pod: ARRIVAL PORT CITY only. Never an inland city or address.
  "Final delivery to Pueblo CO" → pod=Los Angeles, delivery_to=100 Tower Rd Pueblo CO 81004.
- delivery_to: final delivery address or city/state.
- pickup_from: pickup address or city/state. For SI/DR: often a CFS near the port.
- item: cargo type or commodity. Translate to English. Multiple SKUs → comma-separated list.
- volume: ALL quantity/weight as written. "4 boxes / 3.06 CBM / 1,880 kg" | "40HC x 2" | "40 units / 17,006 lbs per unit".
- incoterms: EXW/FOB/CIF/DDP/DAP/etc. null if not stated.
- additional_info: plain string (NOT JSON object). Non-empty sections only:
  [Cargo] HS code, handling, cargo type detail
  [Routing] FCL/LCL, CFS, transit ports
  [Special] OOG (with dims) / temperature / hazmat / stackable
  [Services] specific services
  [Docs] ISF / FTA CO / FDA / bond / Duty & Tax — ONLY if explicitly stated in text. Never infer from address (C/O in delivery address is NOT a document).
  [Timeline] ETD/ETA, pickup date, urgency
  [Note] other context (spot quote, repeat shipment, etc.)
- confidence: 0.0–1.0 (completeness of available info).

RULES:
1. Extract EVERY explicit field. Confidence NEVER blocks extraction.
2. Our company (FNS/FNS USA/Cornerstone/CNRS/GeniZip/@fnsusa.com) → never partner or customer.
3. "유첨서류 참고" / "refer to attachment" → extract all body fields; lower confidence.
4. Email thread → read oldest→newest. LATEST reply is authoritative for ALL field values.
5. Forwarded RFQ → partner=forwarder, customer=end shipper.
6. {"skip":true,"reason":"..."} ONLY if zero shipment info, purely administrative.
7. Multiple RFQs (--new-- separator) → [{...},{...}]

EXAMPLE:
Input: "Sunjin Logistics requests spot quote for Hyundai Wia. POL: Busan, POD: Charleston CFS. Cargo: Shaft Ring Gear (C1). 4 boxes / 3.06 CBM / 1,880.80 kg. DDP. Deliver to GKN Newton C/O Bonded Warehouse, 2515 BGA Drive, Claremont NC 28610. Refer to attachment for Duty & Tax."
Output: {"partner":"Sunjin Logistics","customer":"Hyundai Wia","mode":"SI","pol":"Busan","pod":"Charleston","delivery_to":"GKN Newton C/O Bonded Warehouse, 2515 BGA Drive, Claremont, NC 28610","pickup_from":"Charleston CFS","item":"Shaft Ring Gear (C1)","volume":"4 boxes / 3.06 CBM / 1,880.80 kg","incoterms":"DDP","additional_info":"[Routing] FCL via Charleston CFS | Bonded warehouse delivery\n[Docs] Duty & Tax (attachment referenced)","confidence":0.85}

OUTPUT FORMAT:
Single: {"partner":...,"customer":...,"mode":...,"pol":...,"pod":...,"delivery_to":...,"pickup_from":...,"item":...,"volume":...,"incoterms":...,"additional_info":...,"confidence":...}
Skip: {"skip":true,"reason":"..."}
Multiple: [{...},{...}]"""


# ─────────────────────────────────────────────────────────────────────────────
# Vertical table preprocessor
# ─────────────────────────────────────────────────────────────────────────────

_VERTICAL_TABLE_FIELDS = frozenset({
    "POL", "POD", "INCOTERMS", "INCOTERM",
    "ITEM", "ITEMS", "COMMODITY",
    "SHPR", "CNEE", "SHIPPER", "CONSIGNEE",
    "TYPE", "TYPE & Q'TY", "Q'TY", "QTY",
    "DIMS", "DIMENSIONS", "DIMENSION",
    "GROSS WEIGHT", "WEIGHT", "G.W",
    "REMARK", "REMARKS",
    "PICK UP", "PICKUP",
    "DEST", "DESTINATION",
    "DELIVERY", "DELIVERY TO",
    "CBM", "VOLUME",
    "HS CODE", "HS",
    "CONTAINER", "SIZE", "EQUIPMENT",
    "ORIGIN", "FINAL DEST", "FINAL DESTINATION",
})


def _preprocess_text(text: str) -> str:
    """Convert vertical table format to key: value lines."""
    lines = text.split("\n")
    result = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        line_upper = line.upper().rstrip(":")
        if line_upper in _VERTICAL_TABLE_FIELDS:
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines):
                next_line = lines[j].strip()
                if next_line.upper().rstrip(":") not in _VERTICAL_TABLE_FIELDS and next_line:
                    result.append(f"{line}: {next_line}")
                    i = j + 1
                    continue
        result.append(lines[i])
        i += 1
    return "\n".join(result)


# ─────────────────────────────────────────────────────────────────────────────
# Parser
# ─────────────────────────────────────────────────────────────────────────────

class ClaudeParser:
    def __init__(self):
        pass

    def parse(self, raw: RawRequest) -> list[ParsedRFQ]:
        if "--new--" in raw.content:
            sections = [s.strip() for s in raw.content.split("--new--") if s.strip()]
            results = []
            for i, section in enumerate(sections):
                sub = dataclasses.replace(
                    raw,
                    content=section,
                    source_name=f"{raw.source_name}[{i + 1}]",
                )
                results.extend(self._parse_single(sub))
            return results

        return self._parse_single(raw)

    def _call_ollama(self, user_message: str) -> dict:
        """Call Ollama API with up to 2 retries on timeout."""
        last_exc: Exception = RuntimeError("Ollama call not attempted")
        for attempt in range(3):
            label = f" [retry {attempt}]" if attempt else ""
            logger.info(f"Calling Ollama ({OLLAMA_MODEL}){label} — timeout={OLLAMA_TIMEOUT}s ...")
            t0 = time.time()
            try:
                response = requests.post(
                    f"{OLLAMA_BASE_URL}/api/chat",
                    json={
                        "model": OLLAMA_MODEL,
                        "messages": [
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": user_message},
                        ],
                        "stream": False,
                        "think": False,
                        "options": {
                            "temperature": 0.0,
                            "num_ctx": 8192,    # prompt+response fits in ~5k tokens; 32768 wastes KV cache
                            "num_predict": 900, # JSON response rarely exceeds 700 tokens
                        },
                    },
                    timeout=OLLAMA_TIMEOUT,
                )
                logger.info(f"Ollama responded in {time.time() - t0:.1f}s")
                return response.json()
            except requests.Timeout as exc:
                logger.error(f"Ollama API error: {exc}")
                last_exc = exc
                if attempt < 2:
                    wait = 10 * (attempt + 1)
                    logger.info(f"Retrying in {wait}s...")
                    time.sleep(wait)
            except requests.RequestException as exc:
                logger.error(f"Ollama API error: {exc}")
                raise
        raise last_exc

    def _parse_single(self, raw: RawRequest) -> list[ParsedRFQ]:
        content = raw.content if raw.image_data else _preprocess_text(raw.content)

        pre = _prescreen(content)
        if pre and pre.get("skip"):
            logger.info(f"Prescreened skip ({raw.source_name}): {pre['reason']}")
            return []

        preprocessed = dataclasses.replace(raw, content=content)
        user_message = self._build_prompt(preprocessed)

        try:
            resp = self._call_ollama(user_message)
            raw_text = resp["message"]["content"].strip()
            extracted = json.loads(_clean_json(raw_text))

            # LLM returned multiple RFQs — keep all valid ones
            if isinstance(extracted, list):
                results = []
                for item in extracted:
                    if not isinstance(item, dict) or item.get("skip"):
                        continue
                    conf = _to_float(item.get("confidence"))
                    if conf is not None and conf < 0.1:
                        continue
                    results.append(self._build_parsed_rfq(raw, item, content))
                return results

            if extracted.get("skip"):
                logger.info(f"LLM skip ({raw.source_name}): {extracted.get('reason', '')}")
                return []

            conf = _to_float(extracted.get("confidence"))
            if conf is not None and conf < 0.1:
                logger.info(f"Skipping: confidence {conf} < 0.1")
                return []

            return [self._build_parsed_rfq(raw, extracted, content)]

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON from Ollama: {e}")
            return []
        except requests.RequestException as e:
            logger.error(f"Ollama API error: {e}")
            return []

    def _build_prompt(self, raw: RawRequest) -> str:
        truncated = raw.content[:6000]
        # Use explicit subject, or extract from embedded Subject: line in body
        effective_subject = raw.subject or _extract_subject_from_content(truncated)
        hints = _build_extraction_hints(truncated)
        hints.extend(_extract_subject_hints(effective_subject))
        hint_block = '\n'.join(f"  • {h}" for h in hints)
        hint_section = f"\n[Pre-analysis]\n{hint_block}" if hints else ""
        subject_line = f"Subject: {effective_subject}\n" if effective_subject else ""
        return (
            f"Extract RFQ shipment details from the text below.{hint_section}\n\n"
            f"Source: {raw.source_type} / {raw.source_name}\n"
            f"{subject_line}\n"
            f"--- BEGIN ---\n{truncated}\n--- END ---"
        )

    def _build_parsed_rfq(self, raw: RawRequest, extracted: dict, full_text: str) -> ParsedRFQ:
        # additional_info: handle dict return
        additional_info = extracted.get("additional_info")
        if isinstance(additional_info, dict):
            additional_info = "\n".join(
                f"[{k}] {v}" for k, v in additional_info.items() if v
            )

        # Normalize POL/POD: strip CFS/terminal/area suffixes, map terminals → cities
        pol          = _clean_pod_pol(extracted.get("pol"))
        pod          = _clean_pod_pol(extracted.get("pod"))
        delivery_to  = extracted.get("delivery_to")
        pickup_from  = extracted.get("pickup_from")

        # Pre-infer pol from text (mode-agnostic) so geographic correction has a
        # proper origin even when the LLM only extracted the drayage/CFS leg.
        pol_hint = pol or _infer_pol_from_text(None, full_text)

        # WH mode validation: only UNDO incorrect WH — never force WH from Python.
        # LLM decides WH; Python only corrects if LLM said WH but no clear WH ops keywords found.
        raw_mode_str = extracted.get("mode")
        if raw_mode_str and raw_mode_str.upper() == 'WH' and not _detect_wh_mode(full_text):
            logger.info("Mode WH → None: no WH ops keywords in text, treating as non-WH")
            mode = _correct_mode(None, pol_hint, pod, pickup_from, delivery_to, full_text)
        else:
            mode = _correct_mode(raw_mode_str, pol_hint, pod, pickup_from, delivery_to, full_text)

        # Confirm inferred pol only if mode resolved to inbound
        if not pol and mode in ('SI', 'AI'):
            pol = pol_hint

        # Fix 1: inland POD (e.g. Chicago) → move to delivery_to, clear pod
        pod, delivery_to = _correct_inland_pod(pod, delivery_to, mode)

        # Partner/Customer: clean + validate order + Korean→English
        partner  = _strip_korean(_clean_company(extracted.get("partner")))
        customer = _strip_korean(_clean_company(extracted.get("customer")))
        partner, customer = _validate_partner_customer(partner, customer)

        # Volume: use LLM value or fall back to Python extraction; normalize parentheticals
        volume = extracted.get("volume") or _extract_volume_from_text(full_text)
        if volume:
            # "(total 3.06 CBM)" → "/ 3.06 CBM" so "4 BOXES (total 3.06 CBM)" → "4 BOXES / 3.06 CBM"
            volume = _VOLUME_PAREN_RE.sub(lambda m: f"/ {m.group(1)} {m.group(2).upper()}", volume).strip()

        # Incoterms: use LLM value or fall back to Python detection
        incoterms = extracted.get("incoterms") or _extract_incoterms(full_text)

        # Location fields: strip any remaining Korean location modifiers
        pickup_from = _ko_to_en_location(pickup_from)
        delivery_to = _ko_to_en_location(delivery_to)

        # Item: strip Korean if LLM forgot to translate
        item = _strip_korean(extracted.get("item"))

        # Pickup From: infer from CFS / port context if missing
        pickup_from = _infer_pickup_from(pickup_from, mode, pod, full_text)

        # Fix 3: delivery_to fallback — scan full text for US address (email signature)
        # Also fires when delivery_to is just a short abbreviation (e.g. "HAGA")
        if _is_address_abbreviation(delivery_to) and mode in ('SI', 'AI', 'DR', 'OTR'):
            addr = _extract_address_from_text(full_text)
            if addr:
                prev = delivery_to
                delivery_to = addr
                logger.info(f"delivery_to {'upgraded from abbreviation' if prev else 'inferred'} → {addr}")

        # Additional info: enrich with Python-detected signals
        additional_info = _enrich_additional_info(additional_info, full_text, mode, pod)

        # Hazmat status classification (post-processing, uses enriched additional_info)
        hazmat_status = _detect_hazmat_status(full_text, additional_info)
        if hazmat_status and hazmat_status in ('confirmed', 'pending_confirmation', 'detected'):
            logger.info(f"Hazmat status: {hazmat_status}")

        # Vendor decline / rate-not-competitive detection
        vendor_response_status = (
            extracted.get("vendor_response_status")
            or _detect_vendor_declined(full_text)
        )
        if vendor_response_status:
            logger.info(f"Vendor response status: {vendor_response_status}")

        # Extract vendor-quoted rate lines (preserved in pricing_notes when no rate table match)
        extracted_rate_lines = _extract_rate_lines_from_text(full_text)
        if extracted_rate_lines:
            logger.info(f"Extracted rate lines: {extracted_rate_lines[:80]}...")

        # Confidence: default to 0.7 if LLM omitted it (don't block pricing silently)
        confidence = _to_float(extracted.get("confidence"))
        if confidence is None:
            confidence = 0.7

        return ParsedRFQ(
            source_type=raw.source_type,
            source_name=raw.source_name,
            received_time=raw.received_time,
            sender=raw.sender,
            subject=raw.subject,
            partner=partner,
            customer=customer,
            mode=mode,
            pol=pol,
            pod=pod,
            delivery_to=delivery_to,
            pickup_from=pickup_from,
            item=item,
            volume=volume,
            incoterms=incoterms,
            additional_info=additional_info,
            confidence=confidence,
            hazmat_status=hazmat_status,
            vendor_response_status=vendor_response_status,
            extracted_rate_lines=extracted_rate_lines,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _clean_json(text: str) -> str:
    text = re.sub(r"```(?:json)?", "", text).strip()
    try:
        _, end = json.JSONDecoder().raw_decode(text)
        return text[:end]
    except json.JSONDecodeError:
        return text


def _to_float(value) -> Optional[float]:
    if value is None:
        return None
    try:
        return max(0.0, min(1.0, float(value)))
    except (ValueError, TypeError):
        return None

"""Strip personal data from email text BEFORE it is sent to any model.

Removes: email addresses, phone numbers, Eircodes / postcodes, card numbers and "ending in 1234",
greetings with names, and the lines under address headings ("Delivery address", "Shipping to", ...).
"""

import re

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
# Phone candidates start with + or 0; we then require 9-15 digits so order numbers and prices survive.
PHONE_RE = re.compile(r"(?:\+|\b0)[\d\s().-]{7,20}\d")
EIRCODE_RE = re.compile(r"\b[A-Z]\d[\dW]\s?[A-Z\d]{4}\b")
UK_POSTCODE_RE = re.compile(r"\b[A-Z]{1,2}\d[A-Z\d]?\s\d[A-Z]{2}\b")
CARD_HINT_RE = re.compile(
    r"(?i)\b(?:ending(?:\s+in)?|endet\s+auf|last\s+(?:4|four)(?:\s+digits)?|card\s+no\.?)\s*[:#]?\s*[*•xX\s]*\d{4}\b"
    r"|[*•xX]{4,}[\s-]*\d{4}\b"
)
CARD_NUMBER_RE = re.compile(r"\b(?:\d[ -]?){13,19}\b")
GREETING_RE = re.compile(r"(?im)^(\s*(?:hi|hello|hey|dear|hallo|liebe[rs]?)\s+)([A-ZÄÖÜ][\w'’-]+)")
ADDRESS_HEADINGS = re.compile(
    r"(?i)^\s*(delivery|billing|shipping|postal|home|your)\s+address\b|^\s*(shipping|ship|deliver(?:ing)?|sending)\s+to\b"
    r"|^\s*(lieferadresse|rechnungsadresse|versandadresse|lieferanschrift)\b|^\s*recipient\b"
)
MAX_ADDRESS_LINES = 6


def _luhn_ok(digits: str) -> bool:
    total, parity = 0, len(digits) % 2
    for i, ch in enumerate(digits):
        d = int(ch)
        if i % 2 == parity:
            d = d * 2 - 9 if d * 2 > 9 else d * 2
        total += d
    return total % 10 == 0


ORDER_NUMBER_CONTEXT = re.compile(r"(?i)(order|bestell\w*|invoice|ref\w*|no\.?|nr\.?|number|#)\s*[:#]?\s*$")


def _phone(match: re.Match[str]) -> str:
    digits = re.sub(r"\D", "", match.group(0))
    preceding = match.string[max(0, match.start() - 20) : match.start()]
    if ORDER_NUMBER_CONTEXT.search(preceding):  # "Order no. 0845120397" is an ID, not a phone
        return match.group(0)
    return "[PHONE]" if 9 <= len(digits) <= 15 else match.group(0)


def _card(match: re.Match[str]) -> str:
    digits = re.sub(r"\D", "", match.group(0))
    return "[CARD]" if 13 <= len(digits) <= 19 and _luhn_ok(digits) else match.group(0)


def _drop_address_blocks(text: str) -> str:
    out: list[str] = []
    skipping = 0
    for line in text.splitlines():
        if ADDRESS_HEADINGS.search(line):
            heading = re.split(r":", line, maxsplit=1)[0]
            out.append(f"{heading.strip()}: [ADDRESS REMOVED]")
            skipping = MAX_ADDRESS_LINES
            continue
        if skipping:
            if not line.strip():  # a blank line ends the address block
                skipping = 0
                out.append(line)
            else:
                skipping -= 1
            continue
        out.append(line)
    return "\n".join(out)


def redact(text: str) -> str:
    text = _drop_address_blocks(text)
    text = EMAIL_RE.sub("[EMAIL]", text)
    text = CARD_HINT_RE.sub("[CARD]", text)
    text = CARD_NUMBER_RE.sub(_card, text)
    text = PHONE_RE.sub(_phone, text)
    text = EIRCODE_RE.sub("[EIRCODE]", text)
    text = UK_POSTCODE_RE.sub("[POSTCODE]", text)
    text = GREETING_RE.sub(lambda m: f"{m.group(1)}[NAME]", text)
    return text

import re
import logging
import unicodedata
import httpx

logger = logging.getLogger(__name__)

# Input size limits to prevent ReDoS (Regular Expression Denial of Service) attacks
MAX_INPUT_LENGTH = 10_000       # Maximum character length
MAX_INPUT_BYTES = 50_000        # Maximum byte size (~50KB)


def sanitize_input(text: str) -> str:
    """Sanitize user input before PII scanning to prevent ReDoS and obfuscation.

    Performs:
    1. Unicode normalization (NFKC) to decompose homoglyphs
    2. Control character removal (except newlines and tabs)
    3. Length truncation to MAX_INPUT_LENGTH

    Args:
        text: Raw input text

    Returns:
        Sanitized text safe for regex scanning
    """
    if not text:
        return ""

    # Unicode normalization — decomposes homoglyphs that could bypass regex
    text = unicodedata.normalize("NFKC", text)

    # Remove control characters except common whitespace
    # Keep: \t (tab), \n (newline), \r (carriage return)
    # Remove: all other C0 and C1 control characters
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]", "", text)

    # Remove zero-width characters (used for invisible text injection)
    text = re.sub(r"[\u200b\u200c\u200d\u2060\u2061\u2062\u2063\u2064\ufeff]", "", text)

    # Truncate to max length to prevent ReDoS
    if len(text) > MAX_INPUT_LENGTH:
        logger.warning(
            "PII input truncated from %d to %d characters to prevent ReDoS",
            len(text), MAX_INPUT_LENGTH,
        )
        text = text[:MAX_INPUT_LENGTH]

    return text


def validate_input_size(text: str):
    """Validate input size constraints before PII scanning.

    Returns:
        (is_valid, error_message) — if invalid, error_message describes the issue
    """
    if not text:
        return True, None

    if len(text) > MAX_INPUT_LENGTH:
        return False, f"Input exceeds maximum length of {MAX_INPUT_LENGTH} characters"

    if len(text.encode("utf-8")) > MAX_INPUT_BYTES:
        return False, f"Input exceeds maximum size of {MAX_INPUT_BYTES // 1024}KB"

    return True, None


class PIIDetector:
    def __init__(self):
        self.sin_formatted = re.compile(r'\b\d{3}-\d{3}-\d{3}\b')
        self.sin_unformatted = re.compile(r'\b\d{9}\b')
        self.health_card = re.compile(r'\b\d{4}-\d{3}-\d{3}-[A-Z]{2}\b')
        self.phone = re.compile(
            r'(?:\+?[1-9]\d{0,2}[-.\s]?)?\(?[2-9]\d{2}\)?[-.\s]?\d{3}[-.\s]?\d{4}(?:\s*(?:ext|x)\s*\d+)?|\b\d{10,15}\b'
        )
        self.credit_card = re.compile(r'\b(?:\d[ -]*?){13,16}\b')
        self.driver_license = re.compile(r'\b[A-Z]\d{4}-\d{5}-\d{5}\b')
        self.passport = re.compile(r'\b[A-Z]{2}\d{6}\b')
        # Email regex – placed correctly inside __init__
        self.email = re.compile(r'\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b')

    def _luhn_check(self, number: str) -> bool:
        try:
            digits = [int(d) for d in number.replace('-', '').replace(' ', '')]
            checksum = sum(digits[-1::-2]) + sum(sum(divmod(d*2, 10)) for d in digits[-2::-2])
            return checksum % 10 == 0
        except Exception:
            return False

    def scan(self, text: str) -> dict:
        """Scan text for PII with input sanitization and size validation.

        Input is sanitized before regex scanning to prevent ReDoS attacks
        and obfuscation bypasses. Oversized inputs are truncated with a warning.

        Args:
            text: Raw input text to scan for PII

        Returns:
            Dict mapping PII type names to occurrence counts
        """
        # Sanitize input to prevent ReDoS and obfuscation bypasses
        text = sanitize_input(text)

        findings = {}
        if self.sin_formatted.search(text):
            findings["SIN"] = len(self.sin_formatted.findall(text))
        for match in self.sin_unformatted.findall(text):
            if self._luhn_check(match):
                findings["SIN"] = findings.get("SIN", 0) + 1
        if self.health_card.search(text):
            findings["health_card"] = len(self.health_card.findall(text))
        if self.phone.search(text):
            findings["phone"] = len(self.phone.findall(text))
        # Credit card detection with Luhn validation to reduce false positives
        cc_matches = self.credit_card.findall(text)
        valid_cc_count = 0
        for match in cc_matches:
            cleaned = match.replace('-', '').replace(' ', '')
            if len(cleaned) >= 13 and len(cleaned) <= 19 and self._luhn_check(cleaned):
                valid_cc_count += 1
        if valid_cc_count > 0:
            findings["credit_card"] = valid_cc_count
        if self.driver_license.search(text):
            findings["driver_license"] = len(self.driver_license.findall(text))
        if self.passport.search(text):
            findings["passport"] = len(self.passport.findall(text))
        if self.email.search(text):
            findings["email"] = len(self.email.findall(text))
        return findings


    async def verify_with_llm(self, text: str, pii_types: list[str], ollama_url: str, timeout: int = 30) -> list[str]:
        """Batch-verify PII types in a single LLM call.
        
        Sends all PII types in one prompt to reduce latency and cost.
        Uses injection defense delimiters to prevent prompt injection.
        """
        if not pii_types:
            return []
        pii_list = ", ".join(pii_types)
        prompt = (
            "You are a PII verification assistant. "
            "Return ONLY a valid JSON array of confirmed PII types, no markdown, no extra text. "
            "Format: [\"type1\", \"type2\"] or [] if none found.\n\n"
            f"PII types to check: {pii_list}\n\n"
            "---BEGIN INPUT---\n"
            f"{text}\n"
            "---END INPUT---\n\n"
            "Output:"
        )
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(
                    f"{ollama_url}/api/generate",
                    json={
                        "model": "llama3.2:1b",
                        "prompt": prompt,
                        "stream": False,
                        "options": {"temperature": 0.0, "num_predict": 64}
                    }
                )
                if resp.status_code == 200:
                    raw = resp.json().get("response", "").strip()
                    # Try to parse JSON array from response
                    import json
                    try:
                        if raw.startswith("```"):
                            raw = raw.split("```")[1]
                            if raw.startswith("json"):
                                raw = raw[4:]
                        confirmed = json.loads(raw)
                        if isinstance(confirmed, list):
                            return [t for t in confirmed if t in pii_types]
                    except (json.JSONDecodeError, TypeError):
                        # Fallback: check for YES/NO per type
                        logger.warning(f"LLM batch response unparseable: {raw[:100]}")
                        confirmed = []
                        for pii_type in pii_types:
                            if pii_type.lower() in raw.lower():
                                confirmed.append(pii_type)
                        return confirmed
        except Exception as e:
            logger.warning(f"LLM batch verification failed: {e}")
        return []

"""Unicode normalization — NFKC + homoglyph mapping for injection detection."""
from __future__ import annotations
import unicodedata
import re
import logging

logger = logging.getLogger(__name__)

# Common homoglyphs used to bypass keyword filters
HOMOGLYPH_MAP = {
    "а": "a", "е": "e", "і": "i", "о": "o", "р": "p", "с": "c", "у": "y",
    "х": "x", "А": "A", "Е": "E", "І": "I", "О": "O", "Р": "P", "С": "C",
    "ꓐ": "B", "Ⅽ": "C", "ꓱ": "E", "Ꭼ": "E", "Ꮋ": "H", "Н": "H",
    "Ⅰ": "I", "K": "K", "Ꮮ": "L", "ᗰ": "M", "Ⅿ": "M", "Ν": "N", "Ꮑ": "N",
    "０": "0", "Ｏ": "O", "Ѕ": "S", "꒚": "S", "Т": "T", "Ս": "U",
    "Ⅴ": "V", "Ⅹ": "X", "Ү": "Y", "Ζ": "Z",
}

_HOMOGLYPH_RE = re.compile("|".join(re.escape(k) for k in HOMOGLYPH_MAP))


class TextNormalizer:
    def __init__(self, normalize: bool = True):
        self._enabled = normalize

    def normalize(self, text: str) -> str:
        if not self._enabled or not text:
            return text
        try:
            normalized = unicodedata.normalize("NFKC", text)
            normalized = _HOMOGLYPH_RE.sub(
                lambda m: HOMOGLYPH_MAP.get(m.group(0), m.group(0)),
                normalized,
            )
            return normalized
        except Exception:
            return text

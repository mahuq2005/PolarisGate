"""Encoding decoder — detects and decodes obfuscated payloads (base64, hex, ROT13, URL)."""
from __future__ import annotations
import base64
import binascii
import codecs
import logging
import re
import html

logger = logging.getLogger(__name__)

_BASE64_RE = re.compile(r'(?:[A-Za-z0-9+/]{4}){4,}(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?')
_HEX_RE = re.compile(r'\b(?:[0-9a-fA-F]{2}){8,}\b')
_URL_ENCODED_RE = re.compile(r'%[0-9a-fA-F]{2}')


class EncodingDecoder:
    """Chain of responsibility: tries each decoder, stops on first success."""

    def __init__(self, decode_base64: bool = True, decode_hex: bool = True,
                 decode_rot13: bool = True, decode_url: bool = True):
        self._base64 = decode_base64
        self._hex = decode_hex
        self._rot13 = decode_rot13
        self._url = decode_url

    def decode(self, text: str) -> str:
        """Attempt to decode obfuscated text. Returns decoded text or original."""
        if not text or len(text) < 10:
            return text

        try:
            # Try base64
            if self._base64 and _BASE64_RE.fullmatch(text.strip()):
                decoded = base64.b64decode(text.encode()).decode("utf-8", errors="replace")
                if self._is_meaningful(decoded, text):
                    logger.debug("Base64 decoded payload detected")
                    return decoded

            # Try hex
            if self._hex and _HEX_RE.fullmatch(text.strip().replace(" ", "")):
                try:
                    decoded = bytes.fromhex(text.strip().replace(" ", "")).decode("utf-8", errors="replace")
                    if self._is_meaningful(decoded, text):
                        logger.debug("Hex decoded payload detected")
                        return decoded
                except ValueError:
                    pass

            # Try ROT13 (same as ROT13 twice to reverse)
            if self._rot13:
                rot13 = codecs.encode(text, "rot_13")
                injection_keywords = ["ignore", "instruction", "prompt", "system", "bypass",
                                       "jailbreak", "pretend", "override", "rule", "filter"]
                if any(kw in rot13.lower() for kw in injection_keywords):
                    logger.debug("ROT13 decoded payload detected")
                    return rot13

            # Try URL decode
            if self._url and _URL_ENCODED_RE.search(text):
                decoded = html.unescape(text)
                decoded = __import__("urllib.parse").unquote(decoded)
                if decoded != text:
                    logger.debug("URL decoded payload detected")
                    return decoded
        except Exception:
            pass

        return text

    @staticmethod
    def _is_meaningful(decoded: str, original: str) -> bool:
        """Check if decoded text looks meaningful (not garbage)."""
        if not decoded or len(decoded) < 3:
            return False
        # Must contain mostly printable characters
        printable = sum(1 for c in decoded if c.isprintable() or c in "\n\r\t")
        return printable / max(len(decoded), 1) > 0.7 and decoded != original

import re
import logging
import httpx

logger = logging.getLogger(__name__)

class Rewriter:
    def __init__(self, patterns: dict = None, ollama_url: str = "http://ollama:11434"):
        self.patterns = patterns or {}
        self.ollama_url = ollama_url

    def mask_pii(self, text: str) -> str:
        result = text
        for category, regex_list in self.patterns.items():
            for regex in regex_list:
                result = re.sub(regex, f"[{category.upper()}]", result)
        return result

    async def rewrite_toxic(self, text: str, timeout: int = 30) -> str:
        prompt = (
            "You are a professional content rewriter. "
            "Rewrite the following text to be respectful and professional "
            "without changing the factual content or meaning. "
            "Return ONLY the rewritten text, no explanations, no markdown.\n\n"
            "---BEGIN INPUT---\n"
            f"{text}\n"
            "---END INPUT---\n\n"
            "Rewritten text:"
        )
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(
                    f"{self.ollama_url}/api/generate",
                    json={"model": "llama3.2:1b", "prompt": prompt, "stream": False,
                          "options": {"temperature": 0.1, "num_predict": 200}}
                )
                if resp.status_code == 200:
                    rewritten = resp.json().get("response", text).strip()
                    # Ensure we got meaningful output
                    if len(rewritten) > 0 and rewritten != text:
                        return rewritten
        except Exception as e:
            logger.warning(f"Rewrite failed: {e}")
        return text

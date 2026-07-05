import json, httpx, logging, re
from shared.toxic_keywords import check_toxic_keywords
from shared.circuit_breaker import service_circuit

logger = logging.getLogger(__name__)

# Few-shot examples for improved classification accuracy
FEW_SHOT_EXAMPLES = [
    {
        "text": "You are an idiot and completely useless!",
        "label": {"toxic": True, "toxic_score": 0.95, "reason": "Insult and personal attack"}
    },
    {
        "text": "I disagree with your opinion on the policy.",
        "label": {"toxic": False, "toxic_score": 0.02, "reason": "Respectful disagreement"}
    },
    {
        "text": "I hope someone hurts you badly.",
        "label": {"toxic": True, "toxic_score": 0.98, "reason": "Threat of violence"}
    },
    {
        "text": "Thank you for your help with this project.",
        "label": {"toxic": False, "toxic_score": 0.01, "reason": "Polite and appreciative"}
    },
    {
        "text": "All [group] people are terrible and should be removed.",
        "label": {"toxic": True, "toxic_score": 0.97, "reason": "Hate speech targeting group"}
    },
]

FEW_SHOT_PROMPT = "\n".join(
    f"Text: {ex['text']}\nOutput: {json.dumps(ex['label'])}"
    for ex in FEW_SHOT_EXAMPLES
)


class OllamaToxicityClassifier:
    def __init__(self, model_name="llama3.2:1b", ollama_url="http://ollama:11434"):
        self.model = model_name
        self.base_url = ollama_url

    @service_circuit(service_name="ollama-toxic", failure_threshold=5, recovery_timeout=30)
    async def predict(self, text: str, language: str = "en", model: str = None) -> dict:
        system_prompt = (
            "You are a content safety classifier. "
            "Return ONLY a valid JSON object with no markdown, no code fences, no extra text. "
            "Format: {\"toxic\": bool, \"toxic_score\": 0.0-1.0, \"reason\": string}. "
            "Consider hate speech, harassment, threats, insults, and personal attacks. "
            "Be conservative: only flag as toxic if clearly violating content policies.\n\n"
            "Examples:\n"
            f"{FEW_SHOT_PROMPT}\n\n"
            "Now classify the following text. Return ONLY the JSON object."
        )
        # Injection defense: delimit user input clearly
        prompt = f"---BEGIN INPUT---\nLanguage: {language}\nText: {text}\n---END INPUT---\n\nOutput:"
        use_model = model if model else self.model
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                resp = await client.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": use_model,
                        "prompt": f"{system_prompt}\n\n{prompt}",
                        "stream": False,
                        "options": {"temperature": 0.1, "num_predict": 128}
                    }
                )
                resp.raise_for_status()
                result = resp.json()
                raw = result.get("response", "").strip()
                logger.info(f"LLM response: {raw[:200]}")
                try:
                    # Strip any markdown code fences
                    if raw.startswith("```"):
                        raw = raw.split("```")[1]
                        if raw.startswith("json"):
                            raw = raw[4:]
                    parsed = json.loads(raw)
                    # Validate and clamp values
                    toxic_score = max(0.0, min(1.0, float(parsed.get("toxic_score", 0.5))))
                    flagged = bool(parsed.get("toxic", False))
                    # If score is very low but flagged, override
                    if flagged and toxic_score < 0.3:
                        toxic_score = 0.3
                    return {
                        "toxic_score": toxic_score,
                        "flagged": flagged,
                        "reason": parsed.get("reason", "")
                    }
                except (json.JSONDecodeError, KeyError, ValueError):
                    logger.warning(f"Failed to parse LLM response: {raw[:100]}")
                    return self._keyword_fallback(text)
            except Exception as e:
                logger.error(f"LLM error: {e}")
                return self._keyword_fallback(text)

    def _keyword_fallback(self, text: str) -> dict:
        """Fallback keyword detection using shared keyword definitions.
        
        Uses word-boundary matching to avoid false positives from substring matches.
        """
        toxic, toxic_score, reason = check_toxic_keywords(text)
        return {
            "toxic_score": toxic_score,
            "flagged": toxic,
            "reason": reason
        }

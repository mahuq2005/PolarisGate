"""PolarisGate Metacognitive Self-Correction (CLEAR)
Instead of simple retries, the model identifies its own errors and corrects them.
This is the CLEAR methodology: Contextualized LLM Error Analysis & Revision.
"""
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


class MetacognitiveCorrection:
    """Metacognitive self-correction that identifies and fixes its own errors.
    
    The model diagnoses what went wrong, then generates a corrected response
    with awareness of the error. This is more effective than simple retries.
    """

    def __init__(
        self,
        llm_url: str = "http://ollama:11434/api/generate",
        model: str = "llama3.2:3b",
    ):
        self.llm_url = llm_url
        self.model = model

    async def correct(
        self,
        original_prompt: str,
        hallucinated_response: str,
        error_type: str = "factual_contradiction",
    ) -> dict:
        """Correct a hallucinated response using metacognitive analysis.
        
        Args:
            original_prompt: The original prompt that was given
            hallucinated_response: The response that was flagged as hallucinated
            error_type: Type of error (factual_contradiction, unsupported_claim, etc.)
            
        Returns:
            Dict with corrected_response, diagnosis, and confidence
        """
        # Step 1: Self-diagnose what went wrong
        diagnosis_prompt = (
            f"Original prompt: {original_prompt}\n\n"
            f"My response: {hallucinated_response}\n\n"
            f"The error type was: {error_type}\n"
            f"(e.g., factual contradiction, unsupported claim, fabricated information)\n\n"
            f"Explain why this response is incorrect. Be specific about what facts "
            f"were wrong or what claims were unsupported."
        )
        diagnosis = await self._call_llm(diagnosis_prompt)

        if not diagnosis:
            return {
                "corrected_response": None,
                "diagnosis": "Failed to generate diagnosis",
                "confidence": 0.0,
                "error": "LLM call failed during diagnosis",
            }

        # Step 2: Generate corrected response with awareness of the error
        correction_prompt = (
            f"Original prompt: {original_prompt}\n\n"
            f"My previous incorrect response: {hallucinated_response}\n\n"
            f"Why it was wrong: {diagnosis}\n\n"
            f"Now provide a corrected response that is fully grounded in facts. "
            f"Be careful to only include information that is directly supported "
            f"by the original prompt context. If you are unsure about something, "
            f"say so explicitly."
        )
        corrected = await self._call_llm(correction_prompt)

        if not corrected:
            return {
                "corrected_response": None,
                "diagnosis": diagnosis,
                "confidence": 0.0,
                "error": "LLM call failed during correction",
            }

        return {
            "corrected_response": corrected,
            "diagnosis": diagnosis,
            "confidence": 0.7,  # Moderate confidence — human review still recommended
            "error": None,
        }

    async def _call_llm(self, prompt: str) -> str:
        """Call an LLM via Ollama API."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.llm_url,
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "temperature": 0.3,  # Slightly higher for creative correction
                            "num_predict": 1024,
                        },
                    },
                )
                if response.status_code == 200:
                    data = response.json()
                    return data.get("response", "")
                else:
                    logger.error(f"LLM call failed: {response.status_code}")
                    return ""
        except Exception as e:
            logger.error(f"LLM call error: {e}")
            return ""

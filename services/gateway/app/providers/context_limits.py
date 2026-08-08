"""Context window limits for all supported LLM providers and models.

Each provider/model has a known context window (in tokens).
The gateway uses these limits to trim conversation history
before forwarding to the LLM, preventing token overflow.
"""

# ── Per-model context windows (tokens) ────────────────────────────────────
# Matched by prefix — e.g. "gpt-4o" matches "gpt-4o", "gpt-4o-mini", etc.
# If a model isn't listed, falls back to the provider-level default.
MODEL_CONTEXT_LIMITS: dict[str, int] = {
    # ── Ollama models ─────────────────────────────────────────────────
    "llama3.2:1b": 131072,         # 128K
    "llama3.2:3b": 131072,         # 128K
    "llama3.1:8b": 131072,         # 128K
    "llama3:70b": 32768,           # 32K
    "tinyllama": 2048,             # 2K
    "mistral": 32768,              # 32K
    "mixtral": 32768,              # 32K
    "phi3": 4096,                  # 4K
    "phi3:mini": 4096,             # 4K
    "qwen2.5": 32768,              # 32K
    "qwen2": 32768,                # 32K
    "gemma2": 8192,                # 8K
    "deepseek-r1": 131072,         # 128K
    "deepseek-coder": 16384,       # 16K
    "nomic": 8192,                 # 8K
    "llama-guard": 4096,           # 4K

    # ── OpenAI models ─────────────────────────────────────────────────
    "gpt-4o": 128000,              # 128K
    "gpt-4o-mini": 128000,         # 128K
    "gpt-4-turbo": 128000,         # 128K
    "gpt-4": 8192,                 # 8K
    "gpt-3.5-turbo": 16385,        # 16K
    "o1-": 200000,                 # 200K
    "o1-mini": 128000,             # 128K
    "o3-": 200000,                 # 200K
    "o3-mini": 200000,             # 200K
    "o4-mini": 200000,             # 200K

    # ── Anthropic models ──────────────────────────────────────────────
    "claude-sonnet-4": 200000,     # 200K
    "claude-sonnet-3.5": 200000,   # 200K
    "claude-opus-4": 200000,       # 200K
    "claude-opus-3": 200000,       # 200K
    "claude-haiku": 200000,        # 200K
    "claude-3.5-sonnet": 200000,   # 200K

    # ── Google Gemini models ──────────────────────────────────────────
    "gemini-2.5-pro": 2097152,     # 2M
    "gemini-2.5-flash": 1048576,   # 1M
    "gemini-2.0-flash": 1048576,   # 1M
    "gemini-1.5-pro": 2097152,     # 2M
    "gemini-1.5-flash": 1048576,   # 1M

    # ── Cohere models ─────────────────────────────────────────────────
    "command-r-plus": 128000,      # 128K
    "command-r": 128000,           # 128K
    "command": 4096,               # 4K

    # ── Mistral models ────────────────────────────────────────────────
    "mistral-large": 131072,       # 128K
    "mistral-small": 32768,        # 32K
    "codestral": 32768,            # 32K
    "ministral": 32768,            # 32K

    # ── xAI / Grok models ─────────────────────────────────────────────
    "grok-3": 1000000,             # 1M
    "grok-2": 131072,              # 128K

    # ── DeepSeek models ───────────────────────────────────────────────
    "deepseek-chat": 65536,        # 64K
    "deepseek-reasoner": 65536,    # 64K

    # ── Groq models ───────────────────────────────────────────────────
    "llama-3.3-70b": 8192,         # 8K
    "mixtral-8x7b": 32768,         # 32K
    "gemma2-9b": 8192,             # 8K
}

# ── Provider-level fallbacks (when model doesn't match any pattern) ──────
PROVIDER_CONTEXT_LIMITS: dict[str, int] = {
    "mock":    999999,   # Unlimited
    "ollama":  8192,     # Conservative default for unknown Ollama models
    "openai":  128000,   # Most OpenAI models are 128K
    "anthropic": 200000, # Claude models are 200K
    "google":  1048576,  # Gemini models are 1M+
    "cohere":  4096,     # Command is 4K (older models)
    "mistral": 32768,    # Default 32K
    "groq":    8192,     # Most Groq models are 8K
    "deepseek": 65536,   # DeepSeek V3 is 64K
    "xai":     131072,   # Grok is 128K+
    "together": 32768,   # Default for Together AI
}

# Where no provider known at all
DEFAULT_CONTEXT_LIMIT = 8192


def get_context_limit(provider: str, model: str = "") -> int:
    """Get the context window size (in tokens) for a provider/model.

    Resolution order:
        1. Exact model name match in MODEL_CONTEXT_LIMITS
        2. Model prefix match (e.g. "gpt-4o" matches "gpt-4o-mini")
        3. Provider-level fallback in PROVIDER_CONTEXT_LIMITS
        4. Global DEFAULT_CONTEXT_LIMIT
    """
    provider = provider.lower().strip()

    # 1. Exact model match
    if model and model.lower() in MODEL_CONTEXT_LIMITS:
        return MODEL_CONTEXT_LIMITS[model.lower()]

    # 2. Model prefix match
    if model:
        model_lower = model.lower()
        for prefix, limit in MODEL_CONTEXT_LIMITS.items():
            if model_lower.startswith(prefix):
                return limit

    # 3. Provider fallback
    if provider in PROVIDER_CONTEXT_LIMITS:
        return PROVIDER_CONTEXT_LIMITS[provider]

    # 4. Default
    return DEFAULT_CONTEXT_LIMIT


def sanitize_surrogates(text: str) -> str:
    """Strip lone surrogates (U+D800–U+DFFF) from a string.

    These arise when Unicode text containing emoji or supplementary-plane
    characters is truncated or corrupted.  Lone surrogates produce invalid
    JSON when serialised (``\\uD83D`` without its pair ``\\uDE00``),
    causing providers like DeepSeek to return a 400 error.
    """
    if not text:
        return text
    try:
        # The surrogateescape error handler in Python marks lone surrogates
        # — re-encoding with 'surrogatepass' and ignoring lets us strip them.
        return text.encode("utf-8", errors="surrogatepass").decode("utf-8", errors="ignore")
    except (UnicodeEncodeError, UnicodeDecodeError):
        # Fallback: strip individual surrogate codepoints
        return "".join(ch for ch in text if not (0xD800 <= ord(ch) <= 0xDFFF))


def estimate_tokens(text: str) -> int:
    """Crude token estimation: ~4 characters per token for English text.

    This is intentionally simple — the goal is to prevent overflow,
    not to precisely count tokens. Being conservative (under-estimating
    available space) is safer than overflowing.
    """
    text = sanitize_surrogates(text)
    return max(1, len(text.encode("utf-8")) // 4)


def trim_history(
    messages: list[dict],
    provider: str,
    model: str = "",
    response_reserve_ratio: float = 0.30,
) -> list[dict]:
    """Trim conversation history to fit within the provider's context window.

    Args:
        messages: List of {role, content} dicts ordered oldest→newest
        provider: Provider name for context lookup
        model: Model name for context lookup
        response_reserve_ratio: Fraction of context window to reserve
            for the LLM's response (default: 0.30 = 30%)

    Returns:
        Trimmed list of messages, with oldest messages removed first.
        Always includes at least the last message (latest user input).
    """
    if not messages:
        return messages

    context_limit = get_context_limit(provider, model)
    max_history_tokens = int(context_limit * (1.0 - response_reserve_ratio))

    # Walk backwards from newest to oldest, accumulating until we hit the limit
    total_tokens = 0
    trimmed = []
    for msg in reversed(messages):
        msg_tokens = estimate_tokens(str(msg.get("content", "")))
        if total_tokens + msg_tokens > max_history_tokens and trimmed:
            # Stop — can't fit more (but always include at least one message)
            break
        trimmed.insert(0, msg)
        total_tokens += msg_tokens

    return trimmed
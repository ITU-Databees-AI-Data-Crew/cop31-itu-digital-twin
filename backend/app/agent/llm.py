import os

from langchain_openai import ChatOpenAI

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "xiaomi/mimo-v2.6-pro"  # cheap, supports tool calling


def make_llm(temperature: float = 0.3) -> ChatOpenAI:
    """Chat model on OpenRouter, streaming.

    Needs OPENROUTER_API_KEY (environment or backend/.env). Set COP31_MODEL to use another model;
    it must support tool calling (check "tools" on its OpenRouter page).

    Reasoning is OFF by default. Measured 2026-11-03 on mimo-v2.6-pro: hidden reasoning made one
    model call take 23-40 s (700-1,500 thinking tokens) instead of 3-4 s, with the same tool choice.
    Set COP31_REASONING=on to turn it back on.
    """
    reasoning_on = os.environ.get("COP31_REASONING", "off").lower() in ("on", "1", "true", "yes")
    return ChatOpenAI(
        base_url=OPENROUTER_BASE_URL,
        api_key=os.environ["OPENROUTER_API_KEY"],
        model=os.environ.get("COP31_MODEL", DEFAULT_MODEL),
        temperature=temperature,
        streaming=True,
        extra_body={"reasoning": {"enabled": reasoning_on}},
    )

import os

from langchain_openai import ChatOpenAI

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "xiaomi/mimo-v2.6-pro"  # cheap, supports tool calling


def make_llm(temperature: float = 0.3) -> ChatOpenAI:
    """Chat model on OpenRouter.

    Needs OPENROUTER_API_KEY (environment or backend/.env). Set COP31_MODEL to use another model;
    it must support tool calling (check "tools" on its OpenRouter page).
    """
    return ChatOpenAI(
        base_url=OPENROUTER_BASE_URL,
        api_key=os.environ["OPENROUTER_API_KEY"],
        model=os.environ.get("COP31_MODEL", DEFAULT_MODEL),
        temperature=temperature,
    )

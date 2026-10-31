"""LangChain tabanli sohbet asistani + web search tool'u.

Bina bilgisi (building_info) baglamini system prompt'a gomerek
kullaniciyla cok turlu (multi-turn) bir sohbet dongusu yurutur.
Gecmis mesajlari LangChain chat history ile tutar.

Web search backend secimi (otomatik):
1. TAVILY_API_KEY tanimliysa  -> Tavily (AI search, free tier: 1000 istek/ay)
2. Degilse                    -> DuckDuckGo (ddgs paketi, tamamen ucretsiz, key yok)

Alternatif ucretli/ucretsiz API'ler: Brave Search (2000 sorgu/ay free),
SerpAPI (100 sorgu/ay free). Gerekirse web_search icine eklenebilir.
"""

import os

from langchain_openai import ChatOpenAI
from langchain_core.messages import (
    SystemMessage,
    HumanMessage,
    AIMessage,
    ToolMessage,
)
from langchain_core.tools import tool

MAX_TOOL_ITERATIONS = 5

DEFAULT_SYSTEM_PROMPT = """Sen bir bina enerji yonetimi asistanisin.
Gorevin, sana verilen bina bilgilerini kullanarak kullanicinin
sorularini net, dogru ve anlasilir sekilde yanitlamaktir.

Kurallar:
- Sadece sana verilen bina bilgilerine ve genel teknik bilgine dayan.
- Guncel bilgi gerektiren sorularda (fiyatlar, mevzuat, hava durumu,
  teknoloji haberleri vb.) web_search aracini kullan.
- web_search sonuclarini kullandiginda bilginin kaynagini belirt.
- Emin olmadigin konularda tahmin yurutme, belirsizligi belirt.
- Yanitlarini Turkce ver, kisa ve oz ol.
- Sayisal degerlerden bahsederken birimlerini mutlaka yaz.

Bina bilgileri:
{building_info}
"""


def _search_with_tavily(query: str, max_results: int) -> str:
    """Tavily API ile arama (TAVILY_API_KEY gerekli)."""
    from langchain_tavily import TavilySearch

    tavily = TavilySearch(max_results=max_results)
    results = tavily.invoke({"query": query})

    # Tavily dict ya da list donebilir; iki formati da normalize et
    items = results.get("results", []) if isinstance(results, dict) else results
    lines = []
    for item in items:
        if isinstance(item, dict):
            title = item.get("title", "")
            url = item.get("url", "")
            content = item.get("content", "")
            lines.append(f"- {title}\n  {url}\n  {content}")
        else:
            lines.append(f"- {item}")
    return "\n".join(lines) if lines else "Sonuc bulunamadi."


def _search_with_duckduckgo(query: str, max_results: int) -> str:
    """DuckDuckGo ile ucretsiz arama (API key gerekmez)."""
    from ddgs import DDGS

    with DDGS() as ddgs:
        results = list(ddgs.text(query, max_results=max_results))

    if not results:
        return "Sonuc bulunamadi."
    return "\n".join(
        f"- {r.get('title', '')}\n  {r.get('href', '')}\n  {r.get('body', '')}"
        for r in results
    )


@tool
def web_search(query: str) -> str:
    """Internet'te guncel bilgi arar. Guncel fiyat, mevzuat, haber veya
    bilmedigin guncel bir konu soruldugunda bu araci kullan.

    Args:
        query: Aranacak sorgu metni.
    """
    max_results = 5
    if os.environ.get("TAVILY_API_KEY"):
        try:
            return _search_with_tavily(query, max_results)
        except Exception as e:
            return f"Tavily aramasi basarisiz: {e}"
    try:
        return _search_with_duckduckgo(query, max_results)
    except Exception as e:
        return f"DuckDuckGo aramasi basarisiz: {e}"


TOOLS = [web_search]
TOOLS_BY_NAME = {t.name: t for t in TOOLS}


class Assistant:
    def __init__(self, api_key, model, temperature=0.3):
        self.api_key = api_key
        self.model = model

        self.llm = ChatOpenAI(
            api_key=api_key,
            model=model,
            temperature=temperature,
        )
        self.llm_with_tools = self.llm.bind_tools(TOOLS)

        # Sohbet gecmisi (HumanMessage / AIMessage / ToolMessage listesi)
        self.history = []

    def _run_agent_loop(self, system_text, message):
        """Tool cagrisi gerekiyorsa calistirip modele geri besler.

        Mesaj listesi tek yerde yonetilir: her tool_call'in ardindan mutlaka
        eslesen ToolMessage eklenir. Yeni mesajlar dondurulur; bunlar gecmise
        eklenir ki tool_calls/ToolMessage eslesmesi bozulmasin.
        """
        messages = [
            SystemMessage(content=system_text),
            *self.history,
            HumanMessage(content=message),
        ]
        new_messages = [messages[-1]]

        for _ in range(MAX_TOOL_ITERATIONS):
            response = self.llm_with_tools.invoke(messages)
            messages.append(response)
            new_messages.append(response)

            if not response.tool_calls:
                break

            for call in response.tool_calls:
                selected = TOOLS_BY_NAME[call["name"]]
                try:
                    tool_output = selected.invoke(call["args"])
                except Exception as e:
                    tool_output = f"Tool hatasi: {e}"
                tool_msg = ToolMessage(
                    content=str(tool_output),
                    tool_call_id=call["id"],
                )
                messages.append(tool_msg)
                new_messages.append(tool_msg)
        else:
            new_messages.append(AIMessage(
                content="Maksimum arac cagrisi sayisina ulasildi, yanit veremiyorum."
            ))

        return new_messages

    def send_top_model(self, system_prompt, message, building_info="Bilgi yok."):
        """Tek bir mesaj gonderir, gerekirse tool cagirir, yaniti dondurur.

        system_prompt: None verilirse DEFAULT_SYSTEM_PROMPT kullanilir.
        building_info: system prompt icindeki {building_info} alanina yazilir.
        """
        base_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT
        if "{building_info}" in base_prompt:
            system_text = base_prompt.replace("{building_info}", building_info)
        else:
            system_text = f"{base_prompt}\n\nBina bilgileri:\n{building_info}"

        new_messages = self._run_agent_loop(system_text, message)
        self.history.extend(new_messages)

        return new_messages[-1].content

    def reset_history(self):
        """Sohbet gecmisini temizler."""
        self.history = []

    def chat_loop(self, system_prompt=None, user_question="", building_info="Bilgi yok."):
        """Tek bir kullanici sorusunu isler ve yaniti dondurur.

        Sohbet gecmisi self.history'de tutuldugundan art arda cagrilabilir;
        her cagri onceki turlari hatirlar.
        """
        return self.send_top_model(system_prompt, user_question, building_info)


if __name__ == "__main__":
    assistant = Assistant(
        api_key=os.environ["OPENAI_API_KEY"],
        model="gpt-4o-mini",
    )

    example_building_info = (
        "Bina adi: İTÜ Bilgisayar ve Bilişim Fakültesi\n"
        "Konum: Istanbul\n"
        "Alan: 1000m^2\n"
        "Öğrenci sayısı: 700"
    )

    ans = assistant.chat_loop(
        user_question="Bu binada kac ogrenci var?",
        building_info=example_building_info,
    )
    print(ans)
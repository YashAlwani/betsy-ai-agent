import json
import os
import re

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama

load_dotenv()

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")


def get_llm(temperature: float = 0.1) -> ChatOllama:
    return ChatOllama(
        model=OLLAMA_MODEL,
        base_url=OLLAMA_BASE_URL,
        temperature=temperature,
    )


def call_json(llm: ChatOllama, system: str, user: str) -> dict:
    """Call LLM, parse JSON from response. Returns {fallback: True} on any failure."""
    try:
        response = llm.invoke([
            SystemMessage(content=system),
            HumanMessage(content=user),
        ])
        text = response.content.strip()
        # Strip markdown fences if present
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
        text = re.sub(r"\s*```$", "", text, flags=re.MULTILINE)
        return json.loads(text.strip())
    except Exception as exc:
        return {"fallback": True, "error": str(exc)}


def call_text(llm: ChatOllama, system: str, user: str) -> str:
    """Call LLM, return plain text. Returns error string on failure."""
    try:
        response = llm.invoke([
            SystemMessage(content=system),
            HumanMessage(content=user),
        ])
        return response.content.strip()
    except Exception as exc:
        return f"[LLM unavailable: {exc}]"

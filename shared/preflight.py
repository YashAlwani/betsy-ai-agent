"""Startup checks shared by the run scripts.

Nothing here is fatal — Betsy degrades gracefully (rule-based fallbacks cover
the LLM, proxies 503 while the world is down) — but the checks surface exactly
what will and won't work before you wonder why the reasoning looks canned.
"""
import httpx

from shared.llm import OLLAMA_BASE_URL, OLLAMA_MODEL

OK   = "[ ok ]"
WARN = "[warn]"
FAIL = "[FAIL]"


def check_world(base_url: str = "http://localhost:8001") -> bool:
    try:
        r = httpx.get(f"{base_url}/health", timeout=2.0).json()
        print(f"  {OK}   World service reachable at {base_url} (sim day {r.get('day', '?')})")
        return True
    except Exception:
        print(f"  {WARN} World service NOT reachable at {base_url}")
        print(f"         -> start it with: python run_world.py")
        return False


def check_ollama() -> bool:
    """Verify the Ollama server is up AND the configured model is pulled."""
    try:
        r = httpx.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=2.0)
        r.raise_for_status()
        models = [m.get("name", "") for m in r.json().get("models", [])]
    except Exception:
        print(f"  {WARN} Ollama NOT reachable at {OLLAMA_BASE_URL}")
        print(f"         -> start it with: ollama serve")
        print(f"         Betsy still runs — agents use rule-based fallbacks instead of the LLM.")
        return False

    # "llama3.1:8b" should match "llama3.1:8b" and bare "llama3.1" should match any tag
    def matches(installed: str) -> bool:
        return installed == OLLAMA_MODEL or installed.split(":")[0] == OLLAMA_MODEL

    if any(matches(m) for m in models):
        print(f"  {OK}   Ollama up, model '{OLLAMA_MODEL}' available")
        return True

    print(f"  {WARN} Ollama is up but model '{OLLAMA_MODEL}' is NOT pulled")
    if models:
        print(f"         installed models: {', '.join(models)}")
        print(f"         -> either: ollama pull {OLLAMA_MODEL}")
        print(f"         -> or set  OLLAMA_MODEL={models[0]}  to use one you already have")
    else:
        print(f"         no models installed -> ollama pull {OLLAMA_MODEL}")
    print(f"         Betsy still runs — agents use rule-based fallbacks instead of the LLM.")
    return False


def run_betsy_checks() -> None:
    print("\nPreflight checks:")
    check_world()
    check_ollama()
    print()


def run_world_checks() -> None:
    print("\nPreflight checks:")
    from world.config import WORLD_DB_PATH, WORLD_SEED
    if WORLD_DB_PATH.exists():
        print(f"  {OK}   Existing world found at {WORLD_DB_PATH.name} — simulation will resume")
    else:
        print(f"  {OK}   No {WORLD_DB_PATH.name} yet — a fresh world will be seeded (seed {WORLD_SEED})")
    print()

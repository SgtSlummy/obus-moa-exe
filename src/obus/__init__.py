"""OccultBus MOA Runtime - Dynamic Tarot Card/Key Matching Engine."""
__version__ = "1.0.0"
__author__ = "OBus Team"

import os
from pathlib import Path

# Default paths
DEFAULT_HOME = Path(os.environ.get("OCCULTBUS_HOME", Path.home() / ".occultbus"))
DEFAULT_DECK = DEFAULT_HOME / "deck.json"
DEFAULT_RAG_DB = DEFAULT_HOME / "rag.sqlite3"
DEFAULT_KEYS = DEFAULT_HOME / "solomons_keys.json"
DEFAULT_AGENT_CARDS = DEFAULT_HOME / "tarot_agent_cards.json"
DEFAULT_VERIFICATION = DEFAULT_HOME / "provider_verification.json"

# Verified keys (confirmed working for MOA routing)
VERIFIED_KEYS = [
    "key-codex-oauth",    # OpenAI Codex - Final aggregator
    "key-local-ollama",   # Local Ollama - Routing/scouting specialist
    "key-nous-oauth",     # Nous - Generalist specialist
    "key-nvidia-nim",     # NVIDIA NIM - Reasoning/research specialist
]
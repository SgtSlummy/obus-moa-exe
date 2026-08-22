"""Historical Solomon/Goetic seal mapping for built-in OBus Keys."""
from __future__ import annotations

SOLOMON_SEALS = {
    "key-local-ollama": {"name": "Buer", "number": 10, "file": "File:10-Buer seal.png", "reason": "philosophy, logic, and teaching"},
    "key-codex-oauth": {"name": "Paimon", "number": 9, "file": "File:09-Paimon seal01.png", "reason": "arts, sciences, and hidden knowledge"},
    "key-nous-oauth": {"name": "Stolas", "number": 36, "file": "File:36-Stolas seal.png", "reason": "astronomy, plants, and precious stones"},
    "key-nvidia-nim": {"name": "Vapula", "number": 60, "file": "File:60-Vapula seal.png", "reason": "mechanics, crafts, and sciences"},
    "key-anthropic": {"name": "Orobas", "number": 55, "file": "File:55-Orobas seal.png", "reason": "truthful answers and discernment"},
    "key-google-gemini": {"name": "Dantalion", "number": 71, "file": "File:71-Dantalion seal.png", "reason": "many minds, knowledge, and perspective"},
    "key-openrouter": {"name": "Seere", "number": 70, "file": "File:70-Seere seal01.png", "reason": "swift conveyance across places"},
    "key-mistral": {"name": "Amdusias", "number": 67, "file": "File:67-Amdusias seal.png", "reason": "wind, sound, and instruments"},
    "key-groq": {"name": "Agares", "number": 2, "file": "File:02-Agares seal.png", "reason": "movement, speed, and languages"},
    "key-xai": {"name": "Ose", "number": 57, "file": "File:57-Ose seal.png", "reason": "sciences and secret knowledge"},
    "key-together": {"name": "Forneus", "number": 30, "file": "File:30-Forneus seal.png", "reason": "languages, cooperation, and reputation"},
    "key-fireworks": {"name": "Haures", "number": 64, "file": "File:64-Haures seal.png", "reason": "fire and revealed truths"},
    "key-deepseek": {"name": "Vassago", "number": 3, "file": "File:03-Vassago seal.png", "reason": "discovering hidden and lost things"},
    "key-cerebras": {"name": "Foras", "number": 31, "file": "File:31-Foras seal.png", "reason": "logic, wisdom, and understanding"},
    "key-huggingface": {"name": "Bune", "number": 26, "file": "File:26-Bune seal01.png", "reason": "eloquence, wisdom, and knowledge"},
    "key-azure-openai": {"name": "Vepar", "number": 42, "file": "File:42-Vepar seal01.png", "reason": "waters, navigation, and vessels"},
}

BUILTIN_KEY_IDS = frozenset(SOLOMON_SEALS)

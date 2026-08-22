"""Canonical 78-card OBus agent-persona catalog."""
from __future__ import annotations

DECK_IDS = ["rider-waite-smith", "thoth", "marseille", "wild-unknown", "hermetic", "golden-dawn", "urban-tarot"]

MAJOR = [
    ("fool", "The Fool", "0", "Explorer / Ideator", "exploration", ["ideation", "creative", "discovery", "risk"]),
    ("magician", "The Magician", "I", "Builder / Toolsmith", "builder", ["coding", "building", "execution", "creative", "tools"]),
    ("high-priestess", "The High Priestess", "II", "Synthesis / Intuition", "synthesizer", ["analysis", "synthesis", "review", "evaluation"]),
    ("empress", "The Empress", "III", "Creator / Product Gardener", "creative", ["creative", "product", "design", "narrative"]),
    ("emperor", "The Emperor", "IV", "Planner / Architect", "architect", ["architecture", "planning", "reasoning", "system_design"]),
    ("hierophant", "The Hierophant", "V", "Governance / Knowledge Keeper", "governance", ["governance", "policy", "knowledge", "teaching"]),
    ("lovers", "The Lovers", "VI", "Collaboration / Choice", "collaboration", ["collaboration", "decision", "alignment", "communication"]),
    ("chariot", "The Chariot", "VII", "Fast Executor / Driver", "execution", ["execution", "tools", "fast", "coordination"]),
    ("strength", "Strength", "VIII", "Resilience / Safety", "resilience", ["security", "resilience", "support", "risk"]),
    ("hermit", "The Hermit", "IX", "Researcher / Debugger", "research", ["research", "analysis", "critique", "debugging"]),
    ("wheel-of-fortune", "Wheel of Fortune", "X", "Systems Dynamics / Change", "systems", ["systems", "forecasting", "change", "strategy"]),
    ("justice", "Justice", "XI", "Audit / Legal Reasoning", "audit", ["audit", "legal", "policy", "evaluation"]),
    ("hanged-man", "The Hanged Man", "XII", "Reframing / Constraint Solver", "reframing", ["reframing", "constraints", "reasoning", "critique"]),
    ("death", "Death", "XIII", "Transformation / Refactor", "transformation", ["refactor", "transformation", "migration", "cleanup"]),
    ("temperance", "Temperance", "XIV", "Integration / Balance", "integration", ["integration", "synthesis", "orchestration", "balance"]),
    ("devil", "The Devil", "XV", "Adversarial / Risk Analyst", "adversarial", ["security", "threat_modeling", "risk", "adversarial"]),
    ("tower", "The Tower", "XVI", "Incident Response / Breaker", "incident_response", ["incident", "debugging", "failure", "recovery"]),
    ("star", "The Star", "XVII", "Vision / Long-range Guide", "vision", ["vision", "strategy", "creative", "forecasting"]),
    ("moon", "The Moon", "XVIII", "Ambiguity / Multimodal Scout", "ambiguity", ["ambiguity", "multimodal", "investigation", "intuition"]),
    ("sun", "The Sun", "XIX", "Communication / Clarity", "communication", ["communication", "explanation", "education", "creative"]),
    ("judgement", "Judgement", "XX", "Evaluator / Release Gate", "evaluation", ["evaluation", "review", "testing", "quality"]),
    ("world", "The World", "XXI", "Completion / Final Integrator", "completion", ["synthesis", "delivery", "integration", "orchestration"]),
]

SUITS = {
    "wands": ("Wands", "♜", ["creative", "execution", "leadership", "product"], "flame"),
    "cups": ("Cups", "♢", ["writing", "empathy", "communication", "narrative"], "tide"),
    "swords": ("Swords", "⚔", ["analysis", "security", "reasoning", "debugging"], "storm"),
    "pentacles": ("Pentacles", "✥", ["data", "operations", "finance", "reliability"], "earth"),
}

RANKS = [
    ("ace", "Ace", "origin", ["ideation", "discovery"]),
    ("two", "Two", "choice", ["comparison", "decision"]),
    ("three", "Three", "collaboration", ["collaboration", "planning"]),
    ("four", "Four", "stability", ["structure", "reliability"]),
    ("five", "Five", "conflict", ["critique", "risk"]),
    ("six", "Six", "transition", ["migration", "support"]),
    ("seven", "Seven", "strategy", ["strategy", "evaluation"]),
    ("eight", "Eight", "momentum", ["execution", "automation"]),
    ("nine", "Nine", "mastery", ["expertise", "review"]),
    ("ten", "Ten", "completion", ["delivery", "synthesis"]),
    ("page", "Page", "scout", ["research", "learning"]),
    ("knight", "Knight", "operator", ["execution", "tools"]),
    ("queen", "Queen", "steward", ["coordination", "quality"]),
    ("king", "King", "leader", ["leadership", "architecture"]),
]


def _base_card(slug: str, name: str, symbol: str, persona: str, agent_type: str, capabilities: list[str], arcana: str, suit: str | None = None, rank: str | None = None) -> dict:
    return {
        "id": f"card-{slug}", "slug": slug, "name": name, "symbol": symbol,
        "persona": persona, "agent_type": agent_type, "arcana": arcana,
        "suit": suit, "rank": rank,
        "image": f"/static/art/cards/{slug}.webp", "art_style": "fantasy-realistic-painterly", "reversed": False,
        "active": False, "assignment_mode": "auto", "assigned_key_id": None,
        "tool_ids": [],
        "capabilities": list(dict.fromkeys(capabilities)), "can_aggregate": slug in {"high-priestess", "world", "judgement"},
        "decks": list(DECK_IDS),
    }


def build_card_catalog() -> list[dict]:
    cards = [_base_card(slug, name, numeral, persona, agent_type, caps, "major") for slug, name, numeral, persona, agent_type, caps in MAJOR]
    for suit_slug, (suit_name, symbol, suit_caps, element) in SUITS.items():
        for rank_slug, rank_name, role, rank_caps in RANKS:
            slug = f"{rank_slug}-of-{suit_slug}"
            cards.append(_base_card(
                slug, f"{rank_name} of {suit_name}", symbol,
                f"{rank_name} {suit_name} / {role.title()} {element.title()} Agent",
                f"{role}_{suit_slug}", suit_caps + rank_caps + [element], "minor", suit_slug, rank_slug,
            ))
    assert len(cards) == 78
    return cards


DEFAULT_CARDS = build_card_catalog()

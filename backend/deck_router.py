"""
OBus MOA - Deck-Based Routing System

Decks are task-domain style/ontology packs that influence which tarot cards (agent personas) 
are emphasized. This is a third editable layer:
- Cards = Agent Personas
- Keys = LLM/Provider Handles  
- Decks = Task Style/Ontology

The routing engine selects the best deck based on task classification, then dynamically 
assigns Solomon's Keys (LLM providers) to each card in the deck.
"""
from typing import List, Dict, Optional
from dataclasses import dataclass
from enum import Enum


class TaskType(Enum):
    RESEARCH = "research"
    CREATIVE = "creative"
    TECHNICAL = "technical"
    ANALYSIS = "analysis"
    AGGREGATION = "aggregation"
    GENERAL = "general"


@dataclass
class CardConfig:
    """Configuration for a single tarot card (agent persona)"""
    id: str
    name: str
    symbol: str
    persona: str
    capabilities: List[str]
    can_aggregate: bool = False
    
    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "symbol": self.symbol,
            "persona": self.persona,
            "capabilities": self.capabilities,
            "can_aggregate": self.can_aggregate
        }


@dataclass
class DeckArchetype:
    """A deck is a group of cards optimized for a specific task type"""
    id: str
    name: str
    symbol: str
    description: str
    style: str
    best_for: List[str]
    cards: List[CardConfig]
    image_pack: str
    enabled: bool = True
    priority: int = 5
    
    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "symbol": self.symbol,
            "description": self.description,
            "style": self.style,
            "best_for": self.best_for,
            "cards": [c.to_dict() for c in self.cards],
            "image_pack": self.image_pack,
            "enabled": self.enabled,
            "priority": self.priority
        }


# Pre-configured decks based on cross-examination of card capabilities
DECK_ARCHETYPES = [
    # 1. Rider-Waite-Smith: General purpose, accessible archetype-based
    DeckArchetype(
        id="rider-waite-smith",
        name="Rider–Waite–Smith",
        symbol="🃏",
        description="Classic deck with accessible archetypes. Broad coverage across all domains.",
        style="clear symbolic archetypes, accessible language, broad coverage",
        best_for=["general_routing", "creative_briefs", "copywriting", "campaigns", "user_facing_strategy"],
        image_pack="/static/tarot/rws/",
        cards=[
            CardConfig(id="card-high-priestess", name="The High Priestess", symbol="🗝️", 
                      persona="Synthesis/Aggregator", capabilities=["analysis", "synthesis", "review", "evaluation"]),
            CardConfig(id="card-magician", name="The Magician", symbol="✨",
                      persona="Builder / Executor", capabilities=["coding", "building", "execution", "creative"]),
            CardConfig(id="card-hermit", name="The Hermit", symbol="🔍",
                      persona="Researcher / Critic", capabilities=["research", "analysis", "critique", "retrieval"]),
            CardConfig(id="card-emperor", name="The Emperor", symbol="🧠",
                      persona="Planner / Architect", capabilities=["architecture", "planning", "reasoning"]),
            CardConfig(id="card-fool", name="The Fool", symbol="🌀",
                      persona="Innovation Scout", capabilities=["creative", "ideation", "experimentation"]),
        ],
        priority=5
    ),
    
    # 2. Thoth: Analytical, structural, systems thinking
    DeckArchetype(
        id="thoth",
        name="Thoth",
        symbol="📚",
        description="Dense esoteric correspondences. Analytical, abstract, structural thinking.",
        style="dense esoteric correspondences, analytical, abstract, structural",
        best_for=["systems_architecture", "deep_analysis", "research_synthesis", "technical_planning", "multi_agent_decomposition"],
        image_pack="/static/tarot/thoth/",
        cards=[
            CardConfig(id="card-hermit", name="The Hermit", symbol="🔍",
                      persona="Deep Researcher", capabilities=["research", "analysis", "critique", "retrieval"]),
            CardConfig(id="card-emperor", name="The Emperor", symbol="🧠",
                      persona="System Architect", capabilities=["architecture", "planning", "reasoning"]),
            CardConfig(id="card-pyramid", name="The Pyramid", symbol="🏛️",
                      persona="Structural Analyst", capabilities=["analysis", "systems", "classification"]),
            CardConfig(id="card-astrology", name="Astrology", symbol="✶",
                      persona="Pattern Recognition", capabilities=["pattern_matching", "prediction", "research"]),
        ],
        priority=3
    ),
    
    # 3. Marseille: Minimalist, logical, crisp
    DeckArchetype(
        id="marseille",
        name="Tarot de Marseille",
        symbol="♎",
        description="Historical minimalist design. Crisp archetypes, logical clarity.",
        style="minimalist, historical, crisp archetypes, logical",
        best_for=["logic_checks", "legal_policy_reasoning", "audit_trails", "simple_deterministic_decisions"],
        image_pack="/static/tarot/marseille/",
        cards=[
            CardConfig(id="card-emperor", name="The Emperor", symbol="🧠",
                      persona="Logic Operator", capabilities=["architecture", "planning", "logic", "deterministic"]),
            CardConfig(id="card-fortune", name="Wheel of Fortune", symbol="🔄",
                      persona="Decision Maker", capabilities=["deterministic", "decision_making", "audit"]),
            CardConfig(id="card-strength", name="Strength", symbol="💪",
                      persona="Evaluation Agent", capabilities=["evaluation", "critique", "review", "audit"]),
            CardConfig(id="card-tower", name="The Tower", symbol="⚡",
                      persona="Risk Assessor", capabilities=["risk_analysis", "breakdown", "critique"]),
        ],
        priority=4
    ),
    
    # 4. Wild Unknown: Visual, atmospheric, intuitive
    DeckArchetype(
        id="wild-unknown",
        name="Wild Unknown",
        symbol="🐾",
        description="Animal-centric visual style. Atmospheric, intuitive, symbolic artistic work.",
        style="visual, atmospheric, intuitive, symbolic",
        best_for=["visual_storyboards", "brand_moodboards", "emotion_led_creative_work", "narrative_tone"],
        image_pack="/static/tarot/wild-unknown/",
        cards=[
            CardConfig(id="card-high-priestess", name="The High Priestess", symbol="🗝️",
                      persona="Creative Director", capabilities=["creative", "synthesis", "visual", "brand"]),
            CardConfig(id="card-magician", name="The Magician", symbol="✨",
                      persona="Creative Builder", capabilities=["creative", "building", "storyboard", "design"]),
            CardConfig(id="card-fool", name="The Fool", symbol="🌀",
                      persona="Narrative Explorer", capabilities=["creative", "story", "moodboard", "narrative"]),
            CardConfig(id="card-devil", name="The Devil", symbol="🔗",
                      persona="Emotional Analyst", capabilities=["emotion", "brand", "mood", "intuition"]),
        ],
        priority=2
    ),
    
    # 5. Hermetic: Density, analysis, occult
    DeckArchetype(
        id="hermetic",
        name="Hermetic Tarot",
        symbol="🔺",
        description="Authoritative symbolism. Analytical, correspondence-driven esoteric reasoning.",
        style="symbol-dense, analytical, correspondence-driven, esoteric",
        best_for=["security_review", "threat_modeling", "occult_esoteric_research", "symbol_heavy_reasoning"],
        image_pack="/static/tarot/hermetic/",
        cards=[
            CardConfig(id="card-hermit", name="The Hermit", symbol="🔍",
                      persona="Esoteric Researcher", capabilities=["research", "analysis", "esoteric", "deep"]),
            CardConfig(id="card-high-priestess", name="The High Priestess", symbol="🗝️",
                      persona="Symbol Decoder", capabilities=["analysis", "symbolic", "review", "esoteric"]),
            CardConfig(id="card-hierophant", name="The Hierophant", symbol="📿",
                      persona="Tradition Keeper", capabilities=["research", "audit", "compliance", "policy"]),
            CardConfig(id="card-devil", name="The Devil", symbol="🔗",
                      persona="Threat Analyst", capabilities=["security", "threat", "vulnerability", "risk"]),
        ],
        priority=1
    ),
    
    # 6. Golden Dawn: Structured, ceremonial, complex
    DeckArchetype(
        id="golden-dawn",
        name="Golden Dawn",
        symbol="✶",
        description="Rich correspondences and color symbolism. Structured ceremonial logic, system mapping.",
        style="structured correspondences, ceremonial logic, system mapping, complex",
        best_for=["agent_orchestration", "ritualized_workflows", "complex_multi_step_planning", "classification"],
        image_pack="/static/tarot/golden-dawn/",
        cards=[
            CardConfig(id="card-emperor", name="The Emperor", symbol="🧠",
                      persona="System Planner", capabilities=["architecture", "planning", "orchestration"]),
            CardConfig(id="card-hierophant", name="The Hierophant", symbol="📿",
                      persona="Workflow Architect", capabilities=["workflow", "classification", "planning"]),
            CardConfig(id="card-chariot", name="The Chariot", symbol="🏎️",
                      persona="Execution Coordinator", capabilities=["optimization", "execution", "coordination"]),
            CardConfig(id="card-world", name="The World", symbol="🌍",
                      persona="Completion Orchestrator", capabilities=["completion", "quality_check", "synthesis"]),
        ],
        priority=2
    ),
    
    # 7. Urban Tarot: Contemporary, pragmatic, business
    DeckArchetype(
        id="urban-tarot",
        name="Urban Tarot",
        symbol="🏙️",
        description="Modern urban aesthetic. Practical business contexts, startup scenarios.",
        style="contemporary, pragmatic, business, urban",
        best_for=["startup_planning", "product_launches", "market_positioning", "modern_business_scenarios"],
        image_pack="/static/tarot/urban/",
        cards=[
            CardConfig(id="card-magician", name="The Magician", symbol="✨",
                      persona="Product Builder", capabilities=["coding", "building", "execution", "startup"]),
            CardConfig(id="card-empress", name="The Empress", symbol="🌸",
                      persona="Product Visionary", capabilities=["creative", "design", "vision", "brand"]),
            CardConfig(id="card-emperor", name="The Emperor", symbol="🧠",
                      persona="Startup Planner", capabilities=["architecture", "planning", "scaling"]),
            CardConfig(id="card-world", name="The World", symbol="🌍",
                      persona="Launch Coordinator", capabilities=["completion", "launch", "scaling"]),
        ],
        priority=3
    )
]


# Keyword mapping for auto-deck selection
DECK_KEYWORDS = {
    "rider-waite-smith": [
        "general", "brief", "campaign", "user", "client", "copy", "story", "theme",
        "creative", "design", "brand"
    ],
    "thoth": [
        "architecture", "systems", "research synthesis", "analysis", "planning",
        "decomposition", "technical", "deep", "intellectual", "abstract"
    ],
    "marseille": [
        "logic", "legal", "policy", "compliance", "audit", "deterministic",
        "deterministic", "rational", "audit", "review"
    ],
    "wild-unknown": [
        "storyboard", "visual", "moodboard", "brand feel", "atmospheric",
        "intuitive", "emotional", "narrative", "symbolic"
    ],
    "hermetic": [
        "security", "attack", "threat", "security review", "occult",
        "esoteric", "symbol", "occult-esoteric", "vulnerability", "risk"
    ],
    "golden-dawn": [
        "orchestration", "workflow", "classification", "multi-step",
        "complex", "ritualized", "ceremonial", "agent"
    ],
    "urban-tarot": [
        "startup", "product", "launch", "market", "business",
        "commercial", "urban", "modern", "scaling"
    ]
}


def classify_task(prompt: str) -> str:
    """Classify task to determine best deck"""
    prompt_lower = prompt.lower()
    
    for deck_id, keywords in DECK_KEYWORDS.items():
        if any(keyword in prompt_lower for keyword in keywords):
            return deck_id
    
    return "rider-waite-smith"  # Default


def get_deck_by_id(deck_id: str) -> Optional[Dict]:
    """Get deck by ID"""
    for deck in DECK_ARCHETYPES:
        if deck.id == deck_id:
            return deck.to_dict()
    return None


def get_all_decks() -> List[Dict]:
    """Get all enabled decks, sorted by priority"""
    decs = [d.to_dict() for d in DECK_ARCHETYPES if d.enabled]
    return sorted(decs, key=lambda x: x.get('priority', 5))


def get_cards() -> List[Dict]:
    """Get all unique cards from all enabled decks"""
    seen = set()
    cards = []
    for deck in DECK_ARCHETYPES:
        if not deck.enabled:
            continue
        for card in deck.cards:
            if card.id not in seen:
                seen.add(card.id)
                cards.append(card.to_dict())
    return cards


def get_card_by_id(card_id: str) -> Optional[Dict]:
    """Get single card by ID"""
    cards = get_cards()
    return next((c for c in cards if c["id"] == card_id), None)


def get_deck_summary() -> List[Dict]:
    """Get summary of all decks for UI display"""
    return [{
        "id": d.id,
        "name": d.name,
        "symbol": d.symbol,
        "description": d.description,
        "style": d.style,
        "best_for": d.best_for,
        "card_count": len(d.cards),
        "cards": [c.to_dict() for c in d.cards],
        "image_pack": d.image_pack,
        "enabled": d.enabled,
        "priority": d.priority
    } for d in DECK_ARCHETYPES]


def get_recommended_deck(prompt: str) -> Dict:
    """Get recommended deck and cards for a task"""
    deck_id = classify_task(prompt)
    deck = get_deck_by_id(deck_id)
    
    if not deck:
        deck = get_deck_by_id("rider-waite-smith")
    
    return {
        "recommended_deck_id": deck_id,
        "deck": deck,
        "cards": get_cards()  # All available cards from enabled decks
    }
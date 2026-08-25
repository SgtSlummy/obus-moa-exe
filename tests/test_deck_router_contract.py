from backend.deck_router import DECK_ARCHETYPES, DeckArchetype


def test_deck_archetype_serializes_enabled_state():
    enabled = DECK_ARCHETYPES[0]
    disabled = DeckArchetype(
        id=enabled.id,
        name=enabled.name,
        symbol=enabled.symbol,
        description=enabled.description,
        style=enabled.style,
        best_for=enabled.best_for,
        cards=enabled.cards,
        image_pack=enabled.image_pack,
        enabled=False,
        priority=enabled.priority,
    )

    assert enabled.to_dict()["enabled"] is True
    assert disabled.to_dict()["enabled"] is False

import pytest, json
from abvorn.persona.engine import PersonaEngine
from abvorn.persona.registry import PersonaRegistry


def test_persona_discovery():
    """Should discover personas for a niche."""
    engine = PersonaEngine()
    personas = engine.discover_personas("wireless headphones")
    assert len(personas) >= 2
    for p in personas:
        assert "name" in p
        assert "psychology" in p
        assert "awareness_level" in p["psychology"]
        assert "anxieties" in p["psychology"]


def test_persona_registry():
    """Should register and retrieve personas."""
    registry = PersonaRegistry(":memory:")
    registry.register_persona("p1", "wireless headphones", {
        "name": "Marcus the Commuter",
        "psychology": {"awareness_level": "solution_aware", "anxieties": ["bad battery"]}
    })
    persona = registry.get_persona("p1")
    assert persona is not None
    assert persona["name"] == "Marcus the Commuter"


def test_persona_retirement():
    """Should retire personas that underperform."""
    registry = PersonaRegistry(":memory:")
    registry.register_persona("p_bad", "gaming mice", {"name": "Bad Performer"})
    for _ in range(6):
        registry.update_performance("p_bad", converted=False)
    persona = registry.get_persona("p_bad")
    assert persona["status"] == "retired"
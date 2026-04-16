"""Smoke tests: does pip install -e . produce a working package?"""


def test_aios_importable():
    """The top-level aios package must be importable."""
    import aios
    assert aios is not None


def test_core_event_importable():
    """aios.core.event must be importable (stdlib-only)."""
    from aios.core.event import Event, EventType
    evt = Event.create(EventType.PIPELINE_COMPLETED, source="test")
    assert evt.type == EventType.PIPELINE_COMPLETED
    assert evt.source == "test"
    assert isinstance(evt.id, str) and len(evt.id) > 0


def test_agent_system_importable():
    """aios.agent_system must be importable (guarded imports)."""
    import aios.agent_system
    # AgentManager may be None if sub-deps are missing, but the import must not crash
    assert aios.agent_system is not None

"""Smoke tests: does pip install -e . produce a working package?"""

from importlib.metadata import requires
from pathlib import Path


def test_root_dependency_declarations_match():
    """The editable-package and requirements install paths must stay aligned."""
    root = Path(__file__).resolve().parents[1]
    # Inspect the installed package's real metadata. Its optional dev dependency
    # has an explicit extra marker and is not part of requirements.txt.
    package_dependencies = [
        requirement
        for requirement in requires("taijios") or []
        if not requirement.partition(";")[2].strip().startswith("extra ==")
    ]
    requirements = [
        line.strip()
        for line in (root / "requirements.txt").read_text().splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    assert sorted(package_dependencies) == sorted(requirements)


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

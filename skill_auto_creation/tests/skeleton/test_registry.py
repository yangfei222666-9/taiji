"""
Test skeleton for skill_draft_registry

Purpose: Define what we need to verify, not implement yet.
"""

import sys
from pathlib import Path

# Import stub
sys.path.insert(0, str(Path(__file__).parent.parent / "stubs"))
from skill_draft_registry import SkillDraftRegistry


def test_registry_updates_state_transition():
    """
    Given: draft in 'generated' state
    When: registry transitions to 'validated'
    Then: state file should reflect new state with timestamp
    """
    # TODO: prepare draft in 'generated' state
    # TODO: call registry.transition('validated')
    # TODO: assert state file contains 'validated'
    # TODO: assert state file contains transition timestamp
    pass


def test_registry_records_rejected_reason():
    """
    Given: draft fails validation
    When: registry transitions to 'rejected'
    Then: state file should contain rejection reason
    """
    # TODO: prepare draft with validation errors
    # TODO: call registry.transition('rejected', reason='...')
    # TODO: assert state file contains 'rejected'
    # TODO: assert state file contains reason
    pass


def test_registry_index_matches_filesystem():
    """
    Given: multiple drafts in registry
    When: registry rebuilds index
    Then: index should match actual draft directories
    """
    # TODO: prepare 3 draft directories
    # TODO: call registry.rebuild_index()
    # TODO: assert index contains 3 entries
    # TODO: assert all draft_ids match filesystem
    pass


def test_registry_prevents_duplicate_draft_id():
    """
    Given: draft with existing draft_id
    When: registry tries to register again
    Then: should reject with duplicate error
    """
    # TODO: prepare existing draft
    # TODO: call registry.register() with same draft_id
    # TODO: assert result['success'] == False
    # TODO: assert 'duplicate' in result['error']
    pass


def test_registry_tracks_lifecycle_history():
    """
    Given: draft goes through multiple transitions
    When: querying draft history
    Then: should return all state transitions with timestamps
    """
    # TODO: prepare draft
    # TODO: transition through generated → validated → shadow_run → promoted
    # TODO: call registry.get_history(draft_id)
    # TODO: assert history contains 4 transitions
    pass

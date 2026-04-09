"""
Test skeleton for skill_drafter

Purpose: Define what we need to verify, not implement yet.
"""

import sys
from pathlib import Path

# Import stub
sys.path.insert(0, str(Path(__file__).parent.parent / "stubs"))
from skill_drafter import SkillDrafter


def test_draft_skill_creates_skill_md_and_meta():
    """
    Given: valid candidate from detector
    When: drafter generates draft
    Then: should create SKILL.md and skill_meta.json
    """
    # TODO: prepare candidate fixture
    # TODO: call drafter.draft()
    # TODO: assert output_dir contains SKILL.md
    # TODO: assert output_dir contains skill_meta.json
    pass


def test_drafter_fills_required_frontmatter_fields():
    """
    Given: candidate with minimal info
    When: drafter generates SKILL.md
    Then: frontmatter should contain name, version, type, status, created_at
    """
    # TODO: prepare minimal candidate
    # TODO: call drafter.draft()
    # TODO: parse SKILL.md frontmatter
    # TODO: assert all required fields present
    pass


def test_drafter_uses_template_structure():
    """
    Given: any candidate
    When: drafter generates SKILL.md
    Then: should follow template sections (When to Use, How It Works, etc.)
    """
    # TODO: prepare candidate
    # TODO: call drafter.draft()
    # TODO: parse SKILL.md body
    # TODO: assert contains "## When to Use"
    # TODO: assert contains "## How It Works"
    # TODO: assert contains "## Verification"
    pass


def test_drafter_generates_trigger_spec():
    """
    Given: candidate with activation signals
    When: drafter generates draft
    Then: should create skill_trigger.py with activation logic
    """
    # TODO: prepare candidate with signals
    # TODO: call drafter.draft()
    # TODO: assert output_dir contains skill_trigger.py
    # TODO: assert trigger contains should_activate()
    pass


def test_drafter_includes_example_usage():
    """
    Given: candidate with sample inputs
    When: drafter generates SKILL.md
    Then: should include example usage section
    """
    # TODO: prepare candidate with samples
    # TODO: call drafter.draft()
    # TODO: parse SKILL.md
    # TODO: assert contains "## Example Usage"
    pass

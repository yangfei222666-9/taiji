"""
Test skeleton for skill_validator

Purpose: Define what we need to verify, not implement yet.
"""

import sys
from pathlib import Path

# Import stub
sys.path.insert(0, str(Path(__file__).parent.parent / "stubs"))
from skill_validator import SkillValidator


def test_validator_passes_valid_draft():
    """
    Given: well-formed draft with all required fields
    When: validator runs L0/L1/L2 checks
    Then: should return validation_passed=True
    """
    # TODO: prepare valid draft fixture
    # TODO: call validator.validate()
    # TODO: assert result['validation_passed'] == True
    # TODO: assert result['level'] == 'L2'
    pass


def test_validator_rejects_malformed_frontmatter():
    """
    Given: SKILL.md with missing required frontmatter fields
    When: validator runs L0 check
    Then: should fail with specific error
    """
    # TODO: prepare draft with missing 'name' field
    # TODO: call validator.validate()
    # TODO: assert result['validation_passed'] == False
    # TODO: assert 'missing required field' in result['errors']
    pass


def test_validator_flags_high_risk_content():
    """
    Given: SKILL.md with dangerous commands (rm -rf, eval, etc.)
    When: validator runs L2 security check
    Then: should flag as high risk
    """
    # TODO: prepare draft with 'rm -rf' in example
    # TODO: call validator.validate()
    # TODO: assert result['risk_level'] == 'high'
    # TODO: assert 'dangerous command' in result['warnings']
    pass


def test_validator_checks_trigger_syntax():
    """
    Given: skill_trigger.py with syntax errors
    When: validator runs L1 check
    Then: should fail with syntax error details
    """
    # TODO: prepare draft with invalid Python in trigger
    # TODO: call validator.validate()
    # TODO: assert result['validation_passed'] == False
    # TODO: assert 'syntax error' in result['errors']
    pass


def test_validator_verifies_required_sections():
    """
    Given: SKILL.md missing "How It Works" section
    When: validator runs L0 check
    Then: should warn about missing section
    """
    # TODO: prepare draft without "How It Works"
    # TODO: call validator.validate()
    # TODO: assert 'missing section' in result['warnings']
    pass

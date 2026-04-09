"""
Skill Validator

Validates Skill drafts through three layers: format, security, and risk assessment.

This module is READ-ONLY with respect to the draft content.
It never modifies drafts, never auto-fixes issues, never executes any code in drafts.
"""

from typing import Dict, List, Optional


def validate_skill(
    skill_dir: str,
    rules_path: str
) -> Dict:
    """
    对 Skill 草案做三层验证。
    
    Args:
        skill_dir: Path to draft directory (containing SKILL.md and meta.json)
        rules_path: Path to VALIDATION_RULES.json
    
    Returns:
        Validation result dict:
        {
            "passed": bool,              # Overall pass/fail
            "skill_id": str,             # Skill ID
            "layer": str | None,         # Layer where failure occurred (None if passed)
            "issues": List[Dict],        # List of issues found
            "risk_level": str,           # "low" | "medium" | "high" | "critical"
            "validated_at": str          # ISO timestamp
        }
    
    Raises:
        FileNotFoundError: If skill_dir or rules_path doesn't exist
        ValueError: If SKILL.md or rules are malformed
    
    TODO:
        - Implement layer 1: format validation
        - Implement layer 2: security scanning
        - Implement layer 3: risk assessment
        - Return detailed issue list with line numbers
    """
    raise NotImplementedError("validate_skill not yet implemented")


def validate_format(
    skill_md_content: str,
    required_fields: List[str],
    required_sections: List[str]
) -> List[Dict]:
    """
    Layer 1: 验证 SKILL.md 格式和必填字段。
    
    Args:
        skill_md_content: SKILL.md file content
        required_fields: Required frontmatter fields
        required_sections: Required markdown sections
    
    Returns:
        List of issues:
        [{"rule_id": str, "severity": str, "message": str, "line": int | None}]
    
    TODO:
        - Parse YAML frontmatter
        - Check required fields
        - Check required sections
        - Validate field types
    """
    raise NotImplementedError("validate_format not yet implemented")


def scan_security(
    skill_md_content: str,
    security_rules: List[Dict]
) -> List[Dict]:
    """
    Layer 2: 扫描安全风险和恶意模式。
    
    Args:
        skill_md_content: SKILL.md file content
        security_rules: Security rules from VALIDATION_RULES.json
    
    Returns:
        List of security issues found
    
    TODO:
        - Regex scan for dangerous patterns
        - Check for prompt injection
        - Check for credential exposure
        - Check for destructive commands
    """
    raise NotImplementedError("scan_security not yet implemented")


def assess_risk(
    skill_md_content: str,
    meta: Dict,
    risk_rules: List[Dict]
) -> str:
    """
    Layer 3: 评估操作风险等级。
    
    Args:
        skill_md_content: SKILL.md file content
        meta: Skill metadata dict
        risk_rules: Risk rules from VALIDATION_RULES.json
    
    Returns:
        Risk level: "low" | "medium" | "high" | "critical"
    
    TODO:
        - Check file modification scope
        - Check network access
        - Check privilege requirements
        - Check data access patterns
    """
    raise NotImplementedError("assess_risk not yet implemented")

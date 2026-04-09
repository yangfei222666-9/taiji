"""
Test skeleton for skill_candidate_detector

Purpose: Define what we need to verify, not implement yet.
"""

import sys
from pathlib import Path

# Import stub
sys.path.insert(0, str(Path(__file__).parent.parent / "stubs"))
from skill_candidate_detector import SkillCandidateDetector


def test_detect_candidates_from_old_alert_samples():
    """
    Given: heartbeat logs with repeated alert patterns
    When: detector scans for candidates
    Then: should emit at least 1 candidate with type='alert_deduper'
    """
    # TODO: prepare fixture with 3+ repeated alerts
    # TODO: call detector.detect()
    # TODO: assert len(candidates) >= 1
    # TODO: assert candidates[0]['type'] == 'alert_deduper'
    pass


def test_detector_ignores_quarantined_issue_only_samples():
    """
    Given: heartbeat logs with only quarantined issues (no new alerts)
    When: detector scans
    Then: should NOT emit candidate
    """
    # TODO: prepare fixture with quarantined issues only
    # TODO: call detector.detect()
    # TODO: assert len(candidates) == 0
    pass


def test_detector_does_not_emit_candidate_for_clean_heartbeat():
    """
    Given: heartbeat logs with all HEARTBEAT_OK
    When: detector scans
    Then: should NOT emit candidate
    """
    # TODO: prepare fixture with clean heartbeat
    # TODO: call detector.detect()
    # TODO: assert len(candidates) == 0
    pass


def test_detector_respects_min_occurrence_threshold():
    """
    Given: alert pattern appears only 1 time (below threshold)
    When: detector scans
    Then: should NOT emit candidate
    """
    # TODO: prepare fixture with single occurrence
    # TODO: call detector.detect(min_occurrences=3)
    # TODO: assert len(candidates) == 0
    pass


def test_detector_extracts_alert_metadata():
    """
    Given: repeated alert with skill name and error type
    When: detector emits candidate
    Then: candidate should contain skill_name, error_type, occurrences
    """
    # TODO: prepare fixture with structured alert
    # TODO: call detector.detect()
    # TODO: assert 'skill_name' in candidates[0]
    # TODO: assert 'error_type' in candidates[0]
    # TODO: assert candidates[0]['occurrences'] >= 3
    pass

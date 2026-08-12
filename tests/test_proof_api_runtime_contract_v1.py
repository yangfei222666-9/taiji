"""Static-model and source-marker RED tests for Proof API Contract v1.

The package-consistency tests must be GREEN before the implementation RED is
accepted. The static scenario model executes contract decisions, not HTTP or
runtime behavior. The final class intentionally checks only named source
markers; marker presence cannot prove that an implementation works.

These tests do not start HTTP, read secrets, access Supabase, or call a provider.
"""

from __future__ import annotations

import ast
import hashlib
import json
import sys
import unittest
from pathlib import Path


sys.dont_write_bytecode = True

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts import check_proof_api_runtime_contract_v1 as gate  # noqa: E402


CONTRACT = PROJECT_ROOT / "docs" / "PROOF_API_RUNTIME_CONTRACT_V1.md"
RED_CASES = (
    PROJECT_ROOT
    / "examples"
    / "proof_api_runtime_contract_v1"
    / "fixtures"
    / "red_cases.json"
)

EXPECTED_CONTRACT_SHA256 = (
    "d4b5f4d7e3fd85d16bcb683623aa1322da207c1041dc4b2640ebbd7b940e1f21"
)
EXPECTED_SECTION_10_GROUPS = list(range(1, 30))
EXPECTED_HARNESS_CODES = {
    "health_side_effect_detected",
    "proof_mutation_detected",
}
EXPECTED_REASON_OUTCOMES = {
    "api_sha_mismatch": (409, "FAILED"),
    "artifact_bytes_mismatch": (409, "FAILED"),
    "artifact_digest_mismatch": (409, "FAILED"),
    "artifact_missing": (409, "BLOCKED"),
    "artifact_object_missing": (409, "BLOCKED"),
    "artifact_path_invalid": (409, "FAILED"),
    "artifact_record_failed": (409, "FAILED"),
    "artifact_upload_failed": (409, "FAILED"),
    "dependency_unavailable": (503, "UNVERIFIED"),
    "duplicate_receipt": (409, "FAILED"),
    "event_lineage_mismatch": (409, "FAILED"),
    "event_missing": (409, "BLOCKED"),
    "event_payload_digest_mismatch": (409, "FAILED"),
    "event_persist_failed": (409, "FAILED"),
    "finalization_conflict": (409, "FAILED"),
    "internal_verification_error": (500, "UNVERIFIED"),
    "invalid_invite_token": (401, "BLOCKED"),
    "invalid_request": (400, "BLOCKED"),
    "invalid_state_transition": (409, "FAILED"),
    "invite_expired": (403, "BLOCKED"),
    "missing_api_exact_sha": (503, "UNVERIFIED"),
    "missing_invite_token": (401, "BLOCKED"),
    "producer_image_digest_mismatch": (409, "FAILED"),
    "producer_image_digest_missing": (409, "BLOCKED"),
    "producer_revision_missing": (409, "BLOCKED"),
    "producer_sha_mismatch": (409, "FAILED"),
    "provider_call_forbidden": (500, "FAILED"),
    "receipt_digest_mismatch": (409, "FAILED"),
    "receipt_malformed": (409, "FAILED"),
    "receipt_manifest_mismatch": (409, "FAILED"),
    "receipt_missing": (409, "BLOCKED"),
    "receipt_persist_failed": (409, "FAILED"),
    "request_too_large": (413, "BLOCKED"),
    "root_event_mismatch": (409, "FAILED"),
    "run_access_denied": (403, "BLOCKED"),
    "run_cancelled": (409, "FAILED"),
    "run_failed": (409, "FAILED"),
    "run_id_mismatch": (409, "FAILED"),
    "run_not_found": (404, "BLOCKED"),
    "run_not_terminal": (202, "PENDING"),
    "run_request_id_mismatch": (409, "FAILED"),
    "secret_exposure_detected": (500, "FAILED"),
    "stored_bytes_unverified": (409, "BLOCKED"),
    "unsupported_contract": (422, "BLOCKED"),
    "unsupported_media_type": (415, "BLOCKED"),
}
EXPECTED_SOURCE_GAPS = {
    "atomic_finalization_rpc_source_marker_missing",
    "evidence_schema_source_markers_missing",
    "health_route_source_marker_missing",
    "immutable_receipt_schema_source_markers_missing",
    "proof_auth_source_markers_missing",
    "proof_route_source_marker_missing",
    "rfc8785_source_markers_missing",
    "smoke_instrumentation_source_markers_missing",
    "upstream_identity_source_markers_missing",
}


def load_red_catalog() -> dict:
    return gate.strict_loads(RED_CASES.read_text(encoding="utf-8"))


def conforming_source_bundle() -> dict[str, str]:
    """Inert source markers used only to mutation-test the marker detector."""

    return {
        "auth": " ".join(
            (
                "x-taiji-invite-token",
                "run_access_denied",
                "invite_expired",
                "invalid_invite_token",
            )
        ),
        "database": """
            root_event_id producer_event_id payload_sha256 failure_code
            receipt_sha256 receipt_id unique (run_id)
            create function finalize_proof_run()
        """,
        "health": "export async function GET() {}",
        "jcs": "RFC 8785 canonical receipt_sha256",
        "proof": "export async function POST() {}",
        "smoke": " ".join(
            (
                "health_dependency_call_count",
                "proof_db_mutation_count",
                "proof_storage_mutation_count",
                "provider_calls",
            )
        ),
        "start_run": " ".join(
            (
                "run_request_id",
                "root_event_id",
                "api_exact_sha",
                "evidence_profile",
                "trigger_mode",
            )
        ),
    }


class TestProofApiRedPackageControls(unittest.TestCase):
    """Independent controls that must pass before a semantic RED is credible."""

    def test_contract_hash_is_frozen(self):
        actual = hashlib.sha256(CONTRACT.read_bytes()).hexdigest()
        self.assertEqual(EXPECTED_CONTRACT_SHA256, actual)

    def test_static_package_self_test_is_green(self):
        summary = gate.validate_static_package(PROJECT_ROOT)

        self.assertEqual(
            "PASS_LOCAL_STATIC_MODEL_PACKAGE_SELF_TEST_ONLY", summary["verdict"]
        )
        self.assertEqual(45, summary["reason_codes"])
        self.assertEqual(29, summary["section_10_groups"])
        self.assertGreater(summary["declared_negative_cases"], 45)
        self.assertEqual(
            summary["declared_negative_cases"],
            summary["executed_static_model_negative_cases"],
        )
        self.assertEqual(0, summary["specified_only_cases"])
        self.assertEqual(0, summary["executed_runtime_negative_cases"])
        self.assertFalse(summary["implementation_claimed"])
        self.assertFalse(summary["runtime_called"])
        self.assertFalse(summary["provider_called"])
        self.assertEqual(0, summary["skipped"])

    def test_section_9_mapping_is_independently_frozen(self):
        self.assertEqual(EXPECTED_REASON_OUTCOMES, gate.REASON_OUTCOMES)
        self.assertEqual(45, len(EXPECTED_REASON_OUTCOMES))

    def test_section_10_inventory_is_independently_frozen(self):
        catalog = load_red_catalog()
        groups = sorted({case["section_10_group"] for case in catalog["cases"]})
        reasons = {
            case["expected_reason_code"]
            for case in catalog["cases"]
            if case["expected_reason_code"] is not None
        }
        harness_codes = {
            case["expected_harness_code"]
            for case in catalog["cases"]
            if case["expected_harness_code"] is not None
        }

        self.assertEqual(EXPECTED_SECTION_10_GROUPS, groups)
        self.assertEqual(set(EXPECTED_REASON_OUTCOMES), reasons)
        self.assertEqual(EXPECTED_HARNESS_CODES, harness_codes)

    def test_priority_and_durable_failure_oracles_are_explicit(self):
        cases = {case["case_id"]: case for case in load_red_catalog()["cases"]}
        expected = {
            "red_10_failed_with_durable_failure_code": "artifact_upload_failed",
            "red_23_provider_call_overrides_run_not_found": "provider_call_forbidden",
            "red_24_secret_exposure_overrides_invalid_request": "secret_exposure_detected",
        }
        self.assertEqual(
            expected,
            {case_id: cases[case_id]["expected_reason_code"] for case_id in expected},
        )

    def test_static_scenario_oracles_do_not_read_fixture_expectations(self):
        catalog = load_red_catalog()
        base = gate.validate_static_scenario(catalog["scenario_model"]["base"])
        overrides = catalog["scenario_model"]["overrides"]
        independent_oracles = {
            "red_01_duplicate_json_key": (400, "BLOCKED", "invalid_request", None),
            "red_02_request_body_too_large": (
                413,
                "BLOCKED",
                "request_too_large",
                None,
            ),
            "red_07_dual_carriers": (400, "BLOCKED", "invalid_request", None),
            "red_10_failed_with_durable_failure_code": (
                409,
                "FAILED",
                "artifact_upload_failed",
                None,
            ),
            "red_21_succeeded_with_failure_code": (
                409,
                "FAILED",
                "invalid_state_transition",
                None,
            ),
            "red_23_provider_call_overrides_run_not_found": (
                500,
                "FAILED",
                "provider_call_forbidden",
                None,
            ),
            "red_23_workflow_dispatch": (
                500,
                "FAILED",
                "provider_call_forbidden",
                None,
            ),
            "red_24_secret_exposure_overrides_invalid_request": (
                500,
                "FAILED",
                "secret_exposure_detected",
                None,
            ),
            "red_26_health_dependency_access": (
                None,
                None,
                None,
                "health_side_effect_detected",
            ),
            "red_27_proof_storage_write": (
                None,
                None,
                None,
                "proof_mutation_detected",
            ),
            "red_28_artifact_inventory_extra": (
                409,
                "FAILED",
                "receipt_manifest_mismatch",
                None,
            ),
            "red_29_github_image_invalid_format": (
                409,
                "FAILED",
                "receipt_malformed",
                None,
            ),
            "red_29_mock_image_non_null": (
                409,
                "FAILED",
                "receipt_malformed",
                None,
            ),
        }
        for case_id, expected in independent_oracles.items():
            with self.subTest(case_id=case_id):
                scenario = gate.apply_scenario_patches(
                    base, overrides[case_id], case_id=case_id
                )
                self.assertEqual(expected, gate.evaluate_static_scenario(scenario))

    def test_scenario_override_inventory_is_exact(self):
        catalog = load_red_catalog()
        case_ids = {case["case_id"] for case in catalog["cases"]}
        self.assertEqual(case_ids, set(catalog["scenario_model"]["overrides"]))

    def test_strict_json_loader_rejects_ambiguous_numbers_and_duplicate_keys(self):
        invalid_documents = {
            "duplicate_key": '{"a":1,"a":2}',
            "nan": '{"value":NaN}',
            "infinity": '{"value":Infinity}',
            "float": '{"value":1.5}',
        }
        for name, document in invalid_documents.items():
            with self.subTest(name=name):
                with self.assertRaises(gate.PackageError):
                    gate.strict_loads(document)

    def test_digest_canonicalizer_rejects_values_outside_its_frozen_subset(self):
        invalid_values = {
            "float": {"value": 1.5},
            "non_ascii_string": {"value": "non_ascii_value" + chr(0x00E9)},
            "unsafe_integer": {"value": 9007199254740992},
        }
        for name, value in invalid_values.items():
            with self.subTest(name=name):
                with self.assertRaises(gate.PackageError):
                    gate.canonicalize_jcs_safe_subset(value)

    def test_source_marker_gap_inventory_is_closed_and_named(self):
        observed = set(gate.source_marker_gap_inventory(PROJECT_ROOT))
        self.assertTrue(observed.issubset(EXPECTED_SOURCE_GAPS), observed)

    def test_source_marker_detector_has_an_in_memory_green_control(self):
        self.assertEqual([], gate.evaluate_source_markers(conforming_source_bundle()))

    def test_source_marker_detector_kills_each_marker_independently(self):
        base = conforming_source_bundle()
        mutations = {
            "atomic_finalization_rpc_source_marker_missing": (
                "database",
                base["database"].replace(
                    "create function finalize_proof_run()",
                    "create function commit_proof_run()",
                ),
            ),
            "evidence_schema_source_markers_missing": (
                "database",
                base["database"].replace("root_event_id", "root_anchor"),
            ),
            "immutable_receipt_schema_source_markers_missing": (
                "database",
                base["database"]
                .replace("receipt_sha256", "proof_digest")
                .replace("receipt_id", "proof_record_key"),
            ),
            "health_route_source_marker_missing": ("health", ""),
            "proof_route_source_marker_missing": ("proof", ""),
            "proof_auth_source_markers_missing": ("auth", ""),
            "rfc8785_source_markers_missing": ("jcs", ""),
            "smoke_instrumentation_source_markers_missing": ("smoke", ""),
            "upstream_identity_source_markers_missing": (
                "start_run",
                base["start_run"].replace("run_request_id", "request_key"),
            ),
        }
        self.assertEqual(EXPECTED_SOURCE_GAPS, set(mutations))
        for expected_gap, (source_name, replacement) in mutations.items():
            with self.subTest(expected_gap=expected_gap):
                candidate = dict(base)
                candidate[source_name] = replacement
                self.assertEqual(
                    [expected_gap], gate.evaluate_source_markers(candidate)
                )

    def test_checker_ast_is_read_only_and_uses_only_allowed_stdlib_modules(self):
        checker_path = (
            PROJECT_ROOT / "scripts" / "check_proof_api_runtime_contract_v1.py"
        )
        tree = ast.parse(checker_path.read_text(encoding="utf-8"))
        allowed_roots = {
            "__future__",
            "argparse",
            "copy",
            "datetime",
            "hashlib",
            "json",
            "pathlib",
            "re",
            "sys",
            "typing",
            "uuid",
        }
        forbidden_calls = {
            "FileType",
            "chmod",
            "hardlink_to",
            "lchmod",
            "link_to",
            "mkdir",
            "open",
            "rename",
            "rmdir",
            "symlink_to",
            "touch",
            "unlink",
            "write_bytes",
            "write_text",
        }
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self.assertIn(alias.name.split(".", 1)[0], allowed_roots)
            elif isinstance(node, ast.ImportFrom):
                self.assertIsNotNone(node.module)
                self.assertIn(node.module.split(".", 1)[0], allowed_roots)
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    self.assertNotIn(
                        node.func.id, {"exec", "eval", "open", "__import__"}
                    )
                elif isinstance(node.func, ast.Attribute):
                    self.assertNotIn(node.func.attr, forbidden_calls)


class TestProofApiRootSourceMarkerPreflightRed(unittest.TestCase):
    """Named source-marker RED only; passing does not prove behavior."""

    def assert_marker_present(self, gap: str) -> None:
        observed = gate.source_marker_gap_inventory(PROJECT_ROOT)
        self.assertNotIn(gap, observed, f"named_RED={gap} observed={','.join(observed)}")

    def test_atomic_finalization_rpc_source_marker_present(self):
        self.assert_marker_present("atomic_finalization_rpc_source_marker_missing")

    def test_evidence_schema_source_markers_present(self):
        self.assert_marker_present("evidence_schema_source_markers_missing")

    def test_immutable_receipt_schema_source_markers_present(self):
        self.assert_marker_present("immutable_receipt_schema_source_markers_missing")

    def test_health_route_source_marker_present(self):
        self.assert_marker_present("health_route_source_marker_missing")

    def test_proof_route_source_marker_present(self):
        self.assert_marker_present("proof_route_source_marker_missing")

    def test_proof_auth_source_markers_present(self):
        self.assert_marker_present("proof_auth_source_markers_missing")

    def test_rfc8785_source_markers_present(self):
        self.assert_marker_present("rfc8785_source_markers_missing")

    def test_smoke_instrumentation_source_markers_present(self):
        self.assert_marker_present("smoke_instrumentation_source_markers_missing")

    def test_upstream_identity_source_markers_present(self):
        self.assert_marker_present("upstream_identity_source_markers_missing")


if __name__ == "__main__":
    unittest.main()

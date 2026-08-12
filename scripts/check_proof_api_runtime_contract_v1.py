#!/usr/bin/env python3
"""Validate the static Proof API Runtime Contract v1 RED package.

This checker is deliberately stdlib-only, deterministic, read-only, and bound
to the repository root. It validates contract/schema/fixture consistency. It
does not start HTTP, access Supabase, call a provider, read environment values,
or prove that the future Proof API implementation exists.

Exit codes:
  0: the static package and built-in mutation checks are consistent
  1: a semantic package mismatch was found
  2: the checker could not safely inspect its fixed package inputs
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sys
import uuid
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any, Callable


CONTRACT_ID = "proof_api_runtime_contract_v1"
PROOF_SCOPE = "stored_run_evidence_integrity_v1"
CONTRACT_PATH = "docs/PROOF_API_RUNTIME_CONTRACT_V1.md"
CONTRACT_SHA256 = "d4b5f4d7e3fd85d16bcb683623aa1322da207c1041dc4b2640ebbd7b940e1f21"
SCHEMA_PATH = "evidence/schema/proof_api_runtime_contract_v1.schema.json"
SCHEMA_SHA256 = "b8eac3c1200d8a5545912ff3494b1b88b52128f90a852022ed414d8971d64eeb"
PASS_FIXTURE_PATH = "examples/proof_api_runtime_contract_v1/fixtures/pass_mock.json"
RED_FIXTURE_PATH = "examples/proof_api_runtime_contract_v1/fixtures/red_cases.json"

PACKAGE_ID = "proof_api_runtime_contract_v1_exact_red_package"
POSITIVE_PACKAGE_ID = "proof_api_runtime_contract_v1_positive_controls"
EVIDENCE_PROFILES = {
    "taiji.proof.evidence.github.v1": "github",
    "taiji.proof.evidence.mock.v1": "mock",
}
REQUIRED_CANNOT_CLAIM = {
    "deployment_provenance",
    "github_execution",
    "producer_execution_identity",
    "production_readiness",
    "provider_readiness",
    "repo_wide_pass",
    "task_correctness",
}
HARNESSES = {
    "health_side_effect_detected",
    "proof_mutation_detected",
}

REASON_OUTCOMES: dict[str, tuple[int, str]] = {
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

EXPECTED_SCHEMA_DEFS = {
    "artifact_manifest_item",
    "cannot_claim",
    "event_manifest_item",
    "fixture_case",
    "fixture_catalog",
    "health_response",
    "image_digest",
    "positive_control_catalog",
    "profile_control",
    "proof_nonpass_response",
    "proof_pass_response",
    "proof_request",
    "proof_response",
    "reason_code",
    "receipt",
    "rfc3339_utc",
    "scenario_model",
    "scenario_patch",
    "sha256",
    "sha40",
    "static_scenario",
    "uuid",
    "verdict",
}

FIXTURE_ROOT_KEYS = {
    "cases",
    "contract_id",
    "contract_path",
    "contract_sha256",
    "harness_codes",
    "package_id",
    "scenario_model",
    "schema_path",
    "section_10_groups",
    "section_9_non_pass_reason_codes",
}
CASE_KEYS = {
    "case_id",
    "coverage_level",
    "expected_harness_code",
    "expected_http",
    "expected_proof_accepted",
    "expected_reason_code",
    "expected_verdict",
    "input_kind",
    "mutation",
    "section_10_group",
}
SCENARIO_KEYS = {
    "api_sha_match",
    "artifact_bytes_match",
    "artifact_count",
    "artifact_digest_match",
    "artifact_object_exists",
    "artifact_path_valid",
    "auth_carrier_count",
    "auth_carrier_malformed",
    "content_type",
    "durable_failure_code",
    "event_lineage_valid",
    "event_payload_digest_match",
    "event_present",
    "formats_valid",
    "health_side_effect_count",
    "invite_status",
    "persistence_failure",
    "producer_event_exists",
    "producer_event_field_present",
    "producer_event_same_run",
    "producer_image_format_valid",
    "producer_image_match",
    "producer_image_present",
    "producer_image_required",
    "producer_revision_present",
    "producer_sha_match",
    "proof_mutation_count",
    "provider_call_attempted",
    "raw_body_bytes",
    "raw_body_mode",
    "receipt_api_field_present",
    "receipt_atomic_with_terminal",
    "receipt_count",
    "receipt_digest_match",
    "receipt_exists",
    "receipt_manifest_match",
    "receipt_well_formed",
    "request_additional_fields_present",
    "request_required_fields_present",
    "retry_content_match",
    "root_event_match",
    "run_access_allowed",
    "run_found",
    "run_id_match",
    "run_request_id_match",
    "run_status",
    "schema_supported",
    "secret_exposed",
    "serving_api_sha_present",
    "storage_dependency_available",
    "stored_bytes_read",
    "top_level_receipt_match",
    "workflow_dispatch_attempted",
}
SCENARIO_BOOLEAN_KEYS = {
    key
    for key in SCENARIO_KEYS
    if key
    not in {
        "artifact_count",
        "auth_carrier_count",
        "content_type",
        "durable_failure_code",
        "health_side_effect_count",
        "invite_status",
        "persistence_failure",
        "proof_mutation_count",
        "raw_body_bytes",
        "raw_body_mode",
        "receipt_count",
        "run_status",
    }
}
SCENARIO_INTEGER_KEYS = {
    "artifact_count",
    "auth_carrier_count",
    "health_side_effect_count",
    "proof_mutation_count",
    "raw_body_bytes",
    "receipt_count",
}
POSITIVE_ROOT_KEYS = {
    "contract_id",
    "contract_path",
    "contract_sha256",
    "controls",
    "package_id",
    "schema_path",
}
CONTROL_KEYS = {
    "github_profile",
    "health_configured",
    "health_unconfigured",
    "mock_profile",
    "nonpass_response",
    "signed_url_delivery_failure_irrelevant",
}
REQUEST_KEYS = {
    "expected_api_exact_sha",
    "expected_evidence_profile",
    "expected_producer_exact_sha",
    "expected_producer_image_digest",
    "expected_root_event_id",
    "proof_query_id",
    "run_id",
    "run_request_id",
    "schema_version",
}
HEALTH_KEYS = {
    "api_exact_sha",
    "cannot_claim",
    "reason_codes",
    "revision_binding",
    "schema_version",
    "service",
    "status",
}
RECEIPT_KEYS = {
    "api_exact_sha",
    "artifact_manifest",
    "cannot_claim",
    "contract_id",
    "created_at",
    "event_manifest",
    "evidence_profile",
    "finalized_at",
    "producer_exact_sha",
    "producer_image_digest",
    "proof_scope",
    "reason_codes",
    "receipt_id",
    "receipt_sha256",
    "root_event_id",
    "run_id",
    "run_request_id",
    "schema_version",
    "terminal_run_status",
    "trigger_mode",
    "verdict",
    "verifier_name",
    "verifier_version",
}
PASS_RESPONSE_KEYS = {
    "cannot_claim",
    "checked_at",
    "contract_id",
    "evidence_profile",
    "proof_accepted",
    "proof_query_id",
    "proof_scope",
    "reason_codes",
    "receipt",
    "schema_version",
    "verdict",
}
NONPASS_RESPONSE_KEYS = PASS_RESPONSE_KEYS | {"run_id", "run_request_id"}
EVENT_KEYS = {
    "event_id",
    "event_type",
    "occurred_at",
    "parent_event_id",
    "payload_sha256",
}
ARTIFACT_KEYS = {
    "artifact_id",
    "bucket",
    "bytes",
    "content_type",
    "label",
    "path",
    "producer_event_id",
    "sha256",
}

UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
SHA40_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
IMAGE_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
RFC3339_UTC_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]+)?Z$")


class PackageError(ValueError):
    """A deterministic contract/schema/fixture mismatch."""


class InspectionError(RuntimeError):
    """The fixed package inputs could not be inspected safely."""


def _fail(code: str) -> None:
    raise PackageError(code)


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            _fail("duplicate_json_key")
        result[key] = value
    return result


def _reject_constant(_: str) -> Any:
    _fail("non_finite_number")


def _reject_float(_: str) -> Any:
    _fail("floating_point_not_in_frozen_subset")


def strict_loads(text: str) -> Any:
    try:
        return json.loads(
            text,
            object_pairs_hook=_strict_object,
            parse_constant=_reject_constant,
            parse_float=_reject_float,
        )
    except PackageError:
        raise
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise PackageError("malformed_json") from exc


def _safe_file(repo_root: Path, relative: str) -> Path:
    rel = PurePosixPath(relative)
    if rel.is_absolute() or not rel.parts or ".." in rel.parts:
        raise InspectionError("unsafe_relative_path")
    candidate = repo_root.joinpath(*rel.parts)
    if candidate.is_symlink():
        raise InspectionError("symlink_input_forbidden")
    try:
        resolved_root = repo_root.resolve(strict=True)
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(resolved_root)
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        raise InspectionError(f"fixed_input_unavailable:{relative}") from exc
    if not resolved.is_file():
        raise InspectionError(f"fixed_input_not_regular_file:{relative}")
    return resolved


def _read_text(repo_root: Path, relative: str) -> str:
    try:
        return _safe_file(repo_root, relative).read_text(encoding="utf-8")
    except UnicodeError as exc:
        raise InspectionError(f"fixed_input_not_utf8:{relative}") from exc


def _load_json(repo_root: Path, relative: str) -> Any:
    return strict_loads(_read_text(repo_root, relative))


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _expect_dict(value: Any, code: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        _fail(code)
    return value


def _expect_list(value: Any, code: str) -> list[Any]:
    if not isinstance(value, list):
        _fail(code)
    return value


def _expect_exact_keys(value: dict[str, Any], expected: set[str], code: str) -> None:
    if set(value) != expected:
        _fail(code)


def _expect_string(value: Any, code: str) -> str:
    if not isinstance(value, str):
        _fail(code)
    return value


def _expect_int(value: Any, code: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        _fail(code)
    return value


def _expect_sorted_unique_strings(value: Any, code: str, *, non_empty: bool = False) -> list[str]:
    items = _expect_list(value, code)
    if non_empty and not items:
        _fail(code)
    if any(not isinstance(item, str) or not item for item in items):
        _fail(code)
    if items != sorted(set(items)):
        _fail(code)
    return items


def _expect_uuid(value: Any, code: str) -> str:
    text = _expect_string(value, code)
    if not UUID_RE.fullmatch(text):
        _fail(code)
    try:
        if str(uuid.UUID(text)) != text:
            _fail(code)
    except ValueError as exc:
        raise PackageError(code) from exc
    return text


def _expect_pattern(value: Any, pattern: re.Pattern[str], code: str) -> str:
    text = _expect_string(value, code)
    if not pattern.fullmatch(text):
        _fail(code)
    return text


def _parse_utc(value: Any, code: str) -> datetime:
    text = _expect_pattern(value, RFC3339_UTC_RE, code)
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise PackageError(code) from exc


def _assert_jcs_safe_subset(value: Any, path: str = "root") -> None:
    if value is None or isinstance(value, bool):
        return
    if isinstance(value, int):
        if abs(value) > 9007199254740991:
            _fail(f"jcs_integer_out_of_safe_range:{path}")
        return
    if isinstance(value, float):
        _fail(f"jcs_float_outside_frozen_subset:{path}")
    if isinstance(value, str):
        if any(0xD800 <= ord(char) <= 0xDFFF for char in value):
            _fail(f"jcs_lone_surrogate:{path}")
        if not value.isascii():
            _fail(f"jcs_non_ascii_string_outside_frozen_subset:{path}")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _assert_jcs_safe_subset(item, f"{path}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str) or not key.isascii():
                _fail(f"jcs_non_ascii_key_outside_frozen_subset:{path}")
            _assert_jcs_safe_subset(item, f"{path}.{key}")
        return
    _fail(f"jcs_unsupported_type:{path}")


def canonicalize_jcs_safe_subset(value: Any) -> bytes:
    """Canonicalize the contract's frozen ASCII-key/integer-only JCS subset.

    This is intentionally not presented as a general RFC 8785 implementation.
    Unsupported number/key/string forms fail closed instead of being guessed.
    """

    _assert_jcs_safe_subset(value)
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (TypeError, ValueError) as exc:
        raise PackageError("jcs_safe_subset_serialization_failed") from exc
    return encoded.encode("utf-8")


def _contract_binding(value: dict[str, Any], code: str) -> None:
    if value.get("contract_id") != CONTRACT_ID:
        _fail(code)
    if value.get("contract_path") != CONTRACT_PATH:
        _fail(code)
    if value.get("contract_sha256") != CONTRACT_SHA256:
        _fail(code)
    if value.get("schema_path") != SCHEMA_PATH:
        _fail(code)


def validate_contract_hash(repo_root: Path) -> None:
    raw = _read_text(repo_root, CONTRACT_PATH).encode("utf-8")
    if _sha256_bytes(raw) != CONTRACT_SHA256:
        _fail("contract_sha256_mismatch")


def validate_schema_hash(repo_root: Path) -> None:
    raw = _read_text(repo_root, SCHEMA_PATH).encode("utf-8")
    if _sha256_bytes(raw) != SCHEMA_SHA256:
        _fail("schema_sha256_mismatch")


def _walk_object_schemas(value: Any, path: str = "schema") -> None:
    if isinstance(value, dict):
        if value.get("type") == "object" and value.get("additionalProperties") is not False:
            _fail(f"schema_object_not_closed:{path}")
        for key, item in value.items():
            _walk_object_schemas(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _walk_object_schemas(item, f"{path}[{index}]")


def validate_schema(schema: Any) -> None:
    root = _expect_dict(schema, "schema_root_not_object")
    if root.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
        _fail("schema_dialect_mismatch")
    if root.get("x-taiji-contract-id") != CONTRACT_ID:
        _fail("schema_contract_id_mismatch")
    if root.get("x-taiji-contract-path") != CONTRACT_PATH:
        _fail("schema_contract_path_mismatch")
    if root.get("x-taiji-contract-sha256") != CONTRACT_SHA256:
        _fail("schema_contract_sha256_mismatch")
    definitions = _expect_dict(root.get("$defs"), "schema_defs_missing")
    if set(definitions) != EXPECTED_SCHEMA_DEFS:
        _fail("schema_defs_inventory_mismatch")
    reason_schema = _expect_dict(definitions.get("reason_code"), "reason_schema_missing")
    reason_enum = _expect_sorted_unique_strings(
        reason_schema.get("enum"), "reason_schema_enum_invalid", non_empty=True
    )
    if reason_enum != sorted(REASON_OUTCOMES):
        _fail("reason_schema_closed_set_mismatch")
    fixture_catalog = _expect_dict(
        definitions.get("fixture_catalog"), "fixture_catalog_schema_missing"
    )
    cases_schema = _expect_dict(
        _expect_dict(fixture_catalog.get("properties"), "fixture_catalog_properties_missing").get("cases"),
        "fixture_cases_schema_missing",
    )
    if cases_schema.get("minItems") != 45 or cases_schema.get("uniqueItems") is not True:
        _fail("fixture_cases_schema_not_fail_closed")
    fixture_case = _expect_dict(definitions.get("fixture_case"), "fixture_case_schema_missing")
    fixture_case_properties = _expect_dict(
        fixture_case.get("properties"), "fixture_case_properties_missing"
    )
    if fixture_case_properties.get("coverage_level") != {
        "const": "static_model_executed"
    }:
        _fail("fixture_case_coverage_level_mismatch")
    catalog_required = _expect_list(
        fixture_catalog.get("required"), "fixture_catalog_required_missing"
    )
    if "scenario_model" not in catalog_required:
        _fail("fixture_catalog_scenario_model_not_required")
    scenario_model = _expect_dict(
        definitions.get("scenario_model"), "scenario_model_schema_missing"
    )
    if scenario_model.get("additionalProperties") is not False:
        _fail("scenario_model_schema_not_closed")
    receipt_schema = _expect_dict(definitions.get("receipt"), "receipt_schema_missing")
    expected_receipt_conditional = [
        {
            "if": {
                "properties": {
                    "evidence_profile": {
                        "const": "taiji.proof.evidence.mock.v1"
                    }
                },
                "required": ["evidence_profile"],
            },
            "then": {
                "properties": {
                    "trigger_mode": {"const": "mock"},
                    "producer_image_digest": {"type": "null"},
                }
            },
            "else": {
                "properties": {
                    "trigger_mode": {"const": "github"},
                    "producer_image_digest": {"$ref": "#/$defs/image_digest"},
                }
            },
        }
    ]
    if receipt_schema.get("allOf") != expected_receipt_conditional:
        _fail("receipt_profile_conditional_mismatch")
    _walk_object_schemas(root)


def validate_health(value: Any, expected_binding: str) -> None:
    health = _expect_dict(value, "health_not_object")
    _expect_exact_keys(health, HEALTH_KEYS, "health_keys_mismatch")
    if health["schema_version"] != "taiji.proof.health.v1":
        _fail("health_schema_version_mismatch")
    if health["service"] != "taiji-proof-api" or health["status"] != "ok":
        _fail("health_constant_mismatch")
    if health["revision_binding"] != expected_binding:
        _fail("health_revision_binding_mismatch")
    _expect_sorted_unique_strings(health["cannot_claim"], "health_cannot_claim_invalid", non_empty=True)
    if expected_binding == "configured":
        _expect_pattern(health["api_exact_sha"], SHA40_RE, "health_api_sha_invalid")
        if health["reason_codes"] != []:
            _fail("configured_health_reason_mismatch")
    elif expected_binding == "unconfigured":
        if health["api_exact_sha"] is not None:
            _fail("unconfigured_health_api_sha_not_null")
        if health["reason_codes"] != ["missing_api_exact_sha"]:
            _fail("unconfigured_health_reason_mismatch")
    else:
        _fail("unknown_health_binding")


def validate_request(value: Any) -> dict[str, Any]:
    request = _expect_dict(value, "request_not_object")
    _expect_exact_keys(request, REQUEST_KEYS, "request_keys_mismatch")
    if request["schema_version"] != "taiji.proof.request.v1":
        _fail("request_schema_version_mismatch")
    profile = request["expected_evidence_profile"]
    if profile not in EVIDENCE_PROFILES:
        _fail("request_profile_invalid")
    _expect_uuid(request["proof_query_id"], "proof_query_id_invalid")
    _expect_uuid(request["run_request_id"], "request_run_request_id_invalid")
    _expect_uuid(request["run_id"], "request_run_id_invalid")
    _expect_uuid(request["expected_root_event_id"], "request_root_event_id_invalid")
    _expect_pattern(request["expected_api_exact_sha"], SHA40_RE, "request_api_sha_invalid")
    _expect_pattern(
        request["expected_producer_exact_sha"], SHA40_RE, "request_producer_sha_invalid"
    )
    image_digest = request["expected_producer_image_digest"]
    if EVIDENCE_PROFILES[profile] == "mock":
        if image_digest is not None:
            _fail("mock_request_image_digest_not_null")
    else:
        _expect_pattern(image_digest, IMAGE_DIGEST_RE, "github_request_image_digest_invalid")
    return request


def _validate_event_manifest(value: Any, root_event_id: str) -> tuple[str, str]:
    events = _expect_list(value, "event_manifest_not_array")
    if len(events) != 2:
        _fail("event_manifest_cardinality_mismatch")
    entries = [_expect_dict(item, "event_manifest_item_not_object") for item in events]
    ids: list[str] = []
    for event in entries:
        _expect_exact_keys(event, EVENT_KEYS, "event_manifest_item_keys_mismatch")
        ids.append(_expect_uuid(event["event_id"], "event_id_invalid"))
        parent = event["parent_event_id"]
        if parent is not None:
            _expect_uuid(parent, "parent_event_id_invalid")
        if event["event_type"] not in {"artifact.stored", "run.created"}:
            _fail("event_type_invalid")
        _parse_utc(event["occurred_at"], "event_occurred_at_invalid")
        _expect_pattern(event["payload_sha256"], SHA256_RE, "event_payload_sha256_invalid")
    if ids != sorted(set(ids)):
        _fail("event_manifest_not_sorted_unique")
    roots = [event for event in entries if event["parent_event_id"] is None]
    if len(roots) != 1:
        _fail("event_root_cardinality_mismatch")
    root = roots[0]
    if root["event_id"] != root_event_id or root["event_type"] != "run.created":
        _fail("event_root_binding_mismatch")
    children = [event for event in entries if event["parent_event_id"] is not None]
    if len(children) != 1:
        _fail("event_child_cardinality_mismatch")
    child = children[0]
    if child["parent_event_id"] != root_event_id or child["event_type"] != "artifact.stored":
        _fail("artifact_event_lineage_mismatch")
    return root_event_id, child["event_id"]


def _validate_artifact_manifest(value: Any, run_id: str, producer_event_id: str) -> None:
    artifacts = _expect_list(value, "artifact_manifest_not_array")
    if len(artifacts) != 1:
        _fail("artifact_manifest_cardinality_mismatch")
    artifact = _expect_dict(artifacts[0], "artifact_manifest_item_not_object")
    _expect_exact_keys(artifact, ARTIFACT_KEYS, "artifact_manifest_item_keys_mismatch")
    _expect_uuid(artifact["artifact_id"], "artifact_id_invalid")
    if artifact["producer_event_id"] != producer_event_id:
        _fail("artifact_producer_event_binding_mismatch")
    if artifact["bucket"] != "taiji-artifacts":
        _fail("artifact_bucket_mismatch")
    if artifact["path"] != f"runs/{run_id}/result.json":
        _fail("artifact_path_binding_mismatch")
    if ".." in PurePosixPath(artifact["path"]).parts:
        _fail("artifact_path_traversal")
    if artifact["label"] != "result.json" or artifact["content_type"] != "application/json":
        _fail("artifact_profile_shape_mismatch")
    if _expect_int(artifact["bytes"], "artifact_bytes_invalid") < 0:
        _fail("artifact_bytes_invalid")
    _expect_pattern(artifact["sha256"], SHA256_RE, "artifact_sha256_invalid")


def validate_receipt(value: Any) -> dict[str, Any]:
    receipt = _expect_dict(value, "receipt_not_object")
    _expect_exact_keys(receipt, RECEIPT_KEYS, "receipt_keys_mismatch")
    if "proof_query_id" in receipt:
        _fail("proof_query_id_must_not_be_in_receipt")
    if receipt["contract_id"] != CONTRACT_ID:
        _fail("receipt_contract_id_mismatch")
    if receipt["schema_version"] != "taiji.proof.receipt.v1":
        _fail("receipt_schema_version_mismatch")
    if receipt["proof_scope"] != PROOF_SCOPE:
        _fail("receipt_proof_scope_mismatch")
    profile = receipt["evidence_profile"]
    if profile not in EVIDENCE_PROFILES:
        _fail("receipt_profile_invalid")
    trigger = EVIDENCE_PROFILES[profile]
    if receipt["trigger_mode"] != trigger:
        _fail("receipt_trigger_profile_mismatch")
    _expect_uuid(receipt["receipt_id"], "receipt_id_invalid")
    created_at = _parse_utc(receipt["created_at"], "receipt_created_at_invalid")
    finalized_at = _parse_utc(receipt["finalized_at"], "receipt_finalized_at_invalid")
    if created_at > finalized_at:
        _fail("receipt_timestamp_order_invalid")
    _expect_uuid(receipt["run_request_id"], "receipt_run_request_id_invalid")
    run_id = _expect_uuid(receipt["run_id"], "receipt_run_id_invalid")
    root_event_id = _expect_uuid(receipt["root_event_id"], "receipt_root_event_id_invalid")
    api_sha = _expect_pattern(receipt["api_exact_sha"], SHA40_RE, "receipt_api_sha_invalid")
    producer_sha = _expect_pattern(
        receipt["producer_exact_sha"], SHA40_RE, "receipt_producer_sha_invalid"
    )
    if trigger == "mock":
        if producer_sha != api_sha or receipt["producer_image_digest"] is not None:
            _fail("mock_receipt_producer_invariant_mismatch")
    else:
        _expect_pattern(
            receipt["producer_image_digest"], IMAGE_DIGEST_RE, "github_receipt_image_digest_invalid"
        )
    if receipt["terminal_run_status"] != "succeeded":
        _fail("receipt_terminal_status_mismatch")
    if receipt["verifier_name"] != "taiji-proof-verifier":
        _fail("receipt_verifier_name_mismatch")
    if receipt["verifier_version"] != "1.0.0":
        _fail("receipt_verifier_version_mismatch")
    if receipt["verdict"] != "PASS" or receipt["reason_codes"] != []:
        _fail("receipt_success_invariant_mismatch")
    cannot_claim = set(
        _expect_sorted_unique_strings(
            receipt["cannot_claim"], "receipt_cannot_claim_invalid", non_empty=True
        )
    )
    if not REQUIRED_CANNOT_CLAIM.issubset(cannot_claim):
        _fail("receipt_cannot_claim_baseline_missing")
    _, producer_event_id = _validate_event_manifest(receipt["event_manifest"], root_event_id)
    _validate_artifact_manifest(receipt["artifact_manifest"], run_id, producer_event_id)
    supplied_digest = _expect_pattern(
        receipt["receipt_sha256"], SHA256_RE, "receipt_sha256_invalid"
    )
    digest_input = dict(receipt)
    del digest_input["receipt_sha256"]
    actual_digest = _sha256_bytes(canonicalize_jcs_safe_subset(digest_input))
    if actual_digest != supplied_digest:
        _fail("receipt_test_vector_digest_mismatch")
    return receipt


def validate_pass_response(value: Any, request: dict[str, Any]) -> None:
    response = _expect_dict(value, "pass_response_not_object")
    _expect_exact_keys(response, PASS_RESPONSE_KEYS, "pass_response_keys_mismatch")
    if response["contract_id"] != CONTRACT_ID:
        _fail("pass_response_contract_id_mismatch")
    if response["schema_version"] != "taiji.proof.response.v1":
        _fail("pass_response_schema_version_mismatch")
    if response["proof_scope"] != PROOF_SCOPE:
        _fail("pass_response_scope_mismatch")
    if response["verdict"] != "PASS" or response["proof_accepted"] is not True:
        _fail("pass_response_acceptance_mismatch")
    if response["reason_codes"] != []:
        _fail("pass_response_reason_codes_not_empty")
    receipt = validate_receipt(response["receipt"])
    if response["evidence_profile"] != receipt["evidence_profile"]:
        _fail("response_receipt_profile_mismatch")
    if response["proof_query_id"] != request["proof_query_id"]:
        _fail("response_query_id_mismatch")
    binding_pairs = (
        ("evidence_profile", "expected_evidence_profile"),
        ("run_request_id", "run_request_id"),
        ("run_id", "run_id"),
        ("root_event_id", "expected_root_event_id"),
        ("api_exact_sha", "expected_api_exact_sha"),
        ("producer_exact_sha", "expected_producer_exact_sha"),
        ("producer_image_digest", "expected_producer_image_digest"),
    )
    for receipt_key, request_key in binding_pairs:
        if receipt[receipt_key] != request[request_key]:
            _fail(f"request_receipt_binding_mismatch:{receipt_key}")
    response_cannot_claim = _expect_sorted_unique_strings(
        response["cannot_claim"], "response_cannot_claim_invalid", non_empty=True
    )
    if response_cannot_claim != receipt["cannot_claim"]:
        _fail("response_receipt_cannot_claim_mismatch")
    checked_at = _parse_utc(response["checked_at"], "response_checked_at_invalid")
    finalized_at = _parse_utc(receipt["finalized_at"], "receipt_finalized_at_invalid")
    if finalized_at > checked_at:
        _fail("response_timestamp_order_invalid")


def validate_nonpass_response(value: Any) -> None:
    response = _expect_dict(value, "nonpass_response_not_object")
    _expect_exact_keys(response, NONPASS_RESPONSE_KEYS, "nonpass_response_keys_mismatch")
    if response["contract_id"] != CONTRACT_ID or response["proof_scope"] != PROOF_SCOPE:
        _fail("nonpass_response_control_mismatch")
    if response["schema_version"] != "taiji.proof.response.v1":
        _fail("nonpass_response_schema_version_mismatch")
    if response["proof_accepted"] is not False or response["receipt"] is not None:
        _fail("nonpass_response_fail_closed_mismatch")
    reasons = _expect_list(response["reason_codes"], "nonpass_reason_not_array")
    if len(reasons) != 1 or reasons[0] not in REASON_OUTCOMES:
        _fail("nonpass_reason_not_closed")
    expected_http, expected_verdict = REASON_OUTCOMES[reasons[0]]
    del expected_http
    if response["verdict"] != expected_verdict:
        _fail("nonpass_verdict_reason_mismatch")
    _expect_sorted_unique_strings(
        response["cannot_claim"], "nonpass_cannot_claim_invalid", non_empty=True
    )
    _parse_utc(response["checked_at"], "nonpass_checked_at_invalid")


def validate_positive_catalog(value: Any) -> dict[str, Any]:
    catalog = _expect_dict(value, "positive_catalog_not_object")
    _expect_exact_keys(catalog, POSITIVE_ROOT_KEYS, "positive_catalog_keys_mismatch")
    _contract_binding(catalog, "positive_catalog_contract_binding_mismatch")
    if catalog["package_id"] != POSITIVE_PACKAGE_ID:
        _fail("positive_catalog_package_id_mismatch")
    controls = _expect_dict(catalog["controls"], "positive_controls_not_object")
    _expect_exact_keys(controls, CONTROL_KEYS, "positive_controls_keys_mismatch")
    validate_health(controls["health_configured"], "configured")
    validate_health(controls["health_unconfigured"], "unconfigured")
    for name in ("mock_profile", "github_profile"):
        profile = _expect_dict(controls[name], f"{name}_not_object")
        _expect_exact_keys(profile, {"request", "response"}, f"{name}_keys_mismatch")
        request = validate_request(profile["request"])
        validate_pass_response(profile["response"], request)
        expected_mode = name.removesuffix("_profile")
        if EVIDENCE_PROFILES[request["expected_evidence_profile"]] != expected_mode:
            _fail(f"{name}_mode_mismatch")
    validate_nonpass_response(controls["nonpass_response"])
    signed_url = _expect_dict(
        controls["signed_url_delivery_failure_irrelevant"], "signed_url_control_not_object"
    )
    _expect_exact_keys(
        signed_url,
        {"baseline_verdict", "delivery_failed", "expected_verdict"},
        "signed_url_control_keys_mismatch",
    )
    if signed_url != {
        "baseline_verdict": "PASS",
        "delivery_failed": True,
        "expected_verdict": "PASS",
    }:
        _fail("signed_url_delivery_failure_changed_proof_verdict")
    return catalog


def _validate_scenario_value(key: str, value: Any) -> None:
    if key in SCENARIO_BOOLEAN_KEYS:
        if not isinstance(value, bool):
            _fail(f"scenario_boolean_invalid:{key}")
        return
    if key in SCENARIO_INTEGER_KEYS:
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            _fail(f"scenario_integer_invalid:{key}")
        return
    if key == "content_type":
        if not isinstance(value, str):
            _fail("scenario_content_type_invalid")
        return
    if key == "durable_failure_code":
        if value is not None and value not in REASON_OUTCOMES:
            _fail("scenario_durable_failure_code_invalid")
        return
    if key == "invite_status":
        if value not in {"expired", "invalid", "valid"}:
            _fail("scenario_invite_status_invalid")
        return
    if key == "persistence_failure":
        if value not in {
            None,
            "artifact_record_failed",
            "artifact_upload_failed",
            "event_persist_failed",
            "invalid_state_transition",
            "receipt_persist_failed",
        }:
            _fail("scenario_persistence_failure_invalid")
        return
    if key == "raw_body_mode":
        if value not in {"duplicate_keys", "malformed", "valid"}:
            _fail("scenario_raw_body_mode_invalid")
        return
    if key == "run_status":
        if value not in {"cancelled", "failed", "queued", "running", "succeeded"}:
            _fail("scenario_run_status_invalid")
        return
    _fail(f"scenario_unknown_key:{key}")


def validate_static_scenario(value: Any) -> dict[str, Any]:
    scenario = _expect_dict(value, "scenario_not_object")
    _expect_exact_keys(scenario, SCENARIO_KEYS, "scenario_keys_mismatch")
    for key, item in scenario.items():
        _validate_scenario_value(key, item)
    return scenario


def apply_scenario_patches(
    base: dict[str, Any], value: Any, *, case_id: str
) -> dict[str, Any]:
    patches = _expect_list(value, f"scenario_patches_not_array:{case_id}")
    if not patches:
        _fail(f"scenario_patches_empty:{case_id}")
    candidate = dict(base)
    seen: set[str] = set()
    for raw_patch in patches:
        patch = _expect_dict(raw_patch, f"scenario_patch_not_object:{case_id}")
        _expect_exact_keys(patch, {"path", "value"}, f"scenario_patch_keys_mismatch:{case_id}")
        path = _expect_string(patch["path"], f"scenario_patch_path_invalid:{case_id}")
        if path not in SCENARIO_KEYS:
            _fail(f"scenario_patch_path_unknown:{case_id}")
        if path in seen:
            _fail(f"scenario_patch_path_duplicate:{case_id}")
        _validate_scenario_value(path, patch["value"])
        if patch["value"] == base[path]:
            _fail(f"scenario_patch_noop:{case_id}")
        candidate[path] = patch["value"]
        seen.add(path)
    return validate_static_scenario(candidate)


def _api_outcome(reason: str) -> tuple[int, str, str, None]:
    http, verdict = REASON_OUTCOMES[reason]
    return http, verdict, reason, None


def evaluate_static_scenario(
    scenario: dict[str, Any],
) -> tuple[int | None, str | None, str | None, str | None]:
    """Compute an outcome from observations without reading fixture expectations."""

    scenario = validate_static_scenario(scenario)

    # Contract final safety assertions override every lower-severity condition.
    if scenario["secret_exposed"]:
        return _api_outcome("secret_exposure_detected")
    if scenario["provider_call_attempted"] or scenario["workflow_dispatch_attempted"]:
        return _api_outcome("provider_call_forbidden")

    # Harness-only failures are intentionally not Proof API reason codes.
    if scenario["health_side_effect_count"] > 0:
        return None, None, None, "health_side_effect_detected"
    if scenario["proof_mutation_count"] > 0:
        return None, None, None, "proof_mutation_detected"

    if scenario["raw_body_bytes"] > 16384:
        return _api_outcome("request_too_large")
    if scenario["content_type"] != "application/json":
        return _api_outcome("unsupported_media_type")
    if scenario["raw_body_mode"] != "valid":
        return _api_outcome("invalid_request")
    if not scenario["request_required_fields_present"]:
        return _api_outcome("invalid_request")
    if scenario["request_additional_fields_present"]:
        return _api_outcome("unsupported_contract")
    if not scenario["schema_supported"] or not scenario["formats_valid"]:
        return _api_outcome("unsupported_contract")

    if scenario["auth_carrier_count"] == 0:
        return _api_outcome("missing_invite_token")
    if scenario["auth_carrier_count"] != 1 or scenario["auth_carrier_malformed"]:
        return _api_outcome("invalid_request")
    if scenario["invite_status"] == "invalid":
        return _api_outcome("invalid_invite_token")
    if scenario["invite_status"] == "expired":
        return _api_outcome("invite_expired")
    if not scenario["run_access_allowed"]:
        return _api_outcome("run_access_denied")

    if not scenario["run_found"]:
        return _api_outcome("run_not_found")
    if scenario["durable_failure_code"] is not None and scenario["run_status"] != "failed":
        return _api_outcome("invalid_state_transition")
    if scenario["run_status"] in {"queued", "running"}:
        return _api_outcome("run_not_terminal")
    if scenario["run_status"] == "failed":
        durable = scenario["durable_failure_code"]
        return _api_outcome(durable if durable is not None else "run_failed")
    if scenario["run_status"] == "cancelled":
        return _api_outcome("run_cancelled")

    if not scenario["run_id_match"]:
        return _api_outcome("run_id_mismatch")
    if not scenario["run_request_id_match"]:
        return _api_outcome("run_request_id_mismatch")
    if not scenario["root_event_match"]:
        return _api_outcome("root_event_mismatch")
    if not scenario["serving_api_sha_present"]:
        return _api_outcome("missing_api_exact_sha")
    if not scenario["receipt_api_field_present"]:
        return _api_outcome("receipt_malformed")
    if not scenario["producer_revision_present"]:
        return _api_outcome("producer_revision_missing")
    if scenario["producer_image_required"] and not scenario["producer_image_present"]:
        return _api_outcome("producer_image_digest_missing")
    if not scenario["producer_image_required"] and scenario["producer_image_present"]:
        return _api_outcome("receipt_malformed")
    if scenario["producer_image_present"] and not scenario["producer_image_format_valid"]:
        return _api_outcome("receipt_malformed")
    if not scenario["api_sha_match"]:
        return _api_outcome("api_sha_mismatch")
    if not scenario["producer_sha_match"]:
        return _api_outcome("producer_sha_mismatch")
    if scenario["producer_image_required"] and not scenario["producer_image_match"]:
        return _api_outcome("producer_image_digest_mismatch")

    if scenario["persistence_failure"] is not None:
        return _api_outcome(scenario["persistence_failure"])
    if not scenario["receipt_exists"]:
        return _api_outcome("receipt_missing")
    if not scenario["receipt_well_formed"]:
        return _api_outcome("receipt_malformed")
    if scenario["receipt_count"] != 1:
        return _api_outcome("duplicate_receipt")
    if not scenario["receipt_digest_match"]:
        return _api_outcome("receipt_digest_mismatch")
    if not scenario["receipt_manifest_match"]:
        return _api_outcome("receipt_manifest_mismatch")
    if not scenario["receipt_atomic_with_terminal"]:
        return _api_outcome("invalid_state_transition")
    if not scenario["retry_content_match"]:
        return _api_outcome("finalization_conflict")

    if not scenario["event_present"]:
        return _api_outcome("event_missing")
    if not scenario["event_lineage_valid"]:
        return _api_outcome("event_lineage_mismatch")
    if not scenario["event_payload_digest_match"]:
        return _api_outcome("event_payload_digest_mismatch")
    if scenario["artifact_count"] == 0:
        return _api_outcome("artifact_missing")
    if scenario["artifact_count"] != 1:
        return _api_outcome("receipt_manifest_mismatch")
    if not scenario["storage_dependency_available"]:
        return _api_outcome("dependency_unavailable")
    if not scenario["artifact_object_exists"]:
        return _api_outcome("artifact_object_missing")
    if not scenario["stored_bytes_read"]:
        return _api_outcome("stored_bytes_unverified")
    if not scenario["artifact_path_valid"]:
        return _api_outcome("artifact_path_invalid")
    if not scenario["producer_event_field_present"]:
        return _api_outcome("receipt_malformed")
    if not scenario["producer_event_exists"]:
        return _api_outcome("event_missing")
    if not scenario["producer_event_same_run"]:
        return _api_outcome("event_lineage_mismatch")
    if not scenario["artifact_bytes_match"]:
        return _api_outcome("artifact_bytes_mismatch")
    if not scenario["artifact_digest_match"]:
        return _api_outcome("artifact_digest_mismatch")
    if not scenario["top_level_receipt_match"]:
        return _api_outcome("internal_verification_error")

    return 200, "PASS", None, None


def validate_red_catalog(value: Any) -> dict[str, int]:
    catalog = _expect_dict(value, "red_catalog_not_object")
    _expect_exact_keys(catalog, FIXTURE_ROOT_KEYS, "red_catalog_keys_mismatch")
    _contract_binding(catalog, "red_catalog_contract_binding_mismatch")
    if catalog["package_id"] != PACKAGE_ID:
        _fail("red_catalog_package_id_mismatch")
    reasons = _expect_sorted_unique_strings(
        catalog["section_9_non_pass_reason_codes"],
        "red_catalog_reason_inventory_invalid",
        non_empty=True,
    )
    if reasons != sorted(REASON_OUTCOMES) or len(reasons) != 45:
        _fail("red_catalog_reason_inventory_mismatch")
    groups = _expect_list(catalog["section_10_groups"], "section_10_groups_not_array")
    if any(isinstance(group, bool) or not isinstance(group, int) for group in groups):
        _fail("section_10_group_type_invalid")
    if groups != list(range(1, 30)):
        _fail("section_10_group_inventory_mismatch")
    harnesses = _expect_sorted_unique_strings(
        catalog["harness_codes"], "harness_code_inventory_invalid", non_empty=True
    )
    if harnesses != sorted(HARNESSES):
        _fail("harness_code_inventory_mismatch")
    scenario_model = _expect_dict(catalog["scenario_model"], "scenario_model_not_object")
    _expect_exact_keys(scenario_model, {"base", "overrides"}, "scenario_model_keys_mismatch")
    base_scenario = validate_static_scenario(scenario_model["base"])
    if evaluate_static_scenario(base_scenario) != (200, "PASS", None, None):
        _fail("base_scenario_not_satisfiable")
    overrides = _expect_dict(scenario_model["overrides"], "scenario_overrides_not_object")
    cases = _expect_list(catalog["cases"], "red_cases_not_array")
    if not cases:
        _fail("red_cases_empty")
    case_ids: list[str] = []
    covered_groups: set[int] = set()
    covered_reasons: set[str] = set()
    covered_harnesses: set[str] = set()
    for raw_case in cases:
        case = _expect_dict(raw_case, "red_case_not_object")
        _expect_exact_keys(case, CASE_KEYS, "red_case_keys_mismatch")
        case_id = _expect_string(case["case_id"], "case_id_invalid")
        match = re.fullmatch(r"red_([0-9]{2})_[a-z0-9_]+", case_id)
        if not match:
            _fail("case_id_invalid")
        group = _expect_int(case["section_10_group"], "case_group_invalid")
        if group != int(match.group(1)) or group not in range(1, 30):
            _fail("case_id_group_mismatch")
        if case["coverage_level"] != "static_model_executed":
            _fail("static_case_not_model_executed")
        if case["expected_proof_accepted"] is not False:
            _fail("red_case_must_not_accept_proof")
        if case["input_kind"] not in {
            "artifact",
            "auth",
            "event",
            "finalization",
            "raw_http",
            "receipt",
            "request",
            "revision",
            "run",
            "safety",
            "side_effect",
        }:
            _fail("case_input_kind_invalid")
        _expect_string(case["mutation"], "case_mutation_invalid")
        if case_id not in overrides:
            _fail(f"scenario_override_missing:{case_id}")
        scenario = apply_scenario_patches(base_scenario, overrides[case_id], case_id=case_id)
        actual = evaluate_static_scenario(scenario)
        expected = (
            case["expected_http"],
            case["expected_verdict"],
            case["expected_reason_code"],
            case["expected_harness_code"],
        )
        if actual != expected:
            _fail(f"case_expected_outcome_mismatch:{case_id}")
        http, verdict, reason, harness = actual
        if harness is None:
            _expect_int(http, "case_http_invalid")
            _expect_string(verdict, "case_verdict_invalid")
            _expect_string(reason, "case_reason_invalid")
            covered_reasons.add(reason)
        else:
            if any(value is not None for value in (http, verdict, reason)):
                _fail("harness_case_mixed_with_api_outcome")
            covered_harnesses.add(harness)
        case_ids.append(case_id)
        covered_groups.add(group)
    if case_ids != sorted(set(case_ids)):
        _fail("red_case_ids_not_sorted_unique")
    if set(overrides) != set(case_ids):
        _fail("scenario_override_inventory_mismatch")
    if covered_groups != set(range(1, 30)):
        _fail("section_10_case_coverage_incomplete")
    if covered_reasons != set(REASON_OUTCOMES):
        _fail("section_9_case_coverage_incomplete")
    if covered_harnesses != HARNESSES:
        _fail("harness_case_coverage_incomplete")
    return {
        "declared_negative_cases": len(cases),
        "executed_static_model_negative_cases": len(cases),
        "reason_codes": len(covered_reasons),
        "section_10_groups": len(covered_groups),
        "harness_codes": len(covered_harnesses),
    }


def _expect_mutation_failure(action: Callable[[], None], expected_prefix: str) -> None:
    try:
        action()
    except PackageError as exc:
        if not str(exc).startswith(expected_prefix):
            _fail("mutation_kill_wrong_failure")
        return
    _fail("mutation_survived")


def run_mutation_kills(schema: dict[str, Any], positive: dict[str, Any], red: dict[str, Any]) -> int:
    kills = 0

    mutated_schema = copy.deepcopy(schema)
    mutated_schema["$defs"]["fixture_case"]["additionalProperties"] = True
    _expect_mutation_failure(lambda: validate_schema(mutated_schema), "schema_object_not_closed")
    kills += 1

    mutated_schema = copy.deepcopy(schema)
    mutated_schema["$defs"]["reason_code"]["enum"].append("unknown_reason")
    _expect_mutation_failure(lambda: validate_schema(mutated_schema), "reason_schema")
    kills += 1

    mutated_schema = copy.deepcopy(schema)
    del mutated_schema["$defs"]["receipt"]["allOf"]
    _expect_mutation_failure(
        lambda: validate_schema(mutated_schema), "receipt_profile_conditional_mismatch"
    )
    kills += 1

    mutated_red = copy.deepcopy(red)
    mutated_red["cases"] = [
        case
        for case in mutated_red["cases"]
        if case["case_id"] != "red_15_storage_dependency_unavailable"
    ]
    _expect_mutation_failure(
        lambda: validate_red_catalog(mutated_red), "scenario_override_inventory_mismatch"
    )
    kills += 1

    mutated_red = copy.deepcopy(red)
    mutated_red["cases"][1]["case_id"] = mutated_red["cases"][0]["case_id"]
    _expect_mutation_failure(
        lambda: validate_red_catalog(mutated_red), "red_case_ids_not_sorted_unique"
    )
    kills += 1

    mutated_red = copy.deepcopy(red)
    mutated_red["cases"][0]["expected_verdict"] = "PASS"
    _expect_mutation_failure(lambda: validate_red_catalog(mutated_red), "case_expected_outcome")
    kills += 1

    mutated_red = copy.deepcopy(red)
    mutated_red["scenario_model"]["overrides"]["red_01_duplicate_json_key"] = [
        {"path": "raw_body_bytes", "value": 16385}
    ]
    _expect_mutation_failure(lambda: validate_red_catalog(mutated_red), "case_expected_outcome")
    kills += 1

    mutated_positive = copy.deepcopy(positive)
    mutated_positive["controls"]["mock_profile"]["response"]["receipt"][
        "receipt_sha256"
    ] = "0" * 64
    _expect_mutation_failure(
        lambda: validate_positive_catalog(mutated_positive), "receipt_test_vector_digest_mismatch"
    )
    kills += 1

    _expect_mutation_failure(
        lambda: strict_loads('{"case_id":"a","case_id":"b"}'), "duplicate_json_key"
    )
    kills += 1

    return kills


def validate_static_package(repo_root: Path) -> dict[str, Any]:
    validate_contract_hash(repo_root)
    validate_schema_hash(repo_root)
    schema = _expect_dict(_load_json(repo_root, SCHEMA_PATH), "schema_root_not_object")
    positive = _expect_dict(
        _load_json(repo_root, PASS_FIXTURE_PATH), "positive_catalog_not_object"
    )
    red = _expect_dict(_load_json(repo_root, RED_FIXTURE_PATH), "red_catalog_not_object")
    validate_schema(schema)
    validate_positive_catalog(positive)
    coverage = validate_red_catalog(red)
    mutation_kills = run_mutation_kills(schema, positive, red)
    return {
        "contract_sha256": CONTRACT_SHA256,
        "declared_negative_cases": coverage["declared_negative_cases"],
        "executed_runtime_negative_cases": 0,
        "executed_static_model_negative_cases": coverage[
            "executed_static_model_negative_cases"
        ],
        "harness_codes": coverage["harness_codes"],
        "implementation_claimed": False,
        "mutation_kills": mutation_kills,
        "package_id": PACKAGE_ID,
        "provider_called": False,
        "reason_codes": coverage["reason_codes"],
        "runtime_called": False,
        "schema_sha256": SCHEMA_SHA256,
        "section_10_groups": coverage["section_10_groups"],
        "skipped": 0,
        "specified_only_cases": 0,
        "verdict": "PASS_LOCAL_STATIC_MODEL_PACKAGE_SELF_TEST_ONLY",
    }


def _strip_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    text = re.sub(r"//[^\n]*", "", text)
    text = re.sub(r"--[^\n]*", "", text)
    return text


def _optional_source(repo_root: Path, relative: str) -> str:
    rel = PurePosixPath(relative)
    if rel.is_absolute() or ".." in rel.parts:
        raise InspectionError("unsafe_optional_source_path")
    candidate = repo_root.joinpath(*rel.parts)
    if not candidate.exists():
        return ""
    return _read_text(repo_root, relative)


SOURCE_MARKER_KEYS = {
    "auth",
    "database",
    "health",
    "jcs",
    "proof",
    "smoke",
    "start_run",
}


def evaluate_source_markers(sources: dict[str, str]) -> list[str]:
    """Check only named source markers in an explicit in-memory bundle.

    Marker presence is a preflight locator, not evidence that a capability is
    executable or correct. Dead code and inert strings can satisfy this layer.
    """

    if set(sources) != SOURCE_MARKER_KEYS:
        _fail("source_marker_bundle_keys_mismatch")
    if any(not isinstance(value, str) for value in sources.values()):
        _fail("source_marker_bundle_value_invalid")

    health = _strip_comments(sources["health"])
    proof = _strip_comments(sources["proof"])
    start_run = _strip_comments(sources["start_run"])
    auth = _strip_comments(sources["auth"]) + "\n" + proof
    database = _strip_comments(sources["database"])
    jcs = _strip_comments(sources["jcs"]) + "\n" + proof
    smoke = _strip_comments(sources["smoke"])

    checks: list[tuple[str, bool]] = [
        (
            "health_route_source_marker_missing",
            bool(re.search(r"export\s+(?:async\s+)?function\s+GET\b", health)),
        ),
        (
            "proof_route_source_marker_missing",
            bool(re.search(r"export\s+(?:async\s+)?function\s+POST\b", proof)),
        ),
        (
            "proof_auth_source_markers_missing",
            all(
                token in auth
                for token in (
                    "x-taiji-invite-token",
                    "run_access_denied",
                    "invite_expired",
                    "invalid_invite_token",
                )
            )
            and "assertRunAccess" not in proof,
        ),
        (
            "upstream_identity_source_markers_missing",
            all(
                token in start_run
                for token in (
                    "run_request_id",
                    "root_event_id",
                    "api_exact_sha",
                    "evidence_profile",
                    "trigger_mode",
                )
            ),
        ),
        (
            "evidence_schema_source_markers_missing",
            all(
                token in database
                for token in (
                    "root_event_id",
                    "producer_event_id",
                    "payload_sha256",
                    "failure_code",
                )
            ),
        ),
        (
            "immutable_receipt_schema_source_markers_missing",
            all(token in database for token in ("receipt_sha256", "receipt_id"))
            and bool(re.search(r"unique\s*\([^)]*run_id", database, flags=re.IGNORECASE)),
        ),
        (
            "atomic_finalization_rpc_source_marker_missing",
            bool(re.search(r"create\s+(?:or\s+replace\s+)?function\s+[a-z0-9_]*finaliz", database, re.I)),
        ),
        (
            "rfc8785_source_markers_missing",
            "RFC 8785" in jcs and "canonical" in jcs and "receipt_sha256" in jcs,
        ),
        (
            "smoke_instrumentation_source_markers_missing",
            all(
                token in smoke
                for token in (
                    "health_dependency_call_count",
                    "proof_db_mutation_count",
                    "proof_storage_mutation_count",
                    "provider_calls",
                )
            ),
        ),
    ]
    return [name for name, satisfied in checks if not satisfied]


def source_marker_gap_inventory(repo_root: Path) -> list[str]:
    """Return named root-surface marker gaps without claiming behavior."""

    return evaluate_source_markers(
        {
            "auth": _optional_source(repo_root, "lib/proof-auth.ts"),
            "database": _optional_source(repo_root, "db/schema.sql"),
            "health": _optional_source(repo_root, "app/api/health/route.ts"),
            "jcs": _optional_source(repo_root, "lib/proof-jcs.ts"),
            "proof": _optional_source(repo_root, "app/api/proof/route.ts"),
            "smoke": _optional_source(
                repo_root, "tests/test_proof_api_runtime_smoke_v1.py"
            ),
            "start_run": _optional_source(repo_root, "app/api/start_run/route.ts"),
        }
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check the static Proof API Runtime Contract v1 RED package."
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Validate fixed schema/fixtures and built-in mutation kills without runtime access.",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="Repository root containing the fixed package paths.",
    )
    args = parser.parse_args(argv)
    if not args.self_test:
        parser.error("--self-test is required")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        summary = validate_static_package(args.repo_root)
    except PackageError as exc:
        print(
            json.dumps(
                {
                    "error_code": str(exc),
                    "package_id": PACKAGE_ID,
                    "self_test": "FAIL",
                    "verdict": "BLOCKED_STATIC_PACKAGE_MISMATCH",
                },
                separators=(",", ":"),
                sort_keys=True,
            )
        )
        return 1
    except InspectionError as exc:
        print(
            json.dumps(
                {
                    "error_code": str(exc),
                    "package_id": PACKAGE_ID,
                    "self_test": "ERROR",
                    "verdict": "BLOCKED_INSPECTION_ERROR",
                },
                separators=(",", ":"),
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2
    print(
        json.dumps(
            {"self_test": "PASS", **summary},
            separators=(",", ":"),
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

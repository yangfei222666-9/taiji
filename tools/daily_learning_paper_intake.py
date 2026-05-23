#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
SCOPE = "daily_learning_paper_intake"
MODE = "learning_only_observe_only"
DEFAULT_RUN_PREFIX = "daily_learning_paper_intake"
ARXIV_API_URL = "https://export.arxiv.org/api/query"

TAIJIOS_CATEGORIES = [
    "Evidence Kernel",
    "Product Spine",
    "Local 120B assistant",
    "Operator Toolchain",
    "Physical AI Sandbox",
    "SpaceOps Simulation Kernel",
    "Archive / Ignore",
]

DEFAULT_QUERIES = [
    "all:AI AND all:agent",
    "all:tool AND all:use AND all:agent",
    "all:workflow AND all:verification",
    "all:robotics AND all:foundation AND all:model",
    "all:space AND all:robot",
]

WILL_NOT = [
    "read_or_print_secret",
    "broker",
    "trade",
    "buy",
    "sell",
    "paper-buy",
    "judgment",
    "promote",
    "pass-to-trade",
    "treat_provider_output_as_truth",
    "treat_learning_candidate_as_system_authority",
    "stage",
    "commit",
    "push",
    "PR",
    "merge",
]

NOT_CLAIMED = [
    "repo PASS",
    "system authority",
    "runtime Product Spine complete",
    "provider output truth",
    "provider/API ready",
    "broker ready",
    "trade/order ready",
    "paper-buy ready",
    "judgment ready",
    "promotion ready",
    "pass-to-trade ready",
]

RISK_FLAGS = {
    "learning_only": True,
    "observe_only": True,
    "provider_output_is_truth": False,
    "learning_candidate_is_system_authority": False,
    "judgment_allowed": False,
    "promote_allowed": False,
    "paper_buy_allowed": False,
    "trade_allowed": False,
    "broker_connected": False,
    "secret_read": False,
    "secret_value_logged": False,
    "stage_commit_push_pr_merge": False,
}

SCOPE_PATHS = {
    "tools/daily_learning_paper_intake.py",
    "tests/test_daily_learning_paper_intake.py",
}

SECRETISH_NAME = re.compile(
    r"(^|[._/-])(secret|secrets|token|tokens|key|keys|credential|credentials|password|passwd|private|env)([._/-]|$)",
    flags=re.IGNORECASE,
)


@dataclass(frozen=True)
class OutputPaths:
    summary: Path
    event_flow: Path
    learning_digest: Path
    closeout: Path


def build_payload(
    *,
    repo_root: str | Path = ROOT,
    run_date: str | None = None,
    queries: list[str] | None = None,
    max_papers_per_query: int = 3,
    offline_source: str | Path | None = None,
    user_input_paths: list[str | Path] | None = None,
    user_notes: list[str] | None = None,
    skip_network: bool = False,
    source_delay_seconds: float = 3.0,
) -> dict[str, Any]:
    repo_root_path = Path(repo_root).resolve()
    date_value = run_date or datetime.now().astimezone().date().isoformat()
    now = _utc_now()
    query_list = queries or DEFAULT_QUERIES

    offline = _load_offline_source(offline_source) if offline_source else {}
    source_results: list[dict[str, Any]] = []
    papers: list[dict[str, Any]] = []

    for paper in offline.get("papers", []):
        papers.append(_normalize_paper(paper, "offline_source", date_value))

    if not skip_network:
        for index, query in enumerate(query_list):
            if index and source_delay_seconds > 0:
                time.sleep(source_delay_seconds)
            result = _fetch_arxiv(query, max_papers_per_query)
            source_results.append(result)
            for paper in result["papers"]:
                papers.append(_normalize_paper(paper, "arxiv", date_value, query=query))
    else:
        source_results.append(
            {
                "source": "arxiv",
                "status": "skipped",
                "query": None,
                "url": None,
                "count": 0,
                "error": "network_skipped_by_operator",
                "checked_at_utc": now,
            }
        )

    papers = _dedupe_papers(papers)
    user_inputs = _collect_user_inputs(user_input_paths or [], user_notes or [], offline.get("user_inputs", []), date_value)
    classified_papers = [_classify_paper(paper) for paper in papers]
    classified_inputs = [_classify_user_input(item) for item in user_inputs]
    source_errors = [source for source in source_results if source["status"] == "error"]
    blocked_stage = _blocked_stage(classified_papers, classified_inputs, source_results)
    verdict = _verdict(classified_papers, classified_inputs, source_errors, blocked_stage)
    git_state = _git_state(repo_root_path)
    relevance = _relevance_summary(classified_papers + classified_inputs)
    key_findings = _key_findings(classified_papers, classified_inputs)

    return {
        "schema_version": "0.1",
        "run_id": f"{DEFAULT_RUN_PREFIX}_{date_value.replace('-', '')}",
        "generated_at_utc": now,
        "scope": SCOPE,
        "mode": MODE,
        "date": date_value,
        "repo_root": str(repo_root_path),
        "verdict": verdict,
        "status": _status(verdict),
        "repo_pass": False,
        "repo_verdict": "PARTIAL" if git_state["dirty_count"] or git_state["staged_count"] else "NOT_CLAIMED",
        "sources_checked": source_results,
        "papers_collected": classified_papers,
        "user_inputs_received": classified_inputs,
        "key_findings": key_findings,
        "taijios_relevance": relevance,
        "risk_flags": dict(RISK_FLAGS),
        "not_claimed": NOT_CLAIMED,
        "blocked_stage": blocked_stage,
        "minimum_fix": _minimum_fix(verdict, blocked_stage, source_errors),
        "next_allowed_action": _next_allowed_action(verdict),
        "will_not": WILL_NOT,
        "boundaries": {
            "learning_only": True,
            "observe_only": True,
            "provider_output_is_truth": False,
            "judgment_allowed": False,
            "promote_allowed": False,
            "paper_buy_allowed": False,
            "trade_allowed": False,
        },
        "git": git_state,
        "staged_count": git_state["staged_count"],
        "dirty_count": git_state["dirty_count"],
        "changed_files_outside_scope_count": git_state["changed_files_outside_scope_count"],
        "changed_files_outside_scope": git_state["changed_files_outside_scope"],
        "source_error_count": len(source_errors),
        "paper_count": len(classified_papers),
        "user_input_count": len(classified_inputs),
    }


def write_run(payload: dict[str, Any], output_dir: str | Path) -> OutputPaths:
    output_dir_path = Path(output_dir).resolve()
    output_dir_path.mkdir(parents=True, exist_ok=True)
    paths = OutputPaths(
        summary=output_dir_path / "summary.json",
        event_flow=output_dir_path / "event_flow.jsonl",
        learning_digest=output_dir_path / "learning_digest.md",
        closeout=output_dir_path / "closeout.md",
    )
    output_refs = {
        "summary": str(paths.summary),
        "event_flow": str(paths.event_flow),
        "learning_digest": str(paths.learning_digest),
        "closeout": str(paths.closeout),
    }
    payload = {**payload, "output_paths": output_refs}
    events = _events(payload, output_refs)
    _write_json(paths.summary, payload)
    _write_jsonl(paths.event_flow, events)
    paths.learning_digest.write_text(_learning_digest(payload), encoding="utf-8")
    paths.closeout.write_text(_closeout(payload), encoding="utf-8")
    return paths


def verify_run_dir(run_dir: str | Path) -> dict[str, Any]:
    run_path = Path(run_dir).resolve()
    summary, summary_error = _load_json(run_path / "summary.json")
    events, event_error = _load_jsonl(run_path / "event_flow.jsonl")
    digest_exists = (run_path / "learning_digest.md").exists()
    closeout_text = _read_text(run_path / "closeout.md")
    required_summary_fields = [
        "scope",
        "mode",
        "date",
        "sources_checked",
        "papers_collected",
        "user_inputs_received",
        "key_findings",
        "taijios_relevance",
        "risk_flags",
        "not_claimed",
        "blocked_stage",
        "minimum_fix",
        "next_allowed_action",
    ]
    checks = {
        "summary_json_present": (run_path / "summary.json").exists(),
        "summary_json_parses": summary_error is None,
        "event_flow_jsonl_present": (run_path / "event_flow.jsonl").exists(),
        "event_flow_jsonl_parses": event_error is None,
        "learning_digest_md_present": digest_exists,
        "closeout_md_present": (run_path / "closeout.md").exists(),
        "closeout_md_nonempty": bool(closeout_text.strip()),
        "required_summary_fields_present": all(field in summary for field in required_summary_fields),
        "risk_flags_safe": _risk_flags_safe(summary.get("risk_flags", {})),
        "repo_pass_not_claimed": summary.get("repo_pass") is False and "repo PASS" in summary.get("not_claimed", []),
        "terminal_event_present": any(event.get("event") == "scope_completed" for event in events),
    }
    errors = [name for name, ok in checks.items() if not ok]
    return {
        "ok": not errors,
        "verdict": "PASS" if not errors else "BLOCKED",
        "run_dir": str(run_path),
        "checks": checks,
        "errors": errors,
        "parse_errors": [error for error in [summary_error, event_error] if error],
        "summary_verdict": summary.get("verdict"),
        "event_count": len(events),
    }


def _fetch_arxiv(query: str, max_papers: int) -> dict[str, Any]:
    params = {
        "search_query": query,
        "start": "0",
        "max_results": str(max_papers),
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }
    url = ARXIV_API_URL + "?" + urllib.parse.urlencode(params)
    now = _utc_now()
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "TaijiOS-daily-learning-intake/0.1"})
        with urllib.request.urlopen(request, timeout=20) as response:
            body = response.read()
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return {
            "source": "arxiv",
            "status": "error",
            "query": query,
            "url": url,
            "count": 0,
            "error": f"{type(exc).__name__}: {exc}",
            "checked_at_utc": now,
            "papers": [],
        }

    papers = _parse_arxiv_atom(body)
    return {
        "source": "arxiv",
        "status": "ok",
        "query": query,
        "url": url,
        "count": len(papers),
        "error": None,
        "checked_at_utc": now,
        "papers": papers,
    }


def _parse_arxiv_atom(body: bytes) -> list[dict[str, Any]]:
    root = ET.fromstring(body)
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    papers: list[dict[str, Any]] = []
    for entry in root.findall("atom:entry", ns):
        authors = [
            _text(author.find("atom:name", ns))
            for author in entry.findall("atom:author", ns)
            if _text(author.find("atom:name", ns))
        ]
        papers.append(
            {
                "id": _text(entry.find("atom:id", ns)),
                "title": _clean_ws(_text(entry.find("atom:title", ns))),
                "summary": _clean_ws(_text(entry.find("atom:summary", ns))),
                "published": _text(entry.find("atom:published", ns)),
                "updated": _text(entry.find("atom:updated", ns)),
                "authors": authors,
                "url": _text(entry.find("atom:id", ns)),
            }
        )
    return papers


def _normalize_paper(
    paper: dict[str, Any],
    source: str,
    date_checked: str,
    *,
    query: str | None = None,
) -> dict[str, Any]:
    title = _clean_ws(str(paper.get("title", "")).strip())
    summary = _clean_ws(str(paper.get("summary", paper.get("abstract", ""))).strip())
    url = str(paper.get("url") or paper.get("id") or "").strip()
    return {
        "source": source,
        "query": query,
        "date_checked": date_checked,
        "title": title or "untitled",
        "claim": title or "untitled learning candidate",
        "evidence": {
            "url": url,
            "published": paper.get("published"),
            "updated": paper.get("updated"),
            "authors": paper.get("authors", []),
            "abstract_excerpt": summary[:700],
        },
        "uncertainty": "paper_metadata_and_abstract_only_not_reproduced",
        "possible_value_for_taijios": "",
        "taijios_relevance": [],
        "learning_only": True,
        "judgment_allowed": False,
        "promote_allowed": False,
        "paper_buy_allowed": False,
        "trade_allowed": False,
        "provider_output_is_truth": False,
    }


def _classify_paper(paper: dict[str, Any]) -> dict[str, Any]:
    text = f"{paper.get('title', '')} {paper.get('evidence', {}).get('abstract_excerpt', '')}".lower()
    categories = _classify_text(text)
    return {
        **paper,
        "taijios_relevance": categories,
        "possible_value_for_taijios": _value_statement(categories),
    }


def _classify_user_input(item: dict[str, Any]) -> dict[str, Any]:
    text = f"{item.get('claim', '')} {item.get('evidence', '')}".lower()
    categories = _classify_text(text)
    return {
        **item,
        "taijios_relevance": categories,
        "possible_value_for_taijios": _value_statement(categories),
        "learning_only": True,
        "judgment_allowed": False,
        "promote_allowed": False,
        "paper_buy_allowed": False,
        "trade_allowed": False,
        "provider_output_is_truth": False,
    }


def _classify_text(text: str) -> list[str]:
    categories: list[str] = []
    if any(term in text for term in ["verify", "verification", "evidence", "audit", "eval", "benchmark", "safety"]):
        categories.extend(["Evidence Kernel", "Product Spine"])
    if any(term in text for term in ["event", "workflow", "runtime", "trace", "artifact", "closeout", "preflight"]):
        categories.append("Product Spine")
    if any(term in text for term in ["agent", "tool", "memory", "planner", "operator", "orchestr"]):
        categories.append("Operator Toolchain")
    if any(term in text for term in ["120b", "local model", "open model", "llm", "inference", "quantization"]):
        categories.append("Local 120B assistant")
    if any(term in text for term in ["robot", "robotics", "embodied", "physical ai", "actuator", "control"]):
        categories.append("Physical AI Sandbox")
    if any(term in text for term in ["space", "satellite", "mission", "rover", "orbital", "mars"]):
        categories.append("SpaceOps Simulation Kernel")
    ordered = [category for category in TAIJIOS_CATEGORIES if category in set(categories)]
    return ordered or ["Archive / Ignore"]


def _value_statement(categories: list[str]) -> str:
    if "Archive / Ignore" in categories and len(categories) == 1:
        return "Archive as background context until a stronger TaijiOS evidence link appears."
    return "Candidate learning input for " + ", ".join(categories) + "; requires artifact-backed review before authority changes."


def _collect_user_inputs(
    paths: list[str | Path],
    notes: list[str],
    offline_items: list[dict[str, Any]],
    date_checked: str,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for raw_path in paths:
        path = Path(raw_path).expanduser()
        path_text = str(path)
        secretish = bool(SECRETISH_NAME.search(path.name) or SECRETISH_NAME.search(path_text))
        exists = path.exists()
        stat = path.stat() if exists and not secretish else None
        items.append(
            {
                "source": "user_input_path",
                "date_checked": date_checked,
                "claim": path_text,
                "evidence": {
                    "path": path_text,
                    "exists": exists,
                    "read_content": False,
                    "secretish_name_blocked": secretish,
                    "size_bytes": stat.st_size if stat else None,
                },
                "uncertainty": "content_not_read_to_preserve_secret_boundary",
            }
        )
    for note in notes:
        items.append(
            {
                "source": "user_note",
                "date_checked": date_checked,
                "claim": note[:240],
                "evidence": "user_supplied_note_redacted_to_first_240_chars",
                "uncertainty": "user_supplied_unverified_note",
            }
        )
    for item in offline_items:
        items.append(
            {
                "source": item.get("source", "offline_user_input"),
                "date_checked": item.get("date_checked", date_checked),
                "claim": item.get("claim", "offline user input"),
                "evidence": item.get("evidence", {}),
                "uncertainty": item.get("uncertainty", "offline_fixture_or_user_supplied"),
            }
        )
    return items


def _events(payload: dict[str, Any], output_refs: dict[str, str]) -> list[dict[str, Any]]:
    now = payload["generated_at_utc"]
    status = payload["status"]
    base = {
        "ts": now,
        "scope": payload["scope"],
        "status": status,
        "input_refs": [source.get("url") for source in payload["sources_checked"] if source.get("url")],
        "output_refs": list(output_refs.values()),
        "boundary_flags": dict(RISK_FLAGS),
        "not_claimed": payload["not_claimed"],
    }
    event_specs = [
        ("scope_started", "Boot Preflight", {"will_not": WILL_NOT}),
        (
            "boot_preflight_completed",
            "Boot Preflight",
            {
                "repo_root": payload["repo_root"],
                "mode": payload["mode"],
                "learning_only": True,
            },
        ),
        (
            "sources_collected",
            "EventFlow",
            {
                "source_count": len(payload["sources_checked"]),
                "paper_count": payload["paper_count"],
                "source_error_count": payload["source_error_count"],
            },
        ),
        (
            "learning_candidates_classified",
            "Scope Isolation",
            {
                "taijios_relevance": payload["taijios_relevance"],
                "user_input_count": payload["user_input_count"],
            },
        ),
        (
            "artifact_memory_written",
            "Artifact Memory",
            {
                "artifact_memory_form": "learning_digest.md",
                "learning_digest": output_refs["learning_digest"],
            },
        ),
        ("event_flow_written", "EventFlow", {"event_flow": output_refs["event_flow"]}),
        (
            "verifier_completed",
            "Closeout",
            {
                "risk_flags_safe": _risk_flags_safe(payload["risk_flags"]),
                "repo_pass": False,
            },
        ),
        ("closeout_written", "Closeout", {"closeout": output_refs["closeout"]}),
        (
            "scope_completed",
            "Closeout",
            {
                "verdict": payload["verdict"],
                "blocked_stage": payload["blocked_stage"],
                "next_allowed_action": payload["next_allowed_action"],
            },
        ),
    ]
    return [
        {
            **base,
            "event": event_name,
            "product_spine_component": component,
            "evidence": {"sequence_index": index, **evidence},
        }
        for index, (event_name, component, evidence) in enumerate(event_specs)
    ]


def _learning_digest(payload: dict[str, Any]) -> str:
    paper_lines = []
    for index, paper in enumerate(payload["papers_collected"], start=1):
        evidence = paper.get("evidence", {})
        paper_lines.append(
            "\n".join(
                [
                    f"{index}. {paper['title']}",
                    f"   - source: {paper['source']}",
                    f"   - url: {evidence.get('url') or 'unavailable'}",
                    f"   - date_checked: {paper['date_checked']}",
                    f"   - taijios_relevance: {', '.join(paper['taijios_relevance'])}",
                    f"   - uncertainty: {paper['uncertainty']}",
                    f"   - value: {paper['possible_value_for_taijios']}",
                ]
            )
        )
    if not paper_lines:
        paper_lines.append("No papers collected.")

    input_lines = []
    for index, item in enumerate(payload["user_inputs_received"], start=1):
        input_lines.append(
            f"{index}. {item['claim']} | relevance={', '.join(item['taijios_relevance'])} | uncertainty={item['uncertainty']}"
        )
    if not input_lines:
        input_lines.append("No user inputs supplied.")

    return "\n".join(
        [
            "# TaijiOS Daily Learning Paper Intake",
            "",
            f"verdict: `{payload['verdict']}`",
            f"scope: `{payload['scope']}`",
            f"mode: `{payload['mode']}`",
            f"date: `{payload['date']}`",
            "",
            "## Key Findings",
            "",
            *[f"- {finding}" for finding in payload["key_findings"]],
            "",
            "## Papers Collected",
            "",
            *paper_lines,
            "",
            "## User Inputs Received",
            "",
            *input_lines,
            "",
            "## Boundaries",
            "",
            "- learning_only: `true`",
            "- provider_output_is_truth: `false`",
            "- judgment_allowed: `false`",
            "- promote_allowed: `false`",
            "- paper_buy_allowed: `false`",
            "- trade_allowed: `false`",
            "- repo_pass: `false`",
            "",
        ]
    )


def _closeout(payload: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Daily Learning Paper Intake Closeout",
            "",
            f"verdict: `{payload['verdict']}`",
            f"scope: `{payload['scope']}`",
            f"mode: `{payload['mode']}`",
            f"repo_root: `{payload['repo_root']}`",
            f"date: `{payload['date']}`",
            "",
            "## Artifacts",
            "",
            "- `summary.json`",
            "- `event_flow.jsonl`",
            "- `learning_digest.md`",
            "- `closeout.md`",
            "",
            "## Verification",
            "",
            f"- papers_collected: `{payload['paper_count']}`",
            f"- user_inputs_received: `{payload['user_input_count']}`",
            f"- source_error_count: `{payload['source_error_count']}`",
            f"- risk_flags_safe: `{_risk_flags_safe(payload['risk_flags'])}`",
            f"- staged_count: `{payload['git']['staged_count']}`",
            f"- dirty_count: `{payload['git']['dirty_count']}`",
            "- repo_pass: `false`",
            "",
            "## Git State",
            "",
            f"- branch: `{payload['git']['branch']}`",
            f"- head: `{payload['git']['head']}`",
            f"- changed_files_outside_scope_count: `{payload['git']['changed_files_outside_scope_count']}`",
            "- repo_pass: `false`",
            "",
            "## Boundaries Kept",
            "",
            "- provider output truth: `false`",
            "- learning candidate authority: `false`",
            "- judgment_allowed: `false`",
            "- promote_allowed: `false`",
            "- paper_buy_allowed: `false`",
            "- trade_allowed: `false`",
            "- broker_connected: `false`",
            "- secret_read: `false`",
            "",
            "## Not Claimed",
            "",
            *[f"- {claim}" for claim in payload["not_claimed"]],
            "",
            "## Stop State",
            "",
            f"- blocked_stage: `{payload['blocked_stage']}`",
            f"- minimum_fix: `{payload['minimum_fix']}`",
            f"- next_allowed_action: `{payload['next_allowed_action']}`",
            "",
        ]
    )


def _load_offline_source(path: str | Path | None) -> dict[str, Any]:
    if not path:
        return {}
    source_path = Path(path).resolve()
    data = json.loads(source_path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return {"papers": data, "user_inputs": []}
    if isinstance(data, dict):
        return data
    raise ValueError("offline source must be a JSON object or list")


def _dedupe_papers(papers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for paper in papers:
        key = (paper.get("evidence", {}).get("url") or paper.get("title") or "").lower()
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(paper)
    return deduped


def _key_findings(papers: list[dict[str, Any]], user_inputs: list[dict[str, Any]]) -> list[str]:
    findings = [
        f"Collected {len(papers)} paper learning candidates and {len(user_inputs)} user-input candidates.",
        "All candidates remain learning_only and below judgment/promote/paper-buy/trade authority.",
    ]
    top_categories = [category for category, count in _relevance_summary(papers + user_inputs).items() if count]
    if top_categories:
        findings.append("Top TaijiOS relevance buckets: " + ", ".join(top_categories[:4]) + ".")
    return findings


def _relevance_summary(items: list[dict[str, Any]]) -> dict[str, int]:
    summary = {category: 0 for category in TAIJIOS_CATEGORIES}
    for item in items:
        for category in item.get("taijios_relevance", []):
            summary[category] += 1
    return summary


def _blocked_stage(
    papers: list[dict[str, Any]],
    user_inputs: list[dict[str, Any]],
    sources: list[dict[str, Any]],
) -> str | None:
    if papers or user_inputs:
        return None
    if sources and all(source.get("status") in {"error", "skipped"} for source in sources):
        return "source_collection"
    return "input_collection"


def _verdict(
    papers: list[dict[str, Any]],
    user_inputs: list[dict[str, Any]],
    source_errors: list[dict[str, Any]],
    blocked_stage: str | None,
) -> str:
    if blocked_stage:
        return "BLOCKED"
    if source_errors:
        return "PARTIAL"
    if papers or user_inputs:
        return "PASS"
    return "PENDING"


def _status(verdict: str) -> str:
    return {
        "PASS": "ok",
        "PARTIAL": "partial",
        "BLOCKED": "blocked",
        "PENDING": "pending",
    }[verdict]


def _minimum_fix(verdict: str, blocked_stage: str | None, source_errors: list[dict[str, Any]]) -> str:
    if verdict == "PASS":
        return "none_for_daily_learning_scope"
    if blocked_stage == "source_collection":
        return "restore network/source access or provide an offline-source JSON file"
    if source_errors:
        return "review failed source URLs and rerun, or accept partial source coverage explicitly"
    return "provide at least one paper source or user input"


def _next_allowed_action(verdict: str) -> str:
    if verdict == "PASS":
        return "review learning_digest.md and choose a separate exact-scope implementation candidate if needed"
    if verdict == "PARTIAL":
        return "repair incomplete sources or classify partial findings without promotion"
    if verdict == "BLOCKED":
        return "fix source_collection blocker and rerun in learning_only mode"
    return "run daily learning intake"


def _risk_flags_safe(flags: dict[str, Any]) -> bool:
    return (
        flags.get("learning_only") is True
        and flags.get("observe_only") is True
        and flags.get("provider_output_is_truth") is False
        and flags.get("learning_candidate_is_system_authority") is False
        and flags.get("judgment_allowed") is False
        and flags.get("promote_allowed") is False
        and flags.get("paper_buy_allowed") is False
        and flags.get("trade_allowed") is False
        and flags.get("broker_connected") is False
        and flags.get("secret_read") is False
        and flags.get("secret_value_logged") is False
    )


def _git_state(repo_root: Path) -> dict[str, Any]:
    base = {
        "git_available": False,
        "branch": "unknown",
        "head": "unknown",
        "staged_count": 0,
        "dirty_count": 0,
        "changed_files": [],
        "changed_files_outside_scope": [],
        "changed_files_outside_scope_count": 0,
    }
    try:
        subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=repo_root, check=True, capture_output=True, text=True)
        status = subprocess.run(
            ["git", "status", "--porcelain=v1", "--untracked-files=all"],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.splitlines()
    except (OSError, subprocess.CalledProcessError):
        return base

    changed_files = [_status_path(line) for line in status if line.strip()]
    staged_files = [_status_path(line) for line in status if line[:2] != "??" and line[0] != " "]
    outside_scope = [path for path in changed_files if not _within_scope(path, SCOPE_PATHS) and not path.startswith("runs/ops_check/")]
    base.update(
        {
            "git_available": True,
            "branch": _git_text(repo_root, ["branch", "--show-current"]) or "unknown",
            "head": _git_text(repo_root, ["rev-parse", "HEAD"]) or "unknown",
            "staged_count": len(staged_files),
            "dirty_count": len(changed_files),
            "changed_files": changed_files,
            "changed_files_outside_scope": outside_scope,
            "changed_files_outside_scope_count": len(outside_scope),
        }
    )
    return base


def _git_text(repo_root: Path, args: list[str]) -> str:
    try:
        result = subprocess.run(["git", *args], cwd=repo_root, check=True, capture_output=True, text=True)
    except (OSError, subprocess.CalledProcessError):
        return ""
    return result.stdout.strip()


def _status_path(line: str) -> str:
    raw = line[3:] if len(line) > 3 else line
    if " -> " in raw:
        raw = raw.split(" -> ", 1)[1]
    return raw.strip().strip('"')


def _within_scope(path: str, scope_paths: set[str]) -> bool:
    return any(path == scope or path.startswith(scope.rstrip("/") + "/") for scope in scope_paths)


def _load_json(path: Path) -> tuple[dict[str, Any], str | None]:
    if not path.exists():
        return {}, f"missing:{path}"
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except json.JSONDecodeError as exc:
        return {}, f"invalid_json:{path}:{exc}"


def _load_jsonl(path: Path) -> tuple[list[dict[str, Any]], str | None]:
    if not path.exists():
        return [], f"missing:{path}"
    events: list[dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                events.append(json.loads(line))
    except json.JSONDecodeError as exc:
        return [], f"invalid_jsonl:{path}:{exc}"
    return events, None


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, events: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n" for event in events), encoding="utf-8")


def _text(element: ET.Element | None) -> str:
    return element.text if element is not None and element.text else ""


def _clean_ws(value: str) -> str:
    return " ".join(value.split())


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _default_output_dir(repo_root: Path, run_date: str) -> Path:
    return repo_root / "runs" / "ops_check" / f"{DEFAULT_RUN_PREFIX}_{run_date.replace('-', '')}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Collect daily learning-only paper candidates and write TaijiOS evidence artifacts."
    )
    parser.add_argument("--repo-root", default=str(ROOT))
    parser.add_argument("--date", default=None, help="Run date in YYYY-MM-DD. Defaults to local date.")
    parser.add_argument("--output-dir", default=None, help="Directory for summary.json, event_flow.jsonl, learning_digest.md, closeout.md.")
    parser.add_argument("--query", action="append", default=None, help="arXiv query. Repeat to override defaults.")
    parser.add_argument("--max-papers-per-query", type=int, default=3)
    parser.add_argument("--offline-source", default=None, help="JSON object/list with papers and optional user_inputs; useful for tests.")
    parser.add_argument("--user-input", action="append", default=[], help="User-provided file path; metadata only, content is not read.")
    parser.add_argument("--user-note", action="append", default=[], help="User-provided note string; stored as unverified learning input.")
    parser.add_argument("--skip-network", action="store_true", help="Do not call arXiv; use offline/user inputs only.")
    parser.add_argument("--source-delay-seconds", type=float, default=3.0, help="Delay between live source queries.")
    parser.add_argument("--verify-only", action="store_true", help="Only verify an existing output directory.")
    args = parser.parse_args(argv)

    repo_root = Path(args.repo_root).resolve()
    run_date = args.date or datetime.now().astimezone().date().isoformat()
    output_dir = Path(args.output_dir).resolve() if args.output_dir else _default_output_dir(repo_root, run_date)

    if args.verify_only:
        payload = verify_run_dir(output_dir)
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if payload["ok"] else 1

    payload = build_payload(
        repo_root=repo_root,
        run_date=run_date,
        queries=args.query,
        max_papers_per_query=args.max_papers_per_query,
        offline_source=args.offline_source,
        user_input_paths=args.user_input,
        user_notes=args.user_note,
        skip_network=args.skip_network,
        source_delay_seconds=args.source_delay_seconds,
    )
    paths = write_run(payload, output_dir)
    verification = verify_run_dir(output_dir)
    result = {
        "verdict": payload["verdict"],
        "run_dir": str(output_dir),
        "summary": str(paths.summary),
        "event_flow": str(paths.event_flow),
        "learning_digest": str(paths.learning_digest),
        "closeout": str(paths.closeout),
        "verification_ok": verification["ok"],
        "repo_pass": False,
        "not_claimed": NOT_CLAIMED,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if verification["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

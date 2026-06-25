#!/usr/bin/env python3
"""Validate the static Agent Reliability Demo V0.

This script intentionally validates the demo as an explanatory static artifact.
It does not call providers, open a browser, deploy, or promote the demo to
runtime evidence.
"""

from __future__ import annotations

from html.parser import HTMLParser
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
DEMO_DIR = REPO_ROOT / "demo" / "agent-reliability-gate"
EXPECTED_VERDICTS = {
    "zero-fixture-false-pass": "REJECT",
    "local-pass-remote-unknown": "REJECT",
    "provider-output-candidate": "REJECT",
    "bounded-pass": "PASS",
}
REQUIRED_FILES = {
    "index.html",
    "style.css",
    "app.js",
}
FORBIDDEN_NETWORK_PATTERNS = {
    r"\bfetch\s*\(": "fetch call",
    r"\bXMLHttpRequest\b": "XMLHttpRequest",
    r"\bnavigator\.sendBeacon\b": "sendBeacon",
    r"\bWebSocket\s*\(": "WebSocket",
    r"\bEventSource\s*\(": "EventSource",
    r"\bAuthorization\b": "Authorization header",
    r"\bapi[_-]?key\b": "API key reference",
    r"\bZHIPUAI_API_KEY\b": "provider API key env",
    r"\bOPENAI_API_KEY\b": "provider API key env",
}


class DemoHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.refs: list[str] = []
        self.text_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = dict(attrs)
        if tag == "link" and attr.get("href"):
            self.refs.append(attr["href"] or "")
        if tag == "script" and attr.get("src"):
            self.refs.append(attr["src"] or "")
        if tag == "a" and attr.get("href"):
            self.refs.append(attr["href"] or "")

    def handle_data(self, data: str) -> None:
        self.text_parts.append(data)


def fail(reason: str) -> None:
    print(f"verdict=FAIL reason={reason}")
    raise SystemExit(1)


def resolve_demo_ref(ref: str) -> Path | None:
    if ref.startswith(("http://", "https://", "mailto:", "#")):
        return None
    return (DEMO_DIR / ref).resolve()


def check_required_files() -> None:
    if not DEMO_DIR.is_dir():
        fail(f"missing_demo_dir path={DEMO_DIR}")
    missing = [name for name in REQUIRED_FILES if not (DEMO_DIR / name).is_file()]
    if missing:
        fail(f"missing_files files={','.join(sorted(missing))}")
    print("required_files=PASS")


def check_html_refs_and_boundary() -> None:
    parser = DemoHTMLParser()
    parser.feed((DEMO_DIR / "index.html").read_text(encoding="utf-8"))
    missing: list[str] = []
    for ref in parser.refs:
        target = resolve_demo_ref(ref)
        if target and not target.exists():
            missing.append(ref)
    if missing:
        fail(f"missing_html_refs refs={','.join(missing)}")

    visible_text = " ".join(part.strip() for part in parser.text_parts if part.strip())
    required_text = "Static explanatory demo, not runtime evidence."
    if required_text not in visible_text:
        fail("missing_boundary_banner")
    print("html_refs=PASS")
    print("boundary_banner=PASS")


def check_no_network_or_secret_hooks() -> None:
    findings: list[str] = []
    for path in sorted(DEMO_DIR.glob("*")):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for pattern, label in FORBIDDEN_NETWORK_PATTERNS.items():
            if re.search(pattern, text, flags=re.IGNORECASE):
                findings.append(f"{path.name}:{label}")
    if findings:
        fail(f"forbidden_network_or_secret_hooks findings={','.join(findings)}")
    print("network_and_secret_hooks=PASS")


def check_js_syntax() -> None:
    node = shutil.which("node")
    if not node:
        fail("node_not_found")
    subprocess.run(
        [node, "--check", str(DEMO_DIR / "app.js")],
        check=True,
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    print("js_syntax=PASS")


def check_case_verdicts() -> None:
    node = shutil.which("node")
    if not node:
        fail("node_not_found")

    harness = r"""
const fs = require("fs");
const vm = require("vm");
const source = fs.readFileSync(process.argv[1], "utf8");

function fakeElement() {
  return {
    innerHTML: "",
    textContent: "",
    className: "",
    dataset: {},
    addEventListener: function () {},
    closest: function () { return null; }
  };
}

const elements = {};
const context = {
  console,
  document: {
    querySelector: function (selector) {
      if (!elements[selector]) {
        elements[selector] = fakeElement();
      }
      return elements[selector];
    }
  }
};

const result = vm.runInNewContext(
  source + "\nJSON.stringify(cases.map((example) => [example.id, classify(example).verdict]));",
  context,
  { timeout: 1000 }
);
console.log(result);
"""
    completed = subprocess.run(
        [node, "-e", harness, str(DEMO_DIR / "app.js")],
        check=True,
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    actual = dict(json.loads(completed.stdout))
    if actual != EXPECTED_VERDICTS:
        fail(
            "verdict_mismatch "
            f"expected={json.dumps(EXPECTED_VERDICTS, sort_keys=True)} "
            f"actual={json.dumps(actual, sort_keys=True)}"
        )
    print("case_verdicts=PASS")


def main() -> int:
    check_required_files()
    check_html_refs_and_boundary()
    check_no_network_or_secret_hooks()
    check_js_syntax()
    check_case_verdicts()
    print("verdict=PASS")
    print("provider_called=false")
    print("canonical_truth_promoted=false")
    return 0


if __name__ == "__main__":
    sys.exit(main())

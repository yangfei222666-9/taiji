from pathlib import Path
import os
import re
import subprocess
import sys
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


MARKDOWN_LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def test_reviewer_start_relative_links_resolve():
    doc_path = ROOT / "docs" / "START_HERE_FOR_REVIEWERS.md"
    text = doc_path.read_text(encoding="utf-8")
    targets = MARKDOWN_LINK_RE.findall(text)
    relative_targets = {
        target
        for target in targets
        if not target.startswith("#") and not urlsplit(target).scheme
    }

    assert relative_targets == {
        "portfolio/agent-reliability-proof.md",
        "proof_index.json",
        "research/codex-reliability-gap-map-01.md",
    }
    assert "pip install -e ." not in text

    for target in relative_targets:
        resolved = (doc_path.parent / target).resolve()
        try:
            resolved.relative_to(ROOT.resolve())
        except ValueError as exc:
            raise AssertionError(f"reviewer link escapes repository: {target}") from exc
        assert resolved.is_file(), f"reviewer link does not resolve: {target}"


def test_static_demo_uses_public_absolute_proof_links():
    demo = read("demo/agent-reliability-gate/index.html")

    assert "../../docs/" not in demo
    assert (
        'href="https://github.com/yangfei222666-9/taiji/blob/main/'
        'docs/portfolio/agent-reliability-proof.md"'
    ) in demo
    assert (
        'href="https://github.com/yangfei222666-9/taiji/blob/main/'
        'docs/research/codex-reliability-gap-map-01.md"'
    ) in demo
    assert (
        'href="https://github.com/yangfei222666-9/taiji/blob/main/'
        'docs/START_HERE_FOR_REVIEWERS.md"'
    ) in demo


def test_readme_does_not_publish_missing_github_learning_package():
    readme = read("README.md")

    assert "python -m github_learning" not in readme
    assert "├── github_learning/" not in readme
    assert "| `github_learning/` |" not in readme
    assert "python3 -m learning.analyze_report" not in readme
    assert "| `aios/learning/` |" not in readme
    assert "├── aios/learning/" not in readme


def test_architecture_points_to_shipped_learning_files():
    architecture = read("docs/architecture.md")

    assert "github_learning/discoverer.py" not in architecture
    assert "github_learning/analyzer.py" not in architecture
    assert "github_learning/digester.py" not in architecture
    assert "github_learning/gate.py" not in architecture
    assert "github_learning/solidifier.py" not in architecture
    assert "aios/learning/analyze.py" not in architecture
    assert "aios/learning/baseline.py" not in architecture


def test_packaging_does_not_include_missing_package_glob():
    pyproject = read("pyproject.toml")

    assert '"github_learning*"' not in pyproject


def test_e2e_live_deepseek_phase_is_explicitly_optional():
    e2e = read("test_e2e_full_pipeline.py")

    assert "LIVE_DEEPSEEK_ENABLED" in e2e
    assert "未设置 DEEPSEEK_API_KEY" in e2e
    assert "不能宣称完整 live e2e" in e2e
    assert "YOUR_DEEPSEEK_API_KEY" not in e2e

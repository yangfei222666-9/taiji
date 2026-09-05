from pathlib import Path
import os
import re
import subprocess
import sys
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_reviewer_entry_local_links_resolve_relative_to_document():
    entry = ROOT / "docs/START_HERE_FOR_REVIEWERS.md"
    targets = re.findall(r"\[[^\]]+\]\(([^)]+)\)", entry.read_text(encoding="utf-8"))
    local_paths = [
        unquote(link.path)
        for target in targets
        if not (link := urlsplit(target)).scheme and not link.netloc and link.path
    ]

    assert local_paths, "Reviewer entry must link to local proof material"
    missing = [path for path in local_paths if not (entry.parent / path).is_file()]
    assert not missing, f"Broken reviewer links relative to docs/: {missing}"


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

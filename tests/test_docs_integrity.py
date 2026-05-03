from pathlib import Path
import os
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_readme_does_not_publish_missing_github_learning_package():
    readme = read("README.md")

    assert "python -m github_learning" not in readme
    assert "├── github_learning/" not in readme
    assert "| `github_learning/` |" not in readme
    assert "aios/learning/" in readme


def test_architecture_points_to_shipped_learning_files():
    architecture = read("docs/architecture.md")

    assert "github_learning/discoverer.py" not in architecture
    assert "github_learning/analyzer.py" not in architecture
    assert "github_learning/digester.py" not in architecture
    assert "github_learning/gate.py" not in architecture
    assert "github_learning/solidifier.py" not in architecture
    assert "aios/learning/analyze.py" in architecture
    assert "aios/learning/baseline.py" in architecture


def test_packaging_does_not_include_missing_package_glob():
    pyproject = read("pyproject.toml")

    assert '"github_learning*"' not in pyproject


def test_e2e_live_deepseek_phase_is_explicitly_optional():
    e2e = read("test_e2e_full_pipeline.py")

    assert "LIVE_DEEPSEEK_ENABLED" in e2e
    assert "未设置 DEEPSEEK_API_KEY" in e2e
    assert "不能宣称完整 live e2e" in e2e
    assert "YOUR_DEEPSEEK_API_KEY" not in e2e


def test_learning_report_modules_import_without_circular_dependency():
    env = {**os.environ, "PYTHONPATH": str(ROOT / "aios")}
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import learning.analyze, learning.analyze_report, learning.baseline",
        ],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        timeout=10,
    )

    assert result.returncode == 0, result.stderr

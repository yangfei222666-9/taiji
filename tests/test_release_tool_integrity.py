from pathlib import Path


WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "release.yml"


def test_release_tools_are_version_pinned_and_verified_before_extraction():
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "syft/main/install.sh" not in workflow
    assert "releases/latest" not in workflow
    assert 'SYFT_VERSION: "1.51.0"' in workflow
    assert 'SYFT_SHA256: "2a2e837a2c8d59ec9af5472ee22d3b04ee463c4e44476ecf993fd1e5ab6ebc7f"' in workflow
    assert 'CRANE_VERSION: "0.22.0"' in workflow
    assert 'CRANE_SHA256: "edb74d53fad9a596860f59d1c5d04a43dfb5f441dc71f57060dd0bf39483c833"' in workflow

    syft_download = workflow.index('releases/download/v${SYFT_VERSION}/${SYFT_ARCHIVE}')
    syft_verify = workflow.index('echo "${SYFT_SHA256}  ${SYFT_ARCHIVE}" | sha256sum -c -')
    syft_extract = workflow.index('tar -xzf "${SYFT_ARCHIVE}" syft')
    assert syft_download < syft_verify < syft_extract

    crane_download = workflow.index('releases/download/v${CRANE_VERSION}/${CRANE_ARCHIVE}')
    crane_verify = workflow.index('echo "${CRANE_SHA256}  ${CRANE_ARCHIVE}" | sha256sum -c -')
    crane_extract = workflow.index('tar -xzf "${CRANE_ARCHIVE}" crane')
    assert crane_download < crane_verify < crane_extract

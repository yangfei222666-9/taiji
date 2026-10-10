from aios.core import safe_click


def test_window_binding_rejects_empty_foreground_title(monkeypatch):
    monkeypatch.setattr(safe_click, "_get_foreground_window_title", lambda: "")
    target = safe_click.ClickTarget(
        text="Overview",
        bbox=(200, 200, 260, 240),
        source_window="Sensitive App",
        target_type="content_text",
        confidence=0.99,
    )

    result = safe_click.gate_1_window_binding(target)

    assert result["passed"] is False
    assert result["reason"]
    assert result["current_window"] == ""

from pathlib import Path

import pytest

from aios.agent_system.task_queue import TaskQueue, TaskRecord


def test_save_all_preserves_existing_queue_when_replace_fails(tmp_path, monkeypatch):
    queue_path = tmp_path / "task_queue.jsonl"
    queue = TaskQueue(str(queue_path))
    original = '{"task_id":"original","status":"queued"}\n'
    queue_path.write_text(original, encoding="utf-8")

    def fail_replace(self, target):
        raise OSError("simulated replace failure")

    monkeypatch.setattr(Path, "replace", fail_replace)

    with pytest.raises(OSError, match="simulated replace failure"):
        queue._save_all({
            "replacement": TaskRecord("replacement", {}, "queued", 0, 1),
        })

    assert queue_path.exists()
    assert queue_path.read_text(encoding="utf-8") == original

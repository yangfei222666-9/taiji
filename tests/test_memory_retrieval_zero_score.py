from aios.agent_system import memory_retrieval as memory


def test_query_omits_records_with_zero_token_overlap(monkeypatch):
    monkeypatch.setattr(
        memory,
        "_load",
        lambda: [
            {
                "id": "deploy-1",
                "task_type": "DEPLOY",
                "desc": "kubernetes rollout",
                "text": "restart pod",
                "outcome": "success",
            }
        ],
    )

    hits = memory.query("修复登录超时", top_k=3)

    assert hits == []

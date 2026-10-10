import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_start_run_reserves_active_slot_with_one_rpc():
    route = (ROOT / "app" / "api" / "start_run" / "route.ts").read_text(encoding="utf-8")

    assert "rpc('reserve_run_slot'" in route
    assert ".select('id', { count: 'exact', head: true })" not in route
    assert re.search(r"\.from\('runs'\)\s*\.insert\(", route) is None


def test_reserve_run_slot_serializes_count_and_insert_in_database():
    schema = (ROOT / "db" / "schema.sql").read_text(encoding="utf-8")

    function_at = schema.index("create or replace function public.reserve_run_slot")
    lock_at = schema.index("pg_advisory_xact_lock", function_at)
    count_at = schema.index("from public.runs", lock_at)
    insert_at = schema.index("insert into public.runs", count_at)
    assert function_at < lock_at < count_at < insert_at
    assert "security invoker" in schema[function_at:insert_at]
    assert "revoke all on function public.reserve_run_slot" in schema
    assert "grant execute on function public.reserve_run_slot" in schema

import json
import os
import signal
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from supabase import create_client


SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE"]
RUN_ID = os.environ.get("RUN_ID", "")
ARTIFACT_BUCKET = os.environ.get("ARTIFACT_BUCKET", "taiji-artifacts")
TIMEOUT_SECONDS = int(os.environ.get("DEMO_RUN_TIMEOUT_SECONDS", "30"))
ARTIFACT_TTL_HOURS = int(os.environ.get("ARTIFACT_TTL_HOURS", "24"))

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


class RunTimeout(Exception):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def timeout_handler(_signum, _frame):
    raise RunTimeout(f"run exceeded {TIMEOUT_SECONDS}s timeout")


def update_run(**fields):
    if not RUN_ID:
        raise RuntimeError("RUN_ID is required for run execution")
    supabase.table("runs").update(fields).eq("id", RUN_ID).execute()


def execute_run():
    started = time.time()
    update_run(status="running", progress=10, started_at=utc_now(), logs="ephemeral agent started")

    time.sleep(2)
    update_run(status="running", progress=55, logs="artifact generation started")

    result = {
        "message": "hello from ephemeral agent",
        "run_id": RUN_ID,
        "generated_at": utc_now(),
    }

    storage_path = f"runs/{RUN_ID}/result.json"
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
        json.dump(result, handle, indent=2)
        local_path = Path(handle.name)

    try:
        with local_path.open("rb") as handle:
            supabase.storage.from_(ARTIFACT_BUCKET).upload(
                storage_path,
                handle,
                file_options={
                    "content-type": "application/json",
                    "upsert": "true",
                },
            )

        size = local_path.stat().st_size
        supabase.table("run_artifacts").insert(
            {
                "run_id": RUN_ID,
                "bucket": ARTIFACT_BUCKET,
                "path": storage_path,
                "label": "result.json",
                "content_type": "application/json",
                "bytes": size,
            }
        ).execute()

        update_run(
            status="succeeded",
            progress=100,
            artifact_bucket=ARTIFACT_BUCKET,
            artifact_path=storage_path,
            artifact_url=f"storage://{ARTIFACT_BUCKET}/{storage_path}",
            logs="ephemeral agent completed",
            duration_ms=int((time.time() - started) * 1000),
            finished_at=utc_now(),
        )
    finally:
        local_path.unlink(missing_ok=True)


def cleanup_artifacts():
    cutoff = datetime.now(timezone.utc) - timedelta(hours=ARTIFACT_TTL_HOURS)
    rows = (
        supabase.table("run_artifacts")
        .select("id,bucket,path,created_at")
        .lt("created_at", cutoff.isoformat())
        .execute()
        .data
        or []
    )

    deleted = 0
    for row in rows:
        bucket = row["bucket"]
        path = row["path"]
        supabase.storage.from_(bucket).remove([path])
        supabase.table("run_artifacts").delete().eq("id", row["id"]).execute()
        deleted += 1

    print(json.dumps({"cleanup": "artifacts", "deleted": deleted, "cutoff": cutoff.isoformat()}))


def main():
    if os.environ.get("CLEANUP_MODE") == "artifacts":
        cleanup_artifacts()
        return

    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(TIMEOUT_SECONDS)
    try:
        execute_run()
    except Exception as exc:
        if RUN_ID:
            update_run(
                status="failed",
                progress=100,
                error=str(exc),
                logs=f"ephemeral agent failed: {exc}",
                finished_at=utc_now(),
            )
        raise
    finally:
        signal.alarm(0)


if __name__ == "__main__":
    main()

"""
TaijiOS LLM Gateway — uvicorn entrypoint.

Usage:
    python -m aios.gateway
    # or
    uvicorn aios.gateway.app:app --host 127.0.0.1 --port 9200
"""
import os
import uvicorn


def main():
    host = os.getenv("TAIJIOS_GATEWAY_HOST", "127.0.0.1")
    port = int(os.getenv("TAIJIOS_GATEWAY_PORT", "9200"))
    print(f"[gateway] Starting TaijiOS LLM Gateway on {host}:{port}")
    uvicorn.run("aios.gateway.app:app", host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()

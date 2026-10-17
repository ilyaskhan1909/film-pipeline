"""Read-only execution evidence via the official authenticated Kaggle SDK."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import requests
from kaggle.api.kaggle_api_extended import KaggleApi


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--notebook", default="iliaskhan/notebook6c8f01ed68")
    parser.add_argument("--directory", type=Path, required=True)
    args = parser.parse_args()
    api = KaggleApi()
    api.authenticate()
    status = api.kernels_status(args.notebook)
    args.directory.mkdir(parents=True, exist_ok=True)
    report = {"notebook": args.notebook,
              "observed_at": datetime.now(timezone.utc).isoformat(),
              "transport": "official Kaggle SDK; local access_token; no browser",
              "status": str(status.status),
              "failure_message": status.failure_message or None}
    (args.directory / "remote_status.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    log = api.kernels_logs(args.notebook)
    (args.directory / "execution.log").write_text(log, encoding="utf-8")
    try:
        events = json.loads(log)
        readable = "".join(e.get("data", "") for e in events) if isinstance(events, list) else log
    except json.JSONDecodeError:
        readable = log
    (args.directory / "execution-readable.log").write_text(readable, encoding="utf-8")
    print(json.dumps(dict(report, log_characters=len(log)), ensure_ascii=False))
    if log:
        # Full log is retained on disk; keep the terminal response compact.
        print(readable[-5000:])


if __name__ == "__main__":
    try:
        main()
    except requests.RequestException as exc:
        print(json.dumps({"error_type": type(exc).__name__,
                          "http_status": getattr(getattr(exc, "response", None), "status_code", None)}))
        raise SystemExit(2)

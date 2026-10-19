import argparse
import json
import urllib.error
import urllib.request
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Upload a GraphSentinel CSV or JSON transaction file.")
    parser.add_argument("file", type=Path)
    parser.add_argument("--api", default="http://localhost:8000/api/v1")
    args = parser.parse_args()
    if not args.file.is_file() or args.file.suffix.lower() not in {".csv", ".json"}:
        parser.error("file must be an existing .csv or .json file")
    boundary = "----GraphSentinelBoundary"
    content = args.file.read_bytes()
    body = (
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{args.file.name}\"\r\n"
        f"Content-Type: application/octet-stream\r\n\r\n".encode()
        + content
        + f"\r\n--{boundary}--\r\n".encode()
    )
    request = urllib.request.Request(
        f"{args.api.rstrip('/')}/datasets/upload", data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}, method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            print(json.dumps(json.load(response), indent=2))
    except urllib.error.HTTPError as exc:
        print(exc.read().decode("utf-8", errors="replace"))
        raise SystemExit(exc.code) from exc


if __name__ == "__main__":
    main()

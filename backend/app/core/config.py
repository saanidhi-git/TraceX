import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = Path(os.getenv("GRAPHSENTINEL_DATA_DIR", PROJECT_ROOT / "data"))
DATABASE_PATH = Path(os.getenv("GRAPHSENTINEL_DATABASE", DATA_DIR / "graphsentinel.sqlite3"))
MAX_UPLOAD_BYTES = int(os.getenv("GRAPHSENTINEL_MAX_UPLOAD_BYTES", 10 * 1024 * 1024))
MAX_TRANSACTIONS = int(os.getenv("GRAPHSENTINEL_MAX_TRANSACTIONS", 50_000))
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "GRAPHSENTINEL_CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8080,http://127.0.0.1:8080",
    ).split(",")
    if origin.strip()
]

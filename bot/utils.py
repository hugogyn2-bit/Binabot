import time
import yaml
from datetime import datetime, timezone


def load_yaml(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def sleep_seconds(sec: int):
    time.sleep(max(1, int(sec)))

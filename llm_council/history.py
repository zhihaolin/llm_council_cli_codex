from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


def append_history(record: Dict[str, Any], path: str) -> None:
    history_path = Path(path).expanduser()
    history_path.parent.mkdir(parents=True, exist_ok=True)
    record = dict(record)
    record.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
    with history_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=True) + "\n")

"""CSV provider for offline/multi-asset simulation datasets."""

import csv
from datetime import datetime
from pathlib import Path
from typing import Dict, List


class CsvProvider:
    def __init__(self, base_dir: str = "data"):
        self.base_dir = Path(base_dir)

    def load_ohlcv(self, relative_path: str) -> List[Dict[str, float]]:
        path = self.base_dir / relative_path
        if not path.exists():
            return []

        rows: List[Dict[str, float]] = []
        with open(path, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    rows.append(
                        {
                            "ts": datetime.fromisoformat(str(row.get("ts") or row.get("date"))),
                            "open": float(row.get("open", 0) or 0),
                            "high": float(row.get("high", 0) or 0),
                            "low": float(row.get("low", 0) or 0),
                            "close": float(row.get("close", 0) or 0),
                            "volume": float(row.get("volume", 0) or 0),
                        }
                    )
                except Exception:
                    continue
        return rows

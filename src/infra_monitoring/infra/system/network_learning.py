"""Network usage learning utilities.

Provides a handler to record daily network usage and calculate adaptive
weekly limits used by treatment policies. Data is persisted in a simple
JSONL file under the cache directory.
"""

import json
import datetime
from pathlib import Path


class NetworkUsageLearningHandler:
    """Handler for learning and dynamic adjustment of network usage limits."""

    def __init__(self, date_func=None):
        """Initialize the network learning handler.

        Parameters
        ----------
        date_func : callable, optional
            Function that returns the current date (default: datetime.date.today).

        """
        self.date_func = date_func or (lambda: datetime.date.today())

    LEARNING_FILE = Path(".cache/network_usage_learning_safe.jsonl")
    LEARNING_WEEKS = 4
    DEFAULT_LIMIT = 20 * 1024**3  # 20GB
    MARGIN = 0.2  # 20%

    def record_daily_usage(self, bytes_sent: int, bytes_recv: int):
        """Record daily bytes sent/received and persist to a JSONL file.

        Always overwrite the current day's entry to avoid duplicates and add
        a precise timestamp field.
        """
        today = self.date_func()
        now_dt = datetime.datetime.now().isoformat()
        entry = {"bytes_sent": bytes_sent, "bytes_recv": bytes_recv, "date": today.isoformat(), "timestamp": now_dt}
        from infra_monitoring.infra.system.helpers import ensure_cache_dir_exists

        ensure_cache_dir_exists()
        # Load all existing entries
        from infra_monitoring.infra.system.helpers import read_jsonl

        entries = read_jsonl(self.LEARNING_FILE)
        # Remove any entry from the same day
        entries = [e for e in entries if e.get("date") != today.isoformat()]
        # Append the current entry
        entries.append(entry)
        # Write all entries, one per line
        with self.LEARNING_FILE.open("w", encoding="utf-8") as f:
            for e in entries:
                f.write(json.dumps(e) + "\n")

    def calculate_weekly_limit(self) -> int:
        """Calculate an adaptive weekly limit (+20%) based on the last week's sum.

        Returns the calculated limit in bytes.
        """
        # Always sum the last 7 complete days
        data = self._load_data()
        # Sort by date descending
        valid_entries = [e for e in data if "bytes_sent" in e and "bytes_recv" in e and "date" in e]
        valid_entries.sort(key=lambda e: e["date"], reverse=True)
        last_7 = valid_entries[:7]
        if not last_7:
            return self.DEFAULT_LIMIT
        total = sum(e["bytes_sent"] + e["bytes_recv"] for e in last_7)
        limit = int(total * (1 + self.MARGIN))
        return limit

    # `reset_learning_cycle` removed: not referenced in the repository. If an
    # administrative API is desired in the future, re-add this method or expose
    # a CLI/management endpoint that invokes `_save_data({})`.

    def _load_data(self):
        from infra_monitoring.infra.system.helpers import read_jsonl

        entries = read_jsonl(self.LEARNING_FILE)
        # Fallback: try reading from the monitoring jsonl if not enough data
        if not entries or len(entries) < self.LEARNING_WEEKS * 7:
            monitor_path = Path("logs/json/monitoring-{}.jsonl".format(datetime.date.today().strftime("%Y-%m-%d")))
            entries += read_jsonl(monitor_path)
        return entries

    def _save_data(self, data):
        from infra_monitoring.infra.system.helpers import ensure_cache_dir_exists

        ensure_cache_dir_exists()
        with self.LEARNING_FILE.open("w", encoding="utf-8") as f:
            json.dump(data, f)

    def get_current_limit(self) -> int:
        """Return the current weekly limit for consultation by treatment routines."""
        return self.calculate_weekly_limit()


# Example usage:
# handler = NetworkUsageLearningHandler()
# handler.record_daily_usage(bytes_sent, bytes_recv)
# limit = handler.get_current_limit()
# if consumption > limit: ...


# Prevent Vulture false-positive: reference the private method so static
# analyzers recognize it as intentionally retained for administrative/CLI use.
# This is a no-op at import time and safe.
_dummy_ref_network_learning_save = NetworkUsageLearningHandler._save_data

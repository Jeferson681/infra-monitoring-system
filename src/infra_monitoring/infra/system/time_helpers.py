"""Utility functions to extract timestamps from log-like objects.

Helpers that attempt to locate and normalize date/time fields in JSON-like
structures (dicts and lists). The primary exported function is
``extract_epoch(obj)`` which tries common locations and parses numeric and
ISO formats, returning a float (seconds since epoch) or ``None`` if no
timestamp is found.
"""

from typing import Any, Optional, Iterator
import datetime
import logging

logger = logging.getLogger(__name__)

# Common keys used when scanning for timestamp-like fields
KEYS_TO_MATCH = {"ts", "timestamp", "time", "date", "last_time", "created_at", "data/hora"}


def _epoch_from_numeric(v) -> Optional[float]:
    try:
        n = float(v)
    except (TypeError, ValueError):
        return None
    if n > 1e12:
        return n / 1000.0
    return n


def _parse_date_string(s: str) -> Optional[float]:
    """Try to parse a date/time string into epoch seconds.

    Supports ISO formats, numeric timestamps expressed as strings, and a
    few common timezone-less formats. Returns ``None`` if parsing fails.
    """
    if not isinstance(s, str):
        return None
    t = s.strip()
    if not t:
        return None
    try:
        n = float(t)
        if n > 1e12:
            return n / 1000.0
        return n
    except (TypeError, ValueError):
        pass

    if t.endswith("Z"):
        t2 = t[:-1] + "+00:00"
    else:
        t2 = t

    try:
        dt = datetime.datetime.fromisoformat(t2)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        return dt.timestamp()
    except ValueError:
        pass

    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            dt = datetime.datetime.strptime(t, fmt)
            dt = dt.replace(tzinfo=datetime.timezone.utc)
            return dt.timestamp()
        except ValueError:
            continue

    return None


def _parse_epoch_from_value(v) -> Optional[float]:
    """Normalize an arbitrary value into an epoch float when possible.

    Accepts numbers (int/float/numeric str) and date strings; returns
    ``None`` when a timestamp cannot be extracted.
    """
    if v is None:
        return None
    n = _epoch_from_numeric(v)
    if n is not None:
        return n
    if isinstance(v, str):
        s = _parse_date_string(v)
        if s is not None:
            return s
    return None


def _scan_keys_in_obj(container, depth: int = 3) -> Optional[float]:
    if depth < 0 or container is None:
        return None
    if not isinstance(container, (dict, list)):
        return _parse_epoch_from_value(container)
    keys_to_match = KEYS_TO_MATCH
    if isinstance(container, dict):
        cand = _scan_direct_keys(container, keys_to_match)
        if cand is not None:
            return cand
        for subtree in _iter_likely_subtrees(container):
            cand = _scan_subtree_for_timestamp(subtree, depth - 1)
            if cand is not None:
                return cand
        cand = _scan_values_shallow(container, depth - 1)
        if cand is not None:
            return cand
        return None
    return _scan_list_for_keys(container, depth - 1)


def _scan_list_for_keys(lst: list, depth: int) -> Optional[float]:
    best = None
    for item in lst:
        cand = _scan_keys_in_obj(item, depth)
        if cand is not None and (best is None or cand > best):
            best = cand
    return best


def _scan_direct_keys(container: dict, keys_to_match: set) -> Optional[float]:
    for k, v in container.items():
        try:
            ks = str(k).lower()
        except Exception:
            ks = None
        if ks and ks in keys_to_match:
            cand = _parse_epoch_from_value(v)
            if cand is not None:
                return cand
    return None


def _iter_likely_subtrees(container: dict) -> Iterator[Any]:
    for k in ("metrics_raw", "meta", "data", "payload", "event", "events"):
        if k in container:
            yield container.get(k)


def _scan_values_shallow(container: dict, depth: int) -> Optional[float]:
    for v in container.values():
        if isinstance(v, (dict, list)):
            cand = _scan_keys_in_obj(v, depth)
            if cand is not None:
                return cand
    return None


def _extract_from_metrics_raw(obj: dict) -> Optional[float]:
    m = obj.get("metrics_raw") or {}
    if isinstance(m, dict):
        v = m.get("timestamp")
        if v is not None:
            return _parse_epoch_from_value(v)
    return None


def _extract_from_top_level(obj: dict) -> Optional[float]:
    for key in ("ts", "timestamp"):
        if key in obj:
            v = obj.get(key)
            n = _parse_epoch_from_value(v)
            if n is not None:
                return n
    return None


def _extract_from_common_subtrees(obj: dict) -> Optional[float]:
    for subtree in (obj.get("metrics_raw"), obj.get("meta"), obj.get("events")):
        if subtree is not None:
            n = _scan_keys_in_obj(subtree, depth=3)
            if n is not None:
                return n
    return None


def _check_localized_date_keys(obj: dict) -> Optional[float]:
    for key in ("Data/hora", "Data/Hora", "data/hora", "date", "Date"):
        if key in obj:
            v = obj.get(key)
            n = _parse_epoch_from_value(v)
            if n is not None:
                return n
    return None


def _dfs_scan_for_timestamp(node: Any) -> Optional[float]:
    stack: list[Any] = [node]
    while stack:
        nd = stack.pop()
        if not isinstance(nd, (dict, list)):
            continue
        if isinstance(nd, dict):
            n = _dfs_scan_dict(nd)
            if n is not None:
                return n
            continue
        n = _dfs_scan_list(nd)
        if n is not None:
            return n
    return None


def _dfs_scan_dict(d: dict) -> Optional[float]:
    keys_to_match = KEYS_TO_MATCH
    for k, v in d.items():
        try:
            ks = str(k).lower()
        except Exception:
            ks = None
        if ks and ks in keys_to_match:
            n = _parse_epoch_from_value(v)
            if n is not None:
                return n
        if isinstance(v, (dict, list)):
            return None
    return None


def _dfs_scan_list(lst: list) -> Optional[float]:
    for item in lst:
        if isinstance(item, (dict, list)):
            n = _dfs_scan_for_timestamp(item)
            if n is not None:
                return n
    return None


def _scan_subtree_for_timestamp(subtree: Any, depth: int) -> Optional[float]:
    if isinstance(subtree, list):
        best = None
        for item in subtree:
            cand = _scan_keys_in_obj(item, depth - 1)
            if cand is not None and (best is None or cand > best):
                best = cand
        return best
    return _scan_keys_in_obj(subtree, depth)


def extract_epoch(obj: dict) -> Optional[float]:
    """Extract an epoch timestamp (seconds since epoch) from a log-like object.

    The function tries several locations in order of priority:
      1. ``metrics_raw.timestamp``
      2. top-level fields ``ts`` / ``timestamp``
      3. localized keys such as ``Data/hora``
      4. common subtrees like ``meta`` / ``events``
      5. a DFS scan that searches for timestamp-like keys/values

    Returns ``None`` when nothing parseable is found.
    """
    n = _extract_from_metrics_raw(obj)
    if n is not None:
        return n
    n = _extract_from_top_level(obj)
    if n is not None:
        return n
    n = _check_localized_date_keys(obj)
    if n is not None:
        return n
    n = _extract_from_common_subtrees(obj)
    if n is not None:
        return n
    return _dfs_scan_for_timestamp(obj)
